from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.jobs.predictive_scheduler import (
    enqueue_news_jobs,
    enqueue_price_jobs,
    monthly_training_due,
)


SP = ZoneInfo("America/Sao_Paulo")


class Repository:
    def __init__(self):
        self.jobs = []

    def enqueue_job(self, ticker, **kwargs):
        job = {"ticker": ticker, **kwargs}
        self.jobs.append(job)
        return job


class EmptyStorage:
    def load_json(self, path):
        return None

    def save_json(self, path, value):
        pass


class Assets:
    def get_all(self):
        return [
            *[SimpleNamespace(ticker=f"S{i:02d}", asset_class="BR_STOCK") for i in range(30)],
            *[SimpleNamespace(ticker=f"F{i:02d}", asset_class="FII") for i in range(10)],
        ]


def test_price_jobs_run_after_market_close_and_catch_up_once():
    repository = Repository()
    before_close = datetime(2026, 8, 24, 18, 59, tzinfo=SP)
    after_close = datetime(2026, 8, 24, 19, 1, tzinfo=SP)

    assert enqueue_price_jobs(repository, ["PETR4", "VALE3"], now=before_close) == []
    jobs = enqueue_price_jobs(repository, ["PETR4", "VALE3"], now=after_close)

    assert len(jobs) == 2
    assert {job["dedupe_key"] for job in jobs} == {
        "PETR4:price:2026-08-24",
        "VALE3:price:2026-08-24",
    }


def test_news_jobs_are_grouped_by_ticker_with_ten_minute_debounce():
    repository = Repository()
    now = datetime(2026, 8, 24, 12, 0, tzinfo=SP)
    news = [
        {"id": "n1", "mentioned_assets": ["PETR4", "VALE3"]},
        {"id": "n2", "mentioned_assets": ["PETR4"]},
    ]

    jobs = enqueue_news_jobs(repository, news, now=now)

    assert len(jobs) == 2
    petr = next(job for job in jobs if job["ticker"] == "PETR4")
    assert petr["run_after"].endswith("12:10:00-03:00")
    assert petr["dedupe_key"].startswith("PETR4:news:")


def test_monthly_training_is_due_after_first_saturday_and_catches_up():
    assert monthly_training_due(datetime(2026, 9, 5, 2, 1, tzinfo=SP), last_month="2026-08") is True
    assert monthly_training_due(datetime(2026, 9, 5, 1, 59, tzinfo=SP), last_month="2026-08") is False
    assert monthly_training_due(datetime(2026, 9, 6, 9, 0, tzinfo=SP), last_month="2026-08") is True
    assert monthly_training_due(datetime(2026, 9, 12, 2, 1, tzinfo=SP), last_month="2026-08") is True
    assert monthly_training_due(datetime(2026, 9, 5, 2, 1, tzinfo=SP), last_month="2026-09") is False


def test_scheduler_fallback_cohort_uses_real_asset_universe_interface():
    from app.jobs.predictive_scheduler import PredictiveScheduler

    scheduler = PredictiveScheduler(
        repository=Repository(),
        storage=EmptyStorage(),
        news=object(),
        assets=Assets(),
    )

    tickers = scheduler._cohort_tickers()

    assert len(tickers) == 30
    assert tickers[:2] == ["S00", "S01"]
    assert tickers[-2:] == ["F04", "F05"]
