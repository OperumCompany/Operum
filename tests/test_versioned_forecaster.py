from __future__ import annotations

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyRegressor

from app.ml.inference import VersionedForecaster


class ModelRepository:
    def __init__(self, records=None):
        self.records = records or {}

    def get_active_model(self, asset_class: str, horizon_days: int):
        return self.records.get((asset_class, horizon_days))


def _market() -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-02", periods=100)
    close = np.linspace(30, 40, len(dates))
    return pd.DataFrame(
        {
            "date": dates,
            "ticker": "PETR4",
            "asset_class": "BR_STOCK",
            "open": close,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": 1_000_000,
        }
    )


def test_versioned_forecaster_uses_baseline_when_no_active_models():
    result = VersionedForecaster(ModelRepository()).forecast("PETR4", "BR_STOCK", _market())

    assert result["generation_mode"] == "baseline"
    assert set(result["horizons"]) == {"1m", "2m", "3m"}
    assert all(item["source"].startswith("baseline") for item in result["horizons"].values())


def test_versioned_forecaster_uses_active_model_and_falls_back_per_horizon(tmp_path):
    model = DummyRegressor(strategy="constant", constant=0.05).fit([[0.0], [1.0]], [0.05, 0.05])
    joblib.dump(model, tmp_path / "model.joblib")
    metadata = {
        "model_version": "model-21",
        "artifact_path": "model.joblib",
        "feature_columns": ["return_1"],
        "feature_medians": {"return_1": 0.0},
        "interval": {"coverage": 0.8, "radius": 0.10},
        "metrics": {"candidate": {"mae": 0.05}, "baseline": {"mae": 0.08}},
    }
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    repository = ModelRepository(
        {("BR_STOCK", 21): {"id": "model-21", "metadata_path": str(metadata_path), "status": "active"}}
    )

    result = VersionedForecaster(repository).forecast("PETR4", "BR_STOCK", _market())

    assert result["generation_mode"] == "mixed"
    assert result["horizons"]["1m"]["expected_return"] == 0.05
    assert result["horizons"]["1m"]["source"] == "xgboost"
    assert result["horizons"]["2m"]["source"].startswith("baseline")
    assert result["model_versions"] == {"1m": "model-21"}

