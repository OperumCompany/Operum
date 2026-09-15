from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.ml.dataset import build_dynamic_research_universe, select_liquid_cohort
from app.ml.features import build_point_in_time_features
from app.ml.intervals import ConformalInterval
from app.ml.macro import merge_released_macro
from app.ml.validation import evaluate_promotion_gate, expanding_walk_forward_splits


def _market_frame(periods: int = 1_600, ticker: str = "PETR4") -> pd.DataFrame:
    dates = pd.bdate_range("2019-01-02", periods=periods)
    close = 20 + np.arange(periods, dtype=float) * 0.02
    return pd.DataFrame(
        {
            "date": dates,
            "ticker": ticker,
            "asset_class": "BR_STOCK",
            "open": close - 0.1,
            "high": close + 0.3,
            "low": close - 0.3,
            "close": close,
            "volume": np.full(periods, 1_000_000.0),
        }
    )


def test_features_at_date_do_not_change_when_future_rows_change():
    frame = _market_frame(180)
    cutoff = frame.loc[120, "date"]

    original = build_point_in_time_features(frame)
    changed = frame.copy()
    changed.loc[changed["date"] > cutoff, ["close", "high", "low", "volume"]] *= 100
    recomputed = build_point_in_time_features(changed)

    expected = original.loc[original["date"] == cutoff].reset_index(drop=True)
    actual = recomputed.loc[recomputed["date"] == cutoff].reset_index(drop=True)
    pd.testing.assert_frame_equal(actual, expected)


def test_external_context_future_release_cannot_change_prior_feature_row():
    market = _market_frame(180)
    dates = market["date"]
    context = pd.DataFrame(
        {
            "reference_date": dates,
            "available_at": dates.dt.normalize() + pd.Timedelta(hours=23, minutes=59),
            "ibov_close": 100_000 + np.arange(len(dates)) * 10,
            "usdbrl_close": 5 + np.arange(len(dates)) * 0.001,
            "brent_close": 70 + np.arange(len(dates)) * 0.01,
        }
    )
    cutoff = dates.iloc[120]
    context.loc[120, "available_at"] = dates.iloc[121] + pd.Timedelta(hours=9)

    original = build_point_in_time_features(market, context=context)
    changed = context.copy()
    changed.loc[120, ["ibov_close", "usdbrl_close", "brent_close"]] *= 100
    recomputed = build_point_in_time_features(market, context=changed)

    columns = ["benchmark_return_21", "usdbrl_return_21", "brent_return_21", "beta_63", "correlation_63"]
    expected = original.loc[original["date"] == cutoff, columns].reset_index(drop=True)
    actual = recomputed.loc[recomputed["date"] == cutoff, columns].reset_index(drop=True)
    pd.testing.assert_frame_equal(actual, expected)
    next_expected = original.loc[original["date"] == dates.iloc[121], "benchmark_return_1"].item()
    next_actual = recomputed.loc[recomputed["date"] == dates.iloc[121], "benchmark_return_1"].item()
    assert next_actual != next_expected


def test_external_context_rejects_date_only_records():
    market = _market_frame(3)
    context = pd.DataFrame(
        {
            "date": market["date"],
            "ibov_close": [100_000, 100_100, 100_200],
            "usdbrl_close": [5.0, 5.1, 5.2],
            "brent_close": [70.0, 71.0, 72.0],
        }
    )

    with pytest.raises(ValueError, match="available_at"):
        build_point_in_time_features(market, context=context)


def test_macro_value_only_appears_after_real_release_timestamp():
    features = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-09", "2024-01-10", "2024-01-11"]),
            "ticker": ["PETR4"] * 3,
        }
    )
    releases = pd.DataFrame(
        {
            "reference_date": pd.to_datetime(["2023-12-01"]),
            "available_at": pd.to_datetime(["2024-01-10T09:00:00"]),
            "selic": [11.75],
            "ipca_12m": [4.62],
        }
    )

    result = merge_released_macro(features, releases)

    assert pd.isna(result.loc[0, "selic"])
    assert result.loc[1, "selic"] == 11.75
    assert result.loc[2, "ipca_12m"] == 4.62


def test_auxiliary_records_require_reference_and_availability_dates():
    features = pd.DataFrame(
        {"date": pd.to_datetime(["2024-01-10"]), "ticker": ["PETR4"]}
    )
    releases = pd.DataFrame(
        {"available_at": pd.to_datetime(["2024-01-10"]), "selic": [11.75]}
    )

    with pytest.raises(ValueError, match="reference_date"):
        merge_released_macro(features, releases)


