from __future__ import annotations

import json
import inspect
import statistics
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import joblib
import numpy as np
import pandas as pd

from app.ml.baselines import evaluate_selected_baseline, select_baseline
from app.ml.calibration import calibrate_interval, evaluate_interval
from app.ml.evaluation import (
    DEFAULT_EVALUATION_SEEDS,
    FINAL_HOLDOUT_DAYS,
    EvaluationConfig,
    build_evaluation_plan,
)
from app.ml.experiments import (
    ExperimentRecord,
    OOSPrediction,
    claim_holdout_access,
    config_hash,
    write_oos_predictions,
)
from app.ml.metrics import compute_regression_metrics
from app.ml.validation import evaluate_promotion_gate


def select_best_baseline(truth, predictions: dict[str, np.ndarray]) -> tuple[str, np.ndarray, dict]:
    """Compatibility wrapper for callers that select and evaluate on one sample."""
    selection = select_baseline(truth, predictions)
    evaluated = evaluate_selected_baseline(selection, truth, predictions)
    return evaluated.name, evaluated.predictions, evaluated.metrics


@dataclass(frozen=True)
class TrainingConfig:
    min_train_days: int = 504
    validation_days: int = 63
    embargo_days: int = 63
    holdout_days: int = FINAL_HOLDOUT_DAYS
    step_days: int = 21
    calibration_days: int = 126
    seeds: tuple[int, ...] = DEFAULT_EVALUATION_SEEDS


@dataclass(frozen=True)
class ModelTrainingResult:
    model_version: str
    status: str
    promotion_eligible: bool
    asset_class: str
    horizon_days: int
    dataset_hash: str
    feature_columns: tuple[str, ...]
    artifact_path: Path
    metadata_path: Path
    metrics: dict


_NON_FEATURE_COLUMNS = {
    "date",
    "ticker",
    "asset_class",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "currency",
    "sector",
}


def _feature_columns(frame: pd.DataFrame) -> tuple[str, ...]:
    columns = []
    for column in frame.columns:
        if column in _NON_FEATURE_COLUMNS or column.startswith("target_"):
            continue
        if pd.api.types.is_numeric_dtype(frame[column]):
            columns.append(column)
    if not columns:
        raise ValueError("Nenhuma feature numerica disponivel")
    return tuple(columns)


def _prepare_matrix(
    frame: pd.DataFrame,
    columns: tuple[str, ...],
    medians: dict[str, float] | None = None,
) -> tuple[pd.DataFrame, dict[str, float]]:
    matrix = frame.loc[:, list(columns)].replace([np.inf, -np.inf], np.nan).astype(float)
    if medians is None:
        medians = {column: float(matrix[column].median()) if matrix[column].notna().any() else 0.0 for column in columns}
    return matrix.fillna(medians), medians


def xgboost_candidate_params() -> tuple[dict, ...]:
    base = {
        "n_estimators": 800,
        "objective": "reg:squarederror",
        "random_state": 42,
        "n_jobs": max(1, min(6, __import__("os").cpu_count() or 1)),
        "early_stopping_rounds": 30,
    }
    variations = (
        {"max_depth": 2, "learning_rate": 0.03, "min_child_weight": 8, "subsample": 0.75, "colsample_bytree": 0.70, "reg_alpha": 0.0, "reg_lambda": 5.0},
        {"max_depth": 3, "learning_rate": 0.03, "min_child_weight": 10, "subsample": 0.80, "colsample_bytree": 0.75, "reg_alpha": 0.1, "reg_lambda": 8.0},
        {"max_depth": 4, "learning_rate": 0.02, "min_child_weight": 12, "subsample": 0.80, "colsample_bytree": 0.70, "reg_alpha": 0.5, "reg_lambda": 10.0},
        {"max_depth": 3, "learning_rate": 0.05, "min_child_weight": 8, "subsample": 0.70, "colsample_bytree": 0.80, "reg_alpha": 1.0, "reg_lambda": 5.0},
    )
    return tuple({**base, **variation} for variation in variations)


def _default_estimator_factory(
    params: dict | None = None,
    *,
    seed: int = 42,
    n_estimators: int | None = None,
):
    import xgboost as xgb

    selected = dict(params or xgboost_candidate_params()[0])
    selected["random_state"] = seed
    if n_estimators is not None:
        selected["n_estimators"] = n_estimators
        selected.pop("early_stopping_rounds", None)
    return xgb.XGBRegressor(**selected)


