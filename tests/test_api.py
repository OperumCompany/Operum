import os
import shutil
import tempfile

TEST_DATA_DIR = tempfile.mkdtemp(prefix="operum-test-data-")
os.environ["OPERUM_DATA_DIR"] = TEST_DATA_DIR

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


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


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
    resp = await client.post("/api/portfolios", json={"name": "Teste", "base_currency": "BRL"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Teste"
    pid = data["id"]

    resp2 = await client.get(f"/api/portfolios/{pid}")
    assert resp2.status_code == 200
    assert resp2.json()["id"] == pid


@pytest.mark.asyncio
async def test_add_and_remove_position(client: AsyncClient):
    resp = await client.post("/api/portfolios", json={"name": "Teste", "base_currency": "BRL"})
    pid = resp.json()["id"]

    resp = await client.post(
        f"/api/portfolios/{pid}/positions",
        json={"ticker": "PETR4", "asset_class": "BR_STOCK", "quantity": 100, "avg_price": 31.2},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["positions"]) == 1

    resp = await client.delete(f"/api/portfolios/{pid}/positions/PETR4")
    assert resp.status_code == 200
    assert len(resp.json()["positions"]) == 0


@pytest.mark.asyncio
async def test_bulk_delete_portfolios(client: AsyncClient):
    created_ids = []
    for name in ("Lote A", "Lote B"):
        resp = await client.post("/api/portfolios", json={"name": name, "base_currency": "BRL"})
        assert resp.status_code == 201
        created_ids.append(resp.json()["id"])

    resp = await client.post("/api/portfolios/bulk-delete", json={"portfolio_ids": created_ids})
    assert resp.status_code == 200
    data = resp.json()
    assert data["deleted_count"] == 2
    assert set(data["deleted_ids"]) == set(created_ids)


@pytest.mark.asyncio
async def test_portfolio_analysis(client: AsyncClient):
    resp = await client.post("/api/portfolios", json={"name": "Analise", "base_currency": "BRL"})
    pid = resp.json()["id"]
    await client.post(
        f"/api/portfolios/{pid}/positions",
        json={"ticker": "PETR4", "asset_class": "BR_STOCK", "quantity": 100},
    )
    await client.post(
        f"/api/portfolios/{pid}/positions",
        json={"ticker": "VALE3", "asset_class": "BR_STOCK", "quantity": 50},
    )
    resp = await client.get(f"/api/portfolios/{pid}/analysis")
    assert resp.status_code == 200
    data = resp.json()
    assert data["num_assets"] == 2


@pytest.mark.asyncio
async def test_news_list(client: AsyncClient):
    resp = await client.get("/api/news?page_size=5")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data
    assert "total_pages" in data


@pytest.mark.asyncio
async def test_news_query_and_pagination_metadata(client: AsyncClient):
    resp = await client.get("/api/news?page=1&page_size=30&q=mercado")
    assert resp.status_code == 200
    data = resp.json()
    assert data["page"] == 1
    assert data["page_size"] == 30
    assert "total_pages" in data


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


@pytest.mark.asyncio
async def test_portfolio_news_endpoint(client: AsyncClient):
    resp = await client.post("/api/portfolios", json={"name": "Noticias", "base_currency": "BRL"})
    pid = resp.json()["id"]
    await client.post(
        f"/api/portfolios/{pid}/positions",
        json={"ticker": "PETR4", "asset_class": "BR_STOCK", "quantity": 10},
    )
    resp = await client.get(f"/api/portfolios/{pid}/news")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


@pytest.mark.asyncio
async def test_portfolio_opinion_structure(client: AsyncClient):
    resp = await client.post("/api/portfolios", json={"name": "Opiniao", "base_currency": "BRL"})
    pid = resp.json()["id"]
    await client.post(
        f"/api/portfolios/{pid}/positions",
        json={"ticker": "PETR4", "asset_class": "BR_STOCK", "quantity": 20, "avg_price": 32},
    )
    await client.post(
        f"/api/portfolios/{pid}/positions",
        json={"ticker": "HGLG11", "asset_class": "FII", "quantity": 10, "avg_price": 165},
    )
    resp = await client.get(f"/api/models/opinion/{pid}")
    assert resp.status_code == 200
    data = resp.json()
    assert "headline" in data
    assert "composition_summary" in data
    assert "block_reviews" in data
    assert "sources" in data
    assert "source_groups" in data


@pytest.mark.asyncio
async def test_position_opinion_endpoint(client: AsyncClient):
    resp = await client.post("/api/portfolios", json={"name": "Ativo", "base_currency": "BRL"})
    pid = resp.json()["id"]
    await client.post(
        f"/api/portfolios/{pid}/positions",
        json={"ticker": "BTC", "asset_class": "CRYPTO", "quantity": 0.05},
    )
    resp = await client.get(f"/api/models/opinion/{pid}/positions/BTC")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "BTC"
    assert "analysis_sections" in data
    assert "current" in data["analysis_sections"]
    assert "sources" in data
    assert "source_groups" in data
    assert "used_news_count" in data
    assert "historical_window" in data


@pytest.mark.asyncio
async def test_cluster_news(client: AsyncClient):
    resp = await client.post("/api/models/cluster/news")
    assert resp.status_code in (200, 404)
    data = resp.json()
    if resp.status_code == 200:
        assert data["status"] == "ok"
    else:
        assert "Nenhuma" in data["detail"]
