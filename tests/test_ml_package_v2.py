from __future__ import annotations

import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from app.ml.feature_pipeline import FoldFeaturePipeline
from app.ml.package_v2 import (
    DIRECTION_COMPONENTS,
    HEAD_COMPONENTS,
    PACKAGE_SCHEMA_VERSION,
    DirectionHead,
    FrozenCausalBaseline,
    PackageValidationError,
    ProbabilisticSlotPackage,
    ReturnHead,
    ValidatedModelConfig,
    load_slot_package,
    save_slot_package,
)
from app.ml.probabilistic import (
    AdaptiveConformalCalibrator,
    OOSBlend,
    TemporalPlattCalibrator,
)


class _LinearRegressor:
    def __init__(self, scale: float, offset: float = 0.0):
        self.scale = scale
        self.offset = offset

    def predict(self, matrix):
        values = np.asarray(matrix, dtype=float)
        return values[:, 1] * self.scale + self.offset


class _ConfiguredRegressor(_LinearRegressor):
    def __init__(self, scale: float, *, objective: str, n_estimators: int):
        super().__init__(scale)
        self.objective = objective
        self.n_estimators = n_estimators

    def get_params(self, deep=True):
        return {
            "objective": self.objective,
            "n_estimators": self.n_estimators,
        }


class _ConfiguredEnsemble:
    def __init__(self, model, seed):
        self.models = (model,)
        self.seeds = (seed,)

    def predict(self, matrix):
        return self.models[0].predict(matrix)


class _FixedProbabilityClassifier:
    def predict_proba(self, matrix):
        values = np.asarray(matrix, dtype=float)
        probability = np.clip(0.55 + values[:, 1] * 0.25, 0.01, 0.99)
        return np.column_stack([1.0 - probability, probability])


def _config(model_type: str, objective: str, *, alpha: float | None = None):
    parameters = {"max_depth": 2, "seed": 17}
    if alpha is not None:
        parameters["quantile_alpha"] = alpha
    return ValidatedModelConfig.create(
        model_type=model_type,
        objective=objective,
        n_estimators=7,
        parameters=parameters,
        history_policy="uniform_expanding",
        validation_ids=("inner-0", "inner-1"),
    )


def _pipeline() -> FoldFeaturePipeline:
    train = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=4),
            "asset_class": ["BR_STOCK"] * 4,
            "return_1": [-0.2, -0.1, 0.1, 0.2],
        }
    )
    return FoldFeaturePipeline(
        numeric_features=("return_1",),
        rank_features=(),
        categorical_features=(),
    ).fit(train)


def _blend(prefix: str) -> OOSBlend:
    truth = np.array([0.0, 0.1, 0.2])
    return OOSBlend.fit(
        truth,
        {
            "baseline": np.zeros(3),
            "xgboost": truth,
            "elastic_net": np.full(3, 0.5),
        },
        baseline_name="baseline",
        calibration_ids=tuple(f"{prefix}-c{index}" for index in range(3)),
        model_fit_ids=tuple(f"{prefix}-t{index}" for index in range(3)),
    )


def _return_head(prefix: str, *, price: bool = False) -> ReturnHead:
    scale = 0.2 if price else 0.4
    return ReturnHead(
        xgboost_center=_LinearRegressor(scale),
        elastic_net=_LinearRegressor(0.0),
        baseline=FrozenCausalBaseline(name="zero", horizon_days=21),
        blend=_blend(prefix),
        quantile_models={
            "q10": _LinearRegressor(scale, 0.05),
            "q50": _LinearRegressor(scale, 0.00),
            "q90": _LinearRegressor(scale, -0.05),
        },
        conformal=AdaptiveConformalCalibrator(
            coverage=0.80,
            max_scores=126,
            initial_scores=(0.01, 0.02),
            observed_row_ids=(f"{prefix}-o0", f"{prefix}-o1"),
        ),
        center_config=_config("center", "reg:absoluteerror"),
        quantile_configs={
            "q10": _config("quantile", "reg:quantileerror", alpha=0.10),
            "q50": _config("quantile", "reg:quantileerror", alpha=0.50),
            "q90": _config("quantile", "reg:quantileerror", alpha=0.90),
        },
    )


