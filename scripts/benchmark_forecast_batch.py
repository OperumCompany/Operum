"""Measure forecast history batches with controlled delays and optional Yahoo I/O."""
import argparse
import json
import logging
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from app.services.forecast_service import ForecastService
from app.services.analysis_execution import analysis_request, start_analysis_executor, stop_analysis_executor
from scripts.benchmark_analysis import load_baseline

TICKERS = ["PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "ABEV3", "WEGE3", "B3SA3"]


def measure(service, workers, repeats):
    samples, frames = [], []
    start_analysis_executor(workers)
    try:
        for _ in range(repeats):
            started = time.perf_counter()
            frames = analysis_request(service._download_batch)(TICKERS)
            samples.append((time.perf_counter() - started) * 1000)
            if not any(frame is not None for frame in frames):
                break
    finally:
        stop_analysis_executor()
    return {"samples_ms": samples, "median_ms": statistics.median(samples), "p95_ms": float(np.percentile(samples, 95)),
            "successful_histories": sum(frame is not None for frame in frames)}, frames


def run(ref, live, output):
    logging.getLogger().setLevel(logging.WARNING)
    service = ForecastService()
    real_fetch = service._fetch_data
    frame = pd.DataFrame({"Close": [1., 2.]})
    def delayed(ticker, period):
        time.sleep(.04)
        return frame
    service._fetch_data = delayed
    serial, _ = measure(service, 1, 5)
    parallel, _ = measure(service, 4, 5)
    report = {"baseline_ref": ref, "controlled": {"one_worker": serial, "four_workers": parallel,
              "reduction_pct": 100 * (1 - parallel["median_ms"] / serial["median_ms"])}}
    assert report["controlled"]["reduction_pct"] >= 50
    if live:
        service._fetch_data = real_fetch
        baseline = load_baseline(ref, "forecast_service").ForecastService()
        # Use the old adapter and sequential calls as the actual before measurement.
        baseline._download_batch = lambda tickers: [baseline._download_data(t, "9mo") for t in tickers]
        old, old_frames = measure(baseline, 1, 2)
        if not old["successful_histories"]:
            report["live_yahoo"] = {"status": "blocked", "before_sequential": old,
                                    "reason": "No histories returned; stop rather than repeat provider failures."}
            Path(output).write_text(json.dumps(report, indent=2), encoding="utf-8")
            return report
        new, new_frames = measure(service, 4, 2)
        equivalence = {}
        for ticker, left, right in zip(TICKERS, old_frames, new_frames):
            if left is None or right is None:
                equivalence[ticker] = "unavailable"
            else:
                try:
                    pd.testing.assert_frame_equal(left.sort_index(axis=1), right.sort_index(axis=1), check_freq=False)
                    equivalence[ticker] = "equal"
                except AssertionError:
                    equivalence[ticker] = "different_live_snapshots"
        report["live_yahoo"] = {"before_sequential": old, "after_four_workers": new, "equivalence": equivalence,
                                "caveat": "Sequential before/after samples can observe market updates and provider caches; small sample."}
    Path(output).write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--output", default="docs/forecast-batch-performance.json")
    args = parser.parse_args()
    run(args.baseline_ref, args.live, args.output)
