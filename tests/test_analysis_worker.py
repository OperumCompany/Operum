from __future__ import annotations

from app.workers.analysis_worker import AnalysisWorker


class Repository:
    def __init__(self, job):
        self.job = job
        self.completed = []
        self.failed = []

    def claim_next_job(self):
        job, self.job = self.job, None
        return job

    def complete_job(self, job_id):
        self.completed.append(job_id)

    def fail_job(self, job_id, error, max_attempts=3):
        self.failed.append((job_id, error, max_attempts))


class Assets:
    def get_by_ticker(self, ticker):
        return type("Asset", (), {"asset_class": "BR_STOCK"})()


class Analysis:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def generate(self, ticker, asset_class, activate=True):
        self.calls.append((ticker, asset_class, activate))
        if self.fail:
            raise RuntimeError("temporary failure")
        return {"ticker": ticker}


class Trainer:
    def __init__(self):
        self.calls = 0

    def __call__(self):
        self.calls += 1
        return {"model_ids": ["shadow-a"]}


def test_worker_completes_successful_analysis_job():
    repository = Repository({"id": "job-1", "ticker": "PETR4", "reason": "news"})
    analysis = Analysis()
    worker = AnalysisWorker(repository=repository, analysis=analysis, assets=Assets())

    result = worker.run_once()

    assert result == {"status": "completed", "job_id": "job-1", "ticker": "PETR4"}
    assert repository.completed == ["job-1"]
    assert analysis.calls == [("PETR4", "BR_STOCK", True)]


def test_worker_requeues_failure_without_claiming_success():
    repository = Repository({"id": "job-2", "ticker": "VALE3", "reason": "price"})
    worker = AnalysisWorker(repository=repository, analysis=Analysis(fail=True), assets=Assets())

    result = worker.run_once()

    assert result["status"] == "failed"
    assert repository.completed == []
    assert repository.failed[0][0] == "job-2"
    assert "temporary failure" in repository.failed[0][1]


def test_worker_routes_monthly_training_without_asset_analysis():
    repository = Repository({"id": "job-train", "ticker": "__TRAIN__", "reason": "monthly_training"})
    analysis = Analysis()
    trainer = Trainer()
    worker = AnalysisWorker(
        repository=repository,
        analysis=analysis,
        assets=Assets(),
        training_handler=trainer,
    )

    result = worker.run_once()

    assert result == {"status": "completed", "job_id": "job-train", "ticker": "__TRAIN__"}
    assert trainer.calls == 1
    assert analysis.calls == []
