from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from app.schemas.portfolio import Portfolio, Position
from app.services.portfolio_analytics_service import PortfolioAnalyticsService


@pytest.mark.parametrize("lengths", [(40, 40, 40), (40, 30, 40)])
def test_benchmark_reuse_preserves_beta_and_refreshes_between_analyses(lengths):
    closes = 100 * np.cumprod(1 + np.linspace(-0.01, 0.02, 40))
    history = pd.DataFrame({"close": closes})
    service = PortfolioAnalyticsService()
    service.assets = SimpleNamespace(get_by_ticker=lambda ticker: None)
    service.market = Mock()
    service.market.get_history.return_value = {"prices": history.to_dict("records")}
    now = datetime.now(timezone.utc)
    portfolio = Portfolio(
        id="test", name="Test", created_at=now, updated_at=now,
        positions=[
            Position(asset_id=ticker, ticker=ticker, asset_class="BR_STOCK", quantity=1)
            for ticker in ("AAA", "BBB", "CCC")
        ],
    )
    prices = {
        position.ticker: history.tail(length).reset_index(drop=True)
        for position, length in zip(portfolio.positions, lengths)
    }
    prices["IBOV"] = history

    first = service.analyze(portfolio, prices)
    assert first["beta"] == pytest.approx(1)
    assert first["benchmark"]["return_21d_pct"] == round((closes[-1] / closes[-22] - 1) * 100, 2)
    assert service.market.get_history.call_count == len(set(lengths))

    second = service.analyze(portfolio, prices)
    assert second == first
    assert service.market.get_history.call_count == 2 * len(set(lengths))


def test_missing_benchmark_is_retried_within_analysis():
    service = PortfolioAnalyticsService()
    service.assets = SimpleNamespace(get_by_ticker=lambda ticker: None)
    closes = 100 * np.cumprod(1 + np.linspace(-0.01, 0.02, 40))
    history = pd.DataFrame({"close": closes})
    service.market = Mock()
    service.market.get_history.side_effect = [None, {"prices": history.to_dict("records")}]
    now = datetime.now(timezone.utc)
    portfolio = Portfolio(
        id="test", name="Test", created_at=now, updated_at=now,
        positions=[
            Position(asset_id=ticker, ticker=ticker, asset_class="BR_STOCK", quantity=1)
            for ticker in ("AAA", "BBB")
        ],
    )
    result = service.analyze(portfolio, {"AAA": history, "BBB": history, "IBOV": history})
    assert result["beta"] == pytest.approx(1)
    assert service.market.get_history.call_count == 2
