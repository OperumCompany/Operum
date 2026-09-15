from __future__ import annotations

import hashlib
import inspect
import json
import statistics
from dataclasses import dataclass, field
from typing import Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from app.ml.evaluation import DEFAULT_EVALUATION_SEEDS, FINAL_HOLDOUT_DAYS, EvaluationPlan
from app.ml.feature_pipeline import FoldFeaturePipeline
from app.ml.gates_v2 import ProbabilisticGateDecision, evaluate_probabilistic_gates
from app.ml.metrics_v2 import (
    classification_metrics,
    group_stability,
    interval_metrics,
    origin_known_regimes,
    quantile_metrics,
    seed_stability,
)
from app.ml.package_v2 import (
    DirectionHead,
    FrozenCausalBaseline,
    ProbabilisticSlotPackage,
    ReturnHead,
    ValidatedModelConfig,
)
from app.ml.probabilistic import (
    CENTER_OBJECTIVES,
    HISTORY_POLICIES,
    QUANTILE_ALPHAS,
    QUANTILE_NAMES,
    AdaptiveConformalCalibrator,
    OOSBlend,
    TemporalPlattCalibrator,
    history_weights_for_origins,
    make_elastic_net,
    make_xgboost_center,
    make_xgboost_classifier,
    make_xgboost_quantile,
    ordered_quantiles,
)


_TARGET_HEADS = ("total", "price")


def _default_center_factory(
    *, objective, seed, n_estimators, validation, parameters
):
    overrides = dict(parameters)
    if validation:
        overrides["early_stopping_rounds"] = 20
    return make_xgboost_center(
        objective=objective,
        seed=seed,
        n_estimators=n_estimators,
        **overrides,
    )


def _default_quantile_factory(
    *, alpha, seed, n_estimators, validation, parameters
):
    overrides = dict(parameters)
    if validation:
        overrides["early_stopping_rounds"] = 20
    return make_xgboost_quantile(
        alpha=alpha,
        seed=seed,
        n_estimators=n_estimators,
        **overrides,
    )


def _default_classifier_factory(
    *, seed, n_estimators, validation, parameters
):
    overrides = dict(parameters)
    if validation:
        overrides["early_stopping_rounds"] = 20
    return make_xgboost_classifier(
        seed=seed,
        n_estimators=n_estimators,
        **overrides,
    )


def _default_elastic_factory(*, seed, parameters):
    return make_elastic_net(seed=seed, **dict(parameters))


@dataclass(frozen=True)
class EstimatorFactories:
    center: Callable[..., object] = _default_center_factory
    elastic_net: Callable[..., object] = _default_elastic_factory
    quantile: Callable[..., object] = _default_quantile_factory
    classifier: Callable[..., object] = _default_classifier_factory


@dataclass(frozen=True)
class ProbabilisticTrainingConfig:
    candidate_rounds: int = 300
    calibration_days: int = 126
    conformal_window: int = 126
    center_parameters: dict = field(
        default_factory=lambda: {
            "max_depth": 3,
            "learning_rate": 0.05,
            "min_child_weight": 8,
            "subsample": 0.80,
            "colsample_bytree": 0.75,
            "reg_alpha": 0.10,
            "reg_lambda": 8.0,
        }
    )
    quantile_parameters: dict = field(
        default_factory=lambda: {
            "max_depth": 3,
            "learning_rate": 0.05,
            "min_child_weight": 8,
            "subsample": 0.80,
            "colsample_bytree": 0.75,
            "reg_alpha": 0.10,
            "reg_lambda": 8.0,
        }
    )
    classifier_parameters: dict = field(
        default_factory=lambda: {
            "max_depth": 3,
            "learning_rate": 0.05,
            "min_child_weight": 8,
            "subsample": 0.80,
            "colsample_bytree": 0.75,
            "reg_alpha": 0.10,
            "reg_lambda": 8.0,
        }
    )
    elastic_parameters: dict = field(
        default_factory=lambda: {"alpha": 0.001, "l1_ratio": 0.50}
    )

    def __post_init__(self) -> None:
        if (
            not isinstance(self.candidate_rounds, int)
            or isinstance(self.candidate_rounds, bool)
            or self.candidate_rounds <= 0
        ):
            raise ValueError("candidate rounds must be a positive integer")
        if self.calibration_days != 126:
            raise ValueError("probability/blend calibration is locked to 126 trading dates")
        if self.conformal_window != 126:
            raise ValueError("adaptive conformal history is locked to 126 OOS rows")
        for parameters in (
            self.center_parameters,
            self.quantile_parameters,
            self.classifier_parameters,
            self.elastic_parameters,
        ):
            try:
                json.dumps(parameters, allow_nan=False)
            except (TypeError, ValueError) as exc:
                raise ValueError("estimator parameters must be JSON-safe") from exc


@dataclass(frozen=True)
class ProbabilisticTrainingResult:
    package: ProbabilisticSlotPackage
    selected_configurations: dict[str, ValidatedModelConfig]
    fold_diagnostics: tuple[dict, ...]
    oos_predictions: tuple[dict, ...]
    oos_provenance: dict
    metrics: dict
    gate_decision: ProbabilisticGateDecision


class MeanRegressorEnsemble:
    def __init__(self, models: Sequence[object], seeds: Sequence[int]):
        if not models or len(models) != len(seeds):
            raise ValueError("regression ensemble models and seeds must align")
        self.models = tuple(models)
        self.seeds = tuple(int(seed) for seed in seeds)

    def predict(self, matrix) -> np.ndarray:
        predictions = [np.asarray(model.predict(matrix), dtype=float) for model in self.models]
        if any(values.ndim != 1 or values.shape[0] != len(matrix) for values in predictions):
            raise ValueError("regression ensemble produced invalid predictions")
        result = np.mean(np.vstack(predictions), axis=0)
        if not np.all(np.isfinite(result)):
            raise ValueError("regression ensemble produced non-finite predictions")
        return result

    def predictions_by_seed(self, matrix) -> dict[int, np.ndarray]:
        return {
            seed: np.asarray(model.predict(matrix), dtype=float)
            for seed, model in zip(self.seeds, self.models)
        }


