from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence

import joblib
import numpy as np
import pandas as pd

from app.ml.feature_pipeline import FoldFeaturePipeline
from app.ml.probabilistic import (
    CENTER_OBJECTIVES,
    HISTORY_POLICIES,
    QUANTILE_ALPHAS,
    QUANTILE_NAMES,
    AdaptiveConformalCalibrator,
    OOSBlend,
    TemporalPlattCalibrator,
    ordered_quantiles,
)


PACKAGE_SCHEMA_VERSION = "operum-probabilistic-slot-v2"
OOS_PROVENANCE_SCHEMA_VERSION = "operum-oos-provenance-v1"
DIRECTION_COMPONENTS = ("classifier", "platt_calibrator")
HEAD_COMPONENTS = (
    "xgboost_center",
    "elastic_net",
    "baseline",
    "blend",
    "q10",
    "q50",
    "q90",
    "adaptive_conformal",
)
_BLEND_COMPONENTS = {"baseline", "xgboost", "elastic_net"}
_METADATA_KEYS = {
    "schema_version",
    "package_id",
    "asset_class",
    "horizon_days",
    "dataset_hash",
    "artifact_file",
    "artifact_sha256",
    "feature_pipeline_state",
    "component_manifest",
    "calibration_state",
    "blend_state",
    "baseline_state",
    "conformal_state",
    "validated_model_state",
    "gate_state",
    "oos_provenance",
    "manifest_hash",
}


class PackageValidationError(ValueError):
    pass


def _canonical_hash(value) -> str:
    try:
        canonical = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise PackageValidationError("package state must be JSON-safe") from exc
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _json_clone(value):
    try:
        return json.loads(json.dumps(value, sort_keys=True, allow_nan=False))
    except (TypeError, ValueError) as exc:
        raise PackageValidationError("package state must be JSON-safe") from exc


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _model_prediction(model, matrix, *, component: str) -> np.ndarray:
    if not hasattr(model, "predict"):
        raise PackageValidationError(f"missing predict method for {component}")
    values = np.asarray(model.predict(matrix), dtype=float)
    if values.ndim != 1 or values.shape[0] != len(matrix) or not np.all(np.isfinite(values)):
        raise ValueError(f"invalid prediction from {component}")
    return values


def _direction_probability(classifier, matrix) -> np.ndarray:
    if not hasattr(classifier, "predict_proba"):
        raise PackageValidationError("direction classifier must expose predict_proba")
    values = np.asarray(classifier.predict_proba(matrix), dtype=float)
    if values.ndim != 2 or values.shape[0] != len(matrix) or values.shape[1] not in {1, 2}:
        raise ValueError("invalid direction probability shape")
    if values.shape[1] == 2:
        probability = values[:, 1]
    else:
        classes = np.asarray(getattr(classifier, "classes_", [1]))
        probability = values[:, 0] if classes.size == 1 and classes[0] == 1 else 1.0 - values[:, 0]
    if not np.all(np.isfinite(probability)):
        raise ValueError("direction classifier produced non-finite probabilities")
    return np.clip(probability, 0.0, 1.0)


