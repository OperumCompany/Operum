from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.ml.intervals import ConformalInterval


@dataclass(frozen=True)
class IntervalCalibration:
    interval: ConformalInterval
    sample_count: int


@dataclass(frozen=True)
class IntervalEvaluation:
    coverage: float
    sample_count: int


def calibrate_interval(*, truth, prediction, coverage: float = 0.80) -> IntervalCalibration:
    actual = np.asarray(truth, dtype=float)
    predicted = np.asarray(prediction, dtype=float)
    if actual.shape != predicted.shape:
        raise ValueError("truth and prediction must have identical shapes")
    residuals = np.abs(actual - predicted)
    valid = residuals[np.isfinite(residuals)]
    return IntervalCalibration(
        interval=ConformalInterval.fit(valid, coverage=coverage),
        sample_count=int(valid.size),
    )


def evaluate_interval(
    calibration: IntervalCalibration,
    *,
    truth,
    prediction,
) -> IntervalEvaluation:
    actual = np.asarray(truth, dtype=float)
    predicted = np.asarray(prediction, dtype=float)
    if actual.shape != predicted.shape:
        raise ValueError("truth and prediction must have identical shapes")
    residuals = np.abs(actual - predicted)
    valid = np.isfinite(residuals)
    if not valid.any():
        raise ValueError("interval evaluation requires valid observations")
    return IntervalEvaluation(
        coverage=float(np.mean(residuals[valid] <= calibration.interval.radius)),
        sample_count=int(valid.sum()),
    )
