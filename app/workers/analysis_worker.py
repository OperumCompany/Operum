from __future__ import annotations

import logging
from pathlib import Path
from app.services.forecast_service import ForecastService
from app.services.file_lock import file_lock
import time

from app.services.asset_universe_service import AssetUniverseService
from app.services.prediction_repository import PredictionRepository
from app.services.predictive_analysis_service import PredictiveAnalysisService
from app.services.prediction_outcome_service import PredictionOutcomeService

logger = logging.getLogger(__name__)


class AnalysisWorker:
    def __init__(self, *, repository=None, analysis=None, assets=None, training_handler=None, outcomes=None, forecast=None):
        self.repository = repository or PredictionRepository()
        self.analysis = analysis or PredictiveAnalysisService(repository=self.repository)
        self.assets = assets or AssetUniverseService()
        self.outcomes = outcomes or PredictionOutcomeService(repository=self.repository)
        if training_handler is None:
            from app.ml.cli import run_scheduled_training

            training_handler = lambda: run_scheduled_training(self.repository)
        self.training_handler = training_handler
        self.forecast = forecast or ForecastService(repository=self.repository)

    def run_once(self) -> dict:
        job = self.repository.claim_next_job()
        if not job:
            return {"status": "idle"}
        ticker = str(job["ticker"]).upper()
        try:
            if job.get("reason") == "forecast_training":
                missing = self.forecast.missing_horizons(ticker, [1, 5, 21, 42, 63])
                if missing:
                    result = self.forecast.train(ticker, horizons=missing)
                    remaining = self.forecast.missing_horizons(ticker, missing)
                    if result.get("status") == "error" or result.get("errors") or remaining:
                        raise RuntimeError(f"Forecast training incomplete; missing horizons: {remaining}")
            elif ticker == "__TRAIN__" or job.get("reason") == "monthly_training":
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
        lock_path = str(Path(self.repository.storage.base_dir) / "ai" / "analysis-worker.lock")
        with file_lock(lock_path, timeout=0):
            self.repository.ensure_schema()
            self.repository.recover_running_jobs()
            while True:
                result = self.run_once()
                if result["status"] in {"idle", "failed"}:
                    time.sleep(poll_seconds)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", help="Identifies this workspace in the process command line")
    parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    try:
        AnalysisWorker().run_forever()
    except TimeoutError:
        logger.error("An analysis worker is already running for this data directory")
        raise SystemExit(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
