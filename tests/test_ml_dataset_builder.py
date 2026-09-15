from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

import app.ml.builder as dataset_builder
from app.ml.builder import materialize_dataset


def _authoritative_sources() -> dict:
    return {
        "prices": {
            "source": "B3",
            "license": "B3 market-data terms",
            "retrieved_at": "2024-12-31T20:00:00+00:00",
            "checksum": "fixture-market-sha256",
            "reconciliation_status": "authoritative",
            "fallback_used": False,
            "errors": [],
            "exclusions": [],
        }
    }


def _verified_source(status="authoritative", *, fallback=False, **overrides) -> dict:
    record = {
        "source": "fixture",
        "license": "public-data license",
        "retrieved_at": "2024-12-31T20:00:00+00:00",
        "checksum": "fixture-sha256",
        "reconciliation_status": status,
        "fallback_used": fallback,
        "errors": [],
        "exclusions": [],
    }
    record.update(overrides)
    return record


def _cohort_market() -> pd.DataFrame:
    dates = pd.bdate_range("2019-01-02", periods=1_300)
    rows = []
    for asset_class, count in (("BR_STOCK", 24), ("FII", 6)):
        for index in range(count):
            close = 10 + index + np.arange(len(dates)) * 0.001
            rows.append(
                pd.DataFrame(
                    {
                        "date": dates,
                        "ticker": f"{'S' if asset_class == 'BR_STOCK' else 'F'}{index:02d}",
                        "asset_class": asset_class,
                        "open": close,
                        "high": close + 0.1,
                        "low": close - 0.1,
                        "close": close,
                        "raw_close": close,
                        "split_adjusted_close": close,
                        "total_return_index": close,
                        "volume": 100_000 + index,
                    }
                )
            )
    return pd.concat(rows, ignore_index=True)


