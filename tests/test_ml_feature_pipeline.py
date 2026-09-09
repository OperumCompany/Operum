from __future__ import annotations

import copy
import json

import numpy as np
import pandas as pd
import pytest

from app.ml.feature_pipeline import FoldFeaturePipeline
from app.ml.features import add_class_specific_features


def _row_frame(**overrides) -> pd.DataFrame:
    rows = 100
    frame = pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-02", periods=rows),
            "ticker": [f"STK{index:03d}" for index in range(rows)],
            "asset_class": "BR_STOCK",
            "sector": ["Banks"] * 50 + ["Energy"] * 50,
            "subsector": "Common",
            "asset_subtype": np.nan,
            "return_21": np.arange(rows, dtype=float),
        }
    )
    for column, values in overrides.items():
        frame[column] = values
    return frame


def _inject_forbidden_category_state(state: dict) -> None:
    vocabulary = state["category_vocabulary"]["sector"]
    vocabulary.append("ticker")
    unknown_index = state["feature_columns"].index("category__sector____unknown__")
    state["feature_columns"].insert(unknown_index, "category__sector__ticker")


def _inject_target_like_category_state(state: dict) -> None:
    vocabulary = state["category_vocabulary"]["sector"]
    vocabulary.append("ticker=ABEV3")
    unknown_index = state["feature_columns"].index("category__sector____unknown__")
    state["feature_columns"].insert(
        unknown_index, "category__sector__ticker%3DABEV3"
    )


def _inject_nested_numeric_state(state: dict) -> None:
    state["reference_numeric"]["return_21"]["target_return_21"] = 1.0


def _inject_nested_category_state(state: dict) -> None:
    state["reference_category"]["sector"]["ticker"] = 0.0


def _replace_feature_in_state(state: dict, old: str, new: str) -> None:
    state["numeric_features"] = [
        new if feature == old else feature for feature in state["numeric_features"]
    ]
    state["rank_features"] = [
        new if feature == old else feature for feature in state["rank_features"]
    ]
    for mapping_name in ("winsor_limits", "numeric_medians", "reference_numeric"):
        mapping = state[mapping_name]
        state[mapping_name] = {
            key.replace(old, new): value for key, value in mapping.items()
        }
    state["feature_columns"] = [
        column.replace(old, new) for column in state["feature_columns"]
    ]


def _inject_compact_target_state(state: dict) -> None:
    _replace_feature_in_state(state, "return_21", "returnTARGET21")


def _inject_compact_ticker_category_state(state: dict) -> None:
    vocabulary = state["category_vocabulary"]["sector"]
    vocabulary.append("TICKERValue=ABEV3")
    unknown_index = state["feature_columns"].index("category__sector____unknown__")
    state["feature_columns"].insert(
        unknown_index, "category__sector__TICKERValue%3DABEV3"
    )


def _inject_uppercase_compact_ticker_category_state(state: dict) -> None:
    vocabulary = state["category_vocabulary"]["sector"]
    vocabulary.append("TICKERVALUE=ABEV3")
    unknown_index = state["feature_columns"].index("category__sector____unknown__")
    state["feature_columns"].insert(
        unknown_index, "category__sector__TICKERVALUE%3DABEV3"
    )


def _inject_uppercase_compact_target_category_state(state: dict) -> None:
    vocabulary = state["category_vocabulary"]["sector"]
    vocabulary.append("RETURNTARGET21")
    unknown_index = state["feature_columns"].index("category__sector____unknown__")
    state["feature_columns"].insert(
        unknown_index, "category__sector__RETURNTARGET21"
    )


