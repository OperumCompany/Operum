from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.forecasting import BaselineForecaster
from app.services.local_storage_service import LocalStorageService
from app.services.prediction_repository import PredictionRepository
from app.services.predictive_analysis_service import PredictiveAnalysisService


class DisabledDatabase:
    enabled = False


class Market:
    def get_history(self, ticker: str, period: str = "1y", interval: str = "1d"):
        dates = pd.bdate_range("2026-01-02", periods=100)
        close = np.linspace(30, 40, len(dates))
        return {
            "prices": [
                {
                    "date": date.isoformat(),
                    "open": price,
                    "high": price + 0.2,
                    "low": price - 0.2,
                    "close": price,
                    "volume": 1_000_000,
                }
                for date, price in zip(dates, close, strict=True)
            ]
        }


class News:
    def get_related_news(self, ticker: str, limit: int = 25, days_back: int = 120):
        return [
            {
                "id": "n1",
                "title": "Petrobras divulga resultado",
                "sentiment_score": 0.4,
                "impact_score": 0.7,
                "relevance_score": 0.9,
                "source_confidence_weight": 0.9,
                "analysis_category": "fundamento",
                "event_tags": ["resultados"],
                "published_at": "2026-08-24T12:00:00+00:00",
                "source_name": "CVM",
            }
        ]


class BaselineVersionedForecaster:
    def forecast(self, ticker: str, asset_class: str, market: pd.DataFrame):
        return BaselineForecaster().forecast(ticker, market["close"])


class UnsafeLLM:
    enabled = True

    def chat_json(self, *args, **kwargs):
        return {
            "summary": "Compre agora por 40 reais.",
            "by_horizon": {"1m": "Compre", "2m": "Compre", "3m": "Compre"},
            "confidence_note": "Garantia de lucro.",
        }


def _service(tmp_path):
    repository = PredictionRepository(
        db=DisabledDatabase(),
        storage=LocalStorageService(str(tmp_path)),
    )
    return (
        PredictiveAnalysisService(
            repository=repository,
            market=Market(),
            news_provider=News(),
            forecaster=BaselineVersionedForecaster(),
            llm=UnsafeLLM(),
        ),
        repository,
    )


def test_snapshot_always_contains_three_horizons_and_safe_friendly_message(tmp_path):
    service, _ = _service(tmp_path)

    result = service.generate("PETR4", "BR_STOCK", activate=True)

    assert set(result["horizons"]) == {"1m", "2m", "3m"}
    assert set(result["friendly_message"]["by_horizon"]) == {"1m", "2m", "3m"}
    text = str(result["friendly_message"]).lower()
    assert "previsibilidade insuficiente" not in text
    assert "compre" not in text
    assert result["analysis_id"]


def test_unchanged_analysis_reuses_active_snapshot(tmp_path):
    service, repository = _service(tmp_path)

    first = service.generate("PETR4", "BR_STOCK", activate=True)
    second = service.generate("PETR4", "BR_STOCK", activate=True)

    assert first["analysis_id"] == second["analysis_id"]
    assert len(repository.list_snapshots("PETR4")) == 1


def test_missing_snapshot_returns_baseline_and_enqueues_full_analysis(tmp_path):
    service, repository = _service(tmp_path)

    result = service.get_or_bootstrap("PETR4", "BR_STOCK")

    assert result["generation_mode"] == "baseline"
    assert set(result["horizons"]) == {"1m", "2m", "3m"}
    assert repository.get_active_snapshot("PETR4") is not None
    claimed = repository.claim_next_job()
    assert claimed["ticker"] == "PETR4"
    assert claimed["reason"] == "missing_snapshot"


def test_existing_snapshot_is_read_without_recomputing(tmp_path):
    service, repository = _service(tmp_path)
    expected = service.get_or_bootstrap("PETR4", "BR_STOCK")

    service.market = type("FailMarket", (), {"get_history": lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("recomputed"))})()
    actual = service.get_or_bootstrap("PETR4", "BR_STOCK")

    assert actual["analysis_id"] == expected["analysis_id"]
