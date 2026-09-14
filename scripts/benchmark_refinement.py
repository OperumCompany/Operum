"""Compare real local LLM calls on synthetic, identical analysis inputs.

Market/news inputs are fixtures: this is not an end-to-end production benchmark.
No model unload, training, portfolio writes or provider configuration changes.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import logging
import os
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for name in ("NEWS_EMBEDDINGS_ENABLED", "FINANCIAL_NLP_ENABLED"):
    os.environ[name] = "false"

from scripts.benchmark_analysis import load_baseline, run_comparison
from app.services import analysis_execution as execution
from app.services.llm_service import LLMService
from app.services.asset_analysis_service import AssetAnalysisService


def run(ref, repeats, output, resume=False):
    inputs = {}
    def capture(operation, size, args, kwargs):
        inputs.setdefault((operation, size), (deepcopy(args), dict(kwargs)))
    logging.getLogger().setLevel(logging.WARNING)
    run_comparison(ref, 1, capture)
    before = load_baseline(ref, "llm_service").LLMService()
    after = LLMService()
    before.enabled = after.enabled = True
    if not after.is_reachable():
        raise RuntimeError("Configured LLM is not reachable")
    validator = object.__new__(AssetAnalysisService)
    rows = []
    report = {"baseline_ref": ref, "model": after.model, "provider": after.provider,
              "scope": "Real LLM; synthetic market/news/portfolio inputs. Not full endpoint latency.",
              "cold_start": "Not forced; initial residency unknown to avoid unloading the user's model.",
              "samples": rows}

    if resume and Path(output).exists():
        saved = json.loads(Path(output).read_text(encoding="utf-8"))
        if saved["baseline_ref"] != ref or saved["model"] != after.model:
            raise ValueError("Cannot mix different baseline revisions or models")
        rows.extend(saved["samples"])

    class Measurements(logging.Handler):
        def emit(self, record):
            context = execution._context.get()
            if context is None:
                return
            if record.msg.startswith("llm_refinement_metrics"):
                provider, outcome, http_ms, metrics = record.args
                context.llm_measurement = {"outcome": outcome, "http_ms": http_ms, "metrics": metrics}
            elif "timed out" in record.getMessage().lower():
                execution.count("llm_timeout")
    handler = Measurements()
    for name in ("app.services.llm_service", "before_llm_service"):
        logging.getLogger(name).setLevel(logging.INFO)
        logging.getLogger(name).addHandler(handler)

    @execution.analysis_request
    def sample(label, key, phase):
        args, kwargs = inputs[key]
        kwargs = dict(kwargs)
        model = kwargs.pop("response_model")
        started = time.perf_counter()
        if label == "before":
            result = before.chat_json(*args, **kwargs)
        else:
            result = after.chat_json(*args, **kwargs, response_model=model)
        elapsed = (time.perf_counter() - started) * 1000
        # Report both schema acceptance and actual legacy partial acceptance separately.
        legacy_accepted = bool(result) and (validator._valid_refined_box_sections(result) if key[0] == "asset" else any(
            isinstance(result.get(k), str) and result[k].strip() for k in ("headline", "composition_summary", "final_diagnosis", "conclusion")))
        try:
            parsed = model.model_validate(result).model_dump()
            valid = key[0] != "asset" or validator._valid_refined_box_sections(parsed)
        except Exception:
            valid = False
        return {"version": label, "operation": key[0], "positions": key[1], "phase": phase,
                "elapsed_ms": round(elapsed, 2), "schema_and_content_valid": valid,
                "legacy_text_accepted": bool(legacy_accepted), "counts": dict(execution._context.get().counts),
                "text": result, "measurement": getattr(execution._context.get(), "llm_measurement", None)}

    def save():
        groups = {}
        for row in rows:
            groups.setdefault((row["version"], row["operation"], row["positions"], row["phase"]), []).append(row)
        report["summary"] = []
        for key, values in groups.items():
            times = sorted(item["elapsed_ms"] for item in values)
            import numpy as np
            report["summary"].append({"version": key[0], "operation": key[1], "positions": key[2], "phase": key[3],
                                      "samples": len(values), "median_ms": round(statistics.median(times), 2),
                                      "p95_ms": round(float(np.percentile(times, 95)), 2),
                                      "valid_rate": sum(item["schema_and_content_valid"] for item in values) / len(values)})
        Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    for repeat in range(repeats):
        for key in (("asset", 1), ("portfolio", 5), ("portfolio", 10), ("portfolio", 20)):
            for label in (("before", "after") if repeat % 2 == 0 else ("after", "before")):
                phase = "initial" if repeat == 0 else "warm"
                completed = sum(r["version"] == label and r["operation"] == key[0] and r["positions"] == key[1] and r["phase"] == phase for r in rows)
                if completed >= (1 if repeat == 0 else repeat):
                    continue
                row = sample(label, key, phase)
                rows.append(row)
                save()
                print({k: v for k, v in row.items() if k not in ("text", "counts")}, flush=True)
    for label in ("before", "after"):
        with ThreadPoolExecutor(2) as callers:
            futures = [callers.submit(sample, label, key, "concurrent") for key in (("asset", 1), ("portfolio", 10))
                       if not any(r["version"] == label and r["operation"] == key[0] and r["positions"] == key[1] and r["phase"] == "concurrent" for r in rows)]
            for future in futures:
                rows.append(future.result())
                save()
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--output", default="docs/refinement-live-performance.json")
    args = parser.parse_args()
    run(args.baseline_ref, args.repeats, args.output, args.resume)