def test_fit_state_uses_train_only_limits_medians_and_category_vocabulary():
    train = _row_frame()
    validation = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "ticker": ["NEW1", "NEW2"],
            "asset_class": ["BR_STOCK", "BR_STOCK"],
            "sector": ["Future Sector", "Banks"],
            "subsector": ["Future Subsector", "Common"],
            "asset_subtype": ["Future Type", np.nan],
            "return_21": [1_000_000.0, np.nan],
        }
    )
    pipeline = FoldFeaturePipeline(
        numeric_features=("return_21",),
        rank_features=("return_21",),
    ).fit(train)
    fitted_state = copy.deepcopy(pipeline.to_state())

    transformed = pipeline.transform(validation)

    assert pipeline.to_state() == fitted_state
    assert fitted_state["winsor_limits"]["return_21"] == pytest.approx([0.99, 98.01])
    assert fitted_state["numeric_medians"]["return_21"] == pytest.approx(49.5)
    assert fitted_state["category_vocabulary"]["sector"] == ["Banks", "Energy"]
    assert transformed.loc[0, "return_21"] == pytest.approx(98.01)
    assert transformed.loc[1, "return_21"] == pytest.approx(49.5)
    assert transformed.loc[0, "category__sector____unknown__"] == 1.0
    assert "category__sector__Future%20Sector" not in transformed
    assert not any("ticker" in column.lower() for column in transformed.columns)
    json.dumps(fitted_state)


@pytest.mark.parametrize(
    ("arguments", "forbidden"),
    [
        ({"numeric_features": ("ticker",)}, "ticker"),
        ({"numeric_features": ("target_return_21",)}, "target_return_21"),
        ({"numeric_features": ("actual_return",)}, "actual_return"),
        ({"numeric_features": ("truth",)}, "truth"),
        ({"numeric_features": ("baseline_prediction",)}, "baseline_prediction"),
        ({"numeric_features": ("interval_low",)}, "interval_low"),
        ({"numeric_features": ("probability_up",)}, "probability_up"),
        ({"numeric_features": ("return_target_21",)}, "return_target_21"),
        ({"numeric_features": ("returnTarget21",)}, "returnTarget21"),
        ({"numeric_features": ("returnTARGET21",)}, "returnTARGET21"),
        ({"numeric_features": ("return_target21",)}, "return_target21"),
        ({"numeric_features": ("TICKERValue",)}, "TICKERValue"),
        ({"numeric_features": ("rank__return_interval_21",)}, "rank__return_interval_21"),
        ({"numeric_features": ("missing__forward_return_21",)}, "missing__forward_return_21"),
        ({"numeric_features": ("rank__target_return_21",)}, "rank__target_return_21"),
        ({"numeric_features": ("RANK__TARGET_RETURN_21",)}, "RANK__TARGET_RETURN_21"),
        (
            {
                "numeric_features": ("return_21",),
                "rank_features": ("sector_rank__actual_return",),
            },
            "sector_rank__actual_return",
        ),
        ({"categorical_features": ("sector", "ticker")}, "ticker"),
    ],
)
def test_constructor_rejects_identity_target_and_outcome_feature_injection(
    arguments, forbidden
):
    with pytest.raises(ValueError, match=forbidden):
        FoldFeaturePipeline(**arguments)


def test_constructor_semantically_rejects_uppercase_compact_outcome_marker():
    with pytest.raises(ValueError, match=r"Feature proibida .*RETURNTARGET21"):
        FoldFeaturePipeline(numeric_features=("RETURNTARGET21",))


@pytest.mark.parametrize(
    "tamper",
    [
        lambda state: state["numeric_features"].append("target_return_21"),
        lambda state: state["rank_features"].append("ticker"),
        lambda state: state["categorical_features"].append("actual_return"),
        lambda state: state["feature_columns"].append("missing__actual_return"),
        lambda state: state["reference_numeric"].update(
            {"rank__target_return_21": {"mean": 0.0, "std": 0.0, "missing_rate": 0.0}}
        ),
        _inject_forbidden_category_state,
        _inject_target_like_category_state,
        _inject_nested_numeric_state,
        _inject_nested_category_state,
        _inject_compact_target_state,
        _inject_compact_ticker_category_state,
        _inject_uppercase_compact_ticker_category_state,
        _inject_uppercase_compact_target_category_state,
        lambda state: state.update({"unknown_state": {"ticker": "ABEV3"}}),
        lambda state: state.update({"unknown_state": {"note": "safe"}}),
        lambda state: state["reference_numeric"].update(
            {"rogue_metric": {"mean": 0.0, "std": 0.0, "missing_rate": 0.0}}
        ),
        lambda state: state["reference_numeric"]["return_21"].update(
            {"note": 0.0}
        ),
        lambda state: state["reference_category"]["sector"].update(
            {"note": 0.0}
        ),
        lambda state: state["reference_numeric"]["return_21"].update(
            {"mean": np.inf}
        ),
    ],
)
def test_restoration_rejects_tampered_identity_target_or_outcome_state(tamper):
    fitted = FoldFeaturePipeline(
        numeric_features=("return_21",), rank_features=("return_21",)
    ).fit(_row_frame())
    state = fitted.to_state()
    tamper(state)

    with pytest.raises(ValueError, match="proibida|inconsistente"):
        FoldFeaturePipeline.from_state(state)


