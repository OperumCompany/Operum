from unittest.mock import Mock

import joblib
import numpy as np
import pandas as pd
import pytest

from app.services.analysis_execution import analysis_request, forecast_availability
from app.services.forecast_service import ForecastService
from app.workers.analysis_worker import AnalysisWorker


class ConstantModel:
    def __init__(self, value=0.02):
        self.value = value

    def predict(self, frame):
        return np.full(len(frame), self.value)


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setenv("OPERUM_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("OPERUM_MODELS_DIR", raising=False)
    repository = Mock()
    repository.enqueue_job.return_value = {"status": "pending"}
    service = ForecastService(repository=repository)
    close = np.linspace(80, 120, 180)
    service._download_data = Mock(return_value=pd.DataFrame({"Close": close, "High": close + 1, "Low": close - 1}))
    service.train = Mock(side_effect=AssertionError("Never train in serving"))
    return service


def test_existing_disk_models_are_loaded_before_any_training_decision(service):
    from pathlib import Path
    Path(service.model_dir).mkdir(parents=True)
    for horizon in (1, 5, 21):
        joblib.dump(ConstantModel(), service._model_path("PETR4", horizon))
    original = service._prepare_features
    service._prepare_features = Mock(wraps=original)
    result = service.predict_multi("PETR4", [1, 5, 21])
    assert len(result["predictions"]) == 3
    assert service._prepare_features.call_count == 1
    service.train.assert_not_called()
    service.repository.enqueue_job.assert_not_called()


def test_missing_models_are_enqueued_without_training_or_forecast_download(service):
    @analysis_request
    def run():
        assert service.predict_multi("PETR4", [5, 21]) is None
        assert service.predict_multi("PETR4", [1]) is None
        return forecast_availability()
    status = run()
    assert status == {"status": "unavailable", "items": [{"ticker": "PETR4", "missing_horizons": [1, 5, 21], "preparation": "pending"}]}
    assert service.repository.enqueue_job.call_count == 1
    service.train.assert_not_called()
    service._download_data.assert_not_called()


def test_partial_models_remain_available_and_queue_failure_is_truthful(service):
    service.models = {"PETR4": {5: ConstantModel()}}
    service.repository.enqueue_job.side_effect = RuntimeError("Queue offline")
    @analysis_request
    def run():
        result = service.predict_multi("PETR4", [5, 21])
        return result, forecast_availability()
    result, status = run()
    assert [p["horizon_days"] for p in result["predictions"]] == [5]
    assert status["status"] == "partial"
    assert status["items"][0]["preparation"] == "not_scheduled"
    service.train.assert_not_called()


def test_new_model_and_metadata_are_loaded_without_api_restart(service):
    service._publish_model("PETR4", 5, ConstantModel(0.01), {"test_r2": 0.1})
    assert service.predict_multi("PETR4", [5])["predictions"][0]["predicted_return"] == 0.01
    writer = ForecastService(repository=service.repository)
    writer._publish_model("PETR4", 5, ConstantModel(0.03), {"test_r2": 0.3})
    assert service.predict_multi("PETR4", [5])["predictions"][0]["predicted_return"] == 0.03
    assert service.model_meta["PETR4"][5]["test_r2"] == 0.3


def test_corrupt_model_is_unavailable_without_inline_training(service):
    from pathlib import Path
    Path(service.model_dir).mkdir(parents=True)
    Path(service._model_path("PETR4", 5)).write_text("invalid")
    assert service.predict_multi("PETR4", [5]) is None
    service.train.assert_not_called()


def test_worker_trains_only_missing_forecast_horizons_and_retries_partial_failures():
    repository = Mock()
    repository.claim_next_job.return_value = {"id": "job", "ticker": "PETR4", "reason": "forecast_training"}
    forecast = Mock()
    forecast.missing_horizons.side_effect = [[21, 63], [63]]
    forecast.train.return_value = {"status": "trained", "errors": ["insufficient data"]}
    analysis = Mock()
    worker = AnalysisWorker(repository=repository, forecast=forecast, analysis=analysis)
    assert worker.run_once()["status"] == "failed"
    forecast.train.assert_called_once_with("PETR4", horizons=[21, 63])
    repository.complete_job.assert_not_called()
    repository.fail_job.assert_called_once()
    analysis.generate.assert_not_called()


def test_worker_skips_training_if_another_job_already_prepared_the_models():
    repository = Mock()
    repository.claim_next_job.return_value = {"id": "job", "ticker": "PETR4", "reason": "forecast_training"}
    forecast = Mock()
    forecast.missing_horizons.return_value = []
    worker = AnalysisWorker(repository=repository, forecast=forecast, analysis=Mock())
    assert worker.run_once()["status"] == "completed"
    forecast.train.assert_not_called()


def test_concurrent_publication_never_mixes_model_and_metadata(service):
    from concurrent.futures import ThreadPoolExecutor
    service._publish_model("PETR4", 5, ConstantModel(1), {"version": 1})
    reader = ForecastService(repository=service.repository)
    def publish():
        for version in range(2, 8):
            service._publish_model("PETR4", 5, ConstantModel(version), {"version": version})
    with ThreadPoolExecutor(max_workers=1) as executor:
        pending = executor.submit(publish)
        for _ in range(20):
            assert reader._load_model("PETR4", 5)
            assert reader.models["PETR4"][5].value == reader.model_meta["PETR4"][5]["version"]
        pending.result()


def test_partial_asset_analysis_fills_only_missing_horizons_with_low_confidence(service):
    from datetime import datetime, timezone
    from app.schemas.portfolio import Portfolio, Position
    from app.services.asset_analysis_service import AssetAnalysisService
    asset = AssetAnalysisService()
    asset.forecast = service
    asset.llm.enabled = False
    asset.get_related_news = Mock(return_value=[])
    close = np.linspace(80, 120, 280)
    history = pd.DataFrame({"date": pd.date_range(end="2026-09-13", periods=280).strftime("%Y-%m-%d"), "close": close})
    asset.market.get_history = Mock(return_value={"prices": history.to_dict("records")})
    asset.market.get_current_price = Mock(return_value={"price": 120, "currency": "BRL"})
    service.models = {"PETR4": {5: ConstantModel(0.02)}}
    now = datetime.now(timezone.utc)
    portfolio = Portfolio(id="test", name="Test", created_at=now, updated_at=now,
                          positions=[Position(asset_id="PETR4", ticker="PETR4", asset_class="BR_STOCK", quantity=1)])
    result = asset.generate_asset_analysis(portfolio, "PETR4")
    assert result["forecast_availability"]["status"] == "partial"
    assert result["forecast_availability"]["items"][0]["missing_horizons"] == [21, 42, 63]
    points = {p["horizon_days"]: p for p in result["forecast_anchor_points"]}
    assert set(points) == {5, 21, 42, 63}
    assert points[5]["predicted_return"] == 0.02
    assert all(points[h]["confidence"] == 0.25 for h in (21, 42, 63))
    service.train.assert_not_called()


def test_source_selection_does_not_call_market_forecast_or_llm(tmp_path, monkeypatch):
    from app.services.asset_analysis_service import AssetAnalysisService
    monkeypatch.setenv("OPERUM_DATA_DIR", str(tmp_path))
    asset = AssetAnalysisService()
    asset.get_related_news = Mock(return_value=[])
    asset.market = Mock()
    asset.forecast = Mock()
    asset.llm = Mock()
    assert asset.select_analysis_news("PETR4")["used_news"] == []
    assert asset.market.mock_calls == []
    assert asset.forecast.mock_calls == []
    assert asset.llm.mock_calls == []


def test_interrupted_legacy_export_keeps_atomic_bundle_usable(service, monkeypatch):
    monkeypatch.setattr(service, "_save_model", Mock(side_effect=OSError("Interrupted export")))
    with pytest.raises(OSError):
        service._publish_model("PETR4", 5, ConstantModel(0.03), {"test_r2": 0.4})
    reader = ForecastService(repository=service.repository)
    assert reader._load_model("PETR4", 5)
    assert reader.models["PETR4"][5].value == 0.03
    assert reader.model_meta["PETR4"][5]["test_r2"] == 0.4
    assert reader.list_trained() == ["PETR4"]


def test_no_model_or_market_data_does_not_fabricate_forecast(service):
    from datetime import datetime, timezone
    from app.schemas.portfolio import Portfolio, Position
    from app.services.asset_analysis_service import AssetAnalysisService
    asset = AssetAnalysisService()
    asset.forecast = service
    asset.llm.enabled = False
    asset.get_related_news = Mock(return_value=[])
    asset.market.get_history = Mock(return_value=None)
    asset.market.get_current_price = Mock(return_value=None)
    now = datetime.now(timezone.utc)
    portfolio = Portfolio(id="test", name="Test", created_at=now, updated_at=now,
                          positions=[Position(asset_id="PETR4", ticker="PETR4", asset_class="BR_STOCK", quantity=1)])
    result = asset.generate_asset_analysis(portfolio, "PETR4")
    assert result["forecast_availability"]["status"] == "unavailable"
    assert result["forecast_series"] == []
    assert result["current_snapshot"]["current_price"] is None
    service.train.assert_not_called()
