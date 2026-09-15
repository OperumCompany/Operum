from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.services.asset_universe_service import AssetUniverseService
from app.services.local_storage_service import LocalStorageService
from app.services.news_ingestion_service import NewsIngestionService
from app.services.prediction_repository import PredictionRepository


SAO_PAULO = ZoneInfo("America/Sao_Paulo")


def enqueue_price_jobs(repository, tickers: list[str], *, now: datetime | None = None) -> list[dict]:
    now = (now or datetime.now(SAO_PAULO)).astimezone(SAO_PAULO)
    if now.weekday() >= 5 or now.hour < 19:
        return []
    date_key = now.date().isoformat()
    return [
        repository.enqueue_job(
            ticker.upper(),
            reason="price",
            dedupe_key=f"{ticker.upper()}:price:{date_key}",
            priority=20,
        )
        for ticker in tickers
    ]


def enqueue_news_jobs(repository, news: list[dict], *, now: datetime | None = None) -> list[dict]:
    now = (now or datetime.now(SAO_PAULO)).astimezone(SAO_PAULO)
    by_ticker: dict[str, set[str]] = {}
    for item in news:
        for ticker in item.get("mentioned_assets", []):
            by_ticker.setdefault(str(ticker).upper(), set()).add(str(item.get("id", "")))
    run_after = (now + timedelta(minutes=10)).isoformat()
    jobs = []
    for ticker, ids in sorted(by_ticker.items()):
        fingerprint = hashlib.sha256(json.dumps(sorted(ids)).encode("utf-8")).hexdigest()[:20]
        jobs.append(
            repository.enqueue_job(
                ticker,
                reason="news",
                dedupe_key=f"{ticker}:news:{fingerprint}",
                priority=50,
                run_after=run_after,
            )
        )
    return jobs


def monthly_training_due(now: datetime, *, last_month: str | None) -> bool:
    local = now.astimezone(SAO_PAULO)
    month = local.strftime("%Y-%m")
    first = local.replace(day=1, hour=2, minute=0, second=0, microsecond=0)
    first_saturday = first + timedelta(days=(5 - first.weekday()) % 7)
    return local >= first_saturday and last_month != month


class PredictiveScheduler:
    def __init__(self, *, repository=None, storage=None, news=None, assets=None):
        self.repository = repository or PredictionRepository()
        self.storage = storage or LocalStorageService()
        self.news = news or NewsIngestionService()
        self.assets = assets or AssetUniverseService()
        self.state_path = "ai/predictive/scheduler_state.json"

    def _state(self) -> dict:
        return self.storage.load_json(self.state_path) or {}

    def _save_state(self, state: dict) -> None:
        self.storage.save_json(self.state_path, state)

    def _cohort_tickers(self) -> list[str]:
        latest = self.storage.load_json("datasets/predictive/latest.json") or {}
        tickers = latest.get("tickers")
        if tickers:
            return [str(ticker).upper() for ticker in tickers]
        universe = self.assets.get_all()
        stocks = [asset.ticker for asset in universe if asset.asset_class == "BR_STOCK"][:24]
        fiis = [asset.ticker for asset in universe if asset.asset_class == "FII"][:6]
        return stocks + fiis

    def tick(self, *, now: datetime | None = None) -> dict:
        now = (now or datetime.now(SAO_PAULO)).astimezone(SAO_PAULO)
        state = self._state()
        result = {"news_jobs": 0, "price_jobs": 0, "training_jobs": 0}
        last_news = datetime.fromisoformat(state["last_news_ingest"]) if state.get("last_news_ingest") else None
        if last_news is None or now - last_news.astimezone(SAO_PAULO) >= timedelta(minutes=15):
            previous = {item.id for item in self.news.get_all_raw()}
            self.news.ingest()
            new_items = [item.model_dump(mode="json") for item in self.news.get_all_raw() if item.id not in previous]
            result["news_jobs"] = len(enqueue_news_jobs(self.repository, new_items, now=now))
            state["last_news_ingest"] = now.isoformat()

        price_date = now.date().isoformat()
        if state.get("last_price_date") != price_date:
            price_jobs = enqueue_price_jobs(self.repository, self._cohort_tickers(), now=now)
            if price_jobs:
                state["last_price_date"] = price_date
                result["price_jobs"] = len(price_jobs)

        if monthly_training_due(now, last_month=state.get("last_training_month")):
            month = now.strftime("%Y-%m")
            self.repository.enqueue_job(
                "__TRAIN__",
                reason="monthly_training",
                dedupe_key=f"training:{month}",
                priority=5,
            )
            state["last_training_month"] = month
            result["training_jobs"] = 1
        self._save_state(state)
        return result

    def run_forever(self, *, poll_seconds: float = 30.0) -> None:
        self.repository.ensure_schema()
        while True:
            self.tick()
            time.sleep(poll_seconds)


def main() -> None:
    PredictiveScheduler().run_forever()


if __name__ == "__main__":
    main()