def test_materialized_dataset_is_versioned_and_reproducible(tmp_path):
    market = _cohort_market()
    dates = market["date"].drop_duplicates().sort_values()
    context = pd.DataFrame(
        {
            "reference_date": dates,
            "available_at": dates.dt.normalize() + pd.Timedelta(hours=23, minutes=59),
            "ibov_close": 100_000 + np.arange(len(dates)),
            "usdbrl_close": 5 + np.arange(len(dates)) * 0.001,
            "brent_close": 70 + np.arange(len(dates)) * 0.01,
        }
    )

    sources = _authoritative_sources()
    sources.update(
        {
            "benchmark": _verified_source(),
            "fx": _verified_source(),
            "oil": _verified_source(),
        }
    )
    first = materialize_dataset(
        market,
        context=context,
        output_root=tmp_path,
        cutoff="2024-12-31T23:59:59+00:00",
        sources=sources,
    )
    second = materialize_dataset(
        market,
        context=context,
        output_root=tmp_path,
        cutoff="2024-12-31T23:59:59+00:00",
        sources=sources,
    )

    assert first.dataset_hash == second.dataset_hash
    assert first.dataset_dir == second.dataset_dir
    assert (first.dataset_dir / "market.parquet").exists()
    assert (first.dataset_dir / "features.parquet").exists()
    assert (first.dataset_dir / "context.parquet").exists()
    assert (first.dataset_dir / "quality_report.json").exists()
    assert (first.dataset_dir / "research_eligibility.parquet").exists()
    assert (first.dataset_dir / "research_gate.parquet").exists()
    manifest = json.loads((first.dataset_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "operum-ml-dataset-v2"
    assert manifest["cutoff"] == "2024-12-31T23:59:59+00:00"
    assert len(manifest["display_cohort"]) == 30
    assert manifest["cohort"] == manifest["display_cohort"]
    assert manifest["sources"] == sources
    assert manifest["column_aliases"] == {
        "close": "total_return_index",
        "target_return_{h}": "target_total_return_{h}",
    }
    assert manifest["research_universe"]["required"] == {"BR_STOCK": 80, "FII": 20}
    assert manifest["research_universe"]["latest_gate"]["promotion_blocked"] is True
    assert manifest["research_universe"]["materialized_despite_gate"] is True
    assert manifest["news_in_quantitative_features"] is False
    market_parquet = pd.read_parquet(first.market_path)
    assert {
        "raw_close",
        "split_adjusted_close",
        "total_return_index",
        "close",
    }.issubset(market_parquet.columns)
    pd.testing.assert_series_equal(
        market_parquet["close"], market_parquet["total_return_index"], check_names=False
    )
    features = pd.read_parquet(first.features_path)
    assert "benchmark_return_21" in features
    assert "relative_return_21" in features
    assert "target_price_return_21" in features
    assert "target_income_return_21" in features
    assert "target_total_return_21" in features
    assert "research_eligible" in features
    assert features.loc[features["date"] == dates.iloc[0], "research_eligible"].eq(False).all()
    assert features.loc[
        features["date"] == dates.iloc[252], "research_eligible"
    ].eq(True).all()
    assert manifest["parquet_schemas"]["market"]["version"] == "operum-ml-dataset-v2"
    assert "total_return_index" in manifest["parquet_schemas"]["market"]["columns"]
    assert "target_income_return_21" in manifest["parquet_schemas"]["features"]["columns"]


def test_manifest_retains_explicit_source_failures_and_exclusions(tmp_path):
    market = _cohort_market()
    sources = {
        "prices": {
            "source": "B3",
            "license": "B3 market-data terms",
            "retrieved_at": "2024-12-31T20:00:00+00:00",
            "checksum": "fixture-market-sha256",
            "reconciliation_status": "partial",
            "fallback_used": False,
            "errors": ["authoritative dead-asset history unavailable"],
            "exclusions": [{"ticker": "DEAD3", "reason": "authoritative_history_unavailable"}],
        }
    }

    result = materialize_dataset(
        market,
        output_root=tmp_path,
        cutoff="2024-12-31T23:59:59+00:00",
        sources=sources,
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["sources"]["prices"]["errors"] == [
        "authoritative dead-asset history unavailable"
    ]
    assert manifest["source_exclusions"] == [
        {
            "source_key": "prices",
            "ticker": "DEAD3",
            "reason": "authoritative_history_unavailable",
        }
    ]
    assert manifest["research_universe"]["latest_gate"]["source_data_blocked"] is True
    assert manifest["research_universe"]["latest_gate"]["promotion_blocked"] is True


def test_research_gate_shortfall_does_not_prevent_auditable_materialization(tmp_path):
    dates = pd.bdate_range("2023-01-02", periods=252)
    market = pd.DataFrame(
        {
            "date": dates,
            "ticker": "ONLY3",
            "asset_class": "BR_STOCK",
            "open": 10.0,
            "high": 10.1,
            "low": 9.9,
            "close": 10.0,
            "raw_close": 10.0,
            "split_adjusted_close": 10.0,
            "total_return_index": 10.0,
            "volume": 100_000.0,
        }
    )
    sources = {
        "prices": {
            "source": "B3",
            "license": "B3 market-data terms",
            "retrieved_at": "2024-01-01T00:00:00+00:00",
            "checksum": "fixture-market-sha256",
            "reconciliation_status": "authoritative",
            "fallback_used": False,
            "errors": [],
            "exclusions": [],
        }
    }

    result = materialize_dataset(
        market,
        output_root=tmp_path,
        cutoff="2024-01-01T23:59:59+00:00",
        sources=sources,
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["display_cohort"] == []
    assert manifest["display_cohort_shortfall"] == {"BR_STOCK": 24, "FII": 6}
    assert manifest["research_universe"]["latest_gate"]["promotion_blocked"] is True
    assert result.market_path.exists()


def test_v2_builder_rejects_missing_canonical_market_histories(tmp_path):
    market = _cohort_market().drop(
        columns=["raw_close", "split_adjusted_close", "total_return_index"]
    )

    with pytest.raises(ValueError, match="canonical v2 market columns"):
        materialize_dataset(
            market,
            output_root=tmp_path,
            cutoff="2024-12-31T23:59:59+00:00",
            sources=_authoritative_sources(),
        )


def test_explicit_legacy_market_path_is_non_promotable(tmp_path):
    market = _cohort_market().drop(
        columns=["raw_close", "split_adjusted_close", "total_return_index"]
    )

    result = materialize_dataset(
        market,
        output_root=tmp_path,
        cutoff="2024-12-31T23:59:59+00:00",
        sources=_authoritative_sources(),
        legacy_market=True,
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert manifest["market_contract"] == "legacy_v1_non_promotable"
    assert manifest["research_universe"]["latest_gate"]["source_data_blocked"] is True
    assert manifest["research_universe"]["latest_gate"]["promotion_blocked"] is True


@pytest.mark.parametrize("status", [None, "typo", "unverified", "not_run", "fallback_only"])
def test_source_gate_blocks_every_non_whitelisted_status(status):
    reasons = dataset_builder._source_gate_reasons(
        {"prices": _verified_source(status=status)}, required_keys={"prices"}
    )

    assert reasons


@pytest.mark.parametrize("field", ["license", "checksum", "retrieved_at"])
def test_source_gate_blocks_empty_required_provenance(field):
    reasons = dataset_builder._source_gate_reasons(
        {"prices": _verified_source(**{field: ""})}, required_keys={"prices"}
    )

    assert reasons == [f"prices:missing_{field}"]


def test_source_gate_allows_authoritative_or_reconciled_complete_sources():
    assert dataset_builder._source_gate_reasons(
        {"prices": _verified_source()}, required_keys={"prices"}
    ) == []
    assert dataset_builder._source_gate_reasons(
        {"prices": _verified_source("reconciled", fallback=True)},
        required_keys={"prices"},
    ) == []


def test_context_without_complete_provenance_blocks_source_gate(tmp_path):
    market = _cohort_market()
    dates = market["date"].drop_duplicates().sort_values()
    context = pd.DataFrame(
        {
            "reference_date": dates,
            "available_at": dates.dt.normalize() + pd.Timedelta(hours=23, minutes=59),
            "ibov_close": 100_000.0,
            "usdbrl_close": 5.0,
            "brent_close": 70.0,
        }
    )

    result = materialize_dataset(
        market,
        context=context,
        output_root=tmp_path,
        cutoff="2024-12-31T23:59:59+00:00",
        sources=_authoritative_sources(),
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    gate = manifest["research_universe"]["latest_gate"]
    assert gate["source_data_blocked"] is True
    assert set(manifest["source_gate_reasons"]) == {
        "benchmark:missing_source",
        "fx:missing_source",
        "oil:missing_source",
    }