def _validate_estimator_against_config(
    estimator,
    config: "ValidatedModelConfig",
    *,
    component: str,
) -> None:
    models = tuple(getattr(estimator, "models", (estimator,)))
    if not models:
        raise PackageValidationError(f"{component} model ensemble is empty")
    ensemble_seeds = getattr(estimator, "seeds", None)
    if ensemble_seeds is not None and tuple(int(seed) for seed in ensemble_seeds) != config.seeds:
        raise PackageValidationError(f"{component} validated model seed mismatch")
    for index, model in enumerate(models):
        if not hasattr(model, "get_params"):
            continue
        try:
            parameters = dict(model.get_params())
        except (TypeError, ValueError) as exc:
            raise PackageValidationError(f"{component} model configuration is unreadable") from exc
        actual_rounds = parameters.get("n_estimators")
        if actual_rounds is not None and int(actual_rounds) != config.n_estimators:
            raise PackageValidationError(
                f"{component} validated model round mismatch"
            )
        actual_seed = parameters.get("random_state")
        if actual_seed is not None and index < len(config.seeds) and int(actual_seed) != config.seeds[index]:
            raise PackageValidationError(
                f"{component} validated model seed mismatch"
            )
        objective_parameters = parameters
        if hasattr(model, "get_xgb_params"):
            try:
                objective_parameters = dict(model.get_xgb_params())
            except (TypeError, ValueError) as exc:
                raise PackageValidationError(
                    f"{component} model configuration is unreadable"
                ) from exc
        actual_objective = objective_parameters.get("objective")
        if actual_objective is not None and actual_objective != config.objective:
            raise PackageValidationError(
                f"{component} validated model objective mismatch"
            )
        if config.model_type == "quantile":
            actual_alpha = objective_parameters.get(
                "quantile_alpha", parameters.get("quantile_alpha")
            )
            expected_alpha = float(config.parameters["quantile_alpha"])
            if actual_alpha is not None and not np.isclose(
                float(actual_alpha), expected_alpha, atol=0.0, rtol=0.0
            ):
                raise PackageValidationError(
                    f"{component} validated quantile alpha mismatch"
                )
        for name, expected in config.parameters.items():
            if name == "quantile_alpha" or name not in parameters:
                continue
            actual = parameters[name]
            if isinstance(expected, (int, float)) and not isinstance(expected, bool):
                if not np.isclose(float(actual), float(expected), atol=0.0, rtol=0.0):
                    raise PackageValidationError(
                        f"{component} validated model parameter mismatch: {name}"
                    )
            elif actual != expected:
                raise PackageValidationError(
                    f"{component} validated model parameter mismatch: {name}"
                )


