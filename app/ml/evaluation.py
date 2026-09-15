from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


DEFAULT_EVALUATION_SEEDS = (17, 42, 73)
CALIBRATION_DAYS = 126
FINAL_HOLDOUT_DAYS = 126


@dataclass(frozen=True)
class EvaluationConfig:
    min_train_days: int = 504
    calibration_days: int = CALIBRATION_DAYS
    holdout_days: int = FINAL_HOLDOUT_DAYS
    seeds: tuple[int, ...] = DEFAULT_EVALUATION_SEEDS

    def __post_init__(self) -> None:
        if self.min_train_days <= 0:
            raise ValueError("training window must be positive")
        if self.calibration_days != CALIBRATION_DAYS:
            raise ValueError("the calibration window is locked to 126 trading dates")
        if self.holdout_days != FINAL_HOLDOUT_DAYS:
            raise ValueError("the final holdout is locked to 126 trading dates")
        if self.seeds != DEFAULT_EVALUATION_SEEDS:
            raise ValueError("evaluation seeds are locked to (17, 42, 73)")


@dataclass(frozen=True)
class InnerFold:
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int


@dataclass(frozen=True)
class OuterFold:
    train_start: int
    train_end: int
    calibration_start: int
    calibration_end: int
    test_start: int
    test_end: int
    inner_folds: tuple[InnerFold, ...]


@dataclass(frozen=True)
class EvaluationPlan:
    dates: tuple[pd.Timestamp, ...]
    horizon_days: int
    holdout_start: int
    holdout_end: int
    seeds: tuple[int, ...]
    outer_folds: tuple[OuterFold, ...]


def _inner_folds(*, outer_train_end: int, min_train_days: int, horizon_days: int) -> tuple[InnerFold, ...]:
    folds: list[InnerFold] = []
    validation_start = min_train_days + horizon_days
    while validation_start + horizon_days - 1 <= outer_train_end:
        folds.append(
            InnerFold(
                train_start=0,
                train_end=validation_start - horizon_days - 1,
                validation_start=validation_start,
                validation_end=validation_start + horizon_days - 1,
            )
        )
        validation_start += horizon_days
    return tuple(folds)


def build_evaluation_plan(
    dates,
    *,
    horizon_days: int,
    config: EvaluationConfig | None = None,
) -> EvaluationPlan:
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")
    config = config or EvaluationConfig()
    ordered = tuple(pd.DatetimeIndex(pd.to_datetime(dates)).sort_values().unique())
    if len(ordered) <= config.holdout_days:
        raise ValueError("insufficient history for the locked holdout")

    holdout_start = len(ordered) - config.holdout_days
    test_start = config.min_train_days + horizon_days + config.calibration_days
    folds: list[OuterFold] = []
    while test_start + horizon_days <= holdout_start:
        calibration_start = test_start - config.calibration_days
        train_end = calibration_start - horizon_days - 1
        inner = _inner_folds(
            outer_train_end=train_end,
            min_train_days=config.min_train_days,
            horizon_days=horizon_days,
        )
        if inner:
            folds.append(
                OuterFold(
                    train_start=0,
                    train_end=train_end,
                    calibration_start=calibration_start,
                    calibration_end=test_start - 1,
                    test_start=test_start,
                    test_end=test_start + horizon_days - 1,
                    inner_folds=inner,
                )
            )
        test_start += horizon_days

    return EvaluationPlan(
        dates=ordered,
        horizon_days=horizon_days,
        holdout_start=holdout_start,
        holdout_end=len(ordered) - 1,
        seeds=config.seeds,
        outer_folds=tuple(folds),
    )
