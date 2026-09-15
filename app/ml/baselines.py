from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.ml.metrics import compute_regression_metrics


@dataclass(frozen=True)
class BaselineSelection:
    name: str
    metrics: dict[str, float]


@dataclass(frozen=True)
class BaselineEvaluation:
    name: str
    predictions: np.ndarray
    metrics: dict[str, float]


def select_baseline(truth, predictions: dict[str, np.ndarray]) -> BaselineSelection:
    if not predictions:
        raise ValueError("at least one baseline is required")
    ranked = [
        (compute_regression_metrics(truth, values)["mae"], name, values)
        for name, values in predictions.items()
    ]
    _, name, values = min(ranked, key=lambda item: (item[0], item[1]))
    return BaselineSelection(name=name, metrics=compute_regression_metrics(truth, values))


def evaluate_selected_baseline(
    selection: BaselineSelection,
    truth,
    predictions: dict[str, np.ndarray],
) -> BaselineEvaluation:
    if selection.name not in predictions:
        raise ValueError(f"selected baseline is unavailable: {selection.name}")
    values = np.asarray(predictions[selection.name], dtype=float)
    return BaselineEvaluation(
        name=selection.name,
        predictions=values,
        metrics=compute_regression_metrics(truth, values),
    )
