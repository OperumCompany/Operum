from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import pytest

from app.ml.evaluation import EvaluationPlan, InnerFold, OuterFold
from app.ml.feature_pipeline import FoldFeaturePipeline
from app.ml.probabilistic_training import (
    EstimatorFactories,
    ProbabilisticTrainingConfig,
    train_probabilistic_slot,
)


class _RecordingPipeline(FoldFeaturePipeline):
    events: list[dict] = []

    def __init__(self):
        super().__init__(
            numeric_features=(
                "return_1",
                "volatility_21",
                "benchmark_return_21",
            ),
            rank_features=(),
            categorical_features=(),
        )
        self.instance_id = id(self)

    def fit(self, train):
        self.events.append(
            {
                "operation": "fit",
                "instance_id": self.instance_id,
                "date_min": pd.Timestamp(train["date"].min()),
                "date_max": pd.Timestamp(train["date"].max()),
            }
        )
        return super().fit(train)

    def transform(self, frame):
        self.events.append(
            {
                "operation": "transform",
                "instance_id": self.instance_id,
                "date_min": pd.Timestamp(frame["date"].min()),
                "date_max": pd.Timestamp(frame["date"].max()),
            }
        )
        return super().transform(frame)


class _CenterRegressor:
    def __init__(self, objective, seed, n_estimators, validation):
        self.objective = objective
        self.seed = seed
        self.n_estimators = n_estimators
        self.validation = validation
        self.best_iteration = None
        self.slope = 0.0

    def fit(self, matrix, truth, sample_weight=None, **kwargs):
        uniform = sample_weight is None or np.allclose(sample_weight, sample_weight[0])
        robust = self.objective == "reg:absoluteerror"
        signal = np.asarray(matrix["return_1"], dtype=float)
        fitted_slope = float(np.dot(signal, truth) / np.dot(signal, signal))
        self.slope = fitted_slope if uniform and robust else 0.05
        if self.validation:
            self.best_iteration = 2 if uniform and robust else 5
        return self

    def predict(self, matrix):
        return np.asarray(matrix["return_1"], dtype=float) * self.slope


class _ElasticRegressor:
    def fit(self, matrix, truth, sample_weight=None, **kwargs):
        return self

    def predict(self, matrix):
        return np.asarray(matrix["return_1"], dtype=float) * 0.15


class _QuantileRegressor:
    def __init__(self, alpha, validation):
        self.alpha = alpha
        self.validation = validation
        self.best_iteration = None

    def fit(self, matrix, truth, sample_weight=None, **kwargs):
        if self.validation:
            self.best_iteration = {0.10: 1, 0.50: 2, 0.90: 3}[self.alpha]
        return self

    def predict(self, matrix):
        # Deliberately cross q10/q90; package inference must repair this without truth.
        offset = {0.10: 0.05, 0.50: 0.0, 0.90: -0.05}[self.alpha]
        return np.asarray(matrix["return_1"], dtype=float) * 0.40 + offset


class _DirectionClassifier:
    def __init__(self, validation):
        self.validation = validation
        self.best_iteration = None

    def fit(self, matrix, truth, sample_weight=None, **kwargs):
        self.classes_ = np.array([0, 1])
        if self.validation:
            self.best_iteration = 4
        return self

    def predict_proba(self, matrix):
        probability = np.clip(
            0.50 + np.asarray(matrix["return_1"], dtype=float) * 2.0,
            0.05,
            0.95,
        )
        return np.column_stack([1.0 - probability, probability])


def _factories(events: list[dict]) -> EstimatorFactories:
    def center(*, objective, seed, n_estimators, validation, parameters):
        events.append(
            {
                "component": "center",
                "objective": objective,
                "seed": seed,
                "n_estimators": n_estimators,
                "validation": validation,
            }
        )
        return _CenterRegressor(objective, seed, n_estimators, validation)

    def elastic_net(*, seed, parameters):
        events.append({"component": "elastic_net", "seed": seed})
        return _ElasticRegressor()

    def quantile(*, alpha, seed, n_estimators, validation, parameters):
        events.append(
            {
                "component": "quantile",
                "alpha": alpha,
                "seed": seed,
                "n_estimators": n_estimators,
                "validation": validation,
            }
        )
        return _QuantileRegressor(alpha, validation)

    def classifier(*, seed, n_estimators, validation, parameters):
        events.append(
            {
                "component": "classifier",
                "seed": seed,
                "n_estimators": n_estimators,
                "validation": validation,
            }
        )
        return _DirectionClassifier(validation)

    return EstimatorFactories(
        center=center,
        elastic_net=elastic_net,
        quantile=quantile,
        classifier=classifier,
    )


def _frame() -> pd.DataFrame:
    dates = pd.date_range("2020-01-01", periods=360, freq="D")
    signal = np.sin(np.arange(360) / 7.0) * 0.10
    total = signal * 0.40
    price = signal * 0.20
    frame = pd.DataFrame(
        {
            "date": dates,
            "ticker": ["PETR4"] * len(dates),
            "asset_class": ["BR_STOCK"] * len(dates),
            "return_1": signal,
            "volatility_21": np.linspace(0.10, 0.30, len(dates)),
            "benchmark_return_21": np.sin(np.arange(360) / 13.0) * 0.03,
            "target_total_return_5": total,
            "target_price_return_5": price,
        }
    )
    # These values would make any accidental holdout read obvious in model/provenance output.
    frame.loc[234:, ["target_total_return_5", "target_price_return_5"]] = 999.0
    frame.loc[234:, "return_1"] = 999.0
    return frame