@pytest.mark.parametrize(
    "raw_feature",
    [
        "unregistered_signal",
        "missing__return_21",
        "rank__return_21",
        "category__sector__Banks",
    ],
)
def test_constructor_rejects_unregistered_or_generated_raw_numeric_features(
    raw_feature,
):
    with pytest.raises(ValueError, match=raw_feature):
        FoldFeaturePipeline(numeric_features=(raw_feature,))


@pytest.mark.parametrize(
    "legitimate_feature",
    ["return_21", "beta_63", "book_to_market", "ipca_12m"],
)
def test_explicit_numeric_allowlist_retains_representative_legitimate_features(
    legitimate_feature,
):
    pipeline = FoldFeaturePipeline(
        numeric_features=(legitimate_feature,), rank_features=()
    )
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-02"]),
            "ticker": ["SAFE3"],
            "asset_class": ["BR_STOCK"],
            legitimate_feature: [1.0],
        }
    )

    result = pipeline.fit_transform(frame)

    assert legitimate_feature in result


@pytest.mark.parametrize(
    "unsafe_sector",
    [
        "ticker=ABEV3",
        "target_return_21",
        "TICKERValue=ABEV3",
        "TICKERVALUE=ABEV3",
        "SYMBOLVALUE=ABEV3",
        "ASSETID123",
        "RETURNTARGET21",
        "CLASSLABELVALUE",
        "GROUNDTRUTHVALUE",
        "ACTUALRETURN21",
        "REALIZEDRETURN21",
        "FUTURERETURN21",
        "FORWARDRETURN21",
        "PREDICTEDRETURN21",
        "PREDICTIONVALUE",
        "OUTCOMEVALUE",
        "PROBABILITYUP",
        "INTERVALLOW",
        "ＴＩＣＫＥＲＶＡＬＵＥ=ABEV3",
    ],
)
def test_category_vocabulary_cannot_generate_identity_or_outcome_output_names(
    unsafe_sector,
):
    frame = _row_frame(sector=[unsafe_sector] * 100)

    with pytest.raises(ValueError, match="proibida"):
        FoldFeaturePipeline(
            numeric_features=("return_21",), rank_features=("return_21",)
        ).fit(frame)


def test_safe_uppercase_real_category_vocabulary_round_trips_and_transforms():
    frame = _row_frame(
        sector=["ENERGIA ELETRICA"] * 100,
        asset_subtype=["LOGISTICA"] * 100,
    )
    fitted = FoldFeaturePipeline(
        numeric_features=("return_21",), rank_features=("return_21",)
    ).fit(frame)

    restored = FoldFeaturePipeline.from_state(
        json.loads(json.dumps(fitted.to_state()))
    )
    transformed = restored.transform(frame)

    assert transformed["category__sector__ENERGIA%20ELETRICA"].eq(1.0).all()
    assert transformed["category__asset_subtype__LOGISTICA"].eq(1.0).all()
    pd.testing.assert_frame_equal(transformed, fitted.transform(frame))


def test_safe_pipeline_cannot_emit_identity_or_outcome_columns_in_outputs_or_metadata():
    frame = _row_frame()
    frame["target_return_21"] = 9.0
    frame["actual_return"] = 8.0
    pipeline = FoldFeaturePipeline(
        numeric_features=("return_21",), rank_features=("return_21",)
    ).fit(frame)

    transformed = pipeline.transform(frame)
    serialized = json.dumps(
        {
            "state": pipeline.to_state(),
            "metadata": pipeline.feature_group_metadata(),
            "drift": pipeline.drift_summary(frame),
        }
    ).lower()

    assert not any(
        forbidden in column.lower()
        for column in transformed.columns
        for forbidden in ("ticker", "target_", "actual_return")
    )
    assert "ticker" not in serialized
    assert "target_" not in serialized
    assert "actual_return" not in serialized


