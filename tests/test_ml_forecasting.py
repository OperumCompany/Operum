from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.ml.forecasting import BaselineForecaster, build_horizon_output
from app.ml.targets import add_forward_targets
from app.ml.training import compute_regression_metrics, select_best_baseline


def test_forward_targets_are_computed_inside_each_ticker():
    dates = pd.bdate_range("2024-01-02", periods=70)
    first = pd.DataFrame({"date": dates, "ticker": "AAA3", "close": np.arange(1, 71, dtype=float)})
    second = pd.DataFrame({"date": dates, "ticker": "BBB3", "close": np.arange(101, 171, dtype=float)})

    result = add_forward_targets(pd.concat([first, second], ignore_index=True), horizons=(21,))

    aaa = result[result["ticker"] == "AAA3"].reset_index(drop=True)
    bbb = result[result["ticker"] == "BBB3"].reset_index(drop=True)
    assert aaa.loc[0, "target_return_21"] == 22 / 1 - 1
    assert bbb.loc[0, "target_return_21"] == 122 / 101 - 1
    assert pd.isna(aaa.loc[69, "target_return_21"])
    assert pd.isna(bbb.loc[69, "target_return_21"])


def test_forward_targets_decompose_price_income_and_total_return_exactly():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "ticker": ["PETR4", "PETR4"],
            "split_adjusted_close": [100.0, 105.0],
            "total_return_index": [100.0, 107.1],
            "close": [100.0, 107.1],
        }
    )

    result = add_forward_targets(frame, horizons=(1,))

    assert result.loc[0, "target_price_return_1"] == pytest.approx(0.05)
    assert result.loc[0, "target_income_return_1"] == pytest.approx(0.02)
    assert result.loc[0, "target_total_return_1"] == pytest.approx(0.071)
    assert result.loc[0, "target_return_1"] == pytest.approx(0.071)
    assert (1 + result.loc[0, "target_total_return_1"]) == pytest.approx(
        (1 + result.loc[0, "target_price_return_1"])
        * (1 + result.loc[0, "target_income_return_1"])
    )


@pytest.mark.parametrize("bad_future_price", [0.0, -1.0, float("inf")])
def test_forward_targets_reject_invalid_price_return_denominator(bad_future_price):
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "ticker": ["PETR4", "PETR4"],
            "split_adjusted_close": [100.0, bad_future_price],
            "total_return_index": [100.0, 101.0],
            "close": [100.0, 101.0],
        }
    )

    with pytest.raises(ValueError, match="price return denominator"):
        add_forward_targets(frame, horizons=(1,))


def test_forward_targets_reject_non_finite_total_return_values():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02", "2024-01-03"]),
            "ticker": ["PETR4", "PETR4"],
            "split_adjusted_close": [100.0, 101.0],
            "total_return_index": [100.0, float("inf")],
            "close": [100.0, float("inf")],
        }
    )

    with pytest.raises(ValueError, match="non-finite total or income return"):
        add_forward_targets(frame, horizons=(1,))


def test_horizon_output_always_contains_range_and_three_scenarios():
    output = build_horizon_output(
        last_price=40.0,
        expected_return=0.02,
        interval_radius=0.12,
        confidence_score=0.30,
        horizon_days=42,
        source="baseline_zero",
    )

    assert output["confidence"] == {"score": 0.3, "label": "baixa"}
    assert output["direction"] == "alta"
    assert output["price_range"] == {"adverse": 36.0, "base": 40.8, "favorable": 45.6}
    assert set(output["scenarios"]) == {"adverse", "base", "favorable"}
    assert all(output["scenarios"][key] for key in output["scenarios"])


def test_baseline_forecaster_returns_all_public_horizons():
    close = pd.Series(np.linspace(30.0, 40.0, 100))

    result = BaselineForecaster().forecast("PETR4", close)

    assert result["generation_mode"] == "baseline"
    assert set(result["horizons"]) == {"1m", "2m", "3m"}
    assert all(item["confidence"]["label"] == "baixa" for item in result["horizons"].values())


def test_best_baseline_is_selected_by_mae():
    truth = np.array([0.02, -0.01, 0.03])
    predictions = {
        "zero": np.zeros(3),
        "drift": np.array([0.018, -0.012, 0.028]),
        "benchmark_beta": np.array([0.04, 0.01, 0.05]),
    }

    name, values, metrics = select_best_baseline(truth, predictions)

    assert name == "drift"
    np.testing.assert_allclose(values, predictions["drift"])
    assert metrics["mae"] < compute_regression_metrics(truth, predictions["zero"])["mae"]

