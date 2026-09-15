from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TemporalSplit:
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int


@dataclass(frozen=True)
class PromotionDecision:
    promoted: bool
    reasons: tuple[str, ...]


def expanding_walk_forward_splits(
    dates,
    *,
    min_train_days: int = 504,
    validation_days: int = 63,
    embargo_days: int = 63,
    holdout_days: int = 252,
    step_days: int = 21,
) -> list[TemporalSplit]:
    ordered = pd.DatetimeIndex(pd.to_datetime(dates)).sort_values().unique()
    usable_end = len(ordered) - holdout_days
    splits: list[TemporalSplit] = []
    validation_start = min_train_days + embargo_days
    while validation_start + validation_days <= usable_end:
        splits.append(
            TemporalSplit(
                train_start=0,
                train_end=validation_start - embargo_days - 1,
                validation_start=validation_start,
                validation_end=validation_start + validation_days - 1,
            )
        )
        validation_start += step_days
    return splits


def evaluate_promotion_gate(candidate: dict, baseline: dict) -> PromotionDecision:
    reasons: list[str] = []
    baseline_mae = float(baseline["mae"])
    if float(candidate["mae"]) > baseline_mae * 0.98:
        reasons.append("mae")
    required_direction = max(0.52, float(baseline["directional_accuracy"]) + 0.02)
    if float(candidate["directional_accuracy"]) < required_direction:
        reasons.append("directional_accuracy")
    coverage = float(candidate["interval_coverage"])
    if not 0.75 <= coverage <= 0.85:
        reasons.append("interval_coverage")
    baseline_folds = baseline.get("fold_mae", [])
    bad_folds = [
        float(value) > (
            float(baseline_folds[index]) if index < len(baseline_folds) else baseline_mae
        ) * 1.10
        for index, value in enumerate(candidate.get("fold_mae", []))
    ]
    if any(left and right for left, right in zip(bad_folds, bad_folds[1:])):
        reasons.append("fold_stability")
    if float(candidate["holdout_mae"]) > float(baseline["holdout_mae"]) * 0.98:
        reasons.append("holdout_mae")
    holdout_coverage = float(candidate["holdout_interval_coverage"])
    if not 0.75 <= holdout_coverage <= 0.85:
        reasons.append("holdout_interval_coverage")
    return PromotionDecision(promoted=not reasons, reasons=tuple(reasons))
