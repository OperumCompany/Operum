from __future__ import annotations

import logging
import time

from app.services.asset_universe_service import AssetUniverseService
from app.services.prediction_repository import PredictionRepository
from app.services.predictive_analysis_service import PredictiveAnalysisService
from app.services.prediction_outcome_service import PredictionOutcomeService

logger = logging.getLogger(__name__)


class AnalysisWorker:
    def __init__(self, *, repository=None, analysis=None, assets=None, training_handler=None, outcomes=None):
        self.repository = repository or PredictionRepository()
        self.analysis = analysis or PredictiveAnalysisService(repository=self.repository)
        self.assets = assets or AssetUniverseService()
        self.outcomes = outcomes or PredictionOutcomeService(repository=self.repository)
        if training_handler is None:
            from app.ml.cli import run_scheduled_training

            training_handler = lambda: run_scheduled_training(self.repository)
        self.training_handler = training_handler

    def run_once(self) -> dict:
        job = self.repository.claim_next_job()
        if not job:
            return {"status": "idle"}
        ticker = str(job["ticker"]).upper()
        try:
            if ticker == "__TRAIN__" or job.get("reason") == "monthly_training":
                self.training_handler()
            else:
                asset = self.assets.get_by_ticker(ticker)
                asset_class = asset.asset_class if asset else "BR_STOCK"
                self.analysis.generate(ticker, asset_class, activate=True)
                try:
                    self.outcomes.score_due(ticker)
                except Exception:
                    logger.exception("Falha ao apurar previsoes realizadas para %s", ticker)
            self.repository.complete_job(job["id"])
            return {"status": "completed", "job_id": job["id"], "ticker": ticker}
        except Exception as exc:
            logger.exception("Falha no job preditivo %s para %s", job["id"], ticker)
            self.repository.fail_job(job["id"], str(exc), max_attempts=3)
            return {"status": "failed", "job_id": job["id"], "ticker": ticker, "error": str(exc)}

    def run_forever(self, *, poll_seconds: float = 2.0) -> None:
        self.repository.ensure_schema()
        while True:
            result = self.run_once()
            if result["status"] == "idle":
                time.sleep(poll_seconds)


def main() -> None:
    AnalysisWorker().run_forever()


if __name__ == "__main__":
    main()
