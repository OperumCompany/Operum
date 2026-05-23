import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app


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
async def test_cluster_news(client: AsyncClient):
    resp = await client.post("/api/models/cluster/news")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
