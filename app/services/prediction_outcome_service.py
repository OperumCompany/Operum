from __future__ import annotations

from datetime import date

import pandas as pd

from app.services.market_data_service import MarketDataService
from app.services.prediction_repository import PredictionRepository


class PredictionOutcomeService:
    def __init__(self, *, repository=None, market=None):
        self.repository = repository or PredictionRepository()
        self.market = market or MarketDataService()

    def score_due(self, ticker: str, *, as_of: str | date | None = None) -> dict:
        ticker = ticker.upper()
        cutoff = pd.Timestamp(as_of or date.today()).date()
        due = [
            item
            for item in self.repository.list_prediction_outcomes(unscored_only=True)
            if item["ticker"].upper() == ticker
            and pd.Timestamp(item["target_date"]).date() <= cutoff
        ]
        if not due:
            return {"ticker": ticker, "scored": 0}
        history = self.market.get_history(ticker, period="max", interval="1d") or {}
        prices = pd.DataFrame(history.get("prices") or [])
        if prices.empty:
            return {"ticker": ticker, "scored": 0}
        prices["date"] = pd.to_datetime(prices["date"], utc=True).dt.tz_localize(None)
        prices["close"] = pd.to_numeric(prices["close"], errors="coerce")
        prices = prices.dropna(subset=["date", "close"]).sort_values("date")
        snapshots = {
            item["id"]: item
            for item in self.repository.list_snapshots(ticker, limit=max(100, len(due) * 2))
        }
        scored = 0
        for outcome in due:
            snapshot = snapshots.get(outcome["snapshot_id"])
            initial_price = (snapshot or {}).get("payload", {}).get("last_price")
            if not initial_price:
                continue
            observed = prices.loc[prices["date"] >= pd.Timestamp(outcome["target_date"])]
            if observed.empty:
                continue
            actual_return = float(observed.iloc[0]["close"]) / float(initial_price) - 1.0
            self.repository.score_prediction_outcome(
                outcome["snapshot_id"],
                int(outcome["horizon_days"]),
                actual_return,
            )
            scored += 1
        return {"ticker": ticker, "scored": scored}