def test_auxiliary_revision_is_joined_only_after_it_becomes_available():
    features = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-10", "2024-01-11", "2024-02-01"]),
            "ticker": ["PETR4"] * 3,
        }
    )
    releases = pd.DataFrame(
        {
            "reference_date": pd.to_datetime(["2023-12-01", "2023-12-01"]),
            "available_at": pd.to_datetime(["2024-01-10T09:00:00", "2024-01-31T09:00:00"]),
            "ipca_12m": [4.62, 4.51],
        }
    )

    result = merge_released_macro(features, releases)

    assert result["ipca_12m"].tolist() == [4.62, 4.62, 4.51]
    assert result["reference_date"].tolist() == [
        pd.Timestamp("2023-12-01"),
        pd.Timestamp("2023-12-01"),
        pd.Timestamp("2023-12-01"),
    ]


def test_sparse_macro_streams_combine_simultaneous_and_interleaved_releases():
    features = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-10", "2024-01-21", "2024-01-26"]),
            "ticker": ["PETR4"] * 3,
        }
    )
    releases = pd.DataFrame(
        {
            "reference_date": pd.to_datetime(
                ["2024-01-01", "2023-12-01", "2024-01-01", "2024-01-01"]
            ),
            "available_at": pd.to_datetime(
                [
                    "2024-01-10T09:00:00",
                    "2024-01-10T09:00:00",
                    "2024-01-20T09:00:00",
                    "2024-01-25T09:00:00",
                ]
            ),
            "selic": [11.75, np.nan, np.nan, 11.25],
            "ipca_12m": [np.nan, 4.62, 4.51, np.nan],
        }
    )

    result = merge_released_macro(features, releases)

    assert result["selic"].tolist() == [11.75, 11.75, 11.25]
    assert result["ipca_12m"].tolist() == [4.62, 4.51, 4.51]
    assert result["selic_reference_date"].tolist() == [
        pd.Timestamp("2024-01-01")
    ] * 3
    assert result["ipca_12m_reference_date"].tolist() == [
        pd.Timestamp("2023-12-01"),
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-01-01"),
    ]


def test_future_sparse_macro_release_cannot_change_prior_features():
    features = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-10", "2024-01-20"]),
            "ticker": ["PETR4", "PETR4"],
        }
    )
    releases = pd.DataFrame(
        {
            "reference_date": pd.to_datetime(["2024-01-01", "2024-01-01"]),
            "available_at": pd.to_datetime(
                ["2024-01-10T09:00:00", "2024-01-20T09:00:00"]
            ),
            "selic": [11.75, np.nan],
            "ipca_12m": [np.nan, 4.51],
        }
    )
    original = merge_released_macro(features, releases)
    changed = releases.copy()
    changed.loc[1, "ipca_12m"] = 99.0
    recomputed = merge_released_macro(features, changed)

    prior = features.loc[0, "date"]
    pd.testing.assert_frame_equal(
        original.loc[original["date"] == prior].reset_index(drop=True),
        recomputed.loc[recomputed["date"] == prior].reset_index(drop=True),
    )


def test_dynamic_research_eligibility_uses_only_trailing_252_class_sessions():
    dates = pd.bdate_range("2023-01-02", periods=253)
    rows = []
    for ticker, asset_class, liquidity in (
        ("STK1", "BR_STOCK", 1_000_000.0),
        ("FII1", "FII", 500_000.0),
    ):
        rows.append(
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": ticker,
                    "asset_class": asset_class,
                    "close": 10.0,
                    "volume": liquidity,
                }
            )
        )
    market = pd.concat(rows, ignore_index=True)

    eligibility, gate = build_dynamic_research_universe(
        market, minimum_assets={"BR_STOCK": 1, "FII": 1}
    )

    first = eligibility[eligibility["date"] == dates[0]]
    eligible_date = eligibility[eligibility["date"] == dates[252]]
    assert not first["eligible"].any()
    assert eligible_date["eligible"].all()
    assert eligible_date["observed_sessions"].tolist() == [252, 252]
    assert eligible_date["coverage"].tolist() == [1.0, 1.0]
    assert gate.loc[gate["date"] == dates[252], "promotion_blocked"].item() == False


def test_dynamic_eligibility_does_not_change_when_future_liquidity_changes():
    dates = pd.bdate_range("2023-01-02", periods=260)
    market = pd.DataFrame(
        {
            "date": dates,
            "ticker": "STK1",
            "asset_class": "BR_STOCK",
            "close": 10.0,
            "volume": 1_000.0,
        }
    )
    cutoff = dates[252]
    original, _ = build_dynamic_research_universe(
        market, minimum_assets={"BR_STOCK": 1, "FII": 0}
    )
    changed = market.copy()
    changed.loc[changed["date"] > cutoff, "volume"] = 1_000_000_000.0
    recomputed, _ = build_dynamic_research_universe(
        changed, minimum_assets={"BR_STOCK": 1, "FII": 0}
    )

    expected = original.loc[original["date"] == cutoff].reset_index(drop=True)
    actual = recomputed.loc[recomputed["date"] == cutoff].reset_index(drop=True)
    pd.testing.assert_frame_equal(actual, expected)


