from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from app.ml.dataset import RESEARCH_MINIMUM_ASSETS, build_dynamic_research_universe, select_liquid_cohort
from app.ml.features import build_point_in_time_features
from app.ml.macro import merge_released_macro
from app.ml.targets import add_forward_targets


DATASET_SCHEMA_VERSION = "operum-ml-dataset-v2"


@dataclass(frozen=True)
class MaterializedDataset:
    dataset_hash: str
    dataset_dir: Path
    market_path: Path
    features_path: Path
    manifest_path: Path
    quality_report_path: Path
    context_path: Path | None = None
    macro_path: Path | None = None
    eligibility_path: Path | None = None
    research_gate_path: Path | None = None


def _write_versioned_parquet(frame: pd.DataFrame, path: Path, *, table_name: str) -> None:
    table = pa.Table.from_pandas(frame, preserve_index=False)
    metadata = dict(table.schema.metadata or {})
    metadata.update(
        {
            b"operum.schema_version": DATASET_SCHEMA_VERSION.encode("utf-8"),
            b"operum.table": table_name.encode("utf-8"),
        }
    )
    pq.write_table(table.replace_schema_metadata(metadata), path)


def _normalize_sources(sources: dict, cutoff: str) -> dict[str, dict]:
    normalized: dict[str, dict] = {}
    required = {
        "source",
        "license",
        "retrieved_at",
        "checksum",
        "reconciliation_status",
        "fallback_used",
        "errors",
        "exclusions",
    }
    for key, source in sources.items():
        if isinstance(source, str):
            normalized[key] = {
                "source": source,
                "license": "unspecified",
                "retrieved_at": cutoff,
                "checksum": "unavailable: legacy source declaration",
                "reconciliation_status": "legacy_unverified",
                "fallback_used": "Yahoo" in source,
                "errors": ["legacy source declaration lacks independently verified provenance"],
                "exclusions": [],
            }
            continue
        missing = required.difference(source)
        if missing:
            raise ValueError(f"Proveniencia incompleta para {key}: {sorted(missing)}")
        normalized[key] = dict(source)
    if not normalized:
        raise ValueError("Dataset v2 exige proveniencia de fontes")
    return normalized


def _source_gate_reasons(
    sources: dict[str, dict], *, required_keys: set[str]
) -> list[str]:
    """Fail closed unless every required source has complete verified provenance."""
    reasons: list[str] = []
    for key in sorted(required_keys.difference(sources)):
        reasons.append(f"{key}:missing_source")
    for key in sorted(set(sources).union(required_keys)):
        metadata = sources.get(key)
        if metadata is None:
            continue
        for field in ("source", "license", "checksum", "retrieved_at"):
            if not str(metadata.get(field) or "").strip():
                reasons.append(f"{key}:missing_{field}")
        status = metadata.get("reconciliation_status")
        fallback_used = bool(metadata.get("fallback_used"))
        if status not in {"authoritative", "reconciled"}:
            reasons.append(f"{key}:unverified_status:{status}")
        elif status == "authoritative" and fallback_used:
            reasons.append(f"{key}:authoritative_marked_as_fallback")
        elif status == "reconciled" and not fallback_used:
            reasons.append(f"{key}:reconciled_without_fallback")
        if metadata.get("errors"):
            reasons.append(f"{key}:source_errors")
    return reasons


def _canonical_market_columns(
    market: pd.DataFrame, *, legacy_market: bool = False
) -> pd.DataFrame:
    canonical = {"raw_close", "split_adjusted_close", "total_return_index"}
    missing = canonical.difference(market.columns)
    if missing and not legacy_market:
        raise ValueError(f"Missing canonical v2 market columns: {sorted(missing)}")
    if missing and "close" not in market:
        raise ValueError("Mercado legado sem coluna close")
    normalized = market.copy()
    if missing:
        for column in canonical:
            normalized[column] = normalized["close"]
    for column in canonical:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    values = normalized[list(canonical)]
    if values.isna().any().any() or not (
        values.gt(0) & values.lt(float("inf"))
    ).all().all():
        raise ValueError("Canonical v2 market histories must be finite and positive")
    # `close` remains the v1-compatible total-adjusted price input.
    normalized["close"] = normalized["total_return_index"]
    return normalized


def _gate_record(row: pd.Series) -> dict:
    return {
        "date": pd.Timestamp(row["date"]).isoformat(),
        "eligible_br_stock": int(row["eligible_br_stock"]),
        "eligible_fii": int(row["eligible_fii"]),
        "required_br_stock": int(row["required_br_stock"]),
        "required_fii": int(row["required_fii"]),
        "shortfall_br_stock": int(row["shortfall_br_stock"]),
        "shortfall_fii": int(row["shortfall_fii"]),
        "promotion_blocked": bool(row["promotion_blocked"]),
    }