class MeanClassifierEnsemble:
    def __init__(self, models: Sequence[object], seeds: Sequence[int]):
        if not models or len(models) != len(seeds):
            raise ValueError("classifier ensemble models and seeds must align")
        self.models = tuple(models)
        self.seeds = tuple(int(seed) for seed in seeds)
        self.classes_ = np.array([0, 1])

    @staticmethod
    def _positive_probability(model, matrix) -> np.ndarray:
        values = np.asarray(model.predict_proba(matrix), dtype=float)
        if values.ndim != 2 or values.shape[0] != len(matrix) or values.shape[1] not in {1, 2}:
            raise ValueError("classifier ensemble produced invalid probabilities")
        if values.shape[1] == 2:
            return values[:, 1]
        classes = np.asarray(getattr(model, "classes_", [1]))
        return values[:, 0] if classes.size == 1 and classes[0] == 1 else 1.0 - values[:, 0]

    def predict_proba(self, matrix) -> np.ndarray:
        probability = np.mean(
            np.vstack([self._positive_probability(model, matrix) for model in self.models]),
            axis=0,
        )
        probability = np.clip(probability, 0.0, 1.0)
        return np.column_stack([1.0 - probability, probability])


class ConstantProbabilityClassifier:
    def __init__(self, probability_up: float):
        self.probability_up = float(probability_up)
        self.classes_ = np.array([0, 1])

    def fit(self, matrix, truth, **kwargs):
        return self

    def predict_proba(self, matrix) -> np.ndarray:
        probability = np.full(len(matrix), self.probability_up, dtype=float)
        return np.column_stack([1.0 - probability, probability])


@dataclass
class _FittedModels:
    center: MeanRegressorEnsemble
    elastic_net: object
    quantiles: dict[str, MeanRegressorEnsemble]


def _canonical_hash(value) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _target_column(head: str, horizon_days: int) -> str:
    return f"target_{head}_return_{horizon_days}"


def _row_ids(frame: pd.DataFrame) -> tuple[str, ...]:
    return tuple(
        f"{pd.Timestamp(row.date).isoformat()}|{row.ticker}|{row.Index}"
        for row in frame[["date", "ticker"]].itertuples(index=True)
    )


def _frame_for_indices(
    frame: pd.DataFrame, dates: Sequence[pd.Timestamp], start: int, end: int
) -> pd.DataFrame:
    if start < 0 or end < start or end >= len(dates):
        raise ValueError("invalid temporal boundary")
    selected = frame.loc[frame["date"].isin(dates[start : end + 1])].copy()
    return selected.sort_values(["date", "ticker"], kind="mergesort")


def _finite_target(frame: pd.DataFrame, column: str) -> np.ndarray:
    values = pd.to_numeric(frame[column], errors="coerce").to_numpy(dtype=float)
    if values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError(f"training boundary contains invalid target values: {column}")
    return values


def _fit_estimator(
    model,
    matrix,
    truth,
    *,
    sample_weight,
    validation_matrix=None,
    validation_truth=None,
) -> None:
    try:
        parameters = inspect.signature(model.fit).parameters
    except (TypeError, ValueError):
        parameters = {}
    accepts_kwargs = any(
        item.kind is inspect.Parameter.VAR_KEYWORD for item in parameters.values()
    )
    kwargs = {}
    if accepts_kwargs or "sample_weight" in parameters:
        kwargs["sample_weight"] = sample_weight
    if validation_matrix is not None and (accepts_kwargs or "eval_set" in parameters):
        kwargs["eval_set"] = [(validation_matrix, validation_truth)]
    if validation_matrix is not None and (accepts_kwargs or "verbose" in parameters):
        kwargs["verbose"] = False
    model.fit(matrix, truth, **kwargs)


def _best_iteration(model) -> int | None:
    try:
        value = getattr(model, "best_iteration", None)
    except (AttributeError, ValueError):
        return None
    return None if value is None else int(value)


def _validated_rounds(iterations: Sequence[int], fallback: int) -> int:
    if not iterations:
        return fallback
    return int(round(statistics.median(value + 1 for value in iterations)))


def _empty_evidence() -> dict:
    return {
        **{
            head: {
                (policy, objective): {
                    "mae": [],
                    "iterations": [],
                    "validation_ids": [],
                }
                for policy in HISTORY_POLICIES
                for objective in CENTER_OBJECTIVES
            }
            for head in _TARGET_HEADS
        },
        "quantile": {
            head: {
                policy: {
                    name: {"pinball": [], "iterations": [], "validation_ids": []}
                    for name in QUANTILE_NAMES
                }
                for policy in HISTORY_POLICIES
            }
            for head in _TARGET_HEADS
        },
        "classifier": {
            policy: {"brier": [], "iterations": [], "validation_ids": []}
            for policy in HISTORY_POLICIES
        },
    }


def _merge_evidence(destination: dict, source: dict) -> None:
    for head in _TARGET_HEADS:
        for key in destination[head]:
            for field_name in ("mae", "iterations", "validation_ids"):
                destination[head][key][field_name].extend(source[head][key][field_name])
        for policy in HISTORY_POLICIES:
            for name in QUANTILE_NAMES:
                for field_name in ("pinball", "iterations", "validation_ids"):
                    destination["quantile"][head][policy][name][field_name].extend(
                        source["quantile"][head][policy][name][field_name]
                    )
    for policy in HISTORY_POLICIES:
        for field_name in ("brier", "iterations", "validation_ids"):
            destination["classifier"][policy][field_name].extend(
                source["classifier"][policy][field_name]
            )


