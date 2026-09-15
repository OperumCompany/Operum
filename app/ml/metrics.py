from __future__ import annotations

import numpy as np


def compute_regression_metrics(truth, prediction) -> dict[str, float]:
    actual = np.asarray(truth, dtype=float)
    predicted = np.asarray(prediction, dtype=float)
    if actual.shape != predicted.shape:
        raise ValueError("truth and prediction must have identical shapes")
    mask = np.isfinite(actual) & np.isfinite(predicted)
    if not mask.any():
        raise ValueError("metrics require valid observations")
    actual = actual[mask]
    predicted = predicted[mask]
    error = predicted - actual
    return {
        "mae": float(np.mean(np.abs(error))),
        "rmse": float(np.sqrt(np.mean(np.square(error)))),
        "directional_accuracy": float(np.mean(np.sign(predicted) == np.sign(actual))),
    }
