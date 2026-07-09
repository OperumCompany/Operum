import os
import shutil
import tempfile

TEST_DATA_DIR = tempfile.mkdtemp(prefix="operum-test-data-")
os.environ["OPERUM_DATA_DIR"] = TEST_DATA_DIR
os.environ["OPERUM_STORAGE_MODE"] = "local"
os.environ["AI_ENABLED"] = "false"
os.environ["AI_ENHANCE_ASSET_ANALYSIS"] = "false"
os.environ["AI_ENHANCE_PORTFOLIO_ANALYSIS"] = "false"
os.environ["AI_ENABLE_CHATBOT"] = "false"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_data_dir():
    yield
    shutil.rmtree(TEST_DATA_DIR, ignore_errors=True)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def auth_headers(client: AsyncClient, suffix: str = "base") -> dict[str, str]:
    email = f"tester-{suffix}@operum.app"
    password = "Operum123"
    await client.post("/api/auth/register", json={"name": "Tester", "email": email, "password": password})
    login = await client.post("/api/auth/login", json={"email": email, "password": password})
    token = login.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_auth_register_login_and_me(client: AsyncClient):
    register = await client.post("/api/auth/register", json={
        "name": "Camila Real",
        "email": "camila-real@operum.app",
        "password": "Operum123",
    })
    assert register.status_code == 200
    token = register.json()["token"]

    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "camila-real@operum.app"


@pytest.mark.asyncio
async def test_assets_universe(client: AsyncClient):
    resp = await client.get("/api/assets/universe")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


@pytest.mark.asyncio
async def test_assets_search(client: AsyncClient):
    resp = await client.get("/api/assets/search?q=PETR")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert any("PETR" in a["ticker"] for a in data)


