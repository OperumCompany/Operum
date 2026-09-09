from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np


CENTER_OBJECTIVES = ("reg:absoluteerror", "reg:pseudohubererror")
QUANTILE_ALPHAS = (0.10, 0.50, 0.90)
QUANTILE_NAMES = ("q10", "q50", "q90")
HISTORY_POLICIES = ("uniform_expanding", "exponential_504")
PLATT_SCHEMA_VERSION = "operum-platt-v1"
BLEND_SCHEMA_VERSION = "operum-oos-blend-v1"
CONFORMAL_SCHEMA_VERSION = "operum-adaptive-conformal-v1"
_PROBABILITY_EPSILON = 1e-6


def _finite_vector(values, *, name: str) -> np.ndarray:
    vector = np.asarray(values, dtype=float)
    if vector.ndim != 1 or vector.size == 0:
        raise ValueError(f"{name} must be a non-empty one-dimensional array")
    if not np.all(np.isfinite(vector)):
        raise ValueError(f"{name} must contain only finite values")
    return vector


def _row_id_hash(values: Sequence[object]) -> str:
    canonical = json.dumps([str(value) for value in values], separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_disjoint_rows(
    *,
    calibration_ids: Sequence[object],
    model_fit_ids: Sequence[object],
    expected_size: int,
) -> tuple[str, ...]:
    calibration = tuple(str(value) for value in calibration_ids)
    fitted = {str(value) for value in model_fit_ids}
    if len(calibration) != expected_size:
        raise ValueError("calibration ids must align with calibration predictions")
    if len(calibration) != len(set(calibration)):
        raise ValueError("calibration ids must be unique")
    if set(calibration).intersection(fitted):
        raise ValueError("model-fit and calibration rows must be disjoint")
    return calibration


def history_weights(size: int, policy: str) -> np.ndarray:
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ValueError("history size must be a positive integer")
    if policy not in HISTORY_POLICIES:
        raise ValueError(f"unknown history policy: {policy}")
    if policy == "uniform_expanding":
        return np.ones(size, dtype=float)
    age = np.arange(size - 1, -1, -1, dtype=float)
    return np.power(0.5, age / 504.0)


def history_weights_for_origins(origins, policy: str) -> np.ndarray:
    import pandas as pd

    values = pd.DatetimeIndex(pd.to_datetime(origins, errors="coerce"))
    if values.empty or values.isna().any():
        raise ValueError("history origins must contain valid timestamps")
    if policy not in HISTORY_POLICIES:
        raise ValueError(f"unknown history policy: {policy}")
    if policy == "uniform_expanding":
        return np.ones(len(values), dtype=float)
    ordered = pd.DatetimeIndex(values.sort_values().unique())
    positions = {origin: index for index, origin in enumerate(ordered)}
    newest = len(ordered) - 1
    ages = np.asarray([newest - positions[origin] for origin in values], dtype=float)
    return np.power(0.5, ages / 504.0)


def _xgboost_base(*, seed: int, n_estimators: int) -> dict:
    if not isinstance(n_estimators, int) or isinstance(n_estimators, bool) or n_estimators <= 0:
        raise ValueError("n_estimators must be a positive integer")
    return {
        "n_estimators": n_estimators,
        "max_depth": 3,
        "learning_rate": 0.05,
        "min_child_weight": 8,
        "subsample": 0.80,
        "colsample_bytree": 0.75,
        "reg_alpha": 0.10,
        "reg_lambda": 8.0,
        "tree_method": "hist",
        "random_state": int(seed),
        "n_jobs": 1,
        "verbosity": 0,
    }


def make_xgboost_classifier(*, seed: int, n_estimators: int, **overrides):
    import xgboost as xgb

    params = {**_xgboost_base(seed=seed, n_estimators=n_estimators), **overrides}
    params.update({"objective": "binary:logistic", "eval_metric": "logloss"})
    return xgb.XGBClassifier(**params)


def make_xgboost_center(
    *, objective: str, seed: int, n_estimators: int, **overrides
):
    import xgboost as xgb

    if objective not in CENTER_OBJECTIVES:
        raise ValueError(f"unsupported robust objective: {objective}")
    params = {**_xgboost_base(seed=seed, n_estimators=n_estimators), **overrides}
    params.update({"objective": objective, "eval_metric": "mae"})
    return xgb.XGBRegressor(**params)


def make_xgboost_quantile(
    *, alpha: float, seed: int, n_estimators: int, **overrides
):
    import xgboost as xgb

    alpha = float(alpha)
    if alpha not in QUANTILE_ALPHAS:
        raise ValueError(f"unsupported quantile alpha: {alpha}")
    params = {**_xgboost_base(seed=seed, n_estimators=n_estimators), **overrides}
    params.update(
        {
            "objective": "reg:quantileerror",
            "quantile_alpha": alpha,
            "eval_metric": "quantile",
        }
    )
    return xgb.XGBRegressor(**params)


def make_elastic_net(*, seed: int, **overrides):
    from sklearn.linear_model import ElasticNet

    params = {
        "alpha": 0.001,
        "l1_ratio": 0.50,
        "fit_intercept": True,
        "max_iter": 5_000,
        "selection": "cyclic",
        "random_state": int(seed),
    }
    params.update(overrides)
    return ElasticNet(**params)


@dataclass(frozen=True)
class TemporalPlattCalibrator:
    mode: str
    coefficient: float
    intercept: float
    sample_count: int
    calibration_ids_hash: str
    model_fit_ids_hash: str
    clip_epsilon: float = _PROBABILITY_EPSILON

    @classmethod
    def fit(
        cls,
        raw_probabilities,
        labels,
        *,
        calibration_ids: Sequence[object],
        model_fit_ids: Sequence[object],
        clip_epsilon: float = _PROBABILITY_EPSILON,
    ) -> "TemporalPlattCalibrator":
        probabilities = _finite_vector(raw_probabilities, name="raw probabilities")
        outcomes = _finite_vector(labels, name="calibration labels")
        if probabilities.shape != outcomes.shape:
            raise ValueError("probabilities and labels must have identical shapes")
        if not np.all(np.isin(outcomes, (0.0, 1.0))):
            raise ValueError("calibration labels must be binary")
        if not 0.0 < float(clip_epsilon) < 0.5:
            raise ValueError("clip epsilon must be between zero and one half")
        identifiers = _validate_disjoint_rows(
            calibration_ids=calibration_ids,
            model_fit_ids=model_fit_ids,
            expected_size=probabilities.size,
        )
        provenance_hash = _row_id_hash(identifiers)
        fit_provenance_hash = _row_id_hash(tuple(str(value) for value in model_fit_ids))
        if np.unique(outcomes).size < 2:
            return cls(
                mode="one_class_neutral",
                coefficient=0.0,
                intercept=0.0,
                sample_count=int(outcomes.size),
                calibration_ids_hash=provenance_hash,
                model_fit_ids_hash=fit_provenance_hash,
                clip_epsilon=float(clip_epsilon),
            )

        from sklearn.linear_model import LogisticRegression

        clipped = np.clip(probabilities, clip_epsilon, 1.0 - clip_epsilon)
        logits = np.log(clipped / (1.0 - clipped)).reshape(-1, 1)
        model = LogisticRegression(solver="liblinear", random_state=0)
        model.fit(logits, outcomes.astype(int))
        return cls(
            mode="platt",
            coefficient=float(model.coef_[0, 0]),
            intercept=float(model.intercept_[0]),
            sample_count=int(outcomes.size),
            calibration_ids_hash=provenance_hash,
            model_fit_ids_hash=fit_provenance_hash,
            clip_epsilon=float(clip_epsilon),
        )

    def predict(self, raw_probabilities) -> np.ndarray:
        probabilities = _finite_vector(raw_probabilities, name="raw probabilities")
        if self.mode == "one_class_neutral":
            return np.full(probabilities.shape, 0.5, dtype=float)
        if self.mode != "platt":
            raise ValueError("invalid Platt calibration mode")
        clipped = np.clip(probabilities, self.clip_epsilon, 1.0 - self.clip_epsilon)
        logits = np.log(clipped / (1.0 - clipped))
        values = self.coefficient * logits + self.intercept
        calibrated = np.empty(values.shape, dtype=float)
        positive = values >= 0.0
        calibrated[positive] = 1.0 / (1.0 + np.exp(-values[positive]))
        exponential = np.exp(values[~positive])
        calibrated[~positive] = exponential / (1.0 + exponential)
        return np.clip(calibrated, self.clip_epsilon, 1.0 - self.clip_epsilon)

    def state(self) -> dict:
        return {
            "schema_version": PLATT_SCHEMA_VERSION,
            "mode": self.mode,
            "coefficient": self.coefficient,
            "intercept": self.intercept,
            "sample_count": self.sample_count,
            "calibration_ids_hash": self.calibration_ids_hash,
            "model_fit_ids_hash": self.model_fit_ids_hash,
            "clip_epsilon": self.clip_epsilon,
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "TemporalPlattCalibrator":
        expected = {
            "schema_version",
            "mode",
            "coefficient",
            "intercept",
            "sample_count",
            "calibration_ids_hash",
            "model_fit_ids_hash",
            "clip_epsilon",
        }
        if not isinstance(state, Mapping) or set(state) != expected:
            raise ValueError("invalid Platt calibration state")
        if state["schema_version"] != PLATT_SCHEMA_VERSION:
            raise ValueError("incompatible Platt calibration schema")
        mode = state["mode"]
        if mode not in {"platt", "one_class_neutral"}:
            raise ValueError("invalid Platt calibration mode")
        coefficient = float(state["coefficient"])
        intercept = float(state["intercept"])
        epsilon = float(state["clip_epsilon"])
        count = state["sample_count"]
        digest = state["calibration_ids_hash"]
        fit_digest = state["model_fit_ids_hash"]
        if (
            not np.isfinite(coefficient)
            or not np.isfinite(intercept)
            or not 0.0 < epsilon < 0.5
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count <= 0
            or not isinstance(digest, str)
            or len(digest) != 64
            or not isinstance(fit_digest, str)
            or len(fit_digest) != 64
        ):
            raise ValueError("invalid Platt calibration state")
        if mode == "one_class_neutral" and (coefficient != 0.0 or intercept != 0.0):
            raise ValueError("invalid neutral calibration state")
        return cls(mode, coefficient, intercept, count, digest, fit_digest, epsilon)


@dataclass(frozen=True)
class OOSBlend:
    weights: dict[str, float]
    baseline_name: str
    sample_count: int
    calibration_ids_hash: str
    model_fit_ids_hash: str
    component_mae: dict[str, float]

    @classmethod
    def fit(
        cls,
        truth,
        component_predictions: Mapping[str, object],
        *,
        baseline_name: str,
        calibration_ids: Sequence[object],
        model_fit_ids: Sequence[object],
        sample_weight=None,
    ) -> "OOSBlend":
        actual = _finite_vector(truth, name="blend truth")
        if not isinstance(component_predictions, Mapping) or baseline_name not in component_predictions:
            raise ValueError("the frozen baseline component is required")
        if len(component_predictions) < 1:
            raise ValueError("at least one blend component is required")
        identifiers = _validate_disjoint_rows(
            calibration_ids=calibration_ids,
            model_fit_ids=model_fit_ids,
            expected_size=actual.size,
        )
        names = tuple(sorted(str(name) for name in component_predictions))
        if len(names) != len(component_predictions):
            raise ValueError("blend component names must be unique strings")
        predictions = {}
        for name in names:
            values = _finite_vector(component_predictions[name], name=f"{name} predictions")
            if values.shape != actual.shape:
                raise ValueError("all blend predictions must align with truth")
            predictions[name] = values
        if sample_weight is None:
            importance = np.ones(actual.size, dtype=float)
        else:
            importance = _finite_vector(sample_weight, name="blend sample weights")
            if importance.shape != actual.shape or np.any(importance < 0.0) or not importance.any():
                raise ValueError("blend sample weights must be nonnegative and align with truth")
        importance = importance / importance.sum()
        component_mae = {
            name: float(np.sum(importance * np.abs(values - actual)))
            for name, values in predictions.items()
        }
        baseline_mae = component_mae[baseline_name]
        eligible = [
            baseline_name,
            *[
                name
                for name in names
                if name != baseline_name and component_mae[name] < baseline_mae - 1e-15
            ],
        ]
        weights = {name: 0.0 for name in names}
        if len(eligible) == 1:
            weights[baseline_name] = 1.0
            return cls(
                weights=weights,
                baseline_name=baseline_name,
                sample_count=int(actual.size),
                calibration_ids_hash=_row_id_hash(identifiers),
                model_fit_ids_hash=_row_id_hash(
                    tuple(str(value) for value in model_fit_ids)
                ),
                component_mae=component_mae,
            )

        from scipy.optimize import linprog

        matrix = np.column_stack([predictions[name] for name in eligible])
        row_count, component_count = matrix.shape
        objective = np.concatenate([np.zeros(component_count), importance])
        identity = np.eye(row_count)
        upper_matrix = np.block([[matrix, -identity], [-matrix, -identity]])
        upper_bound = np.concatenate([actual, -actual])
        equality_matrix = np.zeros((1, component_count + row_count), dtype=float)
        equality_matrix[0, :component_count] = 1.0
        result = linprog(
            objective,
            A_ub=upper_matrix,
            b_ub=upper_bound,
            A_eq=equality_matrix,
            b_eq=np.array([1.0]),
            bounds=[(0.0, 1.0)] * component_count + [(0.0, None)] * row_count,
            method="highs",
        )
        if not result.success or not np.all(np.isfinite(result.x[:component_count])):
            weights[baseline_name] = 1.0
        else:
            optimized = np.clip(result.x[:component_count], 0.0, 1.0)
            total = float(optimized.sum())
            if total <= 0.0:
                weights[baseline_name] = 1.0
            else:
                optimized /= total
                for name, value in zip(eligible, optimized):
                    weights[name] = float(value)
        return cls(
            weights=weights,
            baseline_name=baseline_name,
            sample_count=int(actual.size),
            calibration_ids_hash=_row_id_hash(identifiers),
            model_fit_ids_hash=_row_id_hash(
                tuple(str(value) for value in model_fit_ids)
            ),
            component_mae=component_mae,
        )

    def predict(self, component_predictions: Mapping[str, object]) -> np.ndarray:
        if set(component_predictions) != set(self.weights):
            raise ValueError("blend component set does not match fitted weights")
        output = None
        expected_shape = None
        for name, weight in self.weights.items():
            values = _finite_vector(component_predictions[name], name=f"{name} predictions")
            if expected_shape is None:
                expected_shape = values.shape
                output = np.zeros(values.shape, dtype=float)
            elif values.shape != expected_shape:
                raise ValueError("blend component predictions must have identical shapes")
            output += weight * values
        if output is None or not np.all(np.isfinite(output)):
            raise ValueError("blend produced invalid predictions")
        return output

    def state(self) -> dict:
        return {
            "schema_version": BLEND_SCHEMA_VERSION,
            "weights": dict(self.weights),
            "baseline_name": self.baseline_name,
            "sample_count": self.sample_count,
            "calibration_ids_hash": self.calibration_ids_hash,
            "model_fit_ids_hash": self.model_fit_ids_hash,
            "component_mae": dict(self.component_mae),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "OOSBlend":
        expected = {
            "schema_version",
            "weights",
            "baseline_name",
            "sample_count",
            "calibration_ids_hash",
            "model_fit_ids_hash",
            "component_mae",
        }
        if not isinstance(state, Mapping) or set(state) != expected:
            raise ValueError("invalid OOS blend state")
        if state["schema_version"] != BLEND_SCHEMA_VERSION:
            raise ValueError("incompatible OOS blend schema")
        weights = state["weights"]
        mae = state["component_mae"]
        baseline = state["baseline_name"]
        count = state["sample_count"]
        digest = state["calibration_ids_hash"]
        fit_digest = state["model_fit_ids_hash"]
        if (
            not isinstance(weights, Mapping)
            or not weights
            or not isinstance(mae, Mapping)
            or set(weights) != set(mae)
            or not isinstance(baseline, str)
            or baseline not in weights
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count <= 0
            or not isinstance(digest, str)
            or len(digest) != 64
            or not isinstance(fit_digest, str)
            or len(fit_digest) != 64
        ):
            raise ValueError("invalid OOS blend state")
        normalized_weights = {str(name): float(value) for name, value in weights.items()}
        normalized_mae = {str(name): float(value) for name, value in mae.items()}
        if (
            any(not np.isfinite(value) or value < 0.0 for value in normalized_weights.values())
            or not np.isclose(sum(normalized_weights.values()), 1.0, atol=1e-12)
            or any(not np.isfinite(value) or value < 0.0 for value in normalized_mae.values())
        ):
            raise ValueError("invalid OOS blend state")
        baseline_mae = normalized_mae[baseline]
        if any(
            name != baseline
            and normalized_mae[name] >= baseline_mae
            and normalized_weights[name] > 1e-12
            for name in normalized_weights
        ):
            raise ValueError("weak challenger has nonzero blend weight")
        return cls(
            normalized_weights,
            baseline,
            count,
            digest,
            fit_digest,
            normalized_mae,
        )


def ordered_quantiles(predictions: Mapping[str, object]) -> dict[str, np.ndarray]:
    if not isinstance(predictions, Mapping) or set(predictions) != set(QUANTILE_NAMES):
        raise ValueError("q10, q50 and q90 predictions are required")
    vectors = [_finite_vector(predictions[name], name=name) for name in QUANTILE_NAMES]
    if len({vector.shape for vector in vectors}) != 1:
        raise ValueError("quantile predictions must have identical shapes")
    sorted_values = np.sort(np.column_stack(vectors), axis=1)
    return {
        name: sorted_values[:, index]
        for index, name in enumerate(QUANTILE_NAMES)
    }


class AdaptiveConformalCalibrator:
    def __init__(
        self,
        *,
        coverage: float = 0.80,
        max_scores: int = 126,
        initial_scores: Sequence[float] = (),
        observed_row_ids: Sequence[object] = (),
    ) -> None:
        if not 0.0 < float(coverage) < 1.0:
            raise ValueError("coverage must be between zero and one")
        if not isinstance(max_scores, int) or isinstance(max_scores, bool) or max_scores <= 0:
            raise ValueError("max_scores must be a positive integer")
        scores = np.asarray(initial_scores, dtype=float)
        if scores.ndim != 1 or np.any(~np.isfinite(scores)) or np.any(scores < 0.0):
            raise ValueError("nonconformity scores must be finite and nonnegative")
        ids = tuple(str(value) for value in observed_row_ids)
        if ids and len(ids) != scores.size:
            raise ValueError("observed row ids must align with scores")
        if len(ids) != len(set(ids)):
            raise ValueError("observed row ids must be unique")
        self.coverage = float(coverage)
        self.max_scores = max_scores
        self._scores = [float(value) for value in scores[-max_scores:]]
        self._row_ids = list(ids[-max_scores:]) if ids else []
        self._seen = set(ids)

    @property
    def radius(self) -> float:
        if not self._scores:
            return 0.0
        ordered = np.sort(np.asarray(self._scores, dtype=float))
        rank = min(ordered.size, int(np.ceil((ordered.size + 1) * self.coverage)))
        return float(ordered[rank - 1])

    def correct(self, lower, upper) -> tuple[np.ndarray, np.ndarray]:
        low = _finite_vector(lower, name="lower interval")
        high = _finite_vector(upper, name="upper interval")
        if low.shape != high.shape or np.any(low > high):
            raise ValueError("interval bounds must align and be ordered")
        radius = self.radius
        return low - radius, high + radius

    def observe(self, *, truth: float, lower: float, upper: float, row_id: object) -> float:
        values = np.asarray([truth, lower, upper], dtype=float)
        if not np.all(np.isfinite(values)) or lower > upper:
            raise ValueError("truth and interval bounds must be finite and ordered")
        identifier = str(row_id)
        if identifier in self._seen:
            raise ValueError("row was already used for conformal calibration")
        score = float(max(lower - truth, truth - upper, 0.0))
        self._scores.append(score)
        self._row_ids.append(identifier)
        self._seen.add(identifier)
        if len(self._scores) > self.max_scores:
            self._scores = self._scores[-self.max_scores :]
            self._row_ids = self._row_ids[-self.max_scores :]
        return score

    def calibrate_oos(
        self,
        *,
        truth,
        lower,
        upper,
        row_ids: Sequence[object],
    ) -> tuple[np.ndarray, np.ndarray]:
        actual = _finite_vector(truth, name="interval truth")
        low = _finite_vector(lower, name="lower interval")
        high = _finite_vector(upper, name="upper interval")
        identifiers = tuple(row_ids)
        if actual.shape != low.shape or low.shape != high.shape or len(identifiers) != actual.size:
            raise ValueError("OOS interval rows must have identical shapes")
        corrected_low = np.empty(actual.shape, dtype=float)
        corrected_high = np.empty(actual.shape, dtype=float)
        for index, identifier in enumerate(identifiers):
            current_low, current_high = self.correct([low[index]], [high[index]])
            corrected_low[index] = current_low[0]
            corrected_high[index] = current_high[0]
            self.observe(
                truth=float(actual[index]),
                lower=float(low[index]),
                upper=float(high[index]),
                row_id=identifier,
            )
        return corrected_low, corrected_high

    def state(self) -> dict:
        return {
            "schema_version": CONFORMAL_SCHEMA_VERSION,
            "coverage": self.coverage,
            "max_scores": self.max_scores,
            "recent_scores": list(self._scores),
            "recent_row_ids": list(self._row_ids),
        }

    @classmethod
    def from_state(cls, state: Mapping[str, object]) -> "AdaptiveConformalCalibrator":
        expected = {
            "schema_version",
            "coverage",
            "max_scores",
            "recent_scores",
            "recent_row_ids",
        }
        if not isinstance(state, Mapping) or set(state) != expected:
            raise ValueError("invalid adaptive conformal state")
        if state["schema_version"] != CONFORMAL_SCHEMA_VERSION:
            raise ValueError("incompatible adaptive conformal schema")
        if not isinstance(state["recent_scores"], list) or not isinstance(
            state["recent_row_ids"], list
        ):
            raise ValueError("invalid adaptive conformal state")
        return cls(
            coverage=float(state["coverage"]),
            max_scores=state["max_scores"],
            initial_scores=state["recent_scores"],
            observed_row_ids=state["recent_row_ids"],
        )