def _plan() -> EvaluationPlan:
    dates = tuple(pd.date_range("2020-01-01", periods=360, freq="D"))
    inner = InnerFold(
        train_start=0,
        train_end=50,
        validation_start=56,
        validation_end=60,
    )
    outer = OuterFold(
        train_start=0,
        train_end=80,
        calibration_start=86,
        calibration_end=211,
        test_start=212,
        test_end=216,
        inner_folds=(inner,),
    )
    return EvaluationPlan(
        dates=dates,
        horizon_days=5,
        holdout_start=234,
        holdout_end=359,
        seeds=(17, 42, 73),
        outer_folds=(outer,),
    )


def test_nested_training_refits_every_boundary_and_never_reads_the_holdout():
    _RecordingPipeline.events = []
    factory_events = []
    result = train_probabilistic_slot(
        _frame(),
        asset_class="BR_STOCK",
        horizon_days=5,
        evaluation_plan=_plan(),
        pipeline_factory=_RecordingPipeline,
        factories=_factories(factory_events),
        config=ProbabilisticTrainingConfig(candidate_rounds=7),
    )

    fits = [event for event in _RecordingPipeline.events if event["operation"] == "fit"]
    transforms = [
        event for event in _RecordingPipeline.events if event["operation"] == "transform"
    ]
    assert len({event["instance_id"] for event in fits}) == len(fits)
    assert {event["date_max"] for event in fits} == {
        pd.Timestamp("2020-02-20"),  # inner train end 50
        pd.Timestamp("2020-03-21"),  # outer train end 80
        pd.Timestamp("2020-04-12"),  # final calibration model train end 102
        pd.Timestamp("2020-08-16"),  # final history end 228
    }
    assert all(event["date_max"] < pd.Timestamp("2020-08-22") for event in transforms)

    assert set(result.selected_configurations) == {"total", "price"}
    for config in result.selected_configurations.values():
        assert config.objective == "reg:absoluteerror"
        assert config.history_policy == "uniform_expanding"
        assert config.n_estimators == 3
    assert result.package.total.center_config.n_estimators == 3
    assert result.package.price.center_config.n_estimators == 3
    assert result.package.direction.config.n_estimators == 5
    assert {
        name: config.n_estimators
        for name, config in result.package.total.quantile_configs.items()
    } == {"q10": 2, "q50": 3, "q90": 4}
    assert {
        name: config.n_estimators
        for name, config in result.package.price.quantile_configs.items()
    } == {"q10": 2, "q50": 3, "q90": 4}
    assert result.package.total.blend.sample_count == 126
    assert result.package.price.blend.sample_count == 126
    assert result.package.direction.calibrator.sample_count == 126
    assert set(result.package.total.quantile_models) == {"q10", "q50", "q90"}
    assert set(result.package.price.quantile_models) == {"q10", "q50", "q90"}

    assert len(result.oos_predictions) == 5
    assert {row["split"] for row in result.oos_predictions} == {"outer_test"}
    assert all(row["truth_total"] != 999.0 for row in result.oos_predictions)
    assert result.oos_provenance["holdout_status"] == "not_accessed_by_task_4"
    assert result.gate_decision.passed is False
    assert result.gate_decision.checks["snapshot_generation"] == "pending_task_5"
    assert any(name.startswith("holdout_") for name in result.gate_decision.reasons)

    final_center_calls = [
        event
        for event in factory_events
        if event["component"] == "center" and event["validation"] is False
    ]
    assert final_center_calls
    assert all(event["n_estimators"] == 3 for event in final_center_calls)
    assert any(
        event["component"] == "quantile" and event["validation"] is True
        for event in factory_events
    )
    assert any(
        event["component"] == "classifier" and event["validation"] is True
        for event in factory_events
    )
    output = result.package.predict(_frame().iloc[[220]].assign(return_1=0.02))
    assert len(output) == 1
    assert output[0]["total"]["quantiles"]["q10"] <= output[0]["total"]["quantiles"]["q90"]


def test_inner_model_selection_cannot_see_outer_or_holdout_truth():
    first_events = []
    first = train_probabilistic_slot(
        _frame(),
        asset_class="BR_STOCK",
        horizon_days=5,
        evaluation_plan=_plan(),
        pipeline_factory=_RecordingPipeline,
        factories=_factories(first_events),
        config=ProbabilisticTrainingConfig(candidate_rounds=7),
    )

    changed = _frame()
    changed.loc[61:233, "target_total_return_5"] *= -10_000.0
    changed.loc[61:233, "target_price_return_5"] *= 10_000.0
    second_events = []
    second = train_probabilistic_slot(
        changed,
        asset_class="BR_STOCK",
        horizon_days=5,
        evaluation_plan=_plan(),
        pipeline_factory=_RecordingPipeline,
        factories=_factories(second_events),
        config=ProbabilisticTrainingConfig(candidate_rounds=7),
    )

    assert {
        name: config.state() for name, config in first.selected_configurations.items()
    } == {name: config.state() for name, config in second.selected_configurations.items()}


@pytest.mark.parametrize("tamper", ["short_calibration", "inner_outside_outer"])
def test_training_rejects_tampered_temporal_boundaries(tamper):
    plan = _plan()
    outer = plan.outer_folds[0]
    if tamper == "short_calibration":
        outer = replace(outer, calibration_end=outer.calibration_end - 1)
    else:
        inner = replace(outer.inner_folds[0], validation_end=outer.train_end + 1)
        outer = replace(outer, inner_folds=(inner,))
    plan = replace(plan, outer_folds=(outer,))

    with pytest.raises(ValueError, match="temporal|calibration|outer"):
        train_probabilistic_slot(
            _frame(),
            asset_class="BR_STOCK",
            horizon_days=5,
            evaluation_plan=plan,
            pipeline_factory=_RecordingPipeline,
            factories=_factories([]),
            config=ProbabilisticTrainingConfig(candidate_rounds=7),
        )