@pytest.mark.asyncio
async def test_create_and_get_portfolio(client: AsyncClient):
    headers = await auth_headers(client, "create")
    resp = await client.post("/api/portfolios", headers=headers, json={"name": "Teste", "base_currency": "BRL"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Teste"
    pid = data["id"]

    resp2 = await client.get(f"/api/portfolios/{pid}", headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["id"] == pid


@pytest.mark.asyncio
async def test_add_and_remove_position(client: AsyncClient):
    headers = await auth_headers(client, "position")
    resp = await client.post("/api/portfolios", headers=headers, json={"name": "Teste", "base_currency": "BRL"})
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/portfolios/{pid}/positions",
        headers=headers,
        json={"ticker": "PETR4", "asset_class": "BR_STOCK", "quantity": 100, "avg_price": 31.2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["positions"]) == 1

    resp = await client.delete(f"/api/portfolios/{pid}/positions/PETR4", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["positions"]) == 0


@pytest.mark.asyncio
async def test_bulk_delete_portfolios(client: AsyncClient):
    headers = await auth_headers(client, "bulk")
    created_ids = []
    for name in ("Lote A", "Lote B"):
        resp = await client.post("/api/portfolios", headers=headers, json={"name": name, "base_currency": "BRL"})
        assert resp.status_code == 201
        created_ids.append(resp.json()["id"])

    resp = await client.post("/api/portfolios/bulk-delete", headers=headers, json={"portfolio_ids": created_ids})
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted_count"] == 2
    assert set(data["deleted_ids"]) == set(created_ids)


@pytest.mark.asyncio
async def test_portfolio_analysis(client: AsyncClient):
    headers = await auth_headers(client, "analysis")
    resp = await client.post("/api/portfolios", headers=headers, json={"name": "Analise", "base_currency": "BRL"})
    pid = resp.json()["id"]
    await client.post(
        f"/api/portfolios/{pid}/positions",
        headers=headers,
        json={"ticker": "PETR4", "asset_class": "BR_STOCK", "quantity": 100},
    )
    await client.post(
        f"/api/portfolios/{pid}/positions",
        headers=headers,
        json={"ticker": "VALE3", "asset_class": "BR_STOCK", "quantity": 50},
    )
    resp = await client.get(f"/api/portfolios/{pid}/analysis", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["num_assets"] == 2
    assert "benchmark" in data
    assert "volatility_window_days" in data


@pytest.mark.asyncio
async def test_portfolio_prices_include_unrealized_pnl(client: AsyncClient):
    headers = await auth_headers(client, "prices")
    resp = await client.post("/api/portfolios", headers=headers, json={"name": "Precos", "base_currency": "BRL"})
    pid = resp.json()["id"]
    await client.post(
        f"/api/portfolios/{pid}/positions",
        headers=headers,
        json={"ticker": "PETR4", "asset_class": "BR_STOCK", "quantity": 10, "avg_price": 30},
    )
    resp = await client.get(f"/api/portfolios/{pid}/prices", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_unrealized_pnl" in data
    assert "unrealized_pnl" in data["positions"][0]
    assert "sparkline_20d" in data["positions"][0]


@pytest.mark.asyncio
async def test_news_list(client: AsyncClient):
    resp = await client.get("/api/news?page_size=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "total_pages" in data
    if data["items"]:
        first = data["items"][0]
        assert "source_id" in first
        assert "source_type" in first
        assert "is_official" in first


@pytest.mark.asyncio
async def test_news_query_and_pagination_metadata(client: AsyncClient):
    resp = await client.get("/api/news?page=1&page_size=30&q=mercado")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 30
    assert "total_pages" in data


@pytest.mark.asyncio
async def test_news_backfill_accepts_source_scope(client: AsyncClient):
    resp = await client.post("/api/news/backfill?start_date=2026-05-01&source_id=b3_comunicados")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "sources" in data


@pytest.mark.asyncio
async def test_market_price_unknown(client: AsyncClient):
    resp = await client.get("/api/market/price/UNKNOWN123")
    assert resp.status_code in (200, 404)
    if resp.status_code == 200:
        assert resp.json().get("price") is None


@pytest.mark.asyncio
async def test_models_status(client: AsyncClient):
    resp = await client.get("/api/models/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "forecast_models" in data
    assert "ai_local" in data
    assert data["ai_local"]["enabled"] is False


@pytest.mark.asyncio
async def test_portfolio_news_endpoint(client: AsyncClient):
    headers = await auth_headers(client, "news")
    resp = await client.post("/api/portfolios", headers=headers, json={"name": "Noticias", "base_currency": "BRL"})
    pid = resp.json()["id"]
    await client.post(
        f"/api/portfolios/{pid}/positions",
        headers=headers,
        json={"ticker": "PETR4", "asset_class": "BR_STOCK", "quantity": 10},
    )
    resp = await client.get(f"/api/portfolios/{pid}/news", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_portfolio_opinion_structure(client: AsyncClient):
    headers = await auth_headers(client, "opinion")
    resp = await client.post("/api/portfolios", headers=headers, json={"name": "Opiniao", "base_currency": "BRL"})
    pid = resp.json()["id"]
    await client.post(
        f"/api/portfolios/{pid}/positions",
        headers=headers,
        json={"ticker": "PETR4", "asset_class": "BR_STOCK", "quantity": 20, "avg_price": 32},
    )
    await client.post(
        f"/api/portfolios/{pid}/positions",
        headers=headers,
        json={"ticker": "HGLG11", "asset_class": "FII", "quantity": 10, "avg_price": 165},
    )
    resp = await client.get(f"/api/models/opinion/{pid}?analysis_horizon=2m", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "headline" in data
    assert "composition_summary" in data
    assert "block_reviews" in data
    assert "sources" in data
    assert "source_groups" in data
    assert "benchmark" in data
    assert data["selected_analysis_horizon"] == "2m"


@pytest.mark.asyncio
async def test_position_opinion_endpoint(client: AsyncClient):
    headers = await auth_headers(client, "position-opinion")
    resp = await client.post("/api/portfolios", headers=headers, json={"name": "Ativo", "base_currency": "BRL"})
    pid = resp.json()["id"]
    await client.post(
        f"/api/portfolios/{pid}/positions",
        headers=headers,
        json={"ticker": "BTC", "asset_class": "CRYPTO", "quantity": 0.05},
    )
    resp = await client.get(
        f"/api/models/opinion/{pid}/positions/BTC?history_horizon=1m&outlook_horizon=1w",
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "BTC"
    assert "analysis_sections" in data
    assert "current" in data["analysis_sections"]
    assert "sources" in data
    assert "source_groups" in data
    assert "used_news_count" in data
    assert "historical_window" in data
    assert data["selected_history_horizon"] == "1m"
    assert data["selected_outlook_horizon"] == "1w"
    assert "historical_series" in data
    assert "forecast_series" in data
    assert "beta_selected" in data["recent_performance"]
    assert "recent_by_horizon" in data["analysis_sections"]
    assert "outlook_by_horizon" in data["analysis_sections"]
    assert "asset_function" in data
    assert "forecast_news_adjustment_pct" in data["recent_performance"]
    if data["sources"]:
        assert "analysis_category" in data["sources"][0]


@pytest.mark.asyncio
async def test_portfolio_analysis_empty_portfolio(client: AsyncClient):
    headers = await auth_headers(client, "empty")
    resp = await client.post("/api/portfolios", headers=headers, json={"name": "Vazia", "base_currency": "BRL"})
    pid = resp.json()["id"]
    analysis = await client.get(f"/api/portfolios/{pid}/analysis", headers=headers)
    assert analysis.status_code == 200
    assert analysis.json()["num_assets"] == 0


@pytest.mark.asyncio
async def test_protected_route_requires_auth(client: AsyncClient):
    resp = await client.get("/api/portfolios")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_status_endpoint(client: AsyncClient):
    resp = await client.get("/api/status")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_cluster_news(client: AsyncClient):
    resp = await client.post("/api/models/cluster/news")
    assert resp.status_code in (200, 404)
    data = resp.json()
    if resp.status_code == 200:
        assert data["status"] == "ok"
    else:
        assert "Nenhuma" in data["detail"]


@pytest.mark.asyncio
async def test_chat_endpoint_with_fallback(client: AsyncClient):
    headers = await auth_headers(client, "chat")
    resp = await client.post(
        "/api/chat",
        headers=headers,
        json={
            "messages": [{"role": "user", "content": "O que e liquidez?"}],
            "use_all_portfolios": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "fallback"
    assert isinstance(data["message"], str)
    assert data["message"]