def test_future_rows_and_validation_extremes_cannot_change_transformed_earlier_rows():
    train = _row_frame()
    pipeline = FoldFeaturePipeline(
        numeric_features=("return_21",),
        rank_features=("return_21",),
    ).fit(train)
    earlier = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-02"] * 3),
            "ticker": ["A", "B", "C"],
            "asset_class": "BR_STOCK",
            "sector": ["Banks", "Banks", "Energy"],
            "return_21": [10.0, 20.0, 30.0],
            "research_eligible": True,
        }
    )
    future = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-03"] * 2),
            "ticker": ["FUTURE1", "FUTURE2"],
            "asset_class": "BR_STOCK",
            "sector": ["Future Sector", "Banks"],
            "return_21": [-1e12, 1e12],
            "research_eligible": True,
        }
    )

    expected = pipeline.transform(earlier)
    actual = pipeline.transform(pd.concat([earlier, future], ignore_index=True)).iloc[:3]

    pd.testing.assert_frame_equal(actual.reset_index(drop=True), expected.reset_index(drop=True))


def test_cross_sectional_ranks_are_per_date_bounded_and_deterministic():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2025-01-02"] * 3 + ["2025-01-03"] * 2 + ["2025-01-06"]
            ),
            "ticker": ["A", "B", "C", "D", "E", "F"],
            "asset_class": "BR_STOCK",
            "return_21": [10.0, 20.0, 30.0, 5.0, 5.0, 100.0],
            "research_eligible": [True, True, True, True, True, True],
        }
    )
    pipeline = FoldFeaturePipeline(
        numeric_features=("return_21",),
        rank_features=("return_21",),
    ).fit(frame)

    result = pipeline.transform(frame)

    assert result["rank__return_21"].tolist() == [-1.0, 0.0, 1.0, 0.0, 0.0, 0.0]
    assert result["rank__return_21"].between(-1.0, 1.0).all()


def test_ineligible_assets_do_not_enter_cross_section_and_keep_explicit_missingness():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-02"] * 3),
            "ticker": ["A", "B", "OUT"],
            "asset_class": "BR_STOCK",
            "return_21": [10.0, 20.0, 1e9],
            "research_eligible": [True, True, False],
        }
    )
    pipeline = FoldFeaturePipeline(
        numeric_features=("return_21",),
        rank_features=("return_21",),
    ).fit(frame)

    result = pipeline.transform(frame)

    assert result.loc[:1, "rank__return_21"].tolist() == [-1.0, 1.0]
    assert result.loc[2, "missing__rank__return_21"] == 1.0


def test_state_round_trip_preserves_transform_exactly():
    train = _row_frame()
    fitted = FoldFeaturePipeline(
        numeric_features=("return_21",),
        rank_features=("return_21",),
    ).fit(train)
    restored = FoldFeaturePipeline.from_state(json.loads(json.dumps(fitted.to_state())))

    pd.testing.assert_frame_equal(restored.transform(train), fitted.transform(train))
    assert restored.to_state() == fitted.to_state()


def test_explicit_null_serialized_statistics_round_trip_and_report_unknown_drift():
    train = _row_frame()
    fitted = FoldFeaturePipeline(
        numeric_features=("return_21",), rank_features=("return_21",)
    ).fit(train)
    state = fitted.to_state()
    state["winsor_limits"]["return_21"] = [None, None]
    state["numeric_medians"]["return_21"] = None
    state["reference_numeric"]["return_21"] = {
        "mean": None,
        "std": None,
        "missing_rate": None,
    }
    state["reference_category"]["sector"] = {"missing_rate": None}

    restored = FoldFeaturePipeline.from_state(state)
    drift = restored.drift_summary(train)

    assert restored.to_state() == state
    assert drift["numeric"]["return_21"]["reference_mean"] is None
    assert drift["numeric"]["return_21"]["standardized_mean_shift"] is None


def test_transform_keeps_fitted_schema_when_optional_sector_column_is_absent():
    train = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-02", "2025-01-02"]),
            "ticker": ["A", "B"],
            "asset_class": "BR_STOCK",
            "sector": ["Banks", "Banks"],
            "return_21": [0.01, 0.02],
        }
    )
    pipeline = FoldFeaturePipeline(
        numeric_features=("return_21",), rank_features=("return_21",)
    ).fit(train)
    without_optional_sector = train.drop(columns="sector")

    result = pipeline.transform(without_optional_sector)

    assert tuple(result.columns) == pipeline.feature_columns_
    assert result["sector_rank__return_21"].tolist() == [-1.0, 1.0]
    assert result["category__sector____unknown__"].eq(1.0).all()


