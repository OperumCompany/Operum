from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import numpy as np

from app.ml.forecasting import confidence_label


@dataclass(frozen=True)
class NewsSignal:
    signal: float
    impact: float
    disagreement: float
    novelty: float
    evidence_count: int
    category_counts: dict[str, int]

    def as_dict(self) -> dict:
        return asdict(self)


class NewsFusionService:
    CATEGORY_WEIGHTS = {"fundamento": 1.0, "macro": 0.72, "setorial": 0.58, "fluxo": 0.35}
    EVENT_HALF_LIFE_DAYS = {
        "resultados": 30.0,
        "dividendos": 30.0,
        "fusoes_aquisicoes": 45.0,
        "regulacao": 35.0,
        "juros": 14.0,
        "inflacao": 14.0,
        "cambio": 10.0,
        "commodities": 10.0,
    }

    @staticmethod
    def _published_at(item: dict) -> datetime:
        value = item.get("published_at")
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        if isinstance(value, str) and value:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc)

    def _half_life(self, item: dict) -> float:
        events = item.get("event_tags") or []
        values = [self.EVENT_HALF_LIFE_DAYS[event] for event in events if event in self.EVENT_HALF_LIFE_DAYS]
        return max(values, default=21.0)

    def aggregate(self, news: list[dict], *, now: datetime | None = None) -> NewsSignal:
        if not news:
            return NewsSignal(0.0, 0.0, 0.0, 0.0, 0, {})
        now = now or datetime.now(timezone.utc)
        weighted_sentiments = []
        weights = []
        impacts = []
        novelties = []
        categories: dict[str, int] = {}
        for item in news:
            sentiment = float(np.clip(item.get("sentiment_score", 0.0), -1.0, 1.0))
            impact = float(np.clip(item.get("impact_score", 0.0), 0.0, 1.0))
            relevance = float(np.clip(item.get("relevance_score", 0.5), 0.0, 1.0))
            source = float(np.clip(item.get("source_confidence_weight", 0.6), 0.0, 1.0))
            novelty = float(np.clip(item.get("novelty_score", 0.5), 0.0, 1.0))
            category = str(item.get("analysis_category", "fluxo"))
            categories[category] = categories.get(category, 0) + 1
            age_days = max(0.0, (now - self._published_at(item)).total_seconds() / 86_400)
            decay = math.exp(-math.log(2) * age_days / self._half_life(item))
            weight = self.CATEGORY_WEIGHTS.get(category, 0.25) * max(impact, 0.05) * max(relevance, 0.10) * max(source, 0.10) * decay
            weights.append(weight)
            weighted_sentiments.append(sentiment)
            impacts.append(impact)
            novelties.append(novelty)
        weight_array = np.asarray(weights, dtype=float)
        sentiment_array = np.asarray(weighted_sentiments, dtype=float)
        total_weight = float(weight_array.sum())
        signal = float(np.average(sentiment_array, weights=weight_array)) if total_weight > 0 else 0.0
        disagreement = float(np.sqrt(np.average(np.square(sentiment_array - signal), weights=weight_array))) if total_weight > 0 else 0.0
        return NewsSignal(
            signal=round(float(np.clip(signal, -1.0, 1.0)), 6),
            impact=round(float(np.average(impacts, weights=weight_array)) if total_weight > 0 else 0.0, 6),
            disagreement=round(float(np.clip(disagreement, 0.0, 1.0)), 6),
            novelty=round(float(np.average(novelties, weights=weight_array)) if total_weight > 0 else 0.0, 6),
            evidence_count=len(news),
            category_counts=categories,
        )

    def apply_to_horizon(self, horizon: dict, news_signal: NewsSignal) -> dict:
        result = dict(horizon)
        ranges = dict(horizon["return_range"])
        original_center = float(horizon["expected_return"])
        original_half_width = max(
            original_center - float(ranges["adverse"]),
            float(ranges["favorable"]) - original_center,
            0.01,
        )
        maximum_shift = original_half_width * 0.25
        center_shift = float(np.clip(news_signal.signal * maximum_shift, -maximum_shift, maximum_shift))
        widening = min(
            0.25,
            news_signal.impact * 0.15 + news_signal.disagreement * 0.08 + news_signal.novelty * 0.02,
        )
        adjusted_center = original_center + center_shift
        adjusted_half_width = original_half_width * (1 + widening)
        adverse = adjusted_center - adjusted_half_width
        favorable = adjusted_center + adjusted_half_width
        confidence = dict(horizon.get("confidence", {"score": 0.30, "label": "baixa"}))
        confidence_score = float(confidence.get("score", 0.30))
        confidence_score = float(np.clip(confidence_score * (1 - news_signal.disagreement * 0.20), 0.05, 0.95))
        result["expected_return"] = round(adjusted_center, 6)
        return_range = {
            "adverse": round(adverse, 6),
            "base": round(adjusted_center, 6),
            "favorable": round(favorable, 6),
        }
        result["expected_total_return"] = round(adjusted_center, 6)
        result["expected_price_return"] = round(adjusted_center, 6)
        result.setdefault("expected_income_return", 0.0)
        result["probability_up"] = round(
            float(np.clip(0.50 + adjusted_center / max(adjusted_half_width * 2.0, 0.01), 0.05, 0.95)),
            6,
        )
        result["return_range"] = return_range
        result["total_return_range"] = dict(return_range)
        result["confidence"] = {
            "score": round(confidence_score, 4),
            "label": confidence_label(confidence_score),
        }
        result["news_fusion"] = {
            **news_signal.as_dict(),
            "center_shift": round(center_shift, 6),
            "interval_widening": round(widening, 6),
            "maximum_center_shift": round(maximum_shift, 6),
        }
        return result

    @staticmethod
    def fingerprint(news: list[dict]) -> str:
        items = [
            {
                "id": item.get("id"),
                "sentiment": item.get("sentiment_score"),
                "impact": item.get("impact_score"),
                "relevance": item.get("relevance_score"),
                "published_at": str(item.get("published_at", "")),
            }
            for item in news
        ]
        serialized = json.dumps(sorted(items, key=lambda item: str(item["id"])), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