@dataclass(frozen=True)
class ValidatedModelConfig:
    model_type: str
    objective: str
    n_estimators: int
    parameters: dict
    history_policy: str
    seeds: tuple[int, ...]
    validation_ids_hash: str
    configuration_hash: str

    @classmethod
    def create(
        cls,
        *,
        model_type: str,
        objective: str,
        n_estimators: int,
        parameters: Mapping[str, object],
        history_policy: str,
        validation_ids: Sequence[object],
        seeds: Sequence[int] = (17,),
    ) -> "ValidatedModelConfig":
        normalized_seeds = tuple(int(seed) for seed in seeds)
        core = {
            "model_type": model_type,
            "objective": objective,
            "n_estimators": n_estimators,
            "parameters": _json_clone(dict(parameters)),
            "history_policy": history_policy,
            "seeds": list(normalized_seeds),
            "validation_ids_hash": _canonical_hash([str(value) for value in validation_ids]),
        }
        instance = cls(
            model_type=model_type,
            objective=objective,
            n_estimators=n_estimators,
            parameters=core["parameters"],
            history_policy=history_policy,
            seeds=normalized_seeds,
            validation_ids_hash=core["validation_ids_hash"],
            configuration_hash=_canonical_hash(core),
        )
        instance.validate()
        return instance

    def validate(self) -> None:
        if self.model_type not in {"classifier", "center", "quantile"}:
            raise PackageValidationError("invalid validated model type")
        if self.model_type == "classifier" and self.objective != "binary:logistic":
            raise PackageValidationError("invalid classifier objective")
        if self.model_type == "center" and self.objective not in CENTER_OBJECTIVES:
            raise PackageValidationError("invalid robust center objective")
        if self.model_type == "quantile" and self.objective != "reg:quantileerror":
            raise PackageValidationError("invalid quantile objective")
        if (
            not isinstance(self.n_estimators, int)
            or isinstance(self.n_estimators, bool)
            or self.n_estimators <= 0
            or self.history_policy not in HISTORY_POLICIES
            or not isinstance(self.parameters, dict)
            or not isinstance(self.seeds, tuple)
            or not self.seeds
            or any(not isinstance(seed, int) or isinstance(seed, bool) for seed in self.seeds)
            or len(self.seeds) != len(set(self.seeds))
            or not isinstance(self.validation_ids_hash, str)
            or len(self.validation_ids_hash) != 64
            or not isinstance(self.configuration_hash, str)
            or len(self.configuration_hash) != 64
        ):
            raise PackageValidationError("invalid validated model configuration")
        if self.model_type == "quantile":
            try:
                alpha = float(self.parameters["quantile_alpha"])
            except (KeyError, TypeError, ValueError) as exc:
                raise PackageValidationError("quantile alpha is missing") from exc
            if alpha not in QUANTILE_ALPHAS:
                raise PackageValidationError("invalid quantile alpha")
        core = {
            "model_type": self.model_type,
            "objective": self.objective,
            "n_estimators": self.n_estimators,
            "parameters": _json_clone(self.parameters),
            "history_policy": self.history_policy,
            "seeds": list(self.seeds),
            "validation_ids_hash": self.validation_ids_hash,
        }
        if _canonical_hash(core) != self.configuration_hash:
            raise PackageValidationError("validated model configuration hash mismatch")

    def state(self) -> dict:
        self.validate()
        return {
            "model_type": self.model_type,
            "objective": self.objective,
            "n_estimators": self.n_estimators,
            "parameters": _json_clone(self.parameters),
            "history_policy": self.history_policy,
            "seeds": list(self.seeds),
            "validation_ids_hash": self.validation_ids_hash,
            "configuration_hash": self.configuration_hash,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "ValidatedModelConfig":
        expected = {
            "model_type",
            "objective",
            "n_estimators",
            "parameters",
            "history_policy",
            "seeds",
            "validation_ids_hash",
            "configuration_hash",
        }
        if not isinstance(state, Mapping) or set(state) != expected:
            raise PackageValidationError("invalid validated model state")
        try:
            instance = cls(
                model_type=state["model_type"],
                objective=state["objective"],
                n_estimators=state["n_estimators"],
                parameters=dict(state["parameters"]),
                history_policy=state["history_policy"],
                seeds=tuple(state["seeds"]),
                validation_ids_hash=state["validation_ids_hash"],
                configuration_hash=state["configuration_hash"],
            )
        except (TypeError, ValueError) as exc:
            raise PackageValidationError("invalid validated model state") from exc
        instance.validate()
        return instance


@dataclass(frozen=True)
class FrozenCausalBaseline:
    name: str
    horizon_days: int

    def __post_init__(self) -> None:
        if self.name not in {"zero", "drift", "benchmark_beta"}:
            raise PackageValidationError("unknown frozen baseline")
        if not isinstance(self.horizon_days, int) or isinstance(self.horizon_days, bool) or self.horizon_days <= 0:
            raise PackageValidationError("baseline horizon must be positive")

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        if self.name == "zero":
            return np.zeros(len(frame), dtype=float)
        if self.name == "benchmark_beta":
            if {"benchmark_return_63", "beta_63"}.issubset(frame.columns):
                benchmark = pd.to_numeric(frame["benchmark_return_63"], errors="coerce").fillna(0.0)
                beta = pd.to_numeric(frame["beta_63"], errors="coerce").fillna(1.0)
                return np.clip(
                    benchmark.to_numpy(dtype=float)
                    * beta.to_numpy(dtype=float)
                    * (self.horizon_days / 63.0),
                    -0.30,
                    0.30,
                )
            return np.zeros(len(frame), dtype=float)
        for column, days in (("return_63", 63), ("return_21", 21), ("return_1", 1)):
            if column in frame:
                values = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
                return np.clip(
                    values.to_numpy(dtype=float) * (self.horizon_days / days),
                    -0.30,
                    0.30,
                )
        return np.zeros(len(frame), dtype=float)

    def state(self) -> dict:
        return {"name": self.name, "horizon_days": self.horizon_days}

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "FrozenCausalBaseline":
        if not isinstance(state, Mapping) or set(state) != {"name", "horizon_days"}:
            raise PackageValidationError("invalid frozen baseline state")
        return cls(name=state["name"], horizon_days=state["horizon_days"])


@dataclass
class DirectionHead:
    classifier: object
    calibrator: TemporalPlattCalibrator
    config: ValidatedModelConfig

    def validate(self) -> None:
        if not hasattr(self.classifier, "predict_proba"):
            raise PackageValidationError("direction classifier is incomplete")
        self.config.validate()
        if self.config.model_type != "classifier":
            raise PackageValidationError("direction model configuration is invalid")
        _validate_estimator_against_config(
            self.classifier, self.config, component="direction"
        )
        TemporalPlattCalibrator.from_state(self.calibrator.state())


@dataclass
class ReturnHead:
    xgboost_center: object
    elastic_net: object
    baseline: FrozenCausalBaseline
    blend: OOSBlend
    quantile_models: dict[str, object]
    conformal: AdaptiveConformalCalibrator
    center_config: ValidatedModelConfig
    quantile_configs: dict[str, ValidatedModelConfig]

    def validate(self) -> None:
        for name, model in {
            "xgboost_center": self.xgboost_center,
            "elastic_net": self.elastic_net,
            **self.quantile_models,
        }.items():
            if not hasattr(model, "predict"):
                raise PackageValidationError(f"return head component is incomplete: {name}")
        if set(self.quantile_models) != set(QUANTILE_NAMES) or set(self.quantile_configs) != set(
            QUANTILE_NAMES
        ):
            raise PackageValidationError("quantile component set is incomplete")
        if set(self.blend.weights) != _BLEND_COMPONENTS:
            raise PackageValidationError("blend component set is incomplete")
        OOSBlend.from_state(self.blend.state())
        AdaptiveConformalCalibrator.from_state(self.conformal.state())
        FrozenCausalBaseline.from_state(self.baseline.state())
        self.center_config.validate()
        if self.center_config.model_type != "center":
            raise PackageValidationError("center model configuration is invalid")
        _validate_estimator_against_config(
            self.xgboost_center, self.center_config, component="center"
        )
        for name, alpha in zip(QUANTILE_NAMES, QUANTILE_ALPHAS):
            config = self.quantile_configs[name]
            config.validate()
            if config.model_type != "quantile" or float(config.parameters["quantile_alpha"]) != alpha:
                raise PackageValidationError("quantile model configuration is invalid")
            _validate_estimator_against_config(
                self.quantile_models[name], config, component=name
            )

    def predict(self, matrix: pd.DataFrame, raw_frame: pd.DataFrame) -> dict[str, object]:
        self.validate()
        components = {
            "xgboost": _model_prediction(
                self.xgboost_center, matrix, component="xgboost center"
            ),
            "elastic_net": _model_prediction(
                self.elastic_net, matrix, component="elastic net"
            ),
            "baseline": self.baseline.predict(raw_frame),
        }
        if any(values.shape != (len(matrix),) or not np.all(np.isfinite(values)) for values in components.values()):
            raise ValueError("return component produced invalid predictions")
        center = self.blend.predict(components)
        quantiles = ordered_quantiles(
            {
                name: _model_prediction(model, matrix, component=name)
                for name, model in self.quantile_models.items()
            }
        )
        quantiles["q10"], quantiles["q90"] = self.conformal.correct(
            quantiles["q10"], quantiles["q90"]
        )
        disagreement = np.std(np.column_stack(list(components.values())), axis=1)
        return {
            "center": center,
            "quantiles": quantiles,
            "component_disagreement": disagreement,
        }


@dataclass
class ProbabilisticSlotPackage:
    asset_class: str
    horizon_days: int
    pipeline: FoldFeaturePipeline
    direction: DirectionHead
    total: ReturnHead
    price: ReturnHead
    stability: dict[str, float]

    def validate(self) -> None:
        if self.asset_class not in {"BR_STOCK", "FII"}:
            raise PackageValidationError("invalid package asset class")
        if not isinstance(self.horizon_days, int) or isinstance(self.horizon_days, bool) or self.horizon_days <= 0:
            raise PackageValidationError("invalid package horizon")
        try:
            restored = FoldFeaturePipeline.from_state(self.pipeline.to_state())
        except (AttributeError, RuntimeError, ValueError) as exc:
            raise PackageValidationError("invalid package feature pipeline") from exc
        if restored.to_state() != self.pipeline.to_state():
            raise PackageValidationError("invalid package feature pipeline")
        self.direction.validate()
        self.total.validate()
        self.price.validate()
        if set(self.stability) != {"seed", "fold"}:
            raise PackageValidationError("seed and fold stability are required")
        if any(
            not np.isfinite(float(value)) or not 0.0 <= float(value) <= 1.0
            for value in self.stability.values()
        ):
            raise PackageValidationError("invalid package stability values")

    def predict(self, frame: pd.DataFrame) -> list[dict]:
        self.validate()
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            raise ValueError("package inference requires rows")
        if "asset_class" in frame and not frame["asset_class"].astype(str).eq(self.asset_class).all():
            raise ValueError("inference rows do not match the package asset class")
        matrix = self.pipeline.transform(frame)
        raw_probability = _direction_probability(self.direction.classifier, matrix)
        probability = self.direction.calibrator.predict(raw_probability)
        total = self.total.predict(matrix, frame)
        price = self.price.predict(matrix, frame)
        numerator = 1.0 + total["center"]
        denominator = 1.0 + price["center"]
        if (
            np.any(numerator <= 0.0)
            or np.any(denominator <= 0.0)
            or not np.all(np.isfinite(total["center"]))
            or not np.all(np.isfinite(price["center"]))
        ):
            raise ValueError("invalid or non-finite income decomposition")
        income = numerator / denominator - 1.0
        if not np.all(np.isfinite(income)):
            raise ValueError("invalid or non-finite income decomposition")

        output = []
        for index in range(len(frame)):
            total_quantiles = {
                name: float(total["quantiles"][name][index]) for name in QUANTILE_NAMES
            }
            price_quantiles = {
                name: float(price["quantiles"][name][index]) for name in QUANTILE_NAMES
            }
            total_width = total_quantiles["q90"] - total_quantiles["q10"]
            price_width = price_quantiles["q90"] - price_quantiles["q10"]
            total_center = float(total["center"][index])
            price_center = float(price["center"][index])
            output.append(
                {
                    "probability_up": float(probability[index]),
                    "total": {"center": total_center, "quantiles": total_quantiles},
                    "price": {"center": price_center, "quantiles": price_quantiles},
                    "income": {"center": float(income[index])},
                    "confidence_inputs": {
                        "probability_distance": float(abs(probability[index] - 0.5)),
                        "relative_width": {
                            "total": float(total_width / max(abs(total_center), 1e-6)),
                            "price": float(price_width / max(abs(price_center), 1e-6)),
                        },
                        "component_disagreement": {
                            "total": float(total["component_disagreement"][index]),
                            "price": float(price["component_disagreement"][index]),
                        },
                        "seed_stability": float(self.stability["seed"]),
                        "fold_stability": float(self.stability["fold"]),
                    },
                }
            )
        return output


@dataclass(frozen=True)
class SavedSlotPackage:
    package_id: str
    artifact_path: Path
    metadata_path: Path


def _validated_model_state(package: ProbabilisticSlotPackage) -> dict:
    return {
        "direction": package.direction.config.state(),
        "total": {
            "center": package.total.center_config.state(),
            "quantiles": {
                name: package.total.quantile_configs[name].state() for name in QUANTILE_NAMES
            },
        },
        "price": {
            "center": package.price.center_config.state(),
            "quantiles": {
                name: package.price.quantile_configs[name].state() for name in QUANTILE_NAMES
            },
        },
    }


def _validate_gate_state(state) -> dict:
    normalized = _json_clone(state)
    if (
        not isinstance(normalized, dict)
        or set(normalized) != {"passed", "reasons", "checks"}
        or not isinstance(normalized["passed"], bool)
        or not isinstance(normalized["reasons"], list)
        or any(not isinstance(value, str) for value in normalized["reasons"])
        or not isinstance(normalized["checks"], dict)
    ):
        raise PackageValidationError("invalid gate state")
    return normalized


def _validate_oos_provenance(state) -> dict:
    normalized = _json_clone(state)
    expected = {
        "schema_version",
        "source",
        "row_count",
        "row_ids_hash",
        "splits",
        "holdout_status",
    }
    if (
        not isinstance(normalized, dict)
        or set(normalized) != expected
        or normalized["schema_version"] != OOS_PROVENANCE_SCHEMA_VERSION
        or not isinstance(normalized["source"], str)
        or not normalized["source"]
        or not isinstance(normalized["row_count"], int)
        or isinstance(normalized["row_count"], bool)
        or normalized["row_count"] <= 0
        or not isinstance(normalized["row_ids_hash"], str)
        or len(normalized["row_ids_hash"]) != 64
        or not isinstance(normalized["splits"], list)
        or not normalized["splits"]
        or any(not isinstance(value, str) for value in normalized["splits"])
        or normalized["holdout_status"]
        not in {"not_accessed_by_task_4", "finalized_by_holdout_ledger"}
    ):
        raise PackageValidationError("invalid OOS provenance state")
    return normalized


def _component_manifest() -> dict:
    return {
        "direction": list(DIRECTION_COMPONENTS),
        "total": list(HEAD_COMPONENTS),
        "price": list(HEAD_COMPONENTS),
    }


def save_slot_package(
    package: ProbabilisticSlotPackage,
    directory: str | Path,
    *,
    dataset_hash: str,
    gate_state: Mapping[str, object],
    oos_provenance: Mapping[str, object],
) -> SavedSlotPackage:
    package.validate()
    if not isinstance(dataset_hash, str) or not dataset_hash:
        raise PackageValidationError("dataset hash is required")
    gate = _validate_gate_state(gate_state)
    provenance = _validate_oos_provenance(oos_provenance)
    root = Path(directory)
    root.mkdir(parents=True, exist_ok=True)
    package_id = str(uuid.uuid4())
    stem = f"{package.asset_class.lower()}_{package.horizon_days}d_{package_id}"
    artifact_path = root / f"{stem}.joblib"
    metadata_path = root / f"{stem}.json"
    joblib.dump(package, artifact_path)
    metadata = {
        "schema_version": PACKAGE_SCHEMA_VERSION,
        "package_id": package_id,
        "asset_class": package.asset_class,
        "horizon_days": package.horizon_days,
        "dataset_hash": dataset_hash,
        "artifact_file": artifact_path.name,
        "artifact_sha256": _sha256_file(artifact_path),
        "feature_pipeline_state": package.pipeline.to_state(),
        "component_manifest": _component_manifest(),
        "calibration_state": {"direction": package.direction.calibrator.state()},
        "blend_state": {
            "total": package.total.blend.state(),
            "price": package.price.blend.state(),
        },
        "baseline_state": {
            "total": package.total.baseline.state(),
            "price": package.price.baseline.state(),
        },
        "conformal_state": {
            "total": package.total.conformal.state(),
            "price": package.price.conformal.state(),
        },
        "validated_model_state": _validated_model_state(package),
        "gate_state": gate,
        "oos_provenance": provenance,
    }
    metadata["manifest_hash"] = _canonical_hash(metadata)
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True, allow_nan=False),
        encoding="utf-8",
    )
    return SavedSlotPackage(package_id, artifact_path, metadata_path)