def test_dynamic_eligibility_and_rank_ignore_current_session_data():
    dates = pd.bdate_range("2023-01-02", periods=253)
    market = pd.concat(
        [
            pd.DataFrame(
                {
                    "date": dates,
                    "ticker": ticker,
                    "asset_class": "BR_STOCK",
                    "close": 10.0,
                    "volume": volume,
                }
            )
            for ticker, volume in (
                ("STK1", np.arange(1.0, 254.0)),
                ("STK2", np.full(253, 127.25)),
            )
        ],
        ignore_index=True,
    )
    cutoff = dates[-1]
    original, _ = build_dynamic_research_universe(
        market, minimum_assets={"BR_STOCK": 1, "FII": 0}
    )
    changed = market.copy()
    changed.loc[
        (changed["ticker"] == "STK1") & (changed["date"] == cutoff),
        ["close", "volume"],
    ] = [0.0, 0.0]
    recomputed, _ = build_dynamic_research_universe(
        changed, minimum_assets={"BR_STOCK": 1, "FII": 0}
    )

    expected = original.loc[original["date"] == cutoff].reset_index(drop=True)
    actual = recomputed.loc[recomputed["date"] == cutoff].reset_index(drop=True)
    pd.testing.assert_frame_equal(actual, expected)


def test_dynamic_eligibility_rejects_sub_98_percent_window_coverage():
    dates = pd.bdate_range("2023-01-02", periods=253)
    market = pd.DataFrame(
        {
            "date": dates.delete([3, 17, 40, 90, 120, 180]),
            "ticker": "STK1",
            "asset_class": "BR_STOCK",
            "close": 10.0,
            "volume": 1_000.0,
        }
    )
    calendar_anchor = pd.DataFrame(
        {
            "date": dates,
            "ticker": "STK2",
            "asset_class": "BR_STOCK",
            "close": 10.0,
            "volume": 1_000.0,
        }
    )

    eligibility, _ = build_dynamic_research_universe(
        pd.concat([market, calendar_anchor], ignore_index=True),
        minimum_assets={"BR_STOCK": 1, "FII": 0},
    )

    affected = eligibility.loc[
        (eligibility["ticker"] == "STK1") & (eligibility["date"] == dates[-1])
    ].iloc[0]
    assert affected["coverage"] == pytest.approx(246 / 252)
    assert affected["eligible"] == False
    assert "insufficient_coverage" in affected["reasons"]


def test_cohort_selects_24_stocks_and_6_fiis_by_liquidity():
    rows = []
    for asset_class, count in (("BR_STOCK", 30), ("FII", 10)):
        for index in range(count):
            ticker = f"{'STK' if asset_class == 'BR_STOCK' else 'FII'}{index:02d}"
            frame = _market_frame(ticker=ticker)
            frame["asset_class"] = asset_class
            frame["volume"] = (index + 1) * 10_000
            rows.append(frame)

    selected, excluded = select_liquid_cohort(pd.concat(rows, ignore_index=True))

    assert len(selected) == 30
    assert sum(item.asset_class == "BR_STOCK" for item in selected) == 24
    assert sum(item.asset_class == "FII" for item in selected) == 6
    assert {item.ticker for item in selected if item.asset_class == "BR_STOCK"} == {
        f"STK{index:02d}" for index in range(6, 30)
    }
    assert excluded


def test_walk_forward_splits_embargo_labels_from_validation_window():
    dates = pd.bdate_range("2019-01-02", periods=1_600)

    splits = expanding_walk_forward_splits(
        dates,
        min_train_days=504,
        validation_days=63,
        embargo_days=63,
        holdout_days=252,
        step_days=63,
    )

    assert splits
    for split in splits:
        assert split.train_end < split.validation_start
        assert dates[split.validation_start] - dates[split.train_end] >= pd.Timedelta(days=63)
        assert split.validation_end < len(dates) - 252


def test_conformal_interval_has_expected_empirical_coverage():
    residuals = np.arange(1, 101, dtype=float) / 100
    interval = ConformalInterval.fit(residuals, coverage=0.80)

    low, high = interval.bounds(np.array([0.0, 1.0]))

    assert interval.radius == 0.81
    np.testing.assert_allclose(low, [-0.81, 0.19])
    np.testing.assert_allclose(high, [0.81, 1.81])


def test_promotion_gate_rejects_overfit_candidate():
    decision = evaluate_promotion_gate(
        candidate={
            "mae": 0.12,
            "directional_accuracy": 0.49,
            "interval_coverage": 0.90,
            "fold_mae": [0.08, 0.13, 0.14],
            "holdout_mae": 0.13,
            "holdout_interval_coverage": 0.90,
        },
        baseline={
            "mae": 0.10,
            "directional_accuracy": 0.51,
            "holdout_mae": 0.10,
        },
    )

    assert decision.promoted is False
    assert "mae" in decision.reasons
    assert "directional_accuracy" in decision.reasons
    assert "interval_coverage" in decision.reasons
