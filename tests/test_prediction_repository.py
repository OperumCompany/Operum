from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.services.local_storage_service import LocalStorageService
from app.services.prediction_repository import PredictionRepository


class DisabledDatabase:
    enabled = False


def _repository(tmp_path) -> PredictionRepository:
    return PredictionRepository(
        db=DisabledDatabase(),
        storage=LocalStorageService(str(tmp_path)),
    )


def test_activating_snapshot_preserves_history_and_replaces_pointer(tmp_path):
    repository = _repository(tmp_path)
    first = repository.save_snapshot(
        ticker="PETR4",
        payload={"generation_mode": "baseline", "horizons": {"1m": {}}},
        data_cutoff="2026-08-24T19:00:00+00:00",
        news_fingerprint="news-a",
        activate=True,
    )
    second = repository.save_snapshot(
        ticker="PETR4",
        payload={"generation_mode": "model", "horizons": {"1m": {"expected_return": 0.02}}},
        data_cutoff="2026-08-25T19:00:00+00:00",
        news_fingerprint="news-b",
        activate=True,
    )

    active = repository.get_active_snapshot("PETR4")
    history = repository.list_snapshots("PETR4")
    assert active["id"] == second["id"]
    assert active["payload"]["generation_mode"] == "model"
    assert {item["id"] for item in history} == {first["id"], second["id"]}


def test_snapshot_records_three_future_outcomes_for_audit(tmp_path):
    repository = _repository(tmp_path)
    horizon = {
        "expected_return": 0.03,
        "return_range": {"adverse": -0.07, "base": 0.03, "favorable": 0.13},
    }
    snapshot = repository.save_snapshot(
        ticker="PETR4",
        payload={
            "generation_mode": "baseline",
            "horizons": {"1m": horizon, "2m": horizon, "3m": horizon},
        },
        data_cutoff="2026-08-24T19:00:00+00:00",
        news_fingerprint="news-a",
        activate=True,
    )

    outcomes = repository.list_prediction_outcomes(snapshot_id=snapshot["id"])

    assert [item["horizon_days"] for item in outcomes] == [21, 42, 63]
    assert all(item["actual_return"] is None for item in outcomes)


def test_shadow_snapshot_can_be_activated_without_regeneration(tmp_path):
    repository = _repository(tmp_path)
    shadow = repository.save_snapshot(
        ticker="PETR4",
        payload={"generation_mode": "model", "horizons": {}},
        data_cutoff="2026-08-24T19:00:00+00:00",
        news_fingerprint="shadow",
        activate=False,
    )

    activated = repository.activate_snapshot(shadow["id"])

    assert activated["is_active"] is True
    assert repository.get_active_snapshot("PETR4")["id"] == shadow["id"]


def test_job_queue_deduplicates_and_recovers_failures(tmp_path):
    repository = _repository(tmp_path)
    first = repository.enqueue_job("PETR4", reason="news", dedupe_key="PETR4:news:abc")
    second = repository.enqueue_job("PETR4", reason="news", dedupe_key="PETR4:news:abc")

    assert first["id"] == second["id"]
    claimed = repository.claim_next_job()
    assert claimed["status"] == "running"
    repository.fail_job(claimed["id"], "temporary", max_attempts=3)
    retry = repository.claim_next_job()
    assert retry["id"] == claimed["id"]
    assert retry["attempts"] == 2
    repository.complete_job(retry["id"])
    assert repository.claim_next_job() is None


def test_failed_job_does_not_change_active_snapshot(tmp_path):
    repository = _repository(tmp_path)
    snapshot = repository.save_snapshot(
        ticker="VALE3",
        payload={"generation_mode": "baseline", "horizons": {}},
        data_cutoff=datetime.now(timezone.utc).isoformat(),
        news_fingerprint="initial",
        activate=True,
    )
    job = repository.enqueue_job("VALE3", reason="price", dedupe_key="VALE3:price:1")
    repository.claim_next_job()
    repository.fail_job(job["id"], "provider unavailable", max_attempts=1)

    assert repository.get_active_snapshot("VALE3")["id"] == snapshot["id"]


def test_supabase_schema_contains_predictive_pipeline_tables_and_active_guard():
    schema = Path("docs/supabase-schema.sql").read_text(encoding="utf-8").lower()

    for table in ("model_versions", "asset_analysis_snapshots", "analysis_jobs", "prediction_outcomes"):
        assert f"create table if not exists public.{table}" in schema
        assert f"alter table public.{table} enable row level security" in schema
    assert "idx_asset_analysis_one_active" in schema
    assert "where is_active" in schema


def test_model_promotion_keeps_only_one_active_version_per_class_and_horizon(tmp_path):
    repository = _repository(tmp_path)
    first = repository.register_model_version(
        {
            "id": "model-a",
            "model_family": "xgboost_pool",
            "asset_class": "BR_STOCK",
            "horizon_days": 21,
            "artifact_path": "a.joblib",
            "metadata_path": "a.json",
            "dataset_hash": "dataset-a",
            "feature_schema_version": "v1",
            "metrics": {},
            "status": "shadow",
        }
    )
    second = repository.register_model_version(
        {
            **first,
            "id": "model-b",
            "artifact_path": "b.joblib",
            "metadata_path": "b.json",
            "dataset_hash": "dataset-b",
        }
    )

    repository.promote_model(second["id"])

    assert repository.get_active_model("BR_STOCK", 21)["id"] == "model-b"
    assert repository.get_model_version("model-a")["status"] == "archived"


def test_model_package_promotion_is_all_or_nothing_when_gate_fails(tmp_path):
    repository = _repository(tmp_path)
    good = repository.register_model_version(
        {
            "id": "good",
            "model_family": "xgboost_pool",
            "asset_class": "BR_STOCK",
            "horizon_days": 21,
            "artifact_path": "good.joblib",
            "metadata_path": "good.json",
            "dataset_hash": "dataset-a",
            "feature_schema_version": "v1",
            "metrics": {"promotion_reasons": []},
            "status": "shadow",
        }
    )
    bad = repository.register_model_version(
        {
            **good,
            "id": "bad",
            "horizon_days": 42,
            "metrics": {"promotion_reasons": ["mae"]},
        }
    )

    try:
        repository.promote_model_package(["good", "bad"], require_gates=True)
    except ValueError:
        pass
    else:
        raise AssertionError("A promoção deveria falhar")

    assert repository.get_model_version("good")["status"] == "shadow"
    assert repository.get_model_version("bad")["status"] == "shadow"