def _package(
    *, invalid_price: bool = False, invalid_total: bool = False
) -> ProbabilisticSlotPackage:
    price = _return_head("price", price=True)
    if invalid_price:
        price.xgboost_center = _LinearRegressor(0.0, -1.10)
    total = _return_head("total")
    if invalid_total:
        total.xgboost_center = _LinearRegressor(0.0, -1.10)
    calibrator = TemporalPlattCalibrator.fit(
        [0.1, 0.3, 0.7, 0.9],
        [0, 0, 1, 1],
        calibration_ids=("dc0", "dc1", "dc2", "dc3"),
        model_fit_ids=("dt0", "dt1"),
    )
    return ProbabilisticSlotPackage(
        asset_class="BR_STOCK",
        horizon_days=21,
        pipeline=_pipeline(),
        direction=DirectionHead(
            classifier=_FixedProbabilityClassifier(),
            calibrator=calibrator,
            config=_config("classifier", "binary:logistic"),
        ),
        total=total,
        price=price,
        stability={"seed": 0.93, "fold": 0.88},
    )


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2025-01-02", "2025-01-03"]),
            "asset_class": ["BR_STOCK", "BR_STOCK"],
            "return_1": [0.05, -0.05],
        }
    )


def _manifest_hash(metadata: dict) -> str:
    canonical = json.dumps(
        {key: value for key, value in metadata.items() if key != "manifest_hash"},
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _gate_state() -> dict:
    return {
        "passed": False,
        "reasons": ["holdout_pending"],
        "checks": {"snapshot_generation": "pending_task_5"},
    }


def _oos_provenance() -> dict:
    return {
        "schema_version": "operum-oos-provenance-v1",
        "source": "nested_outer_test",
        "row_count": 42,
        "row_ids_hash": "a" * 64,
        "splits": ["outer_test"],
        "holdout_status": "not_accessed_by_task_4",
    }


def test_package_inference_is_deterministic_numeric_ordered_and_decomposed_exactly():
    package = _package()
    first = package.predict(_frame())
    second = package.predict(_frame())

    assert first == second
    assert len(first) == 2
    for prediction in first:
        assert 0.0 < prediction["probability_up"] < 1.0
        assert prediction["total"]["quantiles"]["q10"] <= prediction["total"]["quantiles"]["q50"]
        assert prediction["total"]["quantiles"]["q50"] <= prediction["total"]["quantiles"]["q90"]
        assert prediction["price"]["quantiles"]["q10"] <= prediction["price"]["quantiles"]["q50"]
        assert prediction["price"]["quantiles"]["q50"] <= prediction["price"]["quantiles"]["q90"]
        exact_income = (
            (1.0 + prediction["total"]["center"])
            / (1.0 + prediction["price"]["center"])
            - 1.0
        )
        assert prediction["income"]["center"] == pytest.approx(exact_income)
        assert set(prediction["confidence_inputs"]) == {
            "probability_distance",
            "relative_width",
            "component_disagreement",
            "seed_stability",
            "fold_stability",
        }
        assert not any(key in prediction for key in ("text", "message", "recommendation"))


def test_package_rejects_invalid_or_nonfinite_income_decomposition():
    for package in (_package(invalid_price=True), _package(invalid_total=True)):
        with pytest.raises(ValueError, match="income decomposition"):
            package.predict(_frame())


def test_package_round_trip_persists_complete_models_and_json_safe_state(tmp_path):
    package = _package()
    saved = save_slot_package(
        package,
        tmp_path,
        dataset_hash="dataset-abc",
        gate_state=_gate_state(),
        oos_provenance=_oos_provenance(),
    )
    metadata = json.loads(saved.metadata_path.read_text(encoding="utf-8"))
    loaded = load_slot_package(saved.metadata_path)

    assert metadata["schema_version"] == PACKAGE_SCHEMA_VERSION
    assert set(metadata["component_manifest"]["direction"]) == set(DIRECTION_COMPONENTS)
    assert set(metadata["component_manifest"]["total"]) == set(HEAD_COMPONENTS)
    assert set(metadata["component_manifest"]["price"]) == set(HEAD_COMPONENTS)
    assert metadata["feature_pipeline_state"] == package.pipeline.to_state()
    assert metadata["calibration_state"]["direction"] == package.direction.calibrator.state()
    assert metadata["blend_state"]["total"] == package.total.blend.state()
    assert metadata["blend_state"]["price"] == package.price.blend.state()
    assert metadata["gate_state"] == _gate_state()
    assert metadata["oos_provenance"] == _oos_provenance()
    json.dumps(metadata, allow_nan=False)
    assert loaded.predict(_frame()) == package.predict(_frame())


def test_package_rejects_model_rounds_that_do_not_match_validated_state():
    package = _package()
    package.total.xgboost_center = _ConfiguredRegressor(
        0.40,
        objective="reg:absoluteerror",
        n_estimators=6,
    )

    with pytest.raises(PackageValidationError, match="validated.*round"):
        package.validate()

    package = _package()
    package.total.xgboost_center = _ConfiguredEnsemble(
        _ConfiguredRegressor(
            0.40,
            objective="reg:absoluteerror",
            n_estimators=7,
        ),
        seed=42,
    )
    with pytest.raises(PackageValidationError, match="validated.*seed"):
        package.validate()


def test_loader_fails_closed_on_metadata_component_pipeline_or_artifact_tampering(tmp_path):
    saved = save_slot_package(
        _package(),
        tmp_path,
        dataset_hash="dataset-tamper",
        gate_state=_gate_state(),
        oos_provenance=_oos_provenance(),
    )
    original = json.loads(saved.metadata_path.read_text(encoding="utf-8"))

    unsigned = {**original, "horizon_days": 63}
    saved.metadata_path.write_text(json.dumps(unsigned), encoding="utf-8")
    with pytest.raises(PackageValidationError, match="manifest hash"):
        load_slot_package(saved.metadata_path)

    incomplete = json.loads(json.dumps(original))
    incomplete["component_manifest"]["total"].remove("q90")
    incomplete["manifest_hash"] = _manifest_hash(incomplete)
    saved.metadata_path.write_text(json.dumps(incomplete), encoding="utf-8")
    with pytest.raises(PackageValidationError, match="component"):
        load_slot_package(saved.metadata_path)

    injected = json.loads(json.dumps(original))
    injected["calibration_state"]["unvalidated"] = {}
    injected["manifest_hash"] = _manifest_hash(injected)
    saved.metadata_path.write_text(json.dumps(injected), encoding="utf-8")
    with pytest.raises(PackageValidationError, match="component"):
        load_slot_package(saved.metadata_path)

    changed_pipeline = json.loads(json.dumps(original))
    changed_pipeline["feature_pipeline_state"]["numeric_medians"]["return_1"] = 0.123
    changed_pipeline["manifest_hash"] = _manifest_hash(changed_pipeline)
    saved.metadata_path.write_text(json.dumps(changed_pipeline), encoding="utf-8")
    with pytest.raises(PackageValidationError, match="pipeline"):
        load_slot_package(saved.metadata_path)

    saved.metadata_path.write_text(json.dumps(original), encoding="utf-8")
    with saved.artifact_path.open("ab") as destination:
        destination.write(b"tampered")
    with pytest.raises(PackageValidationError, match="artifact hash"):
        load_slot_package(saved.metadata_path)


def test_save_rejects_non_json_gate_or_oos_state(tmp_path):
    with pytest.raises(PackageValidationError, match="JSON-safe"):
        save_slot_package(
            _package(),
            tmp_path,
            dataset_hash="dataset-invalid",
            gate_state={**_gate_state(), "invalid": float("nan")},
            oos_provenance=_oos_provenance(),
        )
