from __future__ import annotations

from app.services.prediction_outcome_service import PredictionOutcomeService


class Repository:
    def __init__(self):
        self.updated = []

    def list_prediction_outcomes(self, unscored_only=False):
        return [
            {
                "snapshot_id": "s1",
                "ticker": "PETR4",
                "horizon_days": 21,
                "target_date": "2026-08-20",
                "actual_return": None,
            }
        ]

    def list_snapshots(self, ticker, limit=100):
        return [{"id": "s1", "payload": {"last_price": 30.0}}]

    def score_prediction_outcome(self, snapshot_id, horizon_days, actual_return):
        self.updated.append((snapshot_id, horizon_days, actual_return))


class Market:
    def get_history(self, ticker, period="1y", interval="1d"):
        return {"prices": [{"date": "2026-08-20", "close": 33.0}]}


def test_due_prediction_outcome_is_scored_against_observed_price():
    repository = Repository()
    service = PredictionOutcomeService(repository=repository, market=Market())

    result = service.score_due("PETR4", as_of="2026-08-24")

    assert result == {"ticker": "PETR4", "scored": 1}
    snapshot_id, horizon, actual = repository.updated[0]
    assert (snapshot_id, horizon) == ("s1", 21)
    assert round(actual, 6) == 0.1