def _select_config(
    evidence: dict[tuple[str, str], dict],
    *,
    config: ProbabilisticTrainingConfig,
) -> ValidatedModelConfig:
    ranked = []
    for (policy, objective), values in evidence.items():
        if not values["mae"]:
            continue
        ranked.append(
            (
                float(np.mean(values["mae"])),
                HISTORY_POLICIES.index(policy),
                CENTER_OBJECTIVES.index(objective),
                policy,
                objective,
                values,
            )
        )
    if not ranked:
        raise ValueError("inner validation evidence is required")
    _, _, _, policy, objective, selected = min(ranked)
    return ValidatedModelConfig.create(
        model_type="center",
        objective=objective,
        n_estimators=_validated_rounds(selected["iterations"], config.candidate_rounds),
        parameters=config.center_parameters,
        history_policy=policy,
        validation_ids=tuple(selected["validation_ids"]),
        seeds=DEFAULT_EVALUATION_SEEDS,
    )


def _select_quantile_configs(
    evidence: dict[str, dict[str, dict]],
    *,
    selected_center: ValidatedModelConfig,
    config: ProbabilisticTrainingConfig,
) -> dict[str, ValidatedModelConfig]:
    selected = {}
    for name, alpha in zip(QUANTILE_NAMES, QUANTILE_ALPHAS):
        values = evidence[selected_center.history_policy][name]
        if not values["pinball"]:
            raise ValueError("inner quantile validation evidence is required")
        selected[name] = ValidatedModelConfig.create(
            model_type="quantile",
            objective="reg:quantileerror",
            n_estimators=_validated_rounds(
                values["iterations"], config.candidate_rounds
            ),
            parameters={**config.quantile_parameters, "quantile_alpha": alpha},
            history_policy=selected_center.history_policy,
            validation_ids=tuple(values["validation_ids"]),
            seeds=DEFAULT_EVALUATION_SEEDS,
        )
    return selected


def _select_direction_config(
    evidence: dict[str, dict],
    *,
    selected_center: ValidatedModelConfig,
    config: ProbabilisticTrainingConfig,
) -> ValidatedModelConfig:
    values = evidence[selected_center.history_policy]
    if not values["brier"]:
        raise ValueError("inner classifier validation evidence is required")
    return ValidatedModelConfig.create(
        model_type="classifier",
        objective="binary:logistic",
        n_estimators=_validated_rounds(values["iterations"], config.candidate_rounds),
        parameters=config.classifier_parameters,
        history_policy=selected_center.history_policy,
        validation_ids=tuple(values["validation_ids"]),
        seeds=DEFAULT_EVALUATION_SEEDS,
    )


def _tune_inner_boundaries(
    working: pd.DataFrame,
    *,
    dates: Sequence[pd.Timestamp],
    inner_folds,
    seeds: Sequence[int],
    horizon_days: int,
    pipeline_factory: Callable[[], FoldFeaturePipeline],
    factories: EstimatorFactories,
    config: ProbabilisticTrainingConfig,
) -> dict:
    evidence = _empty_evidence()
    for inner in inner_folds:
        if inner.validation_start - inner.train_end - 1 < horizon_days:
            raise ValueError("inner validation boundary is not horizon-purged")
        train = _frame_for_indices(working, dates, inner.train_start, inner.train_end)
        validation = _frame_for_indices(
            working, dates, inner.validation_start, inner.validation_end
        )
        pipeline = pipeline_factory()
        pipeline.fit(train)
        train_matrix = pipeline.transform(train)
        validation_matrix = pipeline.transform(validation)
        train_ids = _row_ids(train)
        validation_ids = _row_ids(validation)
        if set(train_ids).intersection(validation_ids):
            raise ValueError("inner model-fit and validation rows must be disjoint")
        for head in _TARGET_HEADS:
            train_truth = _finite_target(train, _target_column(head, horizon_days))
            validation_truth = _finite_target(
                validation, _target_column(head, horizon_days)
            )
            for policy in HISTORY_POLICIES:
                weights = history_weights_for_origins(train["date"], policy)
                for objective in CENTER_OBJECTIVES:
                    for seed in seeds:
                        model = factories.center(
                            objective=objective,
                            seed=seed,
                            n_estimators=config.candidate_rounds,
                            validation=True,
                            parameters=config.center_parameters,
                        )
                        _fit_estimator(
                            model,
                            train_matrix,
                            train_truth,
                            sample_weight=weights,
                            validation_matrix=validation_matrix,
                            validation_truth=validation_truth,
                        )
                        prediction = np.asarray(model.predict(validation_matrix), dtype=float)
                        if prediction.shape != validation_truth.shape or not np.all(
                            np.isfinite(prediction)
                        ):
                            raise ValueError("inner model produced invalid predictions")
                        bucket = evidence[head][(policy, objective)]
                        bucket["mae"].append(
                            float(np.mean(np.abs(prediction - validation_truth)))
                        )
                        iteration = _best_iteration(model)
                        if iteration is not None:
                            bucket["iterations"].append(iteration)
                        bucket["validation_ids"].extend(validation_ids)
                for name, alpha in zip(QUANTILE_NAMES, QUANTILE_ALPHAS):
                    for seed in seeds:
                        model = factories.quantile(
                            alpha=alpha,
                            seed=seed,
                            n_estimators=config.candidate_rounds,
                            validation=True,
                            parameters=config.quantile_parameters,
                        )
                        _fit_estimator(
                            model,
                            train_matrix,
                            train_truth,
                            sample_weight=weights,
                            validation_matrix=validation_matrix,
                            validation_truth=validation_truth,
                        )
                        prediction = np.asarray(
                            model.predict(validation_matrix), dtype=float
                        )
                        if prediction.shape != validation_truth.shape or not np.all(
                            np.isfinite(prediction)
                        ):
                            raise ValueError(
                                "inner quantile model produced invalid predictions"
                            )
                        error = validation_truth - prediction
                        pinball = float(
                            np.mean(
                                np.maximum(
                                    alpha * error, (alpha - 1.0) * error
                                )
                            )
                        )
                        bucket = evidence["quantile"][head][policy][name]
                        bucket["pinball"].append(pinball)
                        iteration = _best_iteration(model)
                        if iteration is not None:
                            bucket["iterations"].append(iteration)
                        bucket["validation_ids"].extend(validation_ids)

        train_direction = (
            _finite_target(train, _target_column("total", horizon_days)) > 0.0
        ).astype(int)
        validation_direction = (
            _finite_target(validation, _target_column("total", horizon_days)) > 0.0
        ).astype(int)
        for policy in HISTORY_POLICIES:
            weights = history_weights_for_origins(train["date"], policy)
            for seed in seeds:
                if np.unique(train_direction).size < 2:
                    model = ConstantProbabilityClassifier(float(train_direction[0]))
                else:
                    model = factories.classifier(
                        seed=seed,
                        n_estimators=config.candidate_rounds,
                        validation=True,
                        parameters=config.classifier_parameters,
                    )
                    _fit_estimator(
                        model,
                        train_matrix,
                        train_direction,
                        sample_weight=weights,
                        validation_matrix=validation_matrix,
                        validation_truth=validation_direction,
                    )
                probability = np.asarray(
                    model.predict_proba(validation_matrix), dtype=float
                )[:, 1]
                if probability.shape != validation_direction.shape or not np.all(
                    np.isfinite(probability)
                ):
                    raise ValueError(
                        "inner classifier produced invalid probabilities"
                    )
                bucket = evidence["classifier"][policy]
                bucket["brier"].append(
                    float(np.mean(np.square(probability - validation_direction)))
                )
                iteration = _best_iteration(model)
                if iteration is not None:
                    bucket["iterations"].append(iteration)
                bucket["validation_ids"].extend(validation_ids)
    return evidence