def _stable_frame_hash(frame: pd.DataFrame, metadata: dict) -> str:
    normalized = frame.sort_values(["ticker", "date"]).reset_index(drop=True).copy()
    normalized["date"] = pd.to_datetime(normalized["date"]).astype("datetime64[ns]")
    digest = hashlib.sha256()
    digest.update(pd.util.hash_pandas_object(normalized, index=False).values.tobytes())
    digest.update(json.dumps(metadata, ensure_ascii=True, sort_keys=True).encode("utf-8"))
    return digest.hexdigest()


def materialize_dataset(
    market: pd.DataFrame,
    *,
    context: pd.DataFrame | None = None,
    macro_releases: pd.DataFrame | None = None,
    output_root: str | Path,
    cutoff: str,
    sources: dict,
    legacy_market: bool = False,
) -> MaterializedDataset:
    cutoff_dt = pd.Timestamp(cutoff)
    comparable_cutoff = cutoff_dt.tz_localize(None) if cutoff_dt.tzinfo else cutoff_dt
    source_manifest = _normalize_sources(sources, cutoff)
    normalized = _canonical_market_columns(market, legacy_market=legacy_market)
    normalized["date"] = pd.to_datetime(normalized["date"]).dt.tz_localize(None)
    normalized = normalized.loc[normalized["date"] <= comparable_cutoff].copy()
    selected, excluded = select_liquid_cohort(normalized, strict=False)
    display_tickers = {item.ticker for item in selected}
    display_counts = {
        asset_class: sum(item.asset_class == asset_class for item in selected)
        for asset_class in ("BR_STOCK", "FII")
    }
    display_shortfall = {
        "BR_STOCK": max(24 - display_counts["BR_STOCK"], 0),
        "FII": max(6 - display_counts["FII"], 0),
    }
    dataset_market = normalized.sort_values(["ticker", "date"]).reset_index(drop=True)
    eligibility, research_gate = build_dynamic_research_universe(dataset_market)
    latest_gate = _gate_record(research_gate.iloc[-1])
    required_source_keys = {"prices"}
    if context is not None:
        required_source_keys.update({"benchmark", "fx", "oil"})
    if macro_releases is not None:
        required_source_keys.add("macro")
    source_gate_reasons = _source_gate_reasons(
        source_manifest, required_keys=required_source_keys
    )
    if legacy_market:
        source_gate_reasons.append("market:legacy_v1_non_promotable")
    source_data_blocked = bool(source_gate_reasons)
    eligibility_blocked = latest_gate["promotion_blocked"]
    latest_gate["eligibility_blocked"] = eligibility_blocked
    latest_gate["source_data_blocked"] = source_data_blocked
    latest_gate["promotion_blocked"] = eligibility_blocked or source_data_blocked

    normalized_context = None
    context_hash = None
    if context is not None:
        normalized_context = context.copy()
        required_context_dates = {"reference_date", "available_at"}
        missing_context_dates = required_context_dates.difference(normalized_context.columns)
        if missing_context_dates:
            raise ValueError(
                f"Contexto point-in-time exige {sorted(missing_context_dates)}"
            )
        normalized_context["reference_date"] = pd.to_datetime(
            normalized_context["reference_date"], errors="coerce"
        ).dt.tz_localize(None)
        normalized_context["available_at"] = pd.to_datetime(
            normalized_context["available_at"], errors="coerce"
        ).dt.tz_localize(None)
        normalized_context = normalized_context.loc[
            normalized_context["available_at"] <= comparable_cutoff
        ].sort_values("available_at").reset_index(drop=True)
        context_hash = hashlib.sha256(
            pd.util.hash_pandas_object(normalized_context, index=False).values.tobytes()
        ).hexdigest()

    normalized_macro = None
    macro_hash = None
    if macro_releases is not None:
        normalized_macro = macro_releases.copy()
        normalized_macro["available_at"] = pd.to_datetime(
            normalized_macro["available_at"]
        ).dt.tz_localize(None)
        normalized_macro = normalized_macro.loc[
            normalized_macro["available_at"] <= comparable_cutoff
        ].sort_values("available_at").reset_index(drop=True)
        macro_hash = hashlib.sha256(
            pd.util.hash_pandas_object(normalized_macro, index=False).values.tobytes()
        ).hexdigest()

    identity = {
        "schema_version": DATASET_SCHEMA_VERSION,
        "cutoff": cutoff,
        "sources": source_manifest,
        "source_gate_reasons": source_gate_reasons,
        "cohort": [item.as_dict() for item in selected],
        "display_cohort": [item.as_dict() for item in selected],
        "display_cohort_shortfall": display_shortfall,
        "market_contract": (
            "legacy_v1_non_promotable" if legacy_market else "canonical_v2"
        ),
        "research_universe": {
            "required": dict(RESEARCH_MINIMUM_ASSETS),
            "latest_gate": latest_gate,
            "materialized_despite_gate": bool(latest_gate["promotion_blocked"]),
        },
        "column_aliases": {
            "close": "total_return_index",
            "target_return_{h}": "target_total_return_{h}",
        },
        "context_hash": context_hash,
        "macro_hash": macro_hash,
        "news_in_quantitative_features": False,
    }
    dataset_hash = _stable_frame_hash(dataset_market, identity)
    dataset_dir = Path(output_root) / dataset_hash[:16]
    dataset_dir.mkdir(parents=True, exist_ok=True)

    featured = build_point_in_time_features(dataset_market, context=normalized_context)
    eligibility_features = eligibility.rename(
        columns={
            "observed_sessions": "research_observed_sessions",
            "coverage": "research_coverage",
            "median_traded_value": "research_median_traded_value",
            "eligible": "research_eligible",
            "reasons": "research_exclusion_reasons",
            "liquidity_rank": "research_liquidity_rank",
        }
    ).drop(columns=["in_research_universe"])
    featured = featured.merge(
        eligibility_features,
        on=["date", "ticker", "asset_class"],
        how="left",
        validate="one_to_one",
    )
    if normalized_macro is not None:
        featured = merge_released_macro(featured, normalized_macro)
    featured = add_forward_targets(featured)
    market_path = dataset_dir / "market.parquet"
    features_path = dataset_dir / "features.parquet"
    manifest_path = dataset_dir / "manifest.json"
    quality_report_path = dataset_dir / "quality_report.json"
    eligibility_path = dataset_dir / "research_eligibility.parquet"
    research_gate_path = dataset_dir / "research_gate.parquet"
    context_path = dataset_dir / "context.parquet" if normalized_context is not None else None
    macro_path = dataset_dir / "macro_releases.parquet" if normalized_macro is not None else None
    _write_versioned_parquet(dataset_market, market_path, table_name="market")
    _write_versioned_parquet(featured, features_path, table_name="features")
    _write_versioned_parquet(eligibility, eligibility_path, table_name="research_eligibility")
    _write_versioned_parquet(research_gate, research_gate_path, table_name="research_gate")
    if context_path is not None:
        _write_versioned_parquet(normalized_context, context_path, table_name="context")
    if macro_path is not None:
        _write_versioned_parquet(normalized_macro, macro_path, table_name="macro_releases")

    source_exclusions = []
    for source_key, metadata in source_manifest.items():
        source_exclusions.extend(
            {"source_key": source_key, **item} for item in metadata.get("exclusions", [])
        )

    manifest = {
        **identity,
        "dataset_hash": dataset_hash,
        "row_count": len(dataset_market),
        "feature_row_count": len(featured),
        "excluded": excluded,
        "source_exclusions": source_exclusions,
        "display_tickers": sorted(display_tickers),
        "parquet_schema_version": DATASET_SCHEMA_VERSION,
        "parquet_schemas": {
            "market": {
                "version": DATASET_SCHEMA_VERSION,
                "columns": list(dataset_market.columns),
            },
            "features": {
                "version": DATASET_SCHEMA_VERSION,
                "columns": list(featured.columns),
            },
            "research_eligibility": {
                "version": DATASET_SCHEMA_VERSION,
                "columns": list(eligibility.columns),
            },
            "research_gate": {
                "version": DATASET_SCHEMA_VERSION,
                "columns": list(research_gate.columns),
            },
        },
        "files": {
            "market": market_path.name,
            "features": features_path.name,
            "quality_report": quality_report_path.name,
            "context": context_path.name if context_path is not None else None,
            "macro_releases": macro_path.name if macro_path is not None else None,
            "research_eligibility": eligibility_path.name,
            "research_gate": research_gate_path.name,
        },
    }
    quality_report = {
        "dataset_hash": dataset_hash,
        "cutoff": cutoff,
        "selected_assets": len(selected),
        "rows": len(dataset_market),
        "date_min": dataset_market["date"].min().isoformat() if not dataset_market.empty else None,
        "date_max": dataset_market["date"].max().isoformat() if not dataset_market.empty else None,
        "coverage": {item.ticker: item.coverage for item in selected},
        "excluded": excluded,
        "source_exclusions": source_exclusions,
        "research_universe_latest_gate": latest_gate,
        "missing_values_by_column": {
            column: int(value) for column, value in featured.isna().sum().items()
        },
    }
    quality_report_path.write_text(
        json.dumps(quality_report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return MaterializedDataset(
        dataset_hash=dataset_hash,
        dataset_dir=dataset_dir,
        market_path=market_path,
        features_path=features_path,
        manifest_path=manifest_path,
        quality_report_path=quality_report_path,
        context_path=context_path,
        macro_path=macro_path,
        eligibility_path=eligibility_path,
        research_gate_path=research_gate_path,
    )
