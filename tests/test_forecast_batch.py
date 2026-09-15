from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd

from app.services.analysis_execution import start_analysis_executor, stop_analysis_executor
from app.services.forecast_service import ForecastService
from app.services.portfolio_opinion_service import PortfolioOpinionService


class Model:
    def predict(self, frame):
        return np.full(len(frame), 0.02)


def make_service(tmp_path, monkeypatch):
    monkeypatch.setenv("OPERUM_MODELS_DIR", str(tmp_path))
    service = ForecastService(repository=Mock())
    service.models = {ticker: {1: Model()} for ticker in ("AAA", "BBB", "CCC")}
    prices = np.linspace(80, 120, 180)
    frame = pd.DataFrame({"Close": prices, "High": prices + 1, "Low": prices - 1})
    service._fetch_data = Mock(return_value=frame)
    return service, frame


def without_time(value):
    value = deepcopy(value)
    for item in value:
        if item:
            item.pop("generated_at")
    return value


def test_batch_matches_sequential_and_deduplicates(tmp_path, monkeypatch):
    service, frame = make_service(tmp_path, monkeypatch)
    tickers = ["AAA", "BBB", "AAA", "CCC"]
    sequential = [service.predict(ticker) for ticker in tickers]
    service._fetch_data.reset_mock()
    start_analysis_executor(4)
    try:
        batch = service.predict_many(tickers)
    finally:
        stop_analysis_executor()
    assert without_time(batch) == without_time(sequential)
    assert service._fetch_data.call_count == 3


def test_missing_short_failed_history_not_retried(tmp_path, monkeypatch):
    service, frame = make_service(tmp_path, monkeypatch)
    service._fetch_data.side_effect = lambda ticker, period: None if ticker == "AAA" else frame[:2] if ticker == "BBB" else frame
    service.train = Mock(side_effect=AssertionError("No inline training"))
    result = service.predict_many(["AAA", "AAA", "BBB", "CCC", "MISSING"])
    assert result[0:3] == [None, None, None]
    assert result[3]["ticker"] == "CCC" and result[4] is None
    assert service._fetch_data.call_count == 3
    service.repository.enqueue_job.assert_called_once()


def test_simultaneous_batches_share_limit_without_mixing_data(tmp_path, monkeypatch):
    service, frame = make_service(tmp_path, monkeypatch)
    lock = threading.Lock()
    active = peak = 0
    def download(ticker, period):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return frame * (2 if ticker == "BBB" else 1)
    service._fetch_data = download
    start_analysis_executor(2)
    try:
        with ThreadPoolExecutor(3) as callers:
            batches = list(callers.map(lambda _: service.predict_many(["AAA", "BBB", "AAA"]), range(3)))
    finally:
        stop_analysis_executor()
    assert peak == 2
    for batch in batches:
        assert [item["last_price"] for item in batch] == [120, 240, 120]


def test_history_adapter_matches_download_defaults(tmp_path, monkeypatch):
    service, _ = make_service(tmp_path, monkeypatch)
    service._fetch_data = ForecastService._fetch_data.__get__(service)
    frame = pd.DataFrame({"Close": [2., 1.], "High": [3., 2.], "Low": [1., 0.]}, index=pd.date_range("2026-01-01", periods=2, tz="America/Sao_Paulo")[::-1])
    ticker = Mock()
    ticker.history.return_value = frame
    factory = Mock(return_value=ticker)
    monkeypatch.setattr("app.services.forecast_service.yf.Ticker", factory)
    result = service._fetch_data("PETR4", "9mo")
    factory.assert_called_once_with("PETR4.SA")
    ticker.history.assert_called_once_with(period="9mo", interval="1d", actions=False, auto_adjust=True, back_adjust=False, repair=False, keepna=False, prepost=False, rounding=False, timeout=10, raise_errors=True)
    expected = frame.sort_index()
    expected.index = expected.index.tz_localize(None)
    pd.testing.assert_frame_equal(result, expected)
    ticker.history.side_effect = RuntimeError("Provider offline")
    assert service._fetch_data("PETR4", "9mo") is None


def test_portfolio_preserves_first_eight_and_duplicate_weight():
    service = object.__new__(PortfolioOpinionService)
    service.forecast = Mock()
    service.forecast.predict_many.return_value = [{"confidence": .2}, {"confidence": .8}, {"confidence": .2}] + [None] * 5
    tickers = ["AAA", "BBB", "AAA", "C", "D", "E", "F", "G", "IGNORED"]
    portfolio = SimpleNamespace(positions=[SimpleNamespace(ticker=t) for t in tickers])
    assert service._compute_forecast_risk(portfolio, {}) == .24
    service.forecast.predict_many.assert_called_once_with(tickers[:8])


def test_eight_downloads_four_workers_reduce_batch_time(tmp_path, monkeypatch):
    service, frame = make_service(tmp_path, monkeypatch)
    service._available_horizons = lambda ticker, horizons: [1]
    service.models = {str(i): {1: Model()} for i in range(8)}
    def download(ticker, period):
        time.sleep(.04)
        return frame
    service._fetch_data = download
    durations = []
    for workers in (1, 4):
        start_analysis_executor(workers)
        try:
            started = time.perf_counter()
            service._download_batch([str(i) for i in range(8)])
            durations.append(time.perf_counter() - started)
        finally:
            stop_analysis_executor()
    assert durations[1] < durations[0] * .5, durations


def test_history_matches_yfinance_download_on_identical_provider_data(tmp_path, monkeypatch):
    import yfinance as yf
    import yfinance.multi as multi
    service, frame = make_service(tmp_path, monkeypatch)
    service._fetch_data = ForecastService._fetch_data.__get__(service)
    frame = frame.copy()
    frame.index = pd.date_range("2026-01-01", periods=len(frame), tz="America/Sao_Paulo", name="Date")
    factory = lambda ticker: SimpleNamespace(history=lambda **kwargs: frame.copy())
    monkeypatch.setattr(multi, "Ticker", factory)
    monkeypatch.setattr(yf, "Ticker", factory)
    old = yf.download("PETR4.SA", period="9mo", progress=False, threads=False, timeout=10)
    old.columns = [column[0] for column in old.columns]
    new = service._fetch_data("PETR4", "9mo")
    pd.testing.assert_frame_equal(old.sort_index(axis=1), new.sort_index(axis=1), check_freq=False)