def test_default_pipeline_has_explicit_indicators_for_absent_authentic_fii_fields():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-02"]),
            "ticker": ["HGLG11"],
            "asset_class": ["FII"],
            "return_21": [0.02],
            "asset_subtype": ["Logistics"],
        }
    )
    pipeline = FoldFeaturePipeline().fit(frame)

    result = pipeline.transform(frame)

    assert result.loc[0, "missing__dividend_yield"] == 1.0
    assert result.loc[0, "missing__vacancy_rate"] == 1.0
    assert result.loc[0, "category__asset_subtype__Logistics"] == 1.0
    assert not any(column.startswith("target_") for column in result)
    assert not any("ticker" in column.lower() for column in result)


def test_class_specific_features_use_only_authentic_inputs_already_on_each_row():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-02", "2025-01-02"]),
            "ticker": ["HGLG11", "PETR4"],
            "asset_class": ["FII", "BR_STOCK"],
            "return_21": [0.03, 0.08],
            "ifix_return_21": [0.01, np.nan],
            "dividend_yield": [0.12, 0.08],
            "cdi_rate": [0.105, 0.105],
            "ipca_12m": [0.045, 0.045],
            "net_income": [np.nan, 20.0],
            "net_equity": [np.nan, 100.0],
            "market_cap": [np.nan, 200.0],
            "net_debt": [np.nan, 30.0],
            "ebitda": [np.nan, 10.0],
            "revenue": [np.nan, 80.0],
            "gross_profit": [np.nan, 40.0],
            "operating_income": [np.nan, 24.0],
        }
    )

    result = add_class_specific_features(frame)

    assert result.loc[0, "relative_return_ifix_21"] == pytest.approx(0.02)
    assert result.loc[0, "real_rate"] == pytest.approx(0.06)
    assert result.loc[0, "dividend_yield_spread_cdi"] == pytest.approx(0.015)
    assert pd.isna(result.loc[1, "relative_return_ifix_21"])
    assert result.loc[1, "earnings_yield"] == pytest.approx(0.10)
    assert result.loc[1, "book_to_market"] == pytest.approx(0.50)
    assert result.loc[1, "roe"] == pytest.approx(0.20)
    assert result.loc[1, "gross_margin"] == pytest.approx(0.50)
    assert result.loc[1, "operating_margin"] == pytest.approx(0.30)
    assert result.loc[1, "net_margin"] == pytest.approx(0.25)
    assert result.loc[1, "net_debt_to_ebitda"] == pytest.approx(3.0)


def test_equity_sector_ranks_compare_only_same_date_same_sector():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-02"] * 4),
            "ticker": ["B1", "B2", "E1", "E2"],
            "asset_class": "BR_STOCK",
            "sector": ["Banks", "Banks", "Energy", "Energy"],
            "return_21": [1.0, 2.0, 100.0, 200.0],
            "research_eligible": True,
        }
    )
    pipeline = FoldFeaturePipeline(
        numeric_features=("return_21",), rank_features=("return_21",)
    ).fit(frame)

    result = pipeline.transform(frame)

    assert result["sector_rank__return_21"].tolist() == [-1.0, 1.0, -1.0, 1.0]


def test_fii_row_neither_receives_nor_mutates_equity_sector_rank():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-02"] * 3),
            "ticker": ["EQ1", "EQ2", "FII1"],
            "asset_class": ["BR_STOCK", "BR_STOCK", "FII"],
            "sector": ["Real Estate", "Real Estate", "Real Estate"],
            "return_21": [0.01, 0.02, 10_000.0],
            "research_eligible": True,
        }
    )
    pipeline = FoldFeaturePipeline(
        numeric_features=("return_21",), rank_features=("return_21",)
    ).fit(frame)
    original = pipeline.transform(frame)
    changed = frame.copy()
    changed.loc[2, "return_21"] = -10_000.0
    mutated = pipeline.transform(changed)

    assert original.loc[:1, "sector_rank__return_21"].tolist() == [-1.0, 1.0]
    assert original.loc[2, "missing__sector_rank__return_21"] == 1.0
    assert original.loc[2, "sector_rank__return_21"] == 0.0
    pd.testing.assert_series_equal(
        mutated.loc[:1, "sector_rank__return_21"],
        original.loc[:1, "sector_rank__return_21"],
    )