def _fit_model(model, X_train, y_train, X_validation=None, y_validation=None) -> None:
    if X_validation is not None and model.__class__.__module__.startswith("xgboost"):
        model.fit(X_train, y_train, eval_set=[(X_validation, y_validation)], verbose=False)
        return
    model.fit(X_train, y_train)


def _baseline_predictions(frame: pd.DataFrame, horizon_days: int) -> dict[str, np.ndarray]:
    size = len(frame)
    drift_column = "return_63" if "return_63" in frame else "return_21" if "return_21" in frame else None
    if drift_column:
        drift = pd.to_numeric(frame[drift_column], errors="coerce").fillna(0.0).to_numpy(dtype=float)
        drift = np.clip(drift * (horizon_days / int(drift_column.rsplit("_", 1)[1])), -0.30, 0.30)
    else:
        drift = np.zeros(size)
    predictions = {"zero": np.zeros(size), "drift": drift}
    if {"benchmark_return_63", "beta_63"}.issubset(frame.columns):
        benchmark = pd.to_numeric(frame["benchmark_return_63"], errors="coerce").fillna(0.0).to_numpy()
        beta = pd.to_numeric(frame["beta_63"], errors="coerce").fillna(1.0).to_numpy()
        predictions["benchmark_beta"] = np.clip(benchmark * beta * (horizon_days / 63), -0.30, 0.30)
    return predictions


def _custom_estimator(
    factory: Callable[..., object],
    *,
    params: dict | None = None,
    seed: int,
    n_estimators: int | None = None,
):
    parameters = inspect.signature(factory).parameters.values()
    accepts_kwargs = any(item.kind is inspect.Parameter.VAR_KEYWORD for item in parameters)
    names = {item.name for item in parameters}
    kwargs = {}
    if accepts_kwargs or "params" in names:
        kwargs["params"] = params
    if accepts_kwargs or "seed" in names:
        kwargs["seed"] = seed
    if accepts_kwargs or "n_estimators" in names:
        kwargs["n_estimators"] = n_estimators
    return factory(**kwargs)


def _factory_accepts(factory: Callable[..., object], name: str) -> bool:
    parameters = inspect.signature(factory).parameters.values()
    return any(item.kind is inspect.Parameter.VAR_KEYWORD for item in parameters) or any(
        item.name == name for item in parameters
    )


def _best_iteration(model) -> int | None:
    value = getattr(model, "best_iteration", None)
    if value is None:
        return None
    return int(value)


def _validated_rounds(best_iterations: list[int]) -> int | None:
    if not best_iterations:
        return None
    return int(round(statistics.median(value + 1 for value in best_iterations)))


def _mean_metrics(items: list[dict[str, float]]) -> dict[str, float]:
    return {
        key: float(np.mean([item[key] for item in items]))
        for key in ("mae", "rmse", "directional_accuracy")
    }


def _frame_for_indices(frame: pd.DataFrame, dates, start: int, end: int) -> pd.DataFrame:
    return frame.loc[frame["date"].isin(dates[start : end + 1])]


def _oos_records(
    frame: pd.DataFrame,
    *,
    split: str,
    fold_index: int | None,
    seeds: tuple[int, ...],
    truth: np.ndarray,
    prediction: np.ndarray,
    baseline_name: str,
    baseline_prediction: np.ndarray,
    radius: float,
) -> list[OOSPrediction]:
    return [
        OOSPrediction(
            date=pd.Timestamp(row.date).isoformat(),
            ticker=str(row.ticker),
            split=split,
            fold_index=fold_index,
            seeds=seeds,
            truth=float(truth[index]),
            prediction=float(prediction[index]),
            baseline_name=baseline_name,
            baseline_prediction=float(baseline_prediction[index]),
            interval_low=float(prediction[index] - radius),
            interval_high=float(prediction[index] + radius),
        )
        for index, row in enumerate(frame[["date", "ticker"]].itertuples(index=False))
    ]


