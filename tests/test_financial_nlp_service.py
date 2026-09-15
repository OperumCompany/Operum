from __future__ import annotations

import pytest

from app.services.financial_nlp_service import FinancialNLPService, benchmark_predictions


class FailingLoader:
    def __call__(self, *args, **kwargs):
        raise OSError("model is not cached")


def test_nlp_service_falls_back_when_local_model_is_unavailable():
    service = FinancialNLPService(model_name="missing/model", pipeline_loader=FailingLoader())

    result = service.score("Empresa registra crescimento de lucro e receita")

    assert result["source"] == "deterministic_fallback"
    assert -1 <= result["sentiment_score"] <= 1


def test_benchmark_rejects_unreviewed_reference_labels():
    records = [
        {"text": "Lucro cresceu", "label": "positive", "review_status": "qwen_draft"},
        {"text": "Receita caiu", "label": "negative", "review_status": "reviewed"},
    ]

    with pytest.raises(ValueError, match="revisados"):
        benchmark_predictions(records, ["positive", "negative"])


def test_benchmark_reports_macro_f1_for_reviewed_labels():
    records = [
        {"text": "Lucro cresceu", "label": "positive", "review_status": "reviewed"},
        {"text": "Receita caiu", "label": "negative", "review_status": "reviewed"},
        {"text": "Sem mudancas", "label": "neutral", "review_status": "reviewed"},
    ]

    result = benchmark_predictions(records, ["positive", "negative", "neutral"])

    assert result["samples"] == 3
    assert result["macro_f1"] == 1.0

