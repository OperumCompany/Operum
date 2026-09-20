import json
from copy import deepcopy
from unittest.mock import Mock

import httpx
import pytest

from app.schemas.analysis_refinement import AssetRefinement, PortfolioRefinement
from app.services.asset_analysis_service import AssetAnalysisService
from app.services.portfolio_opinion_service import PortfolioOpinionService
from app.services.llm_service import LLMService


VALID = {"historico": "Historico preservado.", "situacaoAtual": "Dados limitados.", "perspectiva": "Cenario incerto."}


@pytest.fixture
def llm(monkeypatch):
    service = LLMService()
    service.enabled = True
    service.provider = "ollama"
    service.chat_completion = Mock(side_effect=AssertionError("No generic cleanup path"))
    calls = []
    response = {"message": {"content": json.dumps(VALID)}, "eval_count": 12}

    class Client:
        def __init__(self, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def post(self, url, **kwargs):
            calls.append(kwargs)
            if isinstance(response.get("error"), Exception):
                raise response["error"]
            return httpx.Response(response.get("status", 200), json=response, request=httpx.Request("POST", url))

    monkeypatch.setattr("app.services.llm_service.httpx.Client", Client)
    return service, calls, response


def test_structured_single_call_schema_and_metrics(llm, caplog):
    service, calls, response = llm
    with caplog.at_level("INFO"):
        assert service.chat_json("instructions", {"private": "secret"}, response_model=AssetRefinement) == VALID
    assert len(calls) == 1
    payload = calls[0]["json"]
    assert payload["format"]["required"] == list(VALID)
    assert payload["think"] is False and payload["stream"] is False
    assert payload["messages"][1]["content"] == '{"private":"secret"}'
    assert "validated" in caplog.text and "secret" not in caplog.text
    assert "'load_duration': None" in caplog.text


@pytest.mark.parametrize("content", [
    '{}', '{"historico":3}', '{"historico":',
    json.dumps({**VALID, "score": 90}),
    json.dumps({**VALID, "historico": "   "}),
    json.dumps({**VALID, "historico": "Let me think about the user"}),
])
def test_invalid_json_returns_none_without_retry(llm, content):
    service, calls, response = llm
    response["message"]["content"] = content
    assert service.chat_json("s", {}, response_model=AssetRefinement) is None
    assert len(calls) == 1


@pytest.mark.parametrize("failure", [httpx.ReadTimeout("timeout"), httpx.ConnectError("offline"), 503])
def test_http_failure_does_not_retry(llm, failure):
    service, calls, response = llm
    response["status" if isinstance(failure, int) else "error"] = failure
    assert service.chat_json("s", {}, response_model=AssetRefinement) is None
    assert len(calls) == 1


def test_thinking_is_never_used_and_disabled_makes_no_call(llm):
    service, calls, response = llm
    response["message"] = {"thinking": json.dumps(VALID)}
    assert service.chat_json("s", {}, response_model=AssetRefinement) is None
    service.enabled = False
    assert service.chat_json("s", {}, response_model=AssetRefinement) is None
    assert len(calls) == 1


def test_other_provider_validates_without_format_extension(llm):
    service, calls, response = llm
    service.provider = "compatible"
    response["choices"] = [{"message": {"content": json.dumps(VALID)}}]
    assert service.chat_json("s", {}, response_model=AssetRefinement) == VALID
    assert "format" not in calls[0]["json"]
    assert "response_format" not in calls[0]["json"]


def test_legacy_json_path_unchanged(llm):
    service, calls, _ = llm
    service.chat_completion = Mock(return_value='{"legacy":true}')
    assert service.chat_json("s", {}) == {"legacy": True}
    assert calls == []


def test_asset_semantic_rejection_is_atomic(llm, monkeypatch):
    service, calls, response = llm
    response["message"]["content"] = json.dumps({**VALID, "perspectiva": "Recomendo comprar agora."})
    asset = object.__new__(AssetAnalysisService)
    asset.llm = service
    monkeypatch.setattr("app.services.asset_analysis_service.AI_ENHANCE_ASSET_ANALYSIS", True)
    original = {"analysis_sections": {"box_history_by_horizon": {"1m": "original"}, "box_current": "original"}, "score": 42}
    payload = deepcopy(original)
    assert asset._refine_analysis_sections(payload, "1m", "3m") == original
    assert len(calls) == 1


def test_portfolio_rejection_is_atomic_and_valid_updates_only_text(llm, monkeypatch):
    service, calls, response = llm
    portfolio = object.__new__(PortfolioOpinionService)
    portfolio.llm = service
    monkeypatch.setattr("app.services.portfolio_opinion_service.AI_ENHANCE_PORTFOLIO_ANALYSIS", True)
    original = {"headline": "original", "score": 42, "sources": [{"id": 1}]}
    assert portfolio._refine_opinion_text(deepcopy(original), {}, "1m") == original
    valid = {"headline": "Novo titulo", "composition_summary": "Resumo", "final_diagnosis": "Diagnostico", "conclusion": "Conclusao", "strengths": [], "overlaps": [], "block_reviews": []}
    response["message"]["content"] = json.dumps(valid)
    result = portfolio._refine_opinion_text(deepcopy(original), {}, "1m")
    assert result["score"] == 42 and result["sources"] == original["sources"]
    assert result["headline"] == valid["headline"]
    assert len(calls) == 2


def test_asset_valid_refinement_preserves_metrics_sources_and_other_horizons(llm, monkeypatch):
    service, calls, _ = llm
    asset = object.__new__(AssetAnalysisService)
    asset.llm = service
    monkeypatch.setattr("app.services.asset_analysis_service.AI_ENHANCE_ASSET_ANALYSIS", True)
    original = {"current_snapshot": {"price": 120}, "sources": [{"id": 1}],
                "analysis_sections": {"box_history_by_horizon": {"1m": "old", "3m": "untouched"},
                                      "box_outlook_by_horizon": {"1m": "untouched", "3m": "old"},
                                      "box_current": "old", "summary": "untouched"}}
    result = asset._refine_analysis_sections(deepcopy(original), "1m", "3m")
    assert result["current_snapshot"] == original["current_snapshot"]
    assert result["sources"] == original["sources"]
    assert result["analysis_sections"]["summary"] == "untouched"
    assert result["analysis_sections"]["box_history_by_horizon"] == {"1m": VALID["historico"], "3m": "untouched"}
    assert result["analysis_sections"]["box_outlook_by_horizon"] == {"1m": "untouched", "3m": VALID["perspectiva"]}
    sent = json.loads(calls[0]["json"]["messages"][1]["content"])
    assert sent["selected_history_horizon"] == "1m"
    assert sent["selected_outlook_horizon"] == "3m"


def test_prediction_box_texts_are_normalized_to_display_limits():
    asset = object.__new__(AssetAnalysisService)
    payload = {
        "ticker": "PETR4",
        "confidence": "media",
        "used_news_count": 3,
        "current_snapshot": {"current_price": 31.2, "currency": "BRL", "weight_pct": 12.5},
        "recent_performance": {
            "change_selected_pct": -2.4,
            "forecast_return_selected_pct": 4.1,
            "benchmark_ticker": "IBOV",
        },
        "outlook_3m": {"dominant_topics": ["Petroleo", "Juros"]},
        "analysis_sections": {
            "box_history_by_horizon": {"1m": "Historico curto."},
            "box_current": "Situacao atual curta.",
            "box_outlook_by_horizon": {"3m": "Perspectiva curta."},
            "summary": "Resumo curto fica intacto.",
        },
    }

    result = asset._normalize_prediction_box_texts(payload, "1m", "3m")
    sections = result["analysis_sections"]
    checked = [
        sections["box_history_by_horizon"]["1m"],
        sections["box_current"],
        sections["box_outlook_by_horizon"]["3m"],
    ]
    assert all(750 <= len(text) <= 1250 for text in checked)
    assert sections["summary"] == "Resumo curto fica intacto."