def _fit_regressor_models(
    matrix,
    truth,
    *,
    origins,
    seeds: Sequence[int],
    selected: ValidatedModelConfig,
    quantile_configs: Mapping[str, ValidatedModelConfig],
    factories: EstimatorFactories,
    config: ProbabilisticTrainingConfig,
) -> _FittedModels:
    weights = history_weights_for_origins(origins, selected.history_policy)
    center_models = []
    for seed in seeds:
        model = factories.center(
            objective=selected.objective,
            seed=seed,
            n_estimators=selected.n_estimators,
            validation=False,
            parameters=selected.parameters,
        )
        _fit_estimator(model, matrix, truth, sample_weight=weights)
        center_models.append(model)
    elastic = factories.elastic_net(seed=seeds[0], parameters=config.elastic_parameters)
    _fit_estimator(elastic, matrix, truth, sample_weight=weights)
    quantiles = {}
    for name, alpha in zip(QUANTILE_NAMES, QUANTILE_ALPHAS):
        quantile_config = quantile_configs[name]
        quantile_weights = history_weights_for_origins(
            origins, quantile_config.history_policy
        )
        models = []
        for seed in seeds:
            model = factories.quantile(
                alpha=alpha,
                seed=seed,
                n_estimators=quantile_config.n_estimators,
                validation=False,
                parameters=quantile_config.parameters,
            )
            _fit_estimator(
                model, matrix, truth, sample_weight=quantile_weights
            )
            models.append(model)
        quantiles[name] = MeanRegressorEnsemble(models, seeds)
    return _FittedModels(
        center=MeanRegressorEnsemble(center_models, seeds),
        elastic_net=elastic,
        quantiles=quantiles,
    )


def _fit_classifier(
    matrix,
    truth,
    *,
    origins,
    seeds: Sequence[int],
    direction_config: ValidatedModelConfig,
    factories: EstimatorFactories,
):
    labels = (np.asarray(truth, dtype=float) > 0.0).astype(int)
    if np.unique(labels).size < 2:
        return ConstantProbabilityClassifier(float(labels[0]))
    weights = history_weights_for_origins(
        origins, direction_config.history_policy
    )
    models = []
    for seed in seeds:
        model = factories.classifier(
            seed=seed,
            n_estimators=direction_config.n_estimators,
            validation=False,
            parameters=direction_config.parameters,
        )
        _fit_estimator(model, matrix, labels, sample_weight=weights)
        models.append(model)
    return MeanClassifierEnsemble(models, seeds)


def _baseline_candidates(frame: pd.DataFrame, horizon_days: int) -> dict[str, np.ndarray]:
    candidates = {
        "zero": FrozenCausalBaseline("zero", horizon_days).predict(frame),
        "drift": FrozenCausalBaseline("drift", horizon_days).predict(frame),
    }
    if {"benchmark_return_63", "beta_63"}.issubset(frame.columns):
        candidates["benchmark_beta"] = FrozenCausalBaseline(
            "benchmark_beta", horizon_days
        ).predict(frame)
    return candidates


def _select_baseline(
    truth: np.ndarray, frame: pd.DataFrame, horizon_days: int
) -> FrozenCausalBaseline:
    candidates = _baseline_candidates(frame, horizon_days)
    name = min(
        candidates,
        key=lambda candidate: (
            float(np.mean(np.abs(candidates[candidate] - truth))),
            candidate,
        ),
    )
    return FrozenCausalBaseline(name, horizon_days)


def _center_components(
    models: _FittedModels, matrix, raw_frame, baseline: FrozenCausalBaseline
) -> dict[str, np.ndarray]:
    return {
        "xgboost": np.asarray(models.center.predict(matrix), dtype=float),
        "elastic_net": np.asarray(models.elastic_net.predict(matrix), dtype=float),
        "baseline": baseline.predict(raw_frame),
    }


