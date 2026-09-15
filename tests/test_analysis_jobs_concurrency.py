import multiprocessing

from app.services.file_lock import file_lock
from app.services.local_storage_service import LocalStorageService
from app.services.prediction_repository import PredictionRepository


class DisabledDatabase:
    enabled = False


def repository(directory):
    return PredictionRepository(db=DisabledDatabase(), storage=LocalStorageService(directory))


def enqueue_process(directory, process_index):
    repo = repository(directory)
    for index in range(5):
        repo.enqueue_job("PETR4", reason="forecast_training", dedupe_key="shared")
        repo.enqueue_job("VALE3", reason="forecast_training", dedupe_key=f"{process_index}:{index}")


def test_local_queue_deduplicates_without_losing_other_process_updates(tmp_path):
    context = multiprocessing.get_context("spawn")
    processes = [context.Process(target=enqueue_process, args=(str(tmp_path), n)) for n in range(3)]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=30)
        if process.is_alive():
            process.terminate()
            process.join()
        assert process.exitcode == 0
    jobs = repository(str(tmp_path)).storage.load_json("ai/predictive/jobs.json")
    assert len(jobs) == 16
    assert sum(job["dedupe_key"] == "shared" for job in jobs) == 1


def test_worker_recovery_keeps_attempt_budget_and_daily_deduplication(tmp_path):
    repo = repository(str(tmp_path))
    first = repo.enqueue_job("PETR4", reason="forecast_training", dedupe_key="forecast:PETR4:day1")
    for attempt in range(3):
        job = repo.claim_next_job()
        assert job["attempts"] == attempt + 1
        repo.recover_running_jobs()
    assert repo.claim_next_job() is None
    existing = repo.enqueue_job("PETR4", reason="forecast_training", dedupe_key="forecast:PETR4:day1")
    assert existing["status"] == "failed"
    assert existing["id"] == first["id"]
    repo.enqueue_job("PETR4", reason="forecast_training", dedupe_key="forecast:PETR4:day2")
    assert repo.claim_next_job()["attempts"] == 1


def test_worker_lock_prevents_second_process_owner(tmp_path):
    import pytest
    path = str(tmp_path / "worker.lock")
    with file_lock(path):
        with pytest.raises(TimeoutError):
            with file_lock(path, timeout=0):
                pass
