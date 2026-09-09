from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.news_fusion_service import NewsFusionService


def _news(sentiment: float, impact: float, age_days: int = 0) -> dict:
    return {
        "id": f"news-{sentiment}-{impact}-{age_days}",
        "sentiment_score": sentiment,
        "impact_score": impact,
        "relevance_score": 1.0,
        "source_confidence_weight": 1.0,
        "analysis_category": "fundamento",
        "event_tags": ["resultados"],
        "published_at": (datetime.now(timezone.utc) - timedelta(days=age_days)).isoformat(),
        "novelty_score": 1.0,
    }


def test_news_fusion_caps_center_shift_and_interval_widening():
    service = NewsFusionService()
    signal = service.aggregate([_news(1.0, 1.0), _news(1.0, 1.0)])
    horizon = {
        "expected_return": 0.02,
        "return_range": {"adverse": -0.08, "base": 0.02, "favorable": 0.12},
        "confidence": {"score": 0.60, "label": "media"},
    }

    fused = service.apply_to_horizon(horizon, signal)

    assert fused["expected_return"] <= 0.045
    original_half_width = 0.10
    fused_half_width = (fused["return_range"]["favorable"] - fused["return_range"]["adverse"]) / 2
    assert fused_half_width <= original_half_width * 1.25
    assert fused["news_fusion"]["center_shift"] <= original_half_width * 0.25
    assert 0 <= fused["news_fusion"]["signal"] <= 1


def test_old_news_has_less_weight_than_recent_news():
    service = NewsFusionService()
    recent = service.aggregate([_news(1.0, 1.0, age_days=0), _news(-1.0, 1.0, age_days=40)])
    old = service.aggregate([_news(1.0, 1.0, age_days=40), _news(-1.0, 1.0, age_days=0)])

    assert recent.signal > 0
    assert old.signal < 0


def test_news_fingerprint_is_order_independent():
    service = NewsFusionService()
    first = _news(0.5, 0.8)
    second = _news(-0.2, 0.4)

    assert service.fingerprint([first, second]) == service.fingerprint([second, first])