def _calibrate_head(
    models: _FittedModels,
    *,
    selected: ValidatedModelConfig,
    quantile_configs: Mapping[str, ValidatedModelConfig],
    config: ProbabilisticTrainingConfig,
    train_ids: Sequence[str],
    calibration_ids: Sequence[str],
    calibration_matrix,
    calibration_frame,
    calibration_truth,
    horizon_days: int,
) -> tuple[ReturnHead, dict]:
    baseline = _select_baseline(calibration_truth, calibration_frame, horizon_days)
    components = _center_components(models, calibration_matrix, calibration_frame, baseline)
    blend = OOSBlend.fit(
        calibration_truth,
        components,
        baseline_name="baseline",
        calibration_ids=calibration_ids,
        model_fit_ids=train_ids,
        sample_weight=history_weights_for_origins(
            calibration_frame["date"], selected.history_policy
        ),
    )
    raw_quantiles = ordered_quantiles(
        {
            name: model.predict(calibration_matrix)
            for name, model in models.quantiles.items()
        }
    )
    conformal = AdaptiveConformalCalibrator(
        coverage=0.80,
        max_scores=config.conformal_window,
    )
    lower, upper = conformal.calibrate_oos(
        truth=calibration_truth,
        lower=raw_quantiles["q10"],
        upper=raw_quantiles["q90"],
        row_ids=calibration_ids,
    )
    head = ReturnHead(
        xgboost_center=models.center,
        elastic_net=models.elastic_net,
        baseline=baseline,
        blend=blend,
        quantile_models=models.quantiles,
        conformal=conformal,
        center_config=selected,
        quantile_configs=dict(quantile_configs),
    )
    return head, {
        "center": blend.predict(components),
        "baseline": components["baseline"],
        "quantiles": raw_quantiles,
        "lower": lower,
        "upper": upper,
    }


def _calibrate_direction(
    classifier,
    *,
    direction_config: ValidatedModelConfig,
    train_ids,
    calibration_ids,
    calibration_matrix,
    calibration_truth,
) -> DirectionHead:
    raw = np.asarray(classifier.predict_proba(calibration_matrix), dtype=float)[:, 1]
    calibrator = TemporalPlattCalibrator.fit(
        raw,
        (np.asarray(calibration_truth) > 0.0).astype(int),
        calibration_ids=calibration_ids,
        model_fit_ids=train_ids,
    )
    return DirectionHead(
        classifier=classifier,
        calibrator=calibrator,
        config=direction_config,
    )


def _predict_head_oos(
    head: ReturnHead,
    *,
    matrix,
    raw_frame,
    truth,
    row_ids,
) -> dict:
    components = {
        "xgboost": head.xgboost_center.predict(matrix),
        "elastic_net": head.elastic_net.predict(matrix),
        "baseline": head.baseline.predict(raw_frame),
    }
    center = head.blend.predict(components)
    raw_quantiles = ordered_quantiles(
        {name: model.predict(matrix) for name, model in head.quantile_models.items()}
    )
    adaptive = AdaptiveConformalCalibrator.from_state(head.conformal.state())
    lower, upper = adaptive.calibrate_oos(
        truth=truth,
        lower=raw_quantiles["q10"],
        upper=raw_quantiles["q90"],
        row_ids=row_ids,
    )
    return {
        "center": center,
        "baseline": np.asarray(components["baseline"], dtype=float),
        "quantiles": raw_quantiles,
        "lower": lower,
        "upper": upper,
        "by_seed": head.xgboost_center.predictions_by_seed(matrix),
    }


def _sample_metrics(truth, prediction: dict, probability=None) -> tuple[dict, dict]:
    actual = np.asarray(truth, dtype=float)
    candidate = {
        "mae": float(np.mean(np.abs(np.asarray(prediction["center"]) - actual))),
        **quantile_metrics(actual, prediction["quantiles"]),
        **interval_metrics(
            actual,
            lower=prediction["lower"],
            upper=prediction["upper"],
            coverage=0.80,
        ),
    }
    baseline_values = np.asarray(prediction["baseline"], dtype=float)
    baseline_quantiles = {name: baseline_values for name in QUANTILE_NAMES}
    baseline = {
        "mae": float(np.mean(np.abs(baseline_values - actual))),
        **quantile_metrics(actual, baseline_quantiles),
        **interval_metrics(
            actual,
            lower=baseline_values,
            upper=baseline_values,
            coverage=0.80,
        ),
    }
    if probability is not None:
        labels = (actual > 0.0).astype(int)
        candidate.update(classification_metrics(labels, probability))
        baseline.update(classification_metrics(labels, (baseline_values > 0.0).astype(float)))
    return candidate, baseline


def _combine_head_metrics(total_metrics, price_metrics) -> dict:
    combined = dict(total_metrics)
    for name in ("mae", "pinball_mean", "winkler", "coverage"):
        combined[name] = float((total_metrics[name] + price_metrics[name]) / 2.0)
    return combined


def _aggregate_oos_metrics(records: Sequence[dict]) -> tuple[dict, dict]:
    truth_total = np.asarray([row["truth_total"] for row in records], dtype=float)
    truth_price = np.asarray([row["truth_price"] for row in records], dtype=float)
    total_prediction = {
        "center": np.asarray([row["total_center"] for row in records]),
        "baseline": np.asarray([row["total_baseline"] for row in records]),
        "quantiles": {
            name: np.asarray([row[f"total_{name}"] for row in records])
            for name in QUANTILE_NAMES
        },
        "lower": np.asarray([row["total_low"] for row in records]),
        "upper": np.asarray([row["total_high"] for row in records]),
    }
    price_prediction = {
        "center": np.asarray([row["price_center"] for row in records]),
        "baseline": np.asarray([row["price_baseline"] for row in records]),
        "quantiles": {
            name: np.asarray([row[f"price_{name}"] for row in records])
            for name in QUANTILE_NAMES
        },
        "lower": np.asarray([row["price_low"] for row in records]),
        "upper": np.asarray([row["price_high"] for row in records]),
    }
    probability = np.asarray([row["probability_up"] for row in records])
    total_candidate, total_baseline = _sample_metrics(
        truth_total, total_prediction, probability=probability
    )
    price_candidate, price_baseline = _sample_metrics(truth_price, price_prediction)
    return (
        _combine_head_metrics(total_candidate, price_candidate),
        _combine_head_metrics(total_baseline, price_baseline),
    )


