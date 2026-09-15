"""Offline comparison against a Git revision; never calls market/LLM providers.

python scripts/benchmark_analysis.py --repeats 5
"""
from __future__ import annotations

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import tempfile
import time
import types
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class FrozenDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2026, 9, 13, 12, tzinfo=timezone.utc)
        return value.astimezone(tz) if tz else value.replace(tzinfo=None)


def load_baseline(ref, filename):
    source = subprocess.check_output(["git", "show", f"{ref}:app/services/{filename}.py"], encoding="utf-8")
    module = types.ModuleType(f"before_{filename}")
    module.__file__ = str(Path(__file__).resolve().parents[1] / "app" / "services" / f"{filename}.py")
    exec(compile(source, filename, "exec"), module.__dict__)
    module.datetime = FrozenDatetime
    return module


DEFAULT_BASELINE_REF = "1e4ac3a703bcd81a0ed62f1278ef3c4bbb08283f"


def run_comparison(baseline_ref=DEFAULT_BASELINE_REF, repeats=5, capture_refinement=None):
    import numpy as np
    import pandas as pd
    from app.schemas.news import NewsItem
    from app.schemas.portfolio import Portfolio, Position
    from app.services import analysis_execution as execution
    from app.services.forecast_service import ForecastService
    from app.services.market_data_service import MarketDataService

    before_asset = load_baseline(baseline_ref, "asset_analysis_service")
    before_portfolio = load_baseline(baseline_ref, "portfolio_opinion_service")
    after_asset = importlib.import_module("app.services.asset_analysis_service")
    after_portfolio = importlib.import_module("app.services.portfolio_opinion_service")
    tickers = ["PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "ABEV3", "WEGE3", "B3SA3", "RENT3", "SUZB3",
               "KNRI11", "HGLG11", "MXRF11", "KNCR11", "VISC11", "AAPL34", "MSFT34", "GOOG34", "IVVB11", "BTC"]
    close = 100 * np.cumprod(1 + np.sin(np.arange(280)) * 0.004 + 0.0002)
    frame = pd.DataFrame({"date": pd.date_range(end="2026-09-13", periods=280).strftime("%Y-%m-%d"), "close": close})
    news = [NewsItem(
        id=f"{ticker}-{n}", title=f"{ticker} resultados receita trimestre {n}",
        source_name=f"Fonte {n}", source_url=f"https://example.com/{ticker}/{n}",
        published_at=FrozenDatetime.now(timezone.utc), created_at=FrozenDatetime.now(timezone.utc),
        content_preview=f"{ticker} divulga resultados operacionais e lucro.",
        summary="Resultados e perspectivas divulgados pela companhia.", mentioned_assets=[ticker],
        impact_score=0.6, relevance_score=0.8, sentiment_score=0.1,
    ) for ticker in tickers for n in range(3)]

    def execute(asset_module, portfolio_module, size, mode, operation, history_horizon="3m", outlook_horizon="3m"):
        counts = Counter()
        llm_seconds = 0.0
        class ForecastFixture:
            _interpolate_series = ForecastService._interpolate_series
            def predict_multi(self, ticker, requested_horizons=None):
                counts["forecast"] += 1
                horizons = requested_horizons or [5, 21, 42, 63]
                if mode == "models_absent":
                    execution.record_forecast(ticker, horizons, horizons, "pending")
                    return None
                execution.record_forecast(ticker, horizons, [], "not_scheduled")
                predictions = [{"horizon_days": h, "horizon_label": f"{h}d", "predicted_return": 0.01,
                                "predicted_price": float(close[-1] * 1.01), "confidence": 0.6, "direction": "up"}
                               for h in horizons]
                return {"predictions": predictions, "last_price": float(close[-1]),
                        "generated_at": FrozenDatetime.now(timezone.utc).isoformat(),
                        "forecast_series": self._interpolate_series(float(close[-1]), FrozenDatetime.now(timezone.utc), predictions),
                        "forecast_anchor_points": []}
            def predict_many(self, tickers):
                return [self.predict(ticker) for ticker in tickers]
            def predict(self, ticker):
                result = self.predict_multi(ticker, [1])
                return {"confidence": 0.6} if result else None

        class LLMFixture:
            enabled = True
            def chat_json(self, *args, **kwargs):
                nonlocal llm_seconds
                counts["llm"] += 1
                if capture_refinement is not None and asset_module is after_asset:
                    capture_refinement(operation, size, args, kwargs)
                start = time.perf_counter()
                time.sleep(0.003)
                llm_seconds += time.perf_counter() - start
                return None  # Preserve deterministic text for exact comparison.

        market = MarketDataService()
        def history(*args, **kwargs):
            counts["history"] += 1
            time.sleep(0.003 if mode == "cold_data" else 0.0002)
            return {"prices": frame.to_dict("records")}
        def current(ticker):
            counts["current_price"] += 1
            return {"price": float(close[-1]), "currency": "BRL"}
        market._get_history = history
        market._get_current_price = current
        asset = asset_module.AssetAnalysisService()
        service = portfolio_module.PortfolioOpinionService()
        def load_news():
            counts["news_load"] += 1
            return deepcopy(news)
        for instance in (asset, service):
            instance.forecast = ForecastFixture()
            instance.llm = LLMFixture()
        asset.market = market
        asset.news._get_all_raw = load_news
        asset.semantic_news.semantic_scores = lambda *a, **k: {}
        service.news_service._get_all_raw = load_news
        service.semantic_news.semantic_scores = lambda *a, **k: {}
        service.asset_analysis = asset
        service.analytics.market = market
        assets = {a.ticker: a for a in asset.assets.get_all()}
        now = FrozenDatetime.now(timezone.utc)
        portfolio = Portfolio(id="benchmark", name="Benchmark", created_at=now, updated_at=now,
                              positions=[Position(asset_id=t, ticker=t, asset_class=assets[t].asset_class,
                                                  quantity=n + 1, avg_price=95) for n, t in enumerate(tickers[:size])])
        def run():
            if operation == "asset":
                return asset.generate_asset_analysis(portfolio, tickers[0], history_horizon, outlook_horizon)
            calls = [lambda t=t: market.get_history(t, "1y", "1d") for t in tickers[:size]]
            results = execution.parallel_queries(calls) if asset_module is after_asset else [call() for call in calls]
            prices = {t: pd.DataFrame(result["prices"]) for t, result in zip(tickers[:size], results)}
            analysis = service.analytics.analyze(portfolio, prices)
            return service.generate_opinion(portfolio, analysis, prices, analysis_horizon=history_horizon)
        if asset_module is after_asset:
            run = execution.analysis_request(run)
        with patch.object(asset_module, "AI_ENHANCE_ASSET_ANALYSIS", True), \
             patch.object(portfolio_module, "AI_ENHANCE_PORTFOLIO_ANALYSIS", True):
            start = time.perf_counter()
            result = run()
            elapsed = time.perf_counter() - start
        result.pop("forecast_availability", None)
        return result, elapsed * 1000, llm_seconds * 1000, dict(counts)

    report = []
    with tempfile.TemporaryDirectory(prefix="operum-analysis-bench-") as directory, \
         patch.dict(os.environ, {"OPERUM_DATA_DIR": directory, "OPERUM_MODELS_DIR": str(Path(directory) / "models")}), \
         patch.object(execution, "datetime", FrozenDatetime), \
         patch.object(after_asset, "datetime", FrozenDatetime), \
         patch.object(after_portfolio, "datetime", FrozenDatetime):
        execution.start_analysis_executor(4)
        try:
            for history in ("1w", "1m", "2m", "3m"):
                for outlook in ("1w", "1m", "2m", "3m"):
                    old = execute(before_asset, before_portfolio, 1, "warm_data", "asset", history, outlook)
                    new = execute(after_asset, after_portfolio, 1, "warm_data", "asset", history, outlook)
                    assert old[0] == new[0], f"Asset horizon output changed: {history}/{outlook}"
            for horizon in ("1m", "2m", "3m"):
                old = execute(before_asset, before_portfolio, 10, "warm_data", "portfolio", horizon)
                new = execute(after_asset, after_portfolio, 10, "warm_data", "portfolio", horizon)
                assert old[0] == new[0], f"Portfolio horizon output changed: {horizon}"
            for mode in ("warm_data", "cold_data", "models_absent"):
                for operation, size in [("asset", 1), ("portfolio", 5), ("portfolio", 10), ("portfolio", 20)]:
                    samples = {"before": [], "after": []}
                    for _ in range(repeats):
                        old = execute(before_asset, before_portfolio, size, mode, operation)
                        new = execute(after_asset, after_portfolio, size, mode, operation)
                        assert old[0] == new[0], f"Output changed: {mode}/{operation}/{size}"
                        samples["before"].append(old)
                        samples["after"].append(new)
                    row = {"mode": mode, "operation": operation, "assets": size, "equivalent": True}
                    for label, values in samples.items():
                        row[label] = {"median_ms": round(statistics.median(v[1] for v in values), 2),
                                      "p95_ms": round(float(np.percentile([v[1] for v in values], 95)), 2),
                                      "llm_median_ms": round(statistics.median(v[2] for v in values), 2),
                                      "operations": values[-1][3]}
                    report.append(row)
        finally:
            execution.stop_analysis_executor()
    # Independent equal-latency query acceptance scenario.
    query_samples = {}
    for workers in (1, 4):
        execution.start_analysis_executor(workers)
        try:
            values = []
            for _ in range(repeats):
                start = time.perf_counter()
                execution.parallel_queries([lambda: time.sleep(0.02)] * 10)
                values.append((time.perf_counter() - start) * 1000)
            query_samples[str(workers)] = round(statistics.median(values), 2)
        finally:
            execution.stop_analysis_executor()
    reduction = 1 - query_samples["4"] / query_samples["1"]
    assert reduction >= 0.4, query_samples
    return {"baseline_ref": baseline_ref, "repeats": repeats, "horizon_equivalence_checks": 19,
            "scope": "Offline fixtures; simulated I/O and LLM latency, no real training or inference timing",
            "query_median_ms_by_workers": query_samples, "query_reduction_pct": round(reduction * 100, 2),
            "scenarios": report}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-ref", default=DEFAULT_BASELINE_REF)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output")
    args = parser.parse_args()
    os.environ["OPERUM_STORAGE_MODE"] = "local"
    for name in ("AI_ENABLED", "NEWS_EMBEDDINGS_ENABLED", "FINANCIAL_NLP_ENABLED"):
        os.environ[name] = "false"
    import logging
    logging.disable(logging.INFO)
    report = run_comparison(args.baseline_ref, args.repeats)
    rendered = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
