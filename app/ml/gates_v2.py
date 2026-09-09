from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np


@dataclass(frozen=True)
class ProbabilisticGateDecision:
    passed: bool
    reasons: tuple[str, ...]
    checks: dict[str, bool | str]


def _finite_metric(sample: Mapping[str, object], side: str, name: str) -> float:
    try:
        value = float(sample[side][name])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"missing gate metric: {side}.{name}") from exc
    if not np.isfinite(value):
        raise ValueError(f"non-finite gate metric: {side}.{name}")
    return value


def _sample_checks(prefix: str, sample: Mapping[str, object]) -> dict[str, bool]:
    candidate_mae = _finite_metric(sample, "candidate", "mae")
    baseline_mae = _finite_metric(sample, "baseline", "mae")
    candidate_balanced = _finite_metric(sample, "candidate", "balanced_accuracy")
    baseline_balanced = _finite_metric(sample, "baseline", "balanced_accuracy")
    candidate_brier = _finite_metric(sample, "candidate", "brier")
    baseline_brier = _finite_metric(sample, "baseline", "brier")
    candidate_pinball = _finite_metric(sample, "candidate", "pinball_mean")
    baseline_pinball = _finite_metric(sample, "baseline", "pinball_mean")
    candidate_winkler = _finite_metric(sample, "candidate", "winkler")
    baseline_winkler = _finite_metric(sample, "baseline", "winkler")
    coverage = _finite_metric(sample, "candidate", "coverage")
    return {
        f"{prefix}_mae": candidate_mae <= baseline_mae * 0.98,
        f"{prefix}_balanced_accuracy": candidate_balanced
        >= max(0.52, baseline_balanced + 0.02),
        f"{prefix}_brier": candidate_brier <= baseline_brier * 0.98,
        f"{prefix}_pinball": candidate_pinball <= baseline_pinball * 0.98,
        f"{prefix}_winkler": candidate_winkler <= baseline_winkler * 0.98,
        f"{prefix}_coverage": 0.75 <= coverage <= 0.85,
    }


def _relative_row(row: Mapping[str, object]) -> tuple[float, float]:
    try:
        candidate = float(row["candidate_mae"])
        baseline = float(row["baseline_mae"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("stability rows require candidate_mae and baseline_mae") from exc
    if not np.isfinite(candidate) or not np.isfinite(baseline) or candidate < 0.0 or baseline < 0.0:
        raise ValueError("stability MAE values must be finite and nonnegative")
    return candidate, baseline


def evaluate_probabilistic_gates(
    *,
    oos: Mapping[str, object],
    holdout: Mapping[str, object] | None,
    folds: Sequence[Mapping[str, object]],
    regimes: Sequence[Mapping[str, object]],
    seeds: Sequence[Mapping[str, object]],
    snapshot_generated: bool | None = None,
) -> ProbabilisticGateDecision:
    checks: dict[str, bool | str] = dict(_sample_checks("oos", oos))
    if holdout is None:
        for name in ("mae", "balanced_accuracy", "brier", "pinball", "winkler", "coverage"):
            checks[f"holdout_{name}"] = False
    else:
        checks.update(_sample_checks("holdout", holdout))

    fold_bad = []
    for row in folds:
        candidate, baseline = _relative_row(row)
        fold_bad.append(candidate > baseline * 1.10 + 1e-15)
    checks["fold_stability"] = not any(
        left and right for left, right in zip(fold_bad, fold_bad[1:])
    )

    regime_stable = True
    for row in regimes:
        try:
            count = int(row["count"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("regime stability rows require a count") from exc
        if count < 100:
            continue
        candidate, baseline = _relative_row(row)
        if candidate > baseline * 1.10 + 1e-15:
            regime_stable = False
    checks["regime_stability"] = regime_stable

    if not seeds:
        checks["seed_stability"] = False
    else:
        checks["seed_stability"] = all(
            candidate <= baseline * 1.10 + 1e-15
            for candidate, baseline in (_relative_row(row) for row in seeds)
        )

    if snapshot_generated is None:
        checks["snapshot_generation"] = "pending_task_5"
    else:
        checks["snapshot_generation"] = bool(snapshot_generated)

    reasons = tuple(
        name
        for name, passed in checks.items()
        if passed is False and name != "snapshot_generation"
    )
    if snapshot_generated is False:
        reasons = (*reasons, "snapshot_generation")
    return ProbabilisticGateDecision(passed=not reasons, reasons=reasons, checks=checks)