def _validate_metadata(metadata) -> dict:
    if not isinstance(metadata, dict) or set(metadata) != _METADATA_KEYS:
        raise PackageValidationError("package metadata schema is incomplete")
    if metadata["schema_version"] != PACKAGE_SCHEMA_VERSION:
        raise PackageValidationError("incompatible package schema")
    expected_hash = _canonical_hash(
        {key: value for key, value in metadata.items() if key != "manifest_hash"}
    )
    if metadata["manifest_hash"] != expected_hash:
        raise PackageValidationError("package manifest hash mismatch")
    if metadata["component_manifest"] != _component_manifest():
        raise PackageValidationError("package component manifest is incomplete")
    if (
        not isinstance(metadata["calibration_state"], dict)
        or set(metadata["calibration_state"]) != {"direction"}
        or not isinstance(metadata["blend_state"], dict)
        or set(metadata["blend_state"]) != {"total", "price"}
        or not isinstance(metadata["baseline_state"], dict)
        or set(metadata["baseline_state"]) != {"total", "price"}
        or not isinstance(metadata["conformal_state"], dict)
        or set(metadata["conformal_state"]) != {"total", "price"}
        or not isinstance(metadata["validated_model_state"], dict)
        or set(metadata["validated_model_state"]) != {"direction", "total", "price"}
    ):
        raise PackageValidationError("package component state is incomplete")
    try:
        FoldFeaturePipeline.from_state(metadata["feature_pipeline_state"])
    except (TypeError, ValueError) as exc:
        raise PackageValidationError("invalid feature pipeline state") from exc
    try:
        TemporalPlattCalibrator.from_state(metadata["calibration_state"]["direction"])
        for head in ("total", "price"):
            OOSBlend.from_state(metadata["blend_state"][head])
            FrozenCausalBaseline.from_state(metadata["baseline_state"][head])
            AdaptiveConformalCalibrator.from_state(metadata["conformal_state"][head])
        model_state = metadata["validated_model_state"]
        ValidatedModelConfig.from_state(model_state["direction"])
        for head in ("total", "price"):
            ValidatedModelConfig.from_state(model_state[head]["center"])
            if set(model_state[head]["quantiles"]) != set(QUANTILE_NAMES):
                raise PackageValidationError("quantile model state is incomplete")
            for name in QUANTILE_NAMES:
                ValidatedModelConfig.from_state(model_state[head]["quantiles"][name])
    except (KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, PackageValidationError):
            raise
        raise PackageValidationError("package component state is incomplete") from exc
    _validate_gate_state(metadata["gate_state"])
    _validate_oos_provenance(metadata["oos_provenance"])
    if (
        not isinstance(metadata["asset_class"], str)
        or not isinstance(metadata["horizon_days"], int)
        or isinstance(metadata["horizon_days"], bool)
        or metadata["horizon_days"] <= 0
        or not isinstance(metadata["dataset_hash"], str)
        or not metadata["dataset_hash"]
        or not isinstance(metadata["artifact_file"], str)
        or Path(metadata["artifact_file"]).name != metadata["artifact_file"]
        or not isinstance(metadata["artifact_sha256"], str)
        or len(metadata["artifact_sha256"]) != 64
    ):
        raise PackageValidationError("invalid package metadata identity")
    return metadata