def _validate_plan(plan: EvaluationPlan, *, horizon_days: int) -> None:
    if plan.horizon_days != horizon_days:
        raise ValueError("evaluation plan horizon does not match the slot")
    if plan.seeds != DEFAULT_EVALUATION_SEEDS:
        raise ValueError("probabilistic evaluation seeds are locked to (17, 42, 73)")
    if plan.holdout_end - plan.holdout_start + 1 != FINAL_HOLDOUT_DAYS:
        raise ValueError("probabilistic final holdout is locked to 126 dates")
    if not plan.outer_folds:
        raise ValueError("nested outer folds are required")
    previous_test_end = -1
    for outer in plan.outer_folds:
        indices = (
            outer.train_start,
            outer.train_end,
            outer.calibration_start,
            outer.calibration_end,
            outer.test_start,
            outer.test_end,
        )
        if (
            min(indices) < 0
            or max(indices) >= plan.holdout_start
            or outer.train_start > outer.train_end
            or outer.calibration_start > outer.calibration_end
            or outer.test_start > outer.test_end
        ):
            raise ValueError("invalid outer temporal boundary")
        if outer.train_end >= outer.calibration_start - horizon_days:
            raise ValueError("outer training boundary is not horizon-purged")
        if outer.calibration_end - outer.calibration_start + 1 != 126:
            raise ValueError("outer calibration boundary is locked to 126 dates")
        if outer.test_start != outer.calibration_end + 1:
            raise ValueError("outer test must immediately follow calibration")
        if outer.test_end - outer.test_start + 1 != horizon_days:
            raise ValueError("outer test boundary must equal the horizon")
        if outer.test_end >= plan.holdout_start:
            raise ValueError("outer test overlaps the final holdout")
        if outer.test_start <= previous_test_end:
            raise ValueError("outer test boundaries must not overlap")
        previous_test_end = outer.test_end
        if not outer.inner_folds:
            raise ValueError("each outer fold requires inner validation")
        for inner in outer.inner_folds:
            if (
                inner.train_start < outer.train_start
                or inner.train_end >= inner.validation_start - horizon_days
                or inner.validation_end > outer.train_end
                or inner.validation_end - inner.validation_start + 1 != horizon_days
            ):
                raise ValueError(
                    "inner temporal boundary must be purged and contained in outer training"
                )


