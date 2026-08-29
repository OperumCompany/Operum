from datetime import date, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.portfolio import Portfolio, Position, PositionAdd
from app.services.local_storage_service import LocalStorageService
from app.services.portfolio_service import PortfolioService
from app.services.portfolio_transaction_service import PortfolioTransactionService


class DisabledDb:
    enabled = False


class FakeMarket:
    def get_history(self, ticker: str, period: str = "6mo", interval: str = "1d"):
        today = date.today()
        return {
            "prices": [
                {"date": (today - timedelta(days=2)).isoformat(), "close": 100.0},
                {"date": (today - timedelta(days=1)).isoformat(), "close": 110.0},
                {"date": today.isoformat(), "close": 120.0},
            ]
        }


def make_portfolio(quantity: float = 10, avg_price: float | None = 100) -> Portfolio:
    now = datetime.now(timezone.utc)
    return Portfolio(
        id="portfolio-test",
        owner_id="user-test",
        name="Teste",
        created_at=now,
        updated_at=now,
        positions=[Position(asset_id="PETR4", ticker="PETR4", asset_class="BR_STOCK", quantity=quantity, avg_price=avg_price)],
    )


def test_example_creation_rolls_back_when_ledger_initialization_fails(tmp_path, monkeypatch):
    storage = LocalStorageService(str(tmp_path))
    service = PortfolioService()
    service.storage = storage
    service.db = DisabledDb()
    service.transactions = PortfolioTransactionService(db=DisabledDb(), storage=storage, market=FakeMarket())

    def fail_opening(*args, **kwargs):
        raise RuntimeError("ledger unavailable")

    monkeypatch.setattr(service.transactions, "ensure_opening_transactions", fail_opening)
    with pytest.raises(RuntimeError, match="ledger unavailable"):
        service.create_example("rollback-user")

    assert [portfolio for portfolio in service.list_all("rollback-user") if portfolio.kind == "example"] == []


def test_opening_migration_is_idempotent_and_history_uses_real_movements(tmp_path):
    storage = LocalStorageService(str(tmp_path))
    transactions = PortfolioTransactionService(db=DisabledDb(), storage=storage, market=FakeMarket())
    portfolio = make_portfolio()
    opening_date = date.today() - timedelta(days=2)

    assert transactions.ensure_opening_transactions(portfolio, opening_date) == 1
    assert transactions.ensure_opening_transactions(portfolio, opening_date) == 0
    transactions.append(portfolio.id, "PETR4", "BR_STOCK", "buy", 5, 200, "BRL", date.today() - timedelta(days=1))

    history = transactions.build_history(portfolio, "max", "PETR4")
    assert history["points"][0]["quantity"] == 10
    assert history["points"][0]["invested_value"] == 1000
    assert history["points"][-1]["quantity"] == 15
    assert history["points"][-1]["market_value"] == 1800
    assert history["points"][-1]["invested_value"] == 2000


def test_unknown_opening_cost_surfaces_warning(tmp_path):
    transactions = PortfolioTransactionService(
        db=DisabledDb(), storage=LocalStorageService(str(tmp_path)), market=FakeMarket(),
    )
    portfolio = make_portfolio(avg_price=None)
    transactions.ensure_opening_transactions(portfolio)

    history = transactions.build_history(portfolio, "1m")
    assert history["points"][-1]["invested_value"] is None
    assert any("Custo investido indisponível" in warning for warning in history["warnings"])


@pytest.mark.parametrize("period", ["1m", "6m", "1y", "max"])
def test_supported_history_periods(tmp_path, period):
    transactions = PortfolioTransactionService(
        db=DisabledDb(), storage=LocalStorageService(str(tmp_path)), market=FakeMarket(),
    )
    portfolio = make_portfolio()
    transactions.ensure_opening_transactions(portfolio)
    history = transactions.build_history(portfolio, period)
    assert history["period"] == period
    assert history["available_tickers"] == ["PETR4"]
    assert history["points"]


def test_local_position_add_uses_weighted_average_and_close_preserves_ledger(tmp_path):
    storage = LocalStorageService(str(tmp_path))
    transactions = PortfolioTransactionService(db=DisabledDb(), storage=storage, market=FakeMarket())
    service = PortfolioService.__new__(PortfolioService)
    service.storage = storage
    service.db = DisabledDb()
    service._dir = "portfolios"
    service.transactions = transactions
    portfolio = make_portfolio(quantity=10, avg_price=100)
    storage.save_json(f"portfolios/{portfolio.id}.json", portfolio.model_dump(mode="json"))

    updated = service.add_position(
        portfolio.id,
        PositionAdd(ticker="PETR4", asset_class="BR_STOCK", quantity=10, avg_price=200, occurred_at=date.today()),
        "user-test",
    )
    assert updated is not None
    assert updated.positions[0].quantity == 20
    assert updated.positions[0].avg_price == 150

    removed = service.remove_position(portfolio.id, "PETR4", "user-test")
    assert removed is not None
    assert removed.positions == []
    ledger = transactions.list_for_portfolio(portfolio.id)
    assert [item.kind for item in ledger] == ["opening", "buy", "close"]
    assert sum(item.quantity_delta for item in ledger) == 0

    reopened = service.add_position(
        portfolio.id,
        PositionAdd(ticker="PETR4", asset_class="BR_STOCK", quantity=3, avg_price=50, occurred_at=date.today()),
        "user-test",
    )
    assert reopened is not None
    assert reopened.positions[0].quantity == 3
    assert reopened.positions[0].avg_price == 50
    assert [item.kind for item in transactions.list_for_portfolio(portfolio.id)] == ["opening", "buy", "close", "buy"]


def test_future_transaction_date_is_rejected():
    with pytest.raises(ValidationError):
        PositionAdd(
            ticker="PETR4",
            asset_class="BR_STOCK",
            quantity=1,
            avg_price=10,
            occurred_at=date.today() + timedelta(days=1),
        )
