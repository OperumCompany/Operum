from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyRegressor

from app.ml.experiments import HoldoutAlreadyConsumedError
from app.ml.training import (
    TrainingConfig,
    load_model_package,
    train_pooled_horizon,
    xgboost_candidate_params,
)


class _ValidatedRoundRegressor:
    def __init__(self, *, seed=None, n_estimators=None):
        self.seed = seed
        self.n_estimators = n_estimators
        self.best_iteration = 8

    def fit(self, X, y):
        self.value_ = float(np.mean(y))
        return self

    def predict(self, X):
        return np.full(len(X), self.value_)


class _TemporalRecordingRegressor:
    def __init__(self, events, *, params=None, seed=None, n_estimators=None, ledger_root=None):
        self.events = events
        self.params = params or {"candidate": "unselected"}
        self.seed = seed
        self.n_estimators = n_estimators
        self.ledger_root = ledger_root
        self.best_iteration = 4 if self.params.get("candidate") == "a" else 19

    def fit(self, X, y):
        self.events.append(
            {
                "operation": "fit",
                "candidate": self.params.get("candidate"),
                "seed": self.seed,
                "n_estimators": self.n_estimators,
                "date_min": int(X["date_index"].min()),
                "date_max": int(X["date_index"].max()),
            }
        )
        return self

    def predict(self, X):
        date_min = int(X["date_index"].min())
        date_max = int(X["date_index"].max())
        if date_min >= 774:
            assert list((self.ledger_root / ".holdout-ledger").glob("*.json"))
        self.events.append(
            {
                "operation": "predict",
                "candidate": self.params.get("candidate"),
                "seed": self.seed,
                "n_estimators": self.n_estimators,
                "date_min": date_min,
                "date_max": date_max,
            }
        )
        value = 0.0 if self.params.get("candidate") == "a" else 1.0
        return np.full(len(X), value)


def _training_frame() -> pd.DataFrame:
    dates = pd.bdate_range("2019-01-02", periods=900)
    rows = []
    for index, ticker in enumerate(("AAA3", "BBB3", "CCC3")):
        wave = np.sin(np.arange(len(dates)) / 30 + index) * 0.02
        rows.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": ticker,
                    "asset_class": "BR_STOCK",
                    "close": 20 + index + np.arange(len(dates)) * 0.01,
                    "return_1": wave,
                    "return_21": pd.Series(wave).rolling(21).sum().values,
                    "volatility_21": pd.Series(wave).rolling(21).std().values,
                    "target_return_21": np.roll(wave, -21),
                }
            )
        )
    frame = pd.concat(rows, ignore_index=True)
    frame.loc[frame.groupby("ticker").tail(21).index, "target_return_21"] = np.nan
    return frame


def _heterogeneous_validation_frame() -> pd.DataFrame:
    frame = _training_frame()
    ordered = pd.DatetimeIndex(frame["date"].sort_values().unique())
    date_index = {date: index for index, date in enumerate(ordered)}
    frame["date_index"] = frame["date"].map(date_index)
    frame["target_return_21"] = np.where(frame["date_index"] <= 356, -100.0, 0.6)
    return frame


def test_train_pooled_horizon_saves_auditable_shadow_package(tmp_path):
    frame = _training_frame()
    config = TrainingConfig(
        min_train_days=252,
        validation_days=63,
        embargo_days=21,
        holdout_days=126,
        step_days=63,
    )

    result = train_pooled_horizon(
        frame,
        asset_class="BR_STOCK",
        horizon_days=21,
        dataset_hash="dataset-abc",
        artifact_root=tmp_path,
        config=config,
        estimator_factory=lambda: DummyRegressor(strategy="mean"),
    )

    assert result.status == "shadow"
    assert result.dataset_hash == "dataset-abc"
    assert result.horizon_days == 21
    assert result.feature_columns == ("return_1", "return_21", "volatility_21")
    assert result.artifact_path.exists()
    assert result.metadata_path.exists()
    assert result.metrics["folds"] >= 1
    loaded = load_model_package(result.metadata_path)
    assert loaded["metadata"]["dataset_hash"] == "dataset-abc"
    assert hasattr(loaded["model"], "predict")