def train_probabilistic_slot(
    frame: pd.DataFrame,
    *,
    asset_class: str,
    horizon_days: int,
    evaluation_plan: EvaluationPlan,
    pipeline_factory: Callable[[], FoldFeaturePipeline] = FoldFeaturePipeline,
    factories: EstimatorFactories | None = None,
    config: ProbabilisticTrainingConfig | None = None,
) -> ProbabilisticTrainingResult:
    factories = factories or EstimatorFactories()
    config = config or ProbabilisticTrainingConfig()
    _validate_plan(evaluation_plan, horizon_days=horizon_days)
    required = {
        "date",
        "ticker",
        "asset_class",
        _target_column("total", horizon_days),
        _target_column("price", horizon_days),
    }
    if not isinstance(frame, pd.DataFrame) or required.difference(frame.columns):
        raise ValueError(f"probabilistic training columns are missing: {sorted(required.difference(frame.columns))}")
    dates = tuple(pd.Timestamp(value) for value in evaluation_plan.dates)
    holdout_cutoff = dates[evaluation_plan.holdout_start]
    # Slice away the holdout before inspecting targets or transforming features.
    working = frame.loc[
        frame["asset_class"].astype(str).eq(asset_class)
        & (pd.to_datetime(frame["date"]) < holdout_cutoff)
    ].copy()
    working["date"] = pd.to_datetime(working["date"])
    working = working.sort_values(["date", "ticker"], kind="mergesort")
    if working.empty:
        raise ValueError("no pre-holdout rows are available for the requested slot")

    global_evidence = _empty_evidence()
    fold_diagnostics = []
    oos_records = []
    seed_predictions: dict[int, list[float]] = {seed: [] for seed in evaluation_plan.seeds}
    seed_truth: list[float] = []
    seed_baseline: list[float] = []

    for fold_index, outer in enumerate(evaluation_plan.outer_folds):
        local_evidence = _tune_inner_boundaries(
            working,
            dates=dates,
            inner_folds=outer.inner_folds,
            seeds=evaluation_plan.seeds,
            horizon_days=horizon_days,
            pipeline_factory=pipeline_factory,
            factories=factories,
            config=config,
        )
        _merge_evidence(global_evidence, local_evidence)
        selected = {
            head: _select_config(local_evidence[head], config=config)
            for head in _TARGET_HEADS
        }
        selected_quantiles = {
            head: _select_quantile_configs(
                local_evidence["quantile"][head],
                selected_center=selected[head],
                config=config,
            )
            for head in _TARGET_HEADS
        }
        selected_direction = _select_direction_config(
            local_evidence["classifier"],
            selected_center=selected["total"],
            config=config,
        )

        train = _frame_for_indices(working, dates, outer.train_start, outer.train_end)
        calibration = _frame_for_indices(
            working, dates, outer.calibration_start, outer.calibration_end
        )
        test = _frame_for_indices(working, dates, outer.test_start, outer.test_end)
        pipeline = pipeline_factory()
        pipeline.fit(train)
        train_matrix = pipeline.transform(train)
        calibration_matrix = pipeline.transform(calibration)
        test_matrix = pipeline.transform(test)
        train_ids = _row_ids(train)
        calibration_ids = _row_ids(calibration)
        test_ids = _row_ids(test)
        if set(train_ids).intersection(calibration_ids) or set(calibration_ids).intersection(test_ids):
            raise ValueError("outer model-fit, calibration and test rows must be disjoint")

        models = {}
        heads = {}
        calibration_predictions = {}
        test_predictions = {}
        for head_name in _TARGET_HEADS:
            train_truth = _finite_target(train, _target_column(head_name, horizon_days))
            calibration_truth = _finite_target(
                calibration, _target_column(head_name, horizon_days)
            )
            test_truth = _finite_target(test, _target_column(head_name, horizon_days))
            models[head_name] = _fit_regressor_models(
                train_matrix,
                train_truth,
                origins=train["date"],
                seeds=evaluation_plan.seeds,
                selected=selected[head_name],
                quantile_configs=selected_quantiles[head_name],
                factories=factories,
                config=config,
            )
            heads[head_name], calibration_predictions[head_name] = _calibrate_head(
                models[head_name],
                selected=selected[head_name],
                quantile_configs=selected_quantiles[head_name],
                config=config,
                train_ids=train_ids,
                calibration_ids=calibration_ids,
                calibration_matrix=calibration_matrix,
                calibration_frame=calibration,
                calibration_truth=calibration_truth,
                horizon_days=horizon_days,
            )
            test_predictions[head_name] = _predict_head_oos(
                heads[head_name],
                matrix=test_matrix,
                raw_frame=test,
                truth=test_truth,
                row_ids=test_ids,
            )

        total_train_truth = _finite_target(train, _target_column("total", horizon_days))
        total_calibration_truth = _finite_target(
            calibration, _target_column("total", horizon_days)
        )
        total_test_truth = _finite_target(test, _target_column("total", horizon_days))
        classifier = _fit_classifier(
            train_matrix,
            total_train_truth,
            origins=train["date"],
            seeds=evaluation_plan.seeds,
            direction_config=selected_direction,
            factories=factories,
        )
        direction = _calibrate_direction(
            classifier,
            direction_config=selected_direction,
            train_ids=train_ids,
            calibration_ids=calibration_ids,
            calibration_matrix=calibration_matrix,
            calibration_truth=total_calibration_truth,
        )
        probability = direction.calibrator.predict(
            np.asarray(classifier.predict_proba(test_matrix), dtype=float)[:, 1]
        )

        total_candidate, total_baseline_metrics = _sample_metrics(
            total_test_truth,
            test_predictions["total"],
            probability=probability,
        )
        price_test_truth = _finite_target(test, _target_column("price", horizon_days))
        price_candidate, price_baseline_metrics = _sample_metrics(
            price_test_truth, test_predictions["price"]
        )
        fold_diagnostics.append(
            {
                "fold_index": fold_index,
                "train_end": pd.Timestamp(dates[outer.train_end]).isoformat(),
                "calibration_start": pd.Timestamp(dates[outer.calibration_start]).isoformat(),
                "calibration_end": pd.Timestamp(dates[outer.calibration_end]).isoformat(),
                "test_start": pd.Timestamp(dates[outer.test_start]).isoformat(),
                "test_end": pd.Timestamp(dates[outer.test_end]).isoformat(),
                "selected_configurations": {
                    "center": {
                        name: value.state() for name, value in selected.items()
                    },
                    "quantile": {
                        head: {
                            name: value.state()
                            for name, value in selected_quantiles[head].items()
                        }
                        for head in _TARGET_HEADS
                    },
                    "direction": selected_direction.state(),
                },
                "total": {"candidate": total_candidate, "baseline": total_baseline_metrics},
                "price": {"candidate": price_candidate, "baseline": price_baseline_metrics},
            }
        )

        for position, (row, row_id) in enumerate(zip(test.itertuples(), test_ids)):
            record = {
                "row_id": row_id,
                "date": pd.Timestamp(row.date).isoformat(),
                "ticker": str(row.ticker),
                "split": "outer_test",
                "fold_index": fold_index,
                "seeds": list(evaluation_plan.seeds),
                "truth_total": float(total_test_truth[position]),
                "truth_price": float(price_test_truth[position]),
                "probability_up": float(probability[position]),
                "total_center": float(test_predictions["total"]["center"][position]),
                "total_baseline": float(test_predictions["total"]["baseline"][position]),
                "total_low": float(test_predictions["total"]["lower"][position]),
                "total_high": float(test_predictions["total"]["upper"][position]),
                "price_center": float(test_predictions["price"]["center"][position]),
                "price_baseline": float(test_predictions["price"]["baseline"][position]),
                "price_low": float(test_predictions["price"]["lower"][position]),
                "price_high": float(test_predictions["price"]["upper"][position]),
            }
            for name in QUANTILE_NAMES:
                record[f"total_{name}"] = float(
                    test_predictions["total"]["quantiles"][name][position]
                )
                record[f"price_{name}"] = float(
                    test_predictions["price"]["quantiles"][name][position]
                )
            oos_records.append(record)
        seed_truth.extend(total_test_truth.tolist())
        seed_baseline.extend(test_predictions["total"]["baseline"].tolist())
        for seed in evaluation_plan.seeds:
            seed_predictions[seed].extend(
                test_predictions["total"]["by_seed"][seed].tolist()
            )

    selected_final = {
        head: _select_config(global_evidence[head], config=config) for head in _TARGET_HEADS
    }
    selected_final_quantiles = {
        head: _select_quantile_configs(
            global_evidence["quantile"][head],
            selected_center=selected_final[head],
            config=config,
        )
        for head in _TARGET_HEADS
    }
    selected_final_direction = _select_direction_config(
        global_evidence["classifier"],
        selected_center=selected_final["total"],
        config=config,
    )
    calibration_start = evaluation_plan.holdout_start - config.calibration_days
    calibration_train_end = calibration_start - horizon_days - 1
    final_train_end = evaluation_plan.holdout_start - horizon_days - 1
    if calibration_train_end < 0:
        raise ValueError("insufficient history for disjoint final calibration")
    package_train = _frame_for_indices(working, dates, 0, calibration_train_end)
    package_calibration = _frame_for_indices(
        working, dates, calibration_start, evaluation_plan.holdout_start - 1
    )
    calibration_pipeline = pipeline_factory()
    calibration_pipeline.fit(package_train)
    package_train_matrix = calibration_pipeline.transform(package_train)
    package_calibration_matrix = calibration_pipeline.transform(package_calibration)
    package_train_ids = _row_ids(package_train)
    package_calibration_ids = _row_ids(package_calibration)

    calibration_heads = {}
    for head_name in _TARGET_HEADS:
        calibration_models = _fit_regressor_models(
            package_train_matrix,
            _finite_target(package_train, _target_column(head_name, horizon_days)),
            origins=package_train["date"],
            seeds=evaluation_plan.seeds,
            selected=selected_final[head_name],
            quantile_configs=selected_final_quantiles[head_name],
            factories=factories,
            config=config,
        )
        calibration_heads[head_name], _ = _calibrate_head(
            calibration_models,
            selected=selected_final[head_name],
            quantile_configs=selected_final_quantiles[head_name],
            config=config,
            train_ids=package_train_ids,
            calibration_ids=package_calibration_ids,
            calibration_matrix=package_calibration_matrix,
            calibration_frame=package_calibration,
            calibration_truth=_finite_target(
                package_calibration, _target_column(head_name, horizon_days)
            ),
            horizon_days=horizon_days,
        )
    calibration_classifier = _fit_classifier(
        package_train_matrix,
        _finite_target(package_train, _target_column("total", horizon_days)),
        origins=package_train["date"],
        seeds=evaluation_plan.seeds,
        direction_config=selected_final_direction,
        factories=factories,
    )
    calibrated_direction = _calibrate_direction(
        calibration_classifier,
        direction_config=selected_final_direction,
        train_ids=package_train_ids,
        calibration_ids=package_calibration_ids,
        calibration_matrix=package_calibration_matrix,
        calibration_truth=_finite_target(
            package_calibration, _target_column("total", horizon_days)
        ),
    )

    final_history = _frame_for_indices(working, dates, 0, final_train_end)
    final_pipeline = pipeline_factory()
    final_pipeline.fit(final_history)
    final_matrix = final_pipeline.transform(final_history)
    final_models = {
        head: _fit_regressor_models(
            final_matrix,
            _finite_target(final_history, _target_column(head, horizon_days)),
            origins=final_history["date"],
            seeds=evaluation_plan.seeds,
            selected=selected_final[head],
            quantile_configs=selected_final_quantiles[head],
            factories=factories,
            config=config,
        )
        for head in _TARGET_HEADS
    }
    final_classifier = _fit_classifier(
        final_matrix,
        _finite_target(final_history, _target_column("total", horizon_days)),
        origins=final_history["date"],
        seeds=evaluation_plan.seeds,
        direction_config=selected_final_direction,
        factories=factories,
    )

    stability = seed_stability(
        seed_truth,
        seed_predictions,
        baseline_prediction=seed_baseline,
    )
    fold_rows = [
        {
            "candidate_mae": diagnostic["total"]["candidate"]["mae"],
            "baseline_mae": diagnostic["total"]["baseline"]["mae"],
        }
        for diagnostic in fold_diagnostics
    ]
    fold_ratios = [
        row["candidate_mae"] / max(row["baseline_mae"], 1e-12) for row in fold_rows
    ]
    package = ProbabilisticSlotPackage(
        asset_class=asset_class,
        horizon_days=horizon_days,
        pipeline=final_pipeline,
        direction=DirectionHead(
            classifier=final_classifier,
            calibrator=calibrated_direction.calibrator,
            config=calibrated_direction.config,
        ),
        total=ReturnHead(
            xgboost_center=final_models["total"].center,
            elastic_net=final_models["total"].elastic_net,
            baseline=calibration_heads["total"].baseline,
            blend=calibration_heads["total"].blend,
            quantile_models=final_models["total"].quantiles,
            conformal=calibration_heads["total"].conformal,
            center_config=selected_final["total"],
            quantile_configs=calibration_heads["total"].quantile_configs,
        ),
        price=ReturnHead(
            xgboost_center=final_models["price"].center,
            elastic_net=final_models["price"].elastic_net,
            baseline=calibration_heads["price"].baseline,
            blend=calibration_heads["price"].blend,
            quantile_models=final_models["price"].quantiles,
            conformal=calibration_heads["price"].conformal,
            center_config=selected_final["price"],
            quantile_configs=calibration_heads["price"].quantile_configs,
        ),
        stability={
            "seed": float(np.clip(1.0 / (1.0 + stability["prediction_disagreement"]), 0.0, 1.0)),
            "fold": float(np.clip(1.0 / (1.0 + np.std(fold_ratios)), 0.0, 1.0)),
        },
    )
    package.validate()

    oos_candidate, oos_baseline = _aggregate_oos_metrics(oos_records)
    oos_frame = pd.DataFrame(oos_records)
    development_rows = working.loc[working["date"].isin(pd.to_datetime(oos_frame["date"]))]
    regimes = origin_known_regimes(working).loc[development_rows.index]
    regime_metrics = group_stability(
        oos_frame["truth_total"],
        oos_frame["total_center"],
        oos_frame["total_baseline"],
        regimes.to_numpy(),
        min_observations=100,
    )
    asset_metrics = group_stability(
        oos_frame["truth_total"],
        oos_frame["total_center"],
        oos_frame["total_baseline"],
        oos_frame["ticker"],
    )
    seed_rows = [
        {
            "seed": seed,
            "candidate_mae": values["mae"],
            "baseline_mae": stability["baseline_mae"],
        }
        for seed, values in stability["per_seed"].items()
    ]
    regime_rows = [
        {"name": name, **values} for name, values in regime_metrics.items()
    ]
    gate_decision = evaluate_probabilistic_gates(
        oos={"candidate": oos_candidate, "baseline": oos_baseline},
        holdout=None,
        folds=fold_rows,
        regimes=regime_rows,
        seeds=seed_rows,
    )
    provenance = {
        "schema_version": "operum-oos-provenance-v1",
        "source": "nested_outer_test",
        "row_count": len(oos_records),
        "row_ids_hash": _canonical_hash([row["row_id"] for row in oos_records]),
        "splits": ["outer_test"],
        "holdout_status": "not_accessed_by_task_4",
    }
    metrics = {
        "oos": {"candidate": oos_candidate, "baseline": oos_baseline},
        "fold": fold_rows,
        "asset": asset_metrics,
        "regime": regime_metrics,
        "seed": stability,
        "holdout": "pending_task_1_finalization",
    }
    return ProbabilisticTrainingResult(
        package=package,
        selected_configurations=selected_final,
        fold_diagnostics=tuple(fold_diagnostics),
        oos_predictions=tuple(oos_records),
        oos_provenance=provenance,
        metrics=metrics,
        gate_decision=gate_decision,
    )
