from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.ml.gates_v2 import evaluate_probabilistic_gates
from app.ml.metrics_v2 import (
    classification_metrics,
    group_stability,
    interval_metrics,
    origin_known_regimes,
    quantile_metrics,
    seed_stability,
)
from app.ml.probabilistic import (
    CENTER_OBJECTIVES,
    HISTORY_POLICIES,
    QUANTILE_ALPHAS,
    AdaptiveConformalCalibrator,
    OOSBlend,
    TemporalPlattCalibrator,
    history_weights,
    history_weights_for_origins,
    make_elastic_net,
    make_xgboost_center,
    make_xgboost_classifier,
    make_xgboost_quantile,
    ordered_quantiles,
)


def _passing_gate_sample() -> dict:
    return {
        "candidate": {
            "mae": 0.90,
            "balanced_accuracy": 0.56,
            "brier": 0.090,
            "pinball_mean": 0.090,
            "winkler": 0.90,
            "coverage": 0.80,
        },
        "baseline": {
            "mae": 1.00,
            "balanced_accuracy": 0.53,
            "brier": 0.100,
            "pinball_mean": 0.100,
            "winkler": 1.00,
            "coverage": 0.80,
        },
    }


def test_default_estimators_use_the_locked_robust_objectives():
    assert CENTER_OBJECTIVES == ("reg:absoluteerror", "reg:pseudohubererror")
    assert QUANTILE_ALPHAS == (0.10, 0.50, 0.90)
    assert HISTORY_POLICIES == ("uniform_expanding", "exponential_504")

    classifier = make_xgboost_classifier(seed=17, n_estimators=7)
    absolute = make_xgboost_center(
        objective="reg:absoluteerror", seed=17, n_estimators=7
    )
    pseudo_huber = make_xgboost_center(
        objective="reg:pseudohubererror", seed=17, n_estimators=7
    )
    quantiles = [
        make_xgboost_quantile(alpha=alpha, seed=17, n_estimators=7)
        for alpha in QUANTILE_ALPHAS
    ]

    assert classifier.get_xgb_params()["objective"] == "binary:logistic"
    assert absolute.get_xgb_params()["objective"] == "reg:absoluteerror"
    assert pseudo_huber.get_xgb_params()["objective"] == "reg:pseudohubererror"
    assert [model.get_xgb_params()["objective"] for model in quantiles] == [
        "reg:quantileerror"
    ] * 3
    assert [model.get_xgb_params()["quantile_alpha"] for model in quantiles] == [
        0.10,
        0.50,
        0.90,
    ]
    assert make_elastic_net(seed=17).__class__.__name__ == "ElasticNet"


def test_platt_calibration_is_disjoint_clipped_and_neutral_for_one_class():
    calibration_ids = ("c0", "c1", "c2", "c3")
    fit_ids = ("t0", "t1")
    calibrator = TemporalPlattCalibrator.fit(
        [0.0, 0.20, 0.80, 1.0],
        [0, 0, 1, 1],
        calibration_ids=calibration_ids,
        model_fit_ids=fit_ids,
    )
    calibrated = calibrator.predict([0.0, 0.20, 0.80, 1.0])

    assert np.all(np.isfinite(calibrated))
    assert np.all((calibrated > 0.0) & (calibrated < 1.0))
    assert np.all(np.diff(calibrated) > 0.0)
    assert calibrator.state()["mode"] == "platt"
    assert calibrator.state()["model_fit_ids_hash"] != calibrator.state()[
        "calibration_ids_hash"
    ]

    one_class = TemporalPlattCalibrator.fit(
        [0.1, 0.4, 0.9],
        [1, 1, 1],
        calibration_ids=("a", "b", "c"),
        model_fit_ids=fit_ids,
    )
    assert one_class.state()["mode"] == "one_class_neutral"
    assert one_class.predict([0.01, 0.99]).tolist() == [0.5, 0.5]

    with pytest.raises(ValueError, match="disjoint"):
        TemporalPlattCalibrator.fit(
            [0.2, 0.8],
            [0, 1],
            calibration_ids=("t1", "c1"),
            model_fit_ids=fit_ids,
        )