def test_training_serializes_reusable_oos_audit_without_reopening_holdout(tmp_path):
    requests = []

    def estimator_factory(*, seed=None, n_estimators=None):
        requests.append({"seed": seed, "n_estimators": n_estimators})
        return _ValidatedRoundRegressor(seed=seed, n_estimators=n_estimators)

    result = train_pooled_horizon(
        _training_frame(),
        asset_class="BR_STOCK",
        horizon_days=21,
        dataset_hash="dataset-audit",
        artifact_root=tmp_path,
        config=TrainingConfig(252, 63, 21, 126, 63),
        estimator_factory=estimator_factory,
    )

    metadata = load_model_package(result.metadata_path)["metadata"]
    oos_path = result.metadata_path.parent / metadata["oos_predictions_path"]
    oos_records = [json.loads(line) for line in oos_path.read_text(encoding="utf-8").splitlines()]

    assert metadata["evaluation_config"]["seeds"] == [17, 42, 73]
    assert metadata["evaluation_config"]["holdout_days"] == 126
    assert len(metadata["config_hash"]) == 64
    assert set(metadata["config_hashes"]) == {"evaluation", "selected_params", "training"}
    assert all(len(value) == 64 for value in metadata["config_hashes"].values())
    assert metadata["holdout_access"]["access_count"] == 1
    assert metadata["holdout_access"]["days"] == 126
    assert metadata["holdout_access"]["locked"] is True
    assert metadata["fold_diagnostics"]
    assert metadata["best_iterations"]
    assert metadata["validated_boosting_rounds"] == 9
    assert requests[-1]["n_estimators"] == 9
    assert {item["seed"] for item in requests[:-1]} == {17, 42, 73}
    assert {item["split"] for item in oos_records} == {"outer_test", "holdout"}
    assert sum(item["split"] == "holdout" for item in oos_records) == 126 * 3
    assert metadata["metrics"]["promotion_reasons"] == list(result.metrics["promotion_reasons"])
    assert metadata["baseline_selection_policy"] == "preceding_calibration_mae_per_block"
    assert [item["baseline_name"] for item in metadata["baseline_selections"]] == [
        *[item["baseline_name"] for item in metadata["fold_diagnostics"]],
        metadata["holdout_baseline_name"],
    ]


def test_locked_holdout_is_consumed_once_per_dataset_slot_and_persisted(tmp_path):
    arguments = {
        "asset_class": "BR_STOCK",
        "horizon_days": 21,
        "dataset_hash": "dataset-one-shot",
        "artifact_root": tmp_path,
        "config": TrainingConfig(252, 63, 21, 126, 63),
        "estimator_factory": lambda: DummyRegressor(strategy="mean"),
    }

    first = train_pooled_horizon(_training_frame(), **arguments)
    first_metadata = load_model_package(first.metadata_path)["metadata"]
    ledger_path = tmp_path / first_metadata["holdout_access"]["ledger_path"]
    persisted = json.loads(ledger_path.read_text(encoding="utf-8"))

    assert first_metadata["holdout_access"] == persisted
    with pytest.raises(HoldoutAlreadyConsumedError, match="already consumed"):
        train_pooled_horizon(_training_frame(), **arguments)

    mismatched = {**arguments, "config": TrainingConfig(273, 63, 21, 126, 63)}
    with pytest.raises(HoldoutAlreadyConsumedError, match="configuration mismatch"):
        train_pooled_horizon(_training_frame(), **mismatched)


