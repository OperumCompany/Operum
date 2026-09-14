"""Request-scoped inputs, timings and bounded I/O for analysis requests."""
from __future__ import annotations

import logging
import os
import threading
from collections import Counter
from concurrent.futures import Future, ThreadPoolExecutor, wait
from contextvars import ContextVar, copy_context
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import wraps
from time import perf_counter

logger = logging.getLogger(__name__)


@dataclass
class AnalysisContext:
    now: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    inputs: dict = field(default_factory=dict)
    durations: Counter = field(default_factory=Counter)
    counts: Counter = field(default_factory=Counter)
    forecasts: dict = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


_context: ContextVar[AnalysisContext | None] = ContextVar("analysis_context", default=None)
_executor: ThreadPoolExecutor | None = None
_executor_lock = threading.Lock()


def analysis_now() -> datetime:
    context = _context.get()
    return context.now if context else datetime.now(timezone.utc)


def start_analysis_executor(workers: int | None = None) -> None:
    global _executor
    with _executor_lock:
        if _executor is None:
            workers = workers or int(os.environ.get("OPERUM_ANALYSIS_IO_WORKERS", "4"))
            _executor = ThreadPoolExecutor(max_workers=max(1, min(workers, 16)), thread_name_prefix="analysis-io")


def stop_analysis_executor() -> None:
    global _executor
    with _executor_lock:
        executor, _executor = _executor, None
    if executor is not None:
        executor.shutdown(wait=True, cancel_futures=True)


def parallel_queries(calls):
    # Outside the API lifespan (CLI, unit tests), retain sequential execution.
    # Submitted callables must not submit work to this same pool and wait for it.
    with _executor_lock:
        executor = _executor
        futures = [executor.submit(copy_context().run, call) for call in calls] if executor else None
    if futures is None:
        return [call() for call in calls]
    try:
        return [future.result() for future in futures]
    finally:
        for future in futures:
            future.cancel()
        wait(futures)


def count(name: str) -> None:
    context = _context.get()
    if context:
        with context.lock:
            context.counts[name] += 1


def timed(stage: str):
    def decorate(function):
        @wraps(function)
        def wrapped(*args, **kwargs):
            start = perf_counter()
            try:
                return function(*args, **kwargs)
            finally:
                context = _context.get()
                if context:
                    with context.lock:
                        context.durations[stage] += perf_counter() - start
                        context.counts[stage] += 1
        return wrapped
    return decorate


def analysis_request(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        if _context.get() is not None:
            return function(*args, **kwargs)
        context = AnalysisContext()
        token = _context.set(context)
        start = perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            logger.info("analysis_timing operation=%s total_ms=%.2f stages_ms=%s counts=%s",
                        function.__name__, (perf_counter() - start) * 1000,
                        {k: round(v * 1000, 2) for k, v in context.durations.items()}, dict(context.counts))
            _context.reset(token)
    return wrapped


def request_input(key, loader):
    """Share successful loads only; return copies so consumers cannot mutate inputs."""
    context = _context.get()
    if context is None:
        return loader()
    with context.lock:
        pending = context.inputs.get(key)
        owner = pending is None
        if owner:
            pending = Future()
            context.inputs[key] = pending
        else:
            context.counts["input_reuse"] += 1
    if owner:
        try:
            value = loader()
            pending.set_result(value)
            if value is None:
                with context.lock:
                    context.inputs.pop(key, None)
        except BaseException as exc:
            pending.set_exception(exc)
            with context.lock:
                context.inputs.pop(key, None)
            raise
    return deepcopy(pending.result())


def record_forecast(ticker: str, horizons: list[int], missing: list[int], preparation: str) -> None:
    context = _context.get()
    if context:
        with context.lock:
            item = context.forecasts.setdefault(ticker, {"requested": set(), "missing": set(), "preparation": preparation})
            item["requested"].update(horizons)
            item["missing"].update(missing)
            if missing:
                item["preparation"] = preparation


def forecast_availability() -> dict:
    context = _context.get()
    items = context.forecasts if context else {}
    total = sum(len(item["requested"]) for item in items.values())
    missing = sum(len(item["missing"]) for item in items.values())
    return {
        "status": "ready" if missing == 0 else "unavailable" if missing == total else "partial",
        "items": [{"ticker": ticker, "missing_horizons": sorted(item["missing"]),
                   "preparation": item["preparation"]} for ticker, item in items.items() if item["missing"]],
    }