def train_pooled_horizon(
    frame: pd.DataFrame,
    *,
    asset_class: str,
    horizon_days: int,
    dataset_hash: str,
    artifact_root: str | Path,
    config: TrainingConfig | None = None,
    estimator_factory: Callable[..., object] | None = None,
) -> ModelTrainingResult:
    config = config or TrainingConfig()
    target_column = f"target_return_{horizon_days}"
    if target_column not in frame:
        raise ValueError(f"Alvo ausente: {target_column}")
    working = frame.loc[frame["asset_class"] == asset_class].copy()
    working["date"] = pd.to_datetime(working["date"])
    working = working.loc[pd.to_numeric(working[target_column], errors="coerce").notna()].copy()
    if working.empty:
        raise ValueError(f"Sem amostras para {asset_class}/{horizon_days}d")
    features = _feature_columns(working)
    unique_dates = pd.DatetimeIndex(working["date"].sort_values().unique())
    evaluation_config = EvaluationConfig(
        min_train_days=config.min_train_days,
        calibration_days=config.calibration_days,
        holdout_days=config.holdout_days,
        seeds=config.seeds,
    )
    plan = build_evaluation_plan(
        unique_dates,
        horizon_days=horizon_days,
        config=evaluation_config,
    )
    if not plan.outer_folds:
        raise ValueError("Historico insuficiente para avaliacao temporal v2")

    fold_metrics: list[dict[str, float]] = []
    baseline_fold_metrics: list[dict[str, float]] = []
    fold_coverages: list[float] = []
    fold_diagnostics: list[dict] = []
    oos: list[OOSPrediction] = []
    best_iterations: list[int] = []
    parameter_evidence: dict[str, dict] = {}
    tunes_parameters = estimator_factory is None or _factory_accepts(estimator_factory, "params")

    for fold_index, split in enumerate(plan.outer_folds):
        latest_inner = split.inner_folds[-1]
        tuning_train = _frame_for_indices(
            working, unique_dates, latest_inner.train_start, latest_inner.train_end
        )
        tuning_validation = _frame_for_indices(
            working, unique_dates, latest_inner.validation_start, latest_inner.validation_end
        )
        X_tuning, tuning_medians = _prepare_matrix(tuning_train, features)
        X_tuning_validation, _ = _prepare_matrix(tuning_validation, features, tuning_medians)
        y_tuning = tuning_train[target_column].to_numpy(dtype=float)
        y_tuning_validation = tuning_validation[target_column].to_numpy(dtype=float)
        tuning_lower, tuning_upper = np.quantile(y_tuning, [0.005, 0.995])

        fold_params = None
        fold_best_iterations: list[int] = []
        if tunes_parameters:
            tuning_results = []
            for params in xgboost_candidate_params():
                candidate_metrics = []
                candidate_iterations = []
                for seed in plan.seeds:
                    candidate_model = (
                        _default_estimator_factory(params, seed=seed)
                        if estimator_factory is None
                        else _custom_estimator(
                            estimator_factory,
                            params=params,
                            seed=seed,
                        )
                    )
                    _fit_model(
                        candidate_model,
                        X_tuning,
                        np.clip(y_tuning, tuning_lower, tuning_upper),
                        X_tuning_validation,
                        y_tuning_validation,
                    )
                    candidate_prediction = np.asarray(
                        candidate_model.predict(X_tuning_validation), dtype=float
                    )
                    candidate_metrics.append(
                        compute_regression_metrics(y_tuning_validation, candidate_prediction)["mae"]
                    )
                    iteration = _best_iteration(candidate_model)
                    if iteration is not None:
                        candidate_iterations.append(iteration)
                tuning_results.append(
                    (float(np.mean(candidate_metrics)), params, candidate_iterations)
                )
                evidence_key = config_hash(params)
                evidence = parameter_evidence.setdefault(
                    evidence_key,
                    {"params": params, "mae": [], "best_iterations": []},
                )
                evidence["mae"].extend(candidate_metrics)
                evidence["best_iterations"].extend(candidate_iterations)
            _, fold_params, fold_best_iterations = min(
                tuning_results,
                key=lambda item: (item[0], config_hash(item[1])),
            )
        else:
            for seed in plan.seeds:
                tuning_model = _custom_estimator(estimator_factory, seed=seed)
                _fit_model(
                    tuning_model,
                    X_tuning,
                    np.clip(y_tuning, tuning_lower, tuning_upper),
                    X_tuning_validation,
                    y_tuning_validation,
                )
                iteration = _best_iteration(tuning_model)
                if iteration is not None:
                    fold_best_iterations.append(iteration)

        if not tunes_parameters:
            best_iterations.extend(fold_best_iterations)
        fold_rounds = _validated_rounds(fold_best_iterations)
        train = _frame_for_indices(working, unique_dates, split.train_start, split.train_end)
        calibration = _frame_for_indices(
            working, unique_dates, split.calibration_start, split.calibration_end
        )
        test = _frame_for_indices(working, unique_dates, split.test_start, split.test_end)
        X_train, medians = _prepare_matrix(train, features)
        X_calibration, _ = _prepare_matrix(calibration, features, medians)
        X_test, _ = _prepare_matrix(test, features, medians)
        y_train = train[target_column].to_numpy(dtype=float)
        y_calibration = calibration[target_column].to_numpy(dtype=float)
        y_test = test[target_column].to_numpy(dtype=float)
        lower, upper = np.quantile(y_train, [0.005, 0.995])

        calibration_predictions = []
        test_predictions = []
        for seed in plan.seeds:
            model = (
                _custom_estimator(
                    estimator_factory,
                    params=fold_params,
                    seed=seed,
                    n_estimators=fold_rounds,
                )
                if estimator_factory is not None
                else _default_estimator_factory(
                    fold_params,
                    seed=seed,
                    n_estimators=fold_rounds,
                )
            )
            _fit_model(model, X_train, np.clip(y_train, lower, upper))
            calibration_predictions.append(np.asarray(model.predict(X_calibration), dtype=float))
            test_predictions.append(np.asarray(model.predict(X_test), dtype=float))

        calibration_prediction = np.mean(calibration_predictions, axis=0)
        test_prediction = np.mean(test_predictions, axis=0)
        interval_calibration = calibrate_interval(
            truth=y_calibration,
            prediction=calibration_prediction,
            coverage=0.80,
        )
        interval_evaluation = evaluate_interval(
            interval_calibration,
            truth=y_test,
            prediction=test_prediction,
        )
        baseline_selection = select_baseline(
            y_calibration,
            _baseline_predictions(calibration, horizon_days),
        )
        baseline_evaluation = evaluate_selected_baseline(
            baseline_selection,
            y_test,
            _baseline_predictions(test, horizon_days),
        )
        candidate_metrics = compute_regression_metrics(y_test, test_prediction)
        fold_metrics.append(candidate_metrics)
        baseline_fold_metrics.append(baseline_evaluation.metrics)
        fold_coverages.append(interval_evaluation.coverage)
        fold_diagnostics.append(
            {
                "fold_index": fold_index,
                "train_end": pd.Timestamp(unique_dates[split.train_end]).isoformat(),
                "calibration_start": pd.Timestamp(unique_dates[split.calibration_start]).isoformat(),
                "calibration_end": pd.Timestamp(unique_dates[split.calibration_end]).isoformat(),
                "test_start": pd.Timestamp(unique_dates[split.test_start]).isoformat(),
                "test_end": pd.Timestamp(unique_dates[split.test_end]).isoformat(),
                "inner_validation_end": pd.Timestamp(
                    unique_dates[latest_inner.validation_end]
                ).isoformat(),
                "selected_params": fold_params,
                "baseline_name": baseline_selection.name,
                "best_iterations": fold_best_iterations,
                "validated_boosting_rounds": fold_rounds,
                "interval_radius": interval_calibration.interval.radius,
                "candidate_metrics": candidate_metrics,
                "baseline_metrics": baseline_evaluation.metrics,
                "interval_coverage": interval_evaluation.coverage,
            }
        )
        oos.extend(
            _oos_records(
                test,
                split="outer_test",
                fold_index=fold_index,
                seeds=plan.seeds,
                truth=y_test,
                prediction=test_prediction,
                baseline_name=baseline_evaluation.name,
                baseline_prediction=baseline_evaluation.predictions,
                radius=interval_calibration.interval.radius,
            )
        )

    mean_candidate = _mean_metrics(fold_metrics)
    mean_baseline = _mean_metrics(baseline_fold_metrics)
    validation_coverage = float(np.mean(fold_coverages))
    selected_params = None
    validated_configurations = []
    if parameter_evidence:
        ranked_evidence = []
        for evidence_key, evidence in parameter_evidence.items():
            mean_mae = float(np.mean(evidence["mae"]))
            rounds = _validated_rounds(evidence["best_iterations"])
            validated_configurations.append(
                {
                    "params": evidence["params"],
                    "mean_inner_mae": mean_mae,
                    "best_iterations": evidence["best_iterations"],
                    "boosting_rounds": rounds,
                }
            )
            ranked_evidence.append((mean_mae, evidence_key, evidence))
        _, _, selected_evidence = min(ranked_evidence, key=lambda item: (item[0], item[1]))
        selected_params = selected_evidence["params"]
        best_iterations = list(selected_evidence["best_iterations"])
    validated_rounds = _validated_rounds(best_iterations)

    effective_config = {
        "min_train_days": config.min_train_days,
        "embargo_days": horizon_days,
        "outer_test_days": horizon_days,
        "outer_step_days": horizon_days,
        "inner_validation_days": horizon_days,
        "inner_step_days": horizon_days,
        "calibration_days": config.calibration_days,
        "holdout_days": config.holdout_days,
        "seeds": list(config.seeds),
    }
    selected_configuration_hash = config_hash(
        {
            "evaluation": effective_config,
            "selected_params": selected_params,
            "validated_boosting_rounds": validated_rounds,
        }
    )
    holdout_access = claim_holdout_access(
        artifact_root,
        dataset_hash=dataset_hash,
        asset_class=asset_class,
        horizon_days=horizon_days,
        configuration_hash=selected_configuration_hash,
        holdout_days=config.holdout_days,
    )

    holdout_calibration_start = plan.holdout_start - config.calibration_days
    holdout_train_end = holdout_calibration_start - horizon_days - 1
    pre_holdout = _frame_for_indices(working, unique_dates, 0, holdout_train_end)
    holdout_calibration = _frame_for_indices(
        working,
        unique_dates,
        holdout_calibration_start,
        plan.holdout_start - 1,
    )
    holdout = _frame_for_indices(
        working,
        unique_dates,
        plan.holdout_start,
        plan.holdout_end,
    )
    X_pre, holdout_medians = _prepare_matrix(pre_holdout, features)
    X_holdout_calibration, _ = _prepare_matrix(holdout_calibration, features, holdout_medians)
    X_holdout, _ = _prepare_matrix(holdout, features, holdout_medians)
    y_pre = pre_holdout[target_column].to_numpy(dtype=float)
    y_holdout_calibration = holdout_calibration[target_column].to_numpy(dtype=float)
    y_holdout = holdout[target_column].to_numpy(dtype=float)
    lower, upper = np.quantile(y_pre, [0.005, 0.995])
    holdout_calibration_predictions = []
    holdout_predictions = []
    for seed in plan.seeds:
        evaluation_model = (
            _custom_estimator(
                estimator_factory,
                params=selected_params,
                seed=seed,
                n_estimators=validated_rounds,
            )
            if estimator_factory is not None
            else _default_estimator_factory(
                selected_params,
                seed=seed,
                n_estimators=validated_rounds,
            )
        )
        _fit_model(evaluation_model, X_pre, np.clip(y_pre, lower, upper))
        holdout_calibration_predictions.append(
            np.asarray(evaluation_model.predict(X_holdout_calibration), dtype=float)
        )
        holdout_predictions.append(np.asarray(evaluation_model.predict(X_holdout), dtype=float))
    holdout_calibration_prediction = np.mean(holdout_calibration_predictions, axis=0)
    holdout_prediction = np.mean(holdout_predictions, axis=0)
    holdout_interval = calibrate_interval(
        truth=y_holdout_calibration,
        prediction=holdout_calibration_prediction,
        coverage=0.80,
    )
    holdout_interval_evaluation = evaluate_interval(
        holdout_interval,
        truth=y_holdout,
        prediction=holdout_prediction,
    )
    holdout_metrics = compute_regression_metrics(y_holdout, holdout_prediction)
    holdout_baseline_selection = select_baseline(
        y_holdout_calibration,
        _baseline_predictions(holdout_calibration, horizon_days),
    )
    holdout_baseline_evaluation = evaluate_selected_baseline(
        holdout_baseline_selection,
        y_holdout,
        _baseline_predictions(holdout, horizon_days),
    )
    oos.extend(
        _oos_records(
            holdout,
            split="holdout",
            fold_index=None,
            seeds=plan.seeds,
            truth=y_holdout,
            prediction=holdout_prediction,
            baseline_name=holdout_baseline_evaluation.name,
            baseline_prediction=holdout_baseline_evaluation.predictions,
            radius=holdout_interval.interval.radius,
        )
    )

    gate_candidate = {
        **mean_candidate,
        "interval_coverage": validation_coverage,
        "fold_mae": [fold["mae"] for fold in fold_metrics],
        "holdout_mae": holdout_metrics["mae"],
        "holdout_interval_coverage": holdout_interval_evaluation.coverage,
    }
    gate_baseline = {
        **mean_baseline,
        "fold_mae": [fold["mae"] for fold in baseline_fold_metrics],
        "holdout_mae": holdout_baseline_evaluation.metrics["mae"],
    }
    decision = evaluate_promotion_gate(gate_candidate, gate_baseline)

    X_all, final_medians = _prepare_matrix(working, features)
    y_all = working[target_column].to_numpy(dtype=float)
    lower, upper = np.quantile(y_all, [0.005, 0.995])
    final_model = (
        _custom_estimator(
            estimator_factory,
            params=selected_params,
            seed=42,
            n_estimators=validated_rounds,
        )
        if estimator_factory is not None
        else _default_estimator_factory(
            selected_params,
            seed=42,
            n_estimators=validated_rounds,
        )
    )
    _fit_model(final_model, X_all, np.clip(y_all, lower, upper))

    version = str(uuid.uuid4())
    artifact_dir = Path(artifact_root) / version
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{asset_class.lower()}_{horizon_days}d.joblib"
    metadata_path = artifact_dir / f"{asset_class.lower()}_{horizon_days}d.json"
    oos_path = artifact_dir / f"{asset_class.lower()}_{horizon_days}d_oos.jsonl"
    joblib.dump(final_model, artifact_path)
    write_oos_predictions(oos_path, oos)
    metrics = {
        "folds": len(plan.outer_folds),
        "candidate": mean_candidate,
        "baseline": mean_baseline,
        "holdout": holdout_metrics,
        "holdout_baseline": holdout_baseline_evaluation.metrics,
        "interval_radius": holdout_interval.interval.radius,
        "interval_coverage": validation_coverage,
        "holdout_interval_coverage": holdout_interval_evaluation.coverage,
        "promotion_reasons": list(decision.reasons),
    }
    experiment = ExperimentRecord(
        config_hash=selected_configuration_hash,
        fold_diagnostics=tuple(fold_diagnostics),
        best_iterations=tuple(best_iterations),
        validated_boosting_rounds=validated_rounds,
        holdout_access=holdout_access,
        promotion_reasons=decision.reasons,
    )
    config_hashes = {
        "evaluation": config_hash(effective_config),
        "selected_params": config_hash(selected_params),
        "training": config_hash(asdict(config)),
    }
    baseline_selections = [
        {
            "split": "outer_test",
            "fold_index": item["fold_index"],
            "baseline_name": item["baseline_name"],
        }
        for item in fold_diagnostics
    ]
    baseline_selections.append(
        {
            "split": "holdout",
            "fold_index": None,
            "baseline_name": holdout_baseline_selection.name,
        }
    )
    metadata = {
        "model_version": version,
        "status": "shadow",
        "promotion_eligible": decision.promoted,
        "asset_class": asset_class,
        "horizon_days": horizon_days,
        "dataset_hash": dataset_hash,
        "feature_columns": list(features),
        "feature_medians": final_medians,
        "interval": asdict(holdout_interval.interval),
        "metrics": metrics,
        "artifact_path": artifact_path.name,
        "oos_predictions_path": oos_path.name,
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "training_config": asdict(config),
        "evaluation_config": effective_config,
        "config_hashes": config_hashes,
        "selected_params": selected_params,
        "validated_configurations": validated_configurations,
        "baseline_selection_policy": "preceding_calibration_mae_per_block",
        "baseline_selections": baseline_selections,
        "holdout_baseline_name": holdout_baseline_selection.name,
        **experiment.metadata(),
    }
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    return ModelTrainingResult(
        model_version=version,
        status="shadow",
        promotion_eligible=decision.promoted,
        asset_class=asset_class,
        horizon_days=horizon_days,
        dataset_hash=dataset_hash,
        feature_columns=features,
        artifact_path=artifact_path,
        metadata_path=metadata_path,
        metrics=metrics,
    )


def load_model_package(metadata_path: str | Path) -> dict:
    path = Path(metadata_path)
    metadata = json.loads(path.read_text(encoding="utf-8"))
    model = joblib.load(path.parent / metadata["artifact_path"])
    return {"metadata": metadata, "model": model}
