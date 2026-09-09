from __future__ import annotations

from collections.abc import Mapping

import numpy as np
import pandas as pd


_QUANTILES = {"q10": 0.10, "q50": 0.50, "q90": 0.90}


def _aligned_finite(*values) -> tuple[np.ndarray, ...]:
    arrays = tuple(np.asarray(value, dtype=float) for value in values)
    if not arrays or any(array.ndim != 1 or array.size == 0 for array in arrays):
        raise ValueError("metrics require non-empty one-dimensional arrays")
    if len({array.shape for array in arrays}) != 1:
        raise ValueError("metric inputs must have identical shapes")
    valid = np.logical_and.reduce([np.isfinite(array) for array in arrays])
    if not valid.any():
        raise ValueError("metrics require finite observations")
    return tuple(array[valid] for array in arrays)


def classification_metrics(truth, probability_up) -> dict[str, float]:
    actual, probability = _aligned_finite(truth, probability_up)
    if np.any(~np.isin(actual, (0.0, 1.0))) or np.any((probability < 0.0) | (probability > 1.0)):
        raise ValueError("classification metrics require binary truth and probabilities")
    predicted = probability >= 0.5
    if np.unique(actual).size < 2:
        balanced_accuracy = 0.5
    else:
        positive_recall = np.mean(predicted[actual == 1.0])
        negative_recall = np.mean(~predicted[actual == 0.0])
        balanced_accuracy = float((positive_recall + negative_recall) / 2.0)
    return {
        "balanced_accuracy": balanced_accuracy,
        "brier": float(np.mean(np.square(probability - actual))),
    }


def quantile_metrics(truth, predictions: Mapping[str, object]) -> dict[str, float]:
    if not isinstance(predictions, Mapping) or set(predictions) != set(_QUANTILES):
        raise ValueError("q10, q50 and q90 are required for pinball metrics")
    actual = np.asarray(truth, dtype=float)
    values = {name: np.asarray(predictions[name], dtype=float) for name in _QUANTILES}
    arrays = _aligned_finite(actual, *(values[name] for name in _QUANTILES))
    actual = arrays[0]
    scores = {}
    for index, (name, alpha) in enumerate(_QUANTILES.items(), start=1):
        error = actual - arrays[index]
        scores[f"pinball_{name}"] = float(
            np.mean(np.maximum(alpha * error, (alpha - 1.0) * error))
        )
    scores["pinball_mean"] = float(np.mean(list(scores.values())))
    return scores


def interval_metrics(truth, *, lower, upper, coverage: float = 0.80) -> dict[str, float]:
    if not 0.0 < float(coverage) < 1.0:
        raise ValueError("coverage must be between zero and one")
    actual, low, high = _aligned_finite(truth, lower, upper)
    if np.any(low > high):
        raise ValueError("interval bounds must be ordered")
    alpha = 1.0 - float(coverage)
    width = high - low
    winkler = width.copy()
    below = actual < low
    above = actual > high
    winkler[below] += (2.0 / alpha) * (low[below] - actual[below])
    winkler[above] += (2.0 / alpha) * (actual[above] - high[above])
    return {
        "coverage": float(np.mean((actual >= low) & (actual <= high))),
        "interval_width": float(np.mean(width)),
        "winkler": float(np.mean(winkler)),
    }


def group_stability(
    truth,
    candidate_prediction,
    baseline_prediction,
    groups,
    *,
    min_observations: int = 1,
) -> dict[str, dict[str, float | int]]:
    if min_observations <= 0:
        raise ValueError("minimum observations must be positive")
    actual = np.asarray(truth, dtype=float)
    candidate = np.asarray(candidate_prediction, dtype=float)
    baseline = np.asarray(baseline_prediction, dtype=float)
    labels = np.asarray(groups, dtype=object)
    if any(array.ndim != 1 for array in (actual, candidate, baseline, labels)) or len(
        {array.shape for array in (actual, candidate, baseline, labels)}
    ) != 1:
        raise ValueError("group stability inputs must align")
    valid = np.isfinite(actual) & np.isfinite(candidate) & np.isfinite(baseline) & pd.notna(labels)
    result: dict[str, dict[str, float | int]] = {}
    for label in sorted({str(value) for value in labels[valid]}):
        selected = valid & (labels.astype(str) == label)
        count = int(selected.sum())
        if count < min_observations:
            continue
        candidate_mae = float(np.mean(np.abs(candidate[selected] - actual[selected])))
        baseline_mae = float(np.mean(np.abs(baseline[selected] - actual[selected])))
        if baseline_mae == 0.0:
            ratio = 1.0 if candidate_mae == 0.0 else float("inf")
        else:
            ratio = candidate_mae / baseline_mae
        result[label] = {
            "count": count,
            "candidate_mae": candidate_mae,
            "baseline_mae": baseline_mae,
            "candidate_to_baseline": float(ratio),
        }
    return result


def seed_stability(
    truth,
    predictions_by_seed: Mapping[int, object],
    *,
    baseline_prediction,
) -> dict:
    if not isinstance(predictions_by_seed, Mapping) or not predictions_by_seed:
        raise ValueError("seed predictions are required")
    actual, baseline = _aligned_finite(truth, baseline_prediction)
    baseline_mae = float(np.mean(np.abs(baseline - actual)))
    per_seed = {}
    stacked = []
    stable = True
    for seed in sorted(predictions_by_seed):
        candidate = np.asarray(predictions_by_seed[seed], dtype=float)
        if candidate.shape != np.asarray(truth).shape or not np.all(np.isfinite(candidate)):
            raise ValueError("seed predictions must be finite and align with truth")
        mae = float(np.mean(np.abs(candidate - np.asarray(truth, dtype=float))))
        per_seed[int(seed)] = {"mae": mae}
        stacked.append(candidate)
        limit = baseline_mae * 1.10
        if mae > limit + 1e-15:
            stable = False
    return {
        "stable": stable,
        "baseline_mae": baseline_mae,
        "mae_std": float(np.std([item["mae"] for item in per_seed.values()])),
        "prediction_disagreement": float(np.mean(np.std(np.vstack(stacked), axis=0))),
        "per_seed": per_seed,
    }


def origin_known_regimes(
    frame: pd.DataFrame,
    *,
    min_history: int = 100,
    volatility_column: str = "volatility_21",
    market_return_column: str = "benchmark_return_21",
) -> pd.Series:
    if min_history < 100:
        raise ValueError("regime labels require at least 100 prior observations")
    if volatility_column not in frame or market_return_column not in frame:
        raise ValueError("origin-known volatility and market return features are required")
    volatility = pd.to_numeric(frame[volatility_column], errors="coerce")
    market_return = pd.to_numeric(frame[market_return_column], errors="coerce")
    prior_threshold = volatility.shift(1).expanding(min_periods=min_history).median()
    labels = pd.Series(np.nan, index=frame.index, dtype=object)
    eligible = volatility.notna() & market_return.notna() & prior_threshold.notna()
    volatility_state = np.where(volatility >= prior_threshold, "high_vol", "low_vol")
    market_state = np.where(market_return >= 0.0, "up_market", "down_market")
    combined = pd.Series(
        [f"{left}__{right}" for left, right in zip(volatility_state, market_state)],
        index=frame.index,
        dtype=object,
    )
    labels.loc[eligible] = combined.loc[eligible]
    return labels