def test_oos_blend_is_nonnegative_normalized_and_disables_weak_challengers():
    truth = np.array([0.0, 1.0, 2.0, 3.0])
    blend = OOSBlend.fit(
        truth,
        {
            "baseline": np.array([0.5, 0.5, 1.5, 2.5]),
            "xgboost": np.array([0.0, 1.0, 2.0, 3.0]),
            "elastic_net": np.array([4.0, 4.0, 4.0, 4.0]),
        },
        baseline_name="baseline",
        calibration_ids=("c0", "c1", "c2", "c3"),
        model_fit_ids=("t0", "t1"),
    )

    assert all(weight >= 0.0 for weight in blend.weights.values())
    assert sum(blend.weights.values()) == pytest.approx(1.0)
    assert blend.weights["elastic_net"] == 0.0
    assert blend.state()["model_fit_ids_hash"] != blend.state()[
        "calibration_ids_hash"
    ]
    prediction = blend.predict(
        {
            "baseline": np.array([0.5, 0.5, 1.5, 2.5]),
            "xgboost": np.array([0.0, 1.0, 2.0, 3.0]),
            "elastic_net": np.array([4.0, 4.0, 4.0, 4.0]),
        }
    )
    assert np.mean(np.abs(prediction - truth)) < 0.5

    fallback = OOSBlend.fit(
        truth,
        {
            "baseline": truth,
            "xgboost": truth + 1.0,
            "elastic_net": truth - 1.0,
        },
        baseline_name="baseline",
        calibration_ids=("c0", "c1", "c2", "c3"),
        model_fit_ids=("t0", "t1"),
    )
    assert fallback.weights == {
        "baseline": 1.0,
        "elastic_net": 0.0,
        "xgboost": 0.0,
    }

    with pytest.raises(ValueError, match="disjoint"):
        OOSBlend.fit(
            truth,
            {"baseline": truth, "xgboost": truth},
            baseline_name="baseline",
            calibration_ids=("c0", "c1", "t0", "c3"),
            model_fit_ids=("t0", "t1"),
        )


def test_quantile_crossing_is_fixed_without_truth_and_conformal_is_predict_then_update():
    ordered = ordered_quantiles(
        {
            "q10": np.array([0.30, -0.10]),
            "q50": np.array([0.10, 0.20]),
            "q90": np.array([0.20, 0.00]),
        }
    )
    assert ordered["q10"].tolist() == [0.10, -0.10]
    assert ordered["q50"].tolist() == [0.20, 0.00]
    assert ordered["q90"].tolist() == [0.30, 0.20]

    calibrator = AdaptiveConformalCalibrator(coverage=0.80, max_scores=2)
    first_low, first_high = calibrator.correct([-0.10], [0.10])
    assert first_low.tolist() == [-0.10]
    assert first_high.tolist() == [0.10]
    calibrator.observe(truth=2.0, lower=-0.10, upper=0.10, row_id="row-1")

    second_low, second_high = calibrator.correct([-0.10], [0.10])
    assert second_low[0] < -1.9
    assert second_high[0] > 1.9
    with pytest.raises(ValueError, match="already"):
        calibrator.observe(truth=2.0, lower=-0.10, upper=0.10, row_id="row-1")

    replay = AdaptiveConformalCalibrator(coverage=0.80, max_scores=2)
    lows, highs = replay.calibrate_oos(
        truth=[2.0, 0.0],
        lower=[-0.10, -0.10],
        upper=[0.10, 0.10],
        row_ids=("row-1", "row-2"),
    )
    assert lows[0] == pytest.approx(-0.10)
    assert highs[0] == pytest.approx(0.10)
    assert lows[1] < -1.9
    assert highs[1] > 1.9


def test_history_policies_are_deterministic_and_half_life_is_504_rows():
    assert history_weights(505, "uniform_expanding").tolist() == [1.0] * 505
    exponential = history_weights(505, "exponential_504")
    assert exponential[-1] == pytest.approx(1.0)
    assert exponential[0] == pytest.approx(0.5)
    assert np.all(np.diff(exponential) > 0.0)

    pooled_origins = np.repeat(pd.date_range("2020-01-01", periods=505), 2)
    pooled = history_weights_for_origins(pooled_origins, "exponential_504")
    assert pooled[0] == pytest.approx(0.5)
    assert pooled[1] == pytest.approx(0.5)
    assert pooled[-2:].tolist() == [1.0, 1.0]


