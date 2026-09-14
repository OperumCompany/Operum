from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest

from app.services.analysis_execution import (
    analysis_request, parallel_queries, request_input, start_analysis_executor, stop_analysis_executor,
)


def test_inputs_are_copied_and_discarded_between_requests():
    calls = []

    @analysis_request
    def run():
        def load():
            calls.append(1)
            return {"prices": [1, 2]}
        first = request_input("prices", load)
        first["prices"].append(3)
        assert request_input("prices", load) == {"prices": [1, 2]}

    run()
    run()
    assert len(calls) == 2


def test_missing_inputs_are_retried_and_errors_do_not_poison_context():
    @analysis_request
    def run():
        assert request_input("missing", lambda: None) is None
        assert request_input("missing", lambda: 2) == 2
        with pytest.raises(ValueError):
            request_input("error", lambda: (_ for _ in ()).throw(ValueError()))
        assert request_input("error", lambda: 3) == 3
    run()


def test_concurrency_is_bounded_across_simultaneous_requests_and_keeps_order():
    lock = threading.Lock()
    active = peak = 0

    def query(value):
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(active, peak)
        time.sleep(0.015)
        with lock:
            active -= 1
        return value

    @analysis_request
    def run():
        return parallel_queries([lambda n=n: query(n) for n in range(10)])

    start_analysis_executor(4)
    try:
        with ThreadPoolExecutor(max_workers=3) as callers:
            results = list(callers.map(lambda _: run(), range(3)))
        assert results == [list(range(10))] * 3
        assert 1 < peak <= 4
    finally:
        stop_analysis_executor()


def test_shared_input_is_loaded_once_by_parallel_queries():
    loads = []

    def load():
        loads.append(1)
        time.sleep(0.015)
        return {"value": 1}

    @analysis_request
    def run():
        return parallel_queries([lambda: request_input("shared", load)] * 4)

    start_analysis_executor(4)
    try:
        assert run() == [{"value": 1}] * 4
        assert len(loads) == 1
    finally:
        stop_analysis_executor()


def test_failed_parallel_query_drains_running_tasks():
    finished = []
    def slow():
        time.sleep(0.01)
        finished.append(True)
    def fail():
        raise ValueError("provider failed")
    start_analysis_executor(2)
    try:
        with pytest.raises(ValueError, match="provider failed"):
            parallel_queries([slow, fail])
        assert finished
    finally:
        stop_analysis_executor()
