from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HoldoutAlreadyConsumedError(RuntimeError):
    pass


@dataclass(frozen=True)
class OOSPrediction:
    date: str
    ticker: str
    split: str
    fold_index: int | None
    seeds: tuple[int, ...]
    truth: float
    prediction: float
    baseline_name: str
    baseline_prediction: float
    interval_low: float
    interval_high: float


@dataclass(frozen=True)
class ExperimentRecord:
    config_hash: str
    fold_diagnostics: tuple[dict[str, Any], ...]
    best_iterations: tuple[int, ...]
    validated_boosting_rounds: int | None
    holdout_access: dict[str, Any]
    promotion_reasons: tuple[str, ...]

    def metadata(self) -> dict[str, Any]:
        return {
            "config_hash": self.config_hash,
            "fold_diagnostics": list(self.fold_diagnostics),
            "best_iterations": list(self.best_iterations),
            "validated_boosting_rounds": self.validated_boosting_rounds,
            "holdout_access": self.holdout_access,
            "promotion_reasons": list(self.promotion_reasons),
        }


def config_hash(config) -> str:
    canonical = json.dumps(config, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def claim_holdout_access(
    artifact_root: str | Path,
    *,
    dataset_hash: str,
    asset_class: str,
    horizon_days: int,
    configuration_hash: str,
    holdout_days: int,
) -> dict[str, Any]:
    root = Path(artifact_root)
    ledger_dir = root / ".holdout-ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    slot = {
        "dataset_hash": dataset_hash,
        "asset_class": asset_class,
        "horizon_days": horizon_days,
    }
    ledger_path = ledger_dir / f"{config_hash(slot)}.json"
    relative_path = ledger_path.relative_to(root).as_posix()
    record = {
        **slot,
        "configuration_hash": configuration_hash,
        "access_count": 1,
        "days": holdout_days,
        "locked": True,
        "consumed_at": datetime.now(timezone.utc).isoformat(),
        "ledger_path": relative_path,
    }
    try:
        with ledger_path.open("x", encoding="utf-8") as destination:
            json.dump(record, destination, indent=2, sort_keys=True)
    except FileExistsError as exc:
        persisted = json.loads(ledger_path.read_text(encoding="utf-8"))
        if persisted.get("configuration_hash") != configuration_hash:
            raise HoldoutAlreadyConsumedError(
                "locked holdout configuration mismatch for consumed dataset slot"
            ) from exc
        raise HoldoutAlreadyConsumedError(
            "locked holdout already consumed for dataset slot"
        ) from exc
    return json.loads(ledger_path.read_text(encoding="utf-8"))


def write_oos_predictions(path: str | Path, records: list[OOSPrediction]) -> Path:
    destination = Path(path)
    lines = [json.dumps(asdict(record), sort_keys=True, separators=(",", ":")) for record in records]
    destination.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return destination