def test_probabilistic_metrics_match_hand_checked_values_and_group_stability():
    classification = classification_metrics(
        [0, 0, 1, 1], [0.10, 0.60, 0.40, 0.90]
    )
    assert classification == {
        "balanced_accuracy": pytest.approx(0.50),
        "brier": pytest.approx(0.185),
    }

    quantiles = quantile_metrics(
        [0.0, 1.0],
        {"q10": [-1.0, 0.0], "q50": [0.0, 1.0], "q90": [1.0, 2.0]},
    )
    assert quantiles["pinball_q10"] == pytest.approx(0.10)
    assert quantiles["pinball_q50"] == pytest.approx(0.0)
    assert quantiles["pinball_q90"] == pytest.approx(0.10)
    assert quantiles["pinball_mean"] == pytest.approx(1.0 / 15.0)

    interval = interval_metrics(
        [0.0, 3.0], lower=[-1.0, 0.0], upper=[1.0, 2.0], coverage=0.80
    )
    assert interval["coverage"] == pytest.approx(0.50)
    assert interval["interval_width"] == pytest.approx(2.0)
    assert interval["winkler"] == pytest.approx(7.0)

    groups = group_stability(
        [0.0, 1.0, 2.0, 3.0],
        [0.0, 1.0, 2.5, 3.5],
        [0.2, 0.8, 2.4, 3.4],
        ["A", "A", "B", "B"],
        min_observations=2,
    )
    assert groups["A"]["count"] == 2
    assert groups["A"]["candidate_mae"] == pytest.approx(0.0)
    assert groups["B"]["candidate_to_baseline"] == pytest.approx(1.25)

    stable = seed_stability(
        [0.0, 1.0],
        {17: [0.0, 1.0], 42: [0.1, 0.9], 73: [-0.1, 1.1]},
        baseline_prediction=[0.2, 0.8],
    )
    assert stable["stable"] is True
    assert stable["per_seed"][17]["mae"] == pytest.approx(0.0)


def test_regime_labels_use_only_origin_known_history_and_gate_at_100_rows():
    frame = pd.DataFrame(
        {
            "volatility_21": np.linspace(0.10, 0.40, 105),
            "benchmark_return_21": np.linspace(-0.05, 0.05, 105),
        }
    )
    before = origin_known_regimes(frame)
    changed = frame.copy()
    changed.loc[104, ["volatility_21", "benchmark_return_21"]] = [99.0, -99.0]
    after = origin_known_regimes(changed)

    assert before.iloc[:104].tolist() == after.iloc[:104].tolist()
    assert before.iloc[:100].isna().all()
    assert before.iloc[100:].notna().all()

    passing = _passing_gate_sample()
    ignored_small_regime = evaluate_probabilistic_gates(
        oos=passing,
        holdout=passing,
        folds=[{"candidate_mae": 0.9, "baseline_mae": 1.0}],
        regimes=[{"name": "stress", "count": 99, "candidate_mae": 2.0, "baseline_mae": 1.0}],
        seeds=[{"seed": 17, "candidate_mae": 0.9, "baseline_mae": 1.0}],
    )
    assert ignored_small_regime.passed is True
    assert ignored_small_regime.checks["snapshot_generation"] == "pending_task_5"

    failed_regime = evaluate_probabilistic_gates(
        oos=passing,
        holdout=passing,
        folds=[{"candidate_mae": 0.9, "baseline_mae": 1.0}],
        regimes=[{"name": "stress", "count": 100, "candidate_mae": 1.11, "baseline_mae": 1.0}],
        seeds=[{"seed": 17, "candidate_mae": 0.9, "baseline_mae": 1.0}],
    )
    assert failed_regime.passed is False
    assert "regime_stability" in failed_regime.reasons


def test_approved_gates_enforce_every_locked_threshold():
    passing = _passing_gate_sample()
    decision = evaluate_probabilistic_gates(
        oos=passing,
        holdout=passing,
        folds=[
            {"candidate_mae": 1.11, "baseline_mae": 1.0},
            {"candidate_mae": 0.90, "baseline_mae": 1.0},
            {"candidate_mae": 1.11, "baseline_mae": 1.0},
        ],
        regimes=[],
        seeds=[
            {"seed": 17, "candidate_mae": 0.90, "baseline_mae": 1.0},
            {"seed": 42, "candidate_mae": 0.95, "baseline_mae": 1.0},
            {"seed": 73, "candidate_mae": 0.92, "baseline_mae": 1.0},
        ],
    )
    assert decision.passed is True

    bad = _passing_gate_sample()
    bad["candidate"] = {
        "mae": 0.981,
        "balanced_accuracy": 0.519,
        "brier": 0.099,
        "pinball_mean": 0.099,
        "winkler": 0.99,
        "coverage": 0.86,
    }
    failed = evaluate_probabilistic_gates(
        oos=bad,
        holdout=bad,
        folds=[
            {"candidate_mae": 1.11, "baseline_mae": 1.0},
            {"candidate_mae": 1.11, "baseline_mae": 1.0},
        ],
        regimes=[],
        seeds=[{"seed": 17, "candidate_mae": 1.11, "baseline_mae": 1.0}],
    )

    assert set(failed.reasons) == {
        "oos_mae",
        "oos_balanced_accuracy",
        "oos_brier",
        "oos_pinball",
        "oos_winkler",
        "oos_coverage",
        "holdout_mae",
        "holdout_balanced_accuracy",
        "holdout_brier",
        "holdout_pinball",
        "holdout_winkler",
        "holdout_coverage",
        "fold_stability",
        "seed_stability",
    }
