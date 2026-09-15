from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.ml.baselines import evaluate_selected_baseline, select_baseline
from app.ml.calibration import calibrate_interval, evaluate_interval
from app.ml.evaluation import EvaluationConfig, build_evaluation_plan
from app.ml.experiments import config_hash


def test_evaluation_plan_uses_horizon_purge_and_non_overlapping_outer_blocks():
    dates = pd.bdate_range("2018-01-02", periods=1_100)

    plan = build_evaluation_plan(
        dates,
        horizon_days=42,
        config=EvaluationConfig(min_train_days=252),
    )

    assert plan.seeds == (17, 42, 73)
    assert plan.holdout_start == len(dates) - 126
    assert plan.holdout_end == len(dates) - 1
    assert plan.outer_folds
    for previous, current in zip(plan.outer_folds, plan.outer_folds[1:]):
        assert previous.test_end < current.test_start
        assert current.test_start - previous.test_start == 42
    for fold in plan.outer_folds:
        assert fold.test_end - fold.test_start + 1 == 42
        assert fold.calibration_end - fold.calibration_start + 1 == 126
        assert fold.calibration_end == fold.test_start - 1
        assert fold.calibration_start - fold.train_end - 1 == 42
        assert fold.test_end < plan.holdout_start


def test_evaluation_plan_rejects_changes_to_locked_windows_and_seeds():
    with pytest.raises(ValueError, match="calibration"):
        EvaluationConfig(calibration_days=63)
    with pytest.raises(ValueError, match="holdout"):
        EvaluationConfig(holdout_days=252)
    with pytest.raises(ValueError, match="seeds"):
        EvaluationConfig(seeds=(42,))


def test_evaluation_plan_builds_inner_folds_wholly_inside_each_outer_training_set():
    dates = pd.bdate_range("2018-01-02", periods=1_100)

    plan = build_evaluation_plan(
        dates,
        horizon_days=21,
        config=EvaluationConfig(min_train_days=252),
    )

    assert plan.outer_folds
    for outer in plan.outer_folds:
        assert outer.inner_folds
        for inner in outer.inner_folds:
            assert inner.validation_end <= outer.train_end
            assert inner.validation_start - inner.train_end - 1 == 21
            assert inner.validation_end - inner.validation_start + 1 == 21


def test_baseline_selected_on_training_side_stays_frozen_for_outer_test():
    training_truth = np.array([0.10, 0.20, 0.30])
    training_predictions = {
        "zero": np.zeros(3),
        "drift": np.array([0.09, 0.19, 0.29]),
    }
    outer_truth = np.zeros(3)
    outer_predictions = {
        "zero": np.zeros(3),
        "drift": np.full(3, 0.20),
    }

    selection = select_baseline(training_truth, training_predictions)
    evaluated = evaluate_selected_baseline(selection, outer_truth, outer_predictions)
    contradictory = evaluate_selected_baseline(
        selection,
        np.full(3, 0.20),
        outer_predictions,
    )

    assert selection.name == "drift"
    assert evaluated.name == "drift"
    assert contradictory.name == "drift"
    assert evaluated.metrics["mae"] == pytest.approx(0.20)


def test_interval_calibration_and_evaluation_use_distinct_residual_sets():
    calibration = calibrate_interval(
        truth=np.array([0.0, 0.0, 0.0, 0.0]),
        prediction=np.array([0.01, -0.02, 0.03, -0.04]),
        coverage=0.80,
    )

    result = evaluate_interval(
        calibration,
        truth=np.array([1.0, -1.0]),
        prediction=np.array([0.0, 0.0]),
    )

    assert calibration.sample_count == 4
    assert calibration.interval.radius == 0.04
    assert result.sample_count == 2
    assert result.coverage == 0.0


def test_experiment_config_hash_is_canonical_and_sensitive_to_locked_defaults():
    first = config_hash({"horizon_days": 21, "seeds": [17, 42, 73], "holdout_days": 126})
    reordered = config_hash({"holdout_days": 126, "seeds": [17, 42, 73], "horizon_days": 21})
    changed = config_hash({"horizon_days": 42, "seeds": [17, 42, 73], "holdout_days": 126})

    assert first == reordered
    assert first != changed
    assert len(first) == 64
