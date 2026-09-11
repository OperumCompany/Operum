import asyncio
import os
import shutil
import tempfile
from datetime import date

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

SESSION_COOKIE = "operum_session"


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
    token = login.cookies.get(SESSION_COOKIE)
    assert token
    return {"Cookie": f"{SESSION_COOKIE}={token}"}


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
    token = register.cookies.get(SESSION_COOKIE)
    assert token

    me = await client.get("/api/auth/me", headers={"Cookie": f"{SESSION_COOKIE}={token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "camila-real@operum.app"
    assert "token" not in register.json()

    logout = await client.post("/api/auth/logout", headers={"Cookie": f"{SESSION_COOKIE}={token}"})
    assert logout.status_code == 200
    assert SESSION_COOKIE in logout.headers.get("set-cookie", "")


@pytest.mark.asyncio
async def test_account_deletion_requires_reauthentication_and_removes_session(client: AsyncClient):
    register = await client.post("/api/auth/register", json={
        "name": "Conta para excluir",
        "email": "delete-account@operum.app",
        "password": "Operum123",
    })
    token = register.cookies.get(SESSION_COOKIE)
    assert token
    headers = {"Cookie": f"{SESSION_COOKIE}={token}"}

    invalid_confirmation = await client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={"current_password": "Operum123", "confirmation": "excluir"},
    )
    assert invalid_confirmation.status_code == 400
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 200

    invalid_password = await client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={"current_password": "senha-incorreta", "confirmation": "Excluir"},
    )
    assert invalid_password.status_code == 400

    deleted = await client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={"current_password": "Operum123", "confirmation": "Excluir"},
    )
    assert deleted.status_code == 200
    assert deleted.json() == {"status": "ok"}
    assert (await client.get("/api/auth/me", headers=headers)).status_code == 401

    login = await client.post("/api/auth/login", json={"email": "delete-account@operum.app", "password": "Operum123"})
    assert login.status_code == 401


@pytest.mark.asyncio
async def test_account_deletion_requires_authentication(client: AsyncClient):
    response = await client.request("DELETE", "/api/auth/account", json={"current_password": "Operum123", "confirmation": "Excluir"})
    assert response.status_code == 401


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
async def test_portfolio_update_cannot_change_server_managed_example_fields(client: AsyncClient):
    headers = await auth_headers(client, "immutable-kind")
    created = await client.post("/api/portfolios", headers=headers, json={"name": "Normal", "base_currency": "BRL"})
    portfolio_id = created.json()["id"]

    updated = await client.put(f"/api/portfolios/{portfolio_id}", headers=headers, json={
        "name": "Nome permitido",
        "kind": "example",
        "example_version": 99,
        "owner_id": "outro-usuario",
        "positions": [],
    })
    assert updated.status_code == 422


@pytest.mark.asyncio
async def test_portfolio_partial_settings_update_preserves_unsent_fields(client: AsyncClient):
    headers = await auth_headers(client, "partial-settings")
    created = await client.post("/api/portfolios", headers=headers, json={
        "name": "Configuração",
        "settings": {"risk_profile": "moderado", "forecast_horizon_days": 30},
    })
    portfolio_id = created.json()["id"]

    updated = await client.put(f"/api/portfolios/{portfolio_id}", headers=headers, json={
        "settings": {"risk_profile": "agressivo"},
    })
    assert updated.status_code == 200
    assert updated.json()["settings"] == {"risk_profile": "agressivo", "forecast_horizon_days": 30}