def test_selected_parameter_round_pair_uses_matching_inner_validation_evidence(
    tmp_path,
    monkeypatch,
):
    events = []
    candidates = ({"candidate": "a"}, {"candidate": "b"})
    monkeypatch.setattr("app.ml.training.xgboost_candidate_params", lambda: candidates)

    def estimator_factory(*, params=None, seed=None, n_estimators=None):
        return _TemporalRecordingRegressor(
            events,
            params=params,
            seed=seed,
            n_estimators=n_estimators,
            ledger_root=tmp_path,
        )

    result = train_pooled_horizon(
        _heterogeneous_validation_frame(),
        asset_class="BR_STOCK",
        horizon_days=21,
        dataset_hash="dataset-heterogeneous",
        artifact_root=tmp_path,
        config=TrainingConfig(252, 63, 21, 126, 63),
        estimator_factory=estimator_factory,
    )

    metadata = load_model_package(result.metadata_path)["metadata"]
    ledger_record = json.loads(
        (tmp_path / metadata["holdout_access"]["ledger_path"]).read_text(encoding="utf-8")
    )
    final_fit = events[-1]
    first_holdout_use = next(item for item in events if item["date_max"] >= 774)
    outer_fits = [
        item
        for item in events
        if item["operation"] == "fit"
        and item["n_estimators"] is not None
        and item["date_max"] < 774
    ]
    first_outer_fit_index = events.index(outer_fits[0])
    first_outer_fit, first_calibration_predict, first_test_predict = events[
        first_outer_fit_index : first_outer_fit_index + 3
    ]
    fold_candidates = [item["selected_params"]["candidate"] for item in metadata["fold_diagnostics"]]
    selected_provenance = next(
        item
        for item in metadata["validated_configurations"]
        if item["params"] == {"candidate": "a"}
    )

    assert set(fold_candidates) == {"a", "b"}
    assert fold_candidates.count("b") > fold_candidates.count("a")
    assert metadata["selected_params"] == {"candidate": "a"}
    assert metadata["validated_boosting_rounds"] == 5
    assert selected_provenance["boosting_rounds"] == 5
    assert set(selected_provenance["best_iterations"]) == {4}
    assert ledger_record["configuration_hash"] == metadata["config_hash"]
    assert final_fit["candidate"] == "a"
    assert final_fit["n_estimators"] == 5
    assert first_holdout_use["operation"] == "predict"
    assert first_holdout_use["date_min"] == 774
    assert first_calibration_predict["date_min"] - first_outer_fit["date_max"] - 1 == 21
    assert first_calibration_predict["date_max"] - first_calibration_predict["date_min"] + 1 == 126
    assert first_test_predict["date_min"] == first_calibration_predict["date_max"] + 1
    assert first_test_predict["date_max"] - first_test_predict["date_min"] + 1 == 21
    assert all(
        [item["seed"] for item in outer_fits[index : index + 3]] == [17, 42, 73]
        for index in range(0, len(outer_fits), 3)
    )
    assert {item["seed"] for item in events if item["seed"] is not None} == {17, 42, 73}
    assert all(
        item["date_max"] < 774
        for item in events[: events.index(first_holdout_use)]
    )


def test_model_package_does_not_include_targets_or_identity_as_features(tmp_path):
    result = train_pooled_horizon(
        _training_frame(),
        asset_class="BR_STOCK",
        horizon_days=21,
        dataset_hash="dataset-def",
        artifact_root=tmp_path,
        config=TrainingConfig(252, 63, 21, 126, 63),
        estimator_factory=lambda: DummyRegressor(strategy="median"),
    )

    assert "date" not in result.feature_columns
    assert "ticker" not in result.feature_columns
    assert "close" not in result.feature_columns
    assert not any(name.startswith("target_") for name in result.feature_columns)


def test_xgboost_search_space_is_bounded_and_regularized():
    candidates = xgboost_candidate_params()

    assert 2 <= len(candidates) <= 8
    assert all(candidate["max_depth"] <= 4 for candidate in candidates)
    assert all(candidate["subsample"] < 1 for candidate in candidates)
    assert all(candidate["colsample_bytree"] < 1 for candidate in candidates)
    assert all(candidate["reg_lambda"] >= 1 for candidate in candidates)
    assert all(candidate["early_stopping_rounds"] >= 20 for candidate in candidates)