def load_slot_package(metadata_path: str | Path) -> ProbabilisticSlotPackage:
    path = Path(metadata_path)
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackageValidationError("package metadata is unreadable") from exc
    metadata = _validate_metadata(metadata)
    artifact_path = path.parent / metadata["artifact_file"]
    if not artifact_path.is_file() or _sha256_file(artifact_path) != metadata["artifact_sha256"]:
        raise PackageValidationError("package artifact hash mismatch")
    try:
        package = joblib.load(artifact_path)
    except Exception as exc:
        raise PackageValidationError("package artifact is unreadable") from exc
    if not isinstance(package, ProbabilisticSlotPackage):
        raise PackageValidationError("package artifact has the wrong type")
    package.validate()
    if package.asset_class != metadata["asset_class"] or package.horizon_days != metadata["horizon_days"]:
        raise PackageValidationError("package artifact slot mismatch")
    if package.pipeline.to_state() != metadata["feature_pipeline_state"]:
        raise PackageValidationError("package pipeline state mismatch")
    if package.direction.calibrator.state() != metadata["calibration_state"]["direction"]:
        raise PackageValidationError("package calibration state mismatch")
    for head_name in ("total", "price"):
        head = getattr(package, head_name)
        if head.blend.state() != metadata["blend_state"][head_name]:
            raise PackageValidationError("package blend state mismatch")
        if head.baseline.state() != metadata["baseline_state"][head_name]:
            raise PackageValidationError("package baseline state mismatch")
        if head.conformal.state() != metadata["conformal_state"][head_name]:
            raise PackageValidationError("package conformal state mismatch")
    if _validated_model_state(package) != metadata["validated_model_state"]:
        raise PackageValidationError("package validated model state mismatch")
    return package