@pytest.mark.asyncio
async def test_registration_creates_one_persistent_example_portfolio(client: AsyncClient):
    register = await client.post("/api/auth/register", json={
        "name": "Nova pessoa",
        "email": "example-onboarding@operum.app",
        "password": "Operum123",
    })
    assert register.status_code == 200
    token = register.cookies.get(SESSION_COOKIE)
    assert token
    headers = {"Cookie": f"{SESSION_COOKIE}={token}"}

    listed = await client.get("/api/portfolios", headers=headers)
    assert listed.status_code == 200
    examples = [item for item in listed.json() if item["kind"] == "example"]
    assert len(examples) == 1
    assert examples[0]["name"] == "Carteira Exemplo"
    assert examples[0]["example_version"] == 1
    assert len(examples[0]["positions"]) == 36
    assert sum(item["asset_class"] == "BR_STOCK" for item in examples[0]["positions"]) == 12
    assert sum(item["asset_class"] == "FII" for item in examples[0]["positions"]) == 8
    assert sum(item["asset_class"] == "US_STOCK" for item in examples[0]["positions"]) == 13
    assert sum(item["asset_class"] == "CRYPTO" for item in examples[0]["positions"]) == 3


@pytest.mark.asyncio
async def test_example_endpoint_is_idempotent_and_recreates_a_clean_portfolio(client: AsyncClient):
    headers = await auth_headers(client, "example-idempotent")

    first = await client.post("/api/portfolios/example", headers=headers)
    second = await client.post("/api/portfolios/example", headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["created"] is False
    assert second.json()["portfolio"]["id"] == first.json()["portfolio"]["id"]

    example_id = first.json()["portfolio"]["id"]
    removed = await client.delete(f"/api/portfolios/{example_id}", headers=headers)
    assert removed.status_code == 200

    recreated = await client.post("/api/portfolios/example", headers=headers)
    assert recreated.status_code == 200
    assert recreated.json()["created"] is True
    assert recreated.json()["portfolio"]["id"] != example_id
    assert len(recreated.json()["portfolio"]["positions"]) == 36


@pytest.mark.asyncio
async def test_example_creation_is_safe_under_concurrent_requests(client: AsyncClient):
    headers = await auth_headers(client, "example-concurrent")
    initial = (await client.post("/api/portfolios/example", headers=headers)).json()["portfolio"]
    await client.delete(f"/api/portfolios/{initial['id']}", headers=headers)

    responses = await asyncio.gather(*[
        client.post("/api/portfolios/example", headers=headers)
        for _ in range(6)
    ])
    assert all(response.status_code == 200 for response in responses)
    ids = {response.json()["portfolio"]["id"] for response in responses}
    assert len(ids) == 1

    listed = (await client.get("/api/portfolios", headers=headers)).json()
    assert sum(item["kind"] == "example" for item in listed) == 1


@pytest.mark.asyncio
async def test_example_portfolios_are_isolated_per_user(client: AsyncClient):
    owner_headers = await auth_headers(client, "example-owner")
    other_headers = await auth_headers(client, "example-other")
    owner_example = (await client.post("/api/portfolios/example", headers=owner_headers)).json()["portfolio"]
    other_example = (await client.post("/api/portfolios/example", headers=other_headers)).json()["portfolio"]

    changed = await client.delete(
        f"/api/portfolios/{owner_example['id']}/positions/PETR4",
        headers=owner_headers,
    )
    assert changed.status_code == 200
    assert len(changed.json()["positions"]) == 35

    other = await client.get(f"/api/portfolios/{other_example['id']}", headers=other_headers)
    assert other.status_code == 200
    assert len(other.json()["positions"]) == 36
    assert any(item["ticker"] == "PETR4" for item in other.json()["positions"])


@pytest.mark.asyncio
async def test_example_data_endpoints_never_call_external_market_news_or_ai(client: AsyncClient, monkeypatch):
    headers = await auth_headers(client, "example-offline")
    example = (await client.post("/api/portfolios/example", headers=headers)).json()["portfolio"]
    portfolio_id = example["id"]

    from app.api import models as models_api
    from app.api import portfolios as portfolios_api

    def forbidden(*args, **kwargs):
        raise AssertionError("external service must not be called for an example portfolio")

    monkeypatch.setattr(portfolios_api.market_service, "get_current_price", forbidden)
    monkeypatch.setattr(portfolios_api.market_service, "get_history", forbidden)
    monkeypatch.setattr(portfolios_api.asset_analysis_service, "get_related_news", forbidden)
    monkeypatch.setattr(models_api.market_service, "get_history", forbidden)
    monkeypatch.setattr(models_api.opinion_service, "generate_opinion", forbidden)
    monkeypatch.setattr(models_api.asset_analysis_service, "generate_asset_analysis", forbidden)

    prices = await client.get(f"/api/portfolios/{portfolio_id}/prices", headers=headers)
    history = await client.get(f"/api/portfolios/{portfolio_id}/history?period=1y", headers=headers)
    analysis = await client.get(f"/api/portfolios/{portfolio_id}/analysis", headers=headers)
    news = await client.get(f"/api/portfolios/{portfolio_id}/news", headers=headers)
    opinion = await client.get(f"/api/models/opinion/{portfolio_id}?analysis_horizon=3m", headers=headers)
    position_opinion = await client.get(
        f"/api/models/opinion/{portfolio_id}/positions/PETR4?history_horizon=1m&outlook_horizon=1m",
        headers=headers,
    )

    for response in (prices, history, analysis, news, opinion, position_opinion):
        assert response.status_code == 200, response.text
    assert prices.json()["is_demo"] is True
    assert len(prices.json()["positions"]) == 36
    assert len(history.json()["points"]) == 13
    assert history.json()["warnings"]
    assert analysis.json()["is_demo"] is True
    assert news.json() == {"items": [], "total": 0, "is_demo": True}
    assert opinion.json()["is_demo"] is True
    assert opinion.json()["sources"] == []
    assert position_opinion.json()["is_demo"] is True
    assert position_opinion.json()["sources"] == []


@pytest.mark.asyncio
async def test_chat_linked_only_to_example_is_deterministic_and_offline(client: AsyncClient, monkeypatch):
    headers = await auth_headers(client, "example-chat-offline")
    example = (await client.post("/api/portfolios/example", headers=headers)).json()["portfolio"]
    from app.api import chat as chat_api

    def forbidden(*args, **kwargs):
        raise AssertionError("external service must not be called from example chat context")

    monkeypatch.setattr(chat_api.chat_service.llm, "chat_answer", forbidden)
    monkeypatch.setattr(chat_api.chat_service, "_news_context", forbidden)
    response = await client.post("/api/chat", headers=headers, json={
        "messages": [{"role": "user", "content": "Analise esta carteira"}],
        "portfolio_id": example["id"],
        "use_all_portfolios": False,
    })
    assert response.status_code == 200
    assert response.json()["mode"] == "fallback"
    assert response.json()["used_portfolio_context"] is True
    assert response.json()["sources"] == []
    assert "demonstr" in response.json()["message"].lower()


@pytest.mark.asyncio
async def test_chat_all_portfolios_ignores_example_and_keeps_standard_context(client: AsyncClient):
    headers = await auth_headers(client, "chat-all-with-example")
    created = await client.post("/api/portfolios", headers=headers, json={"name": "Carteira real"})
    await client.post(
        f"/api/portfolios/{created.json()['id']}/positions",
        headers=headers,
        json={"ticker": "PETR4", "asset_class": "BR_STOCK", "quantity": 10, "avg_price": 30},
    )
    response = await client.post("/api/chat", headers=headers, json={
        "messages": [{"role": "user", "content": "Como estão minhas carteiras?"}],
        "use_all_portfolios": True,
    })
    assert response.status_code == 200
    assert response.json()["used_portfolio_context"] is True


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
async def test_portfolio_prices_can_skip_sparklines(client: AsyncClient, monkeypatch):
    headers = await auth_headers(client, "prices-without-sparklines")
    resp = await client.post("/api/portfolios", headers=headers, json={"name": "Precos rapidos", "base_currency": "BRL"})
    pid = resp.json()["id"]
    await client.post(
        f"/api/portfolios/{pid}/positions",
        headers=headers,
        json={"ticker": "PETR4", "asset_class": "BR_STOCK", "quantity": 10, "avg_price": 30},
    )
    from app.api import portfolios as portfolios_api

    monkeypatch.setattr(portfolios_api.market_service, "get_current_price", lambda ticker: {
        "price": 35.0,
        "currency": "BRL",
        "name": ticker,
    })

    def forbidden_history(*args, **kwargs):
        raise AssertionError("history must not be fetched when sparklines are disabled")

    monkeypatch.setattr(portfolios_api.market_service, "get_history", forbidden_history)
    resp = await client.get(f"/api/portfolios/{pid}/prices?include_sparkline=false", headers=headers)

    assert resp.status_code == 200
    assert resp.json()["positions"][0]["sparkline_20d"] == []


@pytest.mark.asyncio
async def test_example_portfolio_prices_can_skip_sparklines(client: AsyncClient):
    headers = await auth_headers(client, "example-prices-without-sparklines")
    example = (await client.post("/api/portfolios/example", headers=headers)).json()["portfolio"]

    resp = await client.get(
        f"/api/portfolios/{example['id']}/prices?include_sparkline=false",
        headers=headers,
    )

    assert resp.status_code == 200
    assert len(resp.json()["positions"]) == 36
    assert all(position["sparkline_20d"] == [] for position in resp.json()["positions"])


@pytest.mark.asyncio
async def test_portfolio_history_contract_and_owner_isolation(client: AsyncClient):
    headers = await auth_headers(client, "history-owner")
    other_headers = await auth_headers(client, "history-other")
    created = await client.post("/api/portfolios", headers=headers, json={"name": "Histórico", "base_currency": "BRL"})
    portfolio_id = created.json()["id"]
    await client.post(
        f"/api/portfolios/{portfolio_id}/positions",
        headers=headers,
        json={"ticker": "PETR4", "asset_class": "BR_STOCK", "quantity": 10, "avg_price": 30, "occurred_at": "2026-08-01"},
    )

    from app.api import portfolios as portfolios_api
    original_get_history = portfolios_api.service.transactions.market.get_history
    portfolios_api.service.transactions.market.get_history = lambda ticker, period="6mo", interval="1d": {
        "prices": [
            {"date": "2026-08-01", "close": 30},
            {"date": date.today().isoformat(), "close": 35},
        ]
    }
    try:
        response = await client.get(f"/api/portfolios/{portfolio_id}/history?period=1m&ticker=PETR4", headers=headers)
        forbidden = await client.get(f"/api/portfolios/{portfolio_id}/history?period=1m", headers=other_headers)
    finally:
        portfolios_api.service.transactions.market.get_history = original_get_history
        await client.delete(f"/api/portfolios/{portfolio_id}", headers=headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["period"] == "1m"
    assert payload["ticker"] == "PETR4"
    assert payload["available_tickers"] == ["PETR4"]
    assert {"market_value", "invested_value", "quantity", "contribution_value"}.issubset(payload["points"][-1])
    assert forbidden.status_code == 404


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
    assert data["search_mode_used"] in {"hybrid", "keyword"}
    assert "semantic_available" in data


@pytest.mark.asyncio
async def test_news_backfill_accepts_source_scope(client: AsyncClient):
    resp = await client.post("/api/news/backfill?start_date=2026-05-01&source_id=b3_comunicados")
    assert resp.status_code == 503
    assert "Token administrativo" in resp.json()["detail"]


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
    assert "composition_diagnosis" in data
    assert "overall_status" in data["composition_diagnosis"]
    assert "metrics" in data["composition_diagnosis"]
    assert "checks" in data["composition_diagnosis"]
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
    assert "box_history_by_horizon" in data["analysis_sections"]
    assert "box_current" in data["analysis_sections"]
    assert "box_outlook_by_horizon" in data["analysis_sections"]
    assert "visual_summary" in data["analysis_sections"]
    assert "summary" in data["analysis_sections"]
    assert "what_happened" in data["analysis_sections"]
    assert "company_situation" in data["analysis_sections"]
    assert "asset_price_situation" in data["analysis_sections"]
    assert "current_situation" in data["analysis_sections"]
    assert "portfolio_impact" in data["analysis_sections"]


@pytest.mark.asyncio
async def test_position_opinion_prefers_detailed_analysis_for_br_stock(client: AsyncClient, monkeypatch):
    from app.api import models as models_api

    headers = await auth_headers(client, "position-opinion-br-stock")
    resp = await client.post("/api/portfolios", headers=headers, json={"name": "Acoes", "base_currency": "BRL"})
    pid = resp.json()["id"]
    await client.post(
        f"/api/portfolios/{pid}/positions",
        headers=headers,
        json={"ticker": "PETR4", "asset_class": "BR_STOCK", "quantity": 10, "avg_price": 32},
    )

    def detailed_analysis(portfolio, ticker, history_horizon, outlook_horizon):
        return {
            "portfolio_id": portfolio.id,
            "ticker": ticker,
            "status": "ok",
            "analysis_sections": {
                "box_current": "Analise detalhada rica para PETR4.",
                "current": "Analise detalhada rica para PETR4.",
                "summary": "Analise detalhada rica para PETR4.",
                "scenarios": {
                    "favorable": "Cenario favoravel.",
                    "base": "Cenario base.",
                    "adverse": "Cenario adverso.",
                },
                "what_to_watch": ["Preco do petroleo"],
                "conclusion": "A leitura nao indica comprar ou vender.",
                "data_quality_warnings": [],
                "box_history_by_horizon": {
                    "1w": "Historico semanal.",
                    "1m": "Historico mensal.",
                    "2m": "Historico bimestral.",
                    "3m": "Historico trimestral.",
                },
                "box_outlook_by_horizon": {
                    "1w": "Perspectiva semanal.",
                    "1m": "Perspectiva mensal.",
                    "2m": "Perspectiva bimestral.",
                    "3m": "Perspectiva trimestral.",
                },
                "company_situation": "Dados fundamentais estruturados ainda limitados.",
            },
            "sources": [],
            "source_groups": [],
            "used_news_count": 0,
            "selected_history_horizon": history_horizon,
            "selected_outlook_horizon": outlook_horizon,
            "asset_function": "acao",
            "recent_performance": {"forecast_news_adjustment_pct": 0},
        }

    def predictive_fallback(*args, **kwargs):
        raise AssertionError("BR_STOCK should prefer the detailed analysis service")

    monkeypatch.setattr(models_api.asset_analysis_service, "generate_asset_analysis", detailed_analysis)
    monkeypatch.setattr(models_api.predictive_analysis_service, "get_or_bootstrap", predictive_fallback)

    resp = await client.get(
        f"/api/models/opinion/{pid}/positions/PETR4?history_horizon=1m&outlook_horizon=1w",
        headers=headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["ticker"] == "PETR4"
    assert data["analysis_sections"]["box_current"] == "Analise detalhada rica para PETR4."
    assert data["selected_history_horizon"] == "1m"
    assert data["selected_outlook_horizon"] == "1w"
    assert "scenarios" in data["analysis_sections"]
    assert "what_to_watch" in data["analysis_sections"]
    assert "conclusion" in data["analysis_sections"]
    assert "data_quality_warnings" in data["analysis_sections"]
    assert isinstance(data["analysis_sections"]["scenarios"], dict)
    assert {"favorable", "base", "adverse"}.issubset(data["analysis_sections"]["scenarios"])
    assert isinstance(data["analysis_sections"]["what_to_watch"], list)
    assert isinstance(data["analysis_sections"]["data_quality_warnings"], list)
    assert set(data["analysis_sections"]["box_history_by_horizon"]) == {"1w", "1m", "2m", "3m"}
    assert set(data["analysis_sections"]["box_outlook_by_horizon"]) == {"1w", "1m", "2m", "3m"}
    box_text = " ".join([
        data["analysis_sections"]["box_history_by_horizon"]["1m"],
        data["analysis_sections"]["box_current"],
        data["analysis_sections"]["box_outlook_by_horizon"]["1w"],
    ]).lower()
    for blocked in ["drawdown", "momentum", "impacto medio", "impacto médio", "peso informacional", "ajuste contextual", "beta estimado", "volatilidade anualizada"]:
        assert blocked not in box_text
    assert "cenario concentrado" not in box_text
    assert "dados fundamentais estruturados" in data["analysis_sections"]["company_situation"].lower()
    assert "comprar" not in data["analysis_sections"]["conclusion"].lower() or "nao indica" in data["analysis_sections"]["conclusion"].lower()
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
async def test_security_headers_are_added(client: AsyncClient):
    resp = await client.get("/api/health")
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "frame-ancestors 'none'" in resp.headers["content-security-policy"]


@pytest.mark.asyncio
async def test_mutating_request_rejects_untrusted_origin(client: AsyncClient):
    resp = await client.post(
        "/api/auth/login",
        headers={"Origin": "https://evil.example"},
        json={"email": "nobody@operum.app", "password": "Operum123"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_login_rate_limit_returns_429(client: AsyncClient, monkeypatch):
    from app.core.rate_limit import rate_limiter

    monkeypatch.setattr(rate_limiter, "enabled", True)
    monkeypatch.setattr(rate_limiter, "_redis", None)
    rate_limiter._memory.clear()

    statuses = []
    for _ in range(6):
        resp = await client.post(
            "/api/auth/login",
            json={"email": "rate-limit@operum.app", "password": "wrong-password"},
        )
        statuses.append(resp.status_code)

    assert statuses[:5] == [401, 401, 401, 401, 401]
    assert statuses[5] == 429


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
    assert data["mode"] == "knowledge_direct"
    assert isinstance(data["message"], str)
    assert data["message"]
    assert data["retrieval"]["news_count"] == 0
    assert all(source["type"] == "knowledge" for source in data["sources"])
    assert "Resposta curta" not in data["message"]
    assert "Explicação" not in data["message"]


@pytest.mark.asyncio
async def test_chat_conversation_crud_and_history(client: AsyncClient):
    headers = await auth_headers(client, "chat-history")
    created = await client.post(
        "/api/chat/conversations", headers=headers, json={"title": "Meu estudo"}
    )
    assert created.status_code == 201
    conversation_id = created.json()["id"]

    sent = await client.post(
        f"/api/chat/conversations/{conversation_id}/messages",
        headers=headers,
        json={"content": "O que é renda variável?"},
    )
    assert sent.status_code == 200
    assert sent.json()["assistant_message"]["mode"] == "knowledge_direct"

    history = await client.get(
        f"/api/chat/conversations/{conversation_id}/messages", headers=headers
    )
    assert history.status_code == 200
    assert [item["role"] for item in history.json()] == ["user", "assistant"]

    renamed = await client.patch(
        f"/api/chat/conversations/{conversation_id}",
        headers=headers,
        json={"title": "Conceitos fundamentais"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["title"] == "Conceitos fundamentais"

    deleted = await client.delete(
        f"/api/chat/conversations/{conversation_id}", headers=headers
    )
    assert deleted.status_code == 200
    missing = await client.get(
        f"/api/chat/conversations/{conversation_id}/messages", headers=headers
    )
    assert missing.status_code == 404


@pytest.mark.asyncio
async def test_chat_conversations_are_isolated_by_owner(client: AsyncClient):
    first_headers = await auth_headers(client, "chat-owner-one")
    second_headers = await auth_headers(client, "chat-owner-two")
    created = await client.post("/api/chat/conversations", headers=first_headers, json={})
    conversation_id = created.json()["id"]

    forbidden = await client.get(
        f"/api/chat/conversations/{conversation_id}/messages", headers=second_headers
    )
    assert forbidden.status_code == 404