def test_fii_rate_aliases_are_used_without_fabricating_absent_rates():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "ticker": ["FII1", "FII2"],
            "asset_class": ["FII", "FII"],
            "dividend_yield": [0.11, 0.12],
            "cdi": [0.10, np.nan],
            "ipca": [0.04, 0.05],
        }
    )

    result = add_class_specific_features(frame)

    assert result.loc[0, "real_rate"] == pytest.approx(0.06)
    assert result.loc[0, "dividend_yield_spread_cdi"] == pytest.approx(0.01)
    assert pd.isna(result.loc[1, "real_rate"])
    assert pd.isna(result.loc[1, "dividend_yield_spread_cdi"])


def test_fii_rate_aliases_resolve_per_row_with_primary_precedence_and_no_fill():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(
                ["2025-01-02", "2025-01-03", "2025-01-06", "2025-01-07"]
            ),
            "ticker": ["FII1"] * 4,
            "asset_class": ["FII"] * 4,
            "dividend_yield": [0.15, 0.15, 0.15, 0.15],
            "cdi_rate": [0.11, np.nan, 0.13, np.nan],
            "cdi": [0.90, 0.12, 0.90, np.nan],
            "ipca_12m": [0.04, np.nan, 0.06, np.nan],
            "ipca": [0.90, 0.05, 0.90, 0.07],
        }
    )

    result = add_class_specific_features(frame)

    assert result["real_rate"].iloc[:3].tolist() == pytest.approx([0.07, 0.07, 0.07])
    assert result["dividend_yield_spread_cdi"].iloc[:3].tolist() == pytest.approx(
        [0.04, 0.03, 0.02]
    )
    assert pd.isna(result.loc[3, "real_rate"])
    assert pd.isna(result.loc[3, "dividend_yield_spread_cdi"])


def test_future_authentic_values_cannot_change_earlier_class_specific_features():
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "ticker": ["HGLG11", "HGLG11"],
            "asset_class": ["FII", "FII"],
            "return_21": [0.03, 0.04],
            "ifix_return_21": [0.01, 0.02],
            "dividend_yield": [0.12, 0.13],
            "cdi_rate": [0.105, 0.105],
            "ipca_12m": [0.045, 0.045],
        }
    )
    original = add_class_specific_features(frame)
    changed = frame.copy()
    changed.loc[1, ["ifix_return_21", "dividend_yield", "cdi_rate", "ipca_12m"]] = 99.0
    recomputed = add_class_specific_features(changed)

    pd.testing.assert_series_equal(recomputed.iloc[0], original.iloc[0])


def test_feature_group_metadata_and_drift_are_versioned_and_target_free():
    train = _row_frame()
    train["target_return_21"] = 123.0
    pipeline = FoldFeaturePipeline(
        numeric_features=("return_21",),
        rank_features=("return_21",),
    ).fit(train)

    metadata = pipeline.feature_group_metadata()
    drift = pipeline.drift_summary(train.assign(return_21=train["return_21"] + 10))

    assert metadata["schema_version"] == "operum-feature-groups-v1"
    assert metadata["pipeline_schema_version"] == "operum-fold-feature-pipeline-v1"
    assert metadata["numeric_feature_schema_version"] == "operum-numeric-features-v1"
    assert metadata["groups"]["price_momentum"] == ["return_21", "missing__return_21"]
    assert metadata["groups"]["cross_sectional_ranks"] == [
        "rank__return_21",
        "missing__rank__return_21",
    ]
    assert metadata["ablations"]["without_price_momentum"]["excluded_features"] == [
        "return_21",
        "missing__return_21",
    ]
    assert drift["schema_version"] == "operum-feature-drift-v1"
    assert drift["numeric"]["return_21"]["current_mean"] > drift["numeric"]["return_21"][
        "reference_mean"
    ]
    assert "target" not in json.dumps(metadata).lower()
    assert "target" not in json.dumps(drift).lower()
