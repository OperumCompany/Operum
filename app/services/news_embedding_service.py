from __future__ import annotations

import hashlib
import json

from app.core.config import (
    NEWS_EMBEDDING_DIMENSIONS,
    NEWS_EMBEDDING_MODEL,
    NEWS_EMBEDDINGS_ENABLED,
)
from app.schemas.news import NewsItem
from app.services.embedding_service import EmbeddingService

EVENT_KEYWORDS = {
    "resultados": ["resultado", "lucro", "receita", "balanco", "balanço", "ebitda", "margem"],
    "juros": ["juros", "selic", "copom", "fed", "treasury"],
    "inflacao": ["inflacao", "inflação", "ipca", "cpi"],
    "credito": ["credito", "crédito", "inadimplencia", "inadimplência", "provisao", "provisão"],
    "dividendos": ["dividendo", "dividendos", "jcp", "proventos"],
    "regulacao": ["regulacao", "regulação", "cvm", "bcb", "regulatorio", "regulatório"],
    "commodities": ["petroleo", "petróleo", "brent", "minerio", "minério", "commodity"],
    "cambio": ["cambio", "câmbio", "dolar", "dólar", "real"],
    "fusoes_aquisicoes": ["fusao", "fusão", "aquisicao", "aquisição", "incorporacao", "incorporação"],
}


class NewsEmbeddingService(EmbeddingService):

    def __init__(self):
        super().__init__()

    @staticmethod
    def detect_events_text(text: str) -> list[str]:
        text = text.lower()
        return sorted(
            event
            for event, keywords in EVENT_KEYWORDS.items()
            if any(keyword in text for keyword in keywords)
        )

    @classmethod
    def detect_events(cls, news: NewsItem) -> list[str]:
        return cls.detect_events_text(
            f"{news.title} {news.summary} {news.content_preview}"
        )

    def document_text(self, news: NewsItem, events: list[str] | None = None) -> str:
        event_tags = events if events is not None else self.detect_events(news)
        parts = [
            news.title,
            news.summary,
            news.content_preview[:1200],
            "Ativos: " + ", ".join(news.mentioned_assets),
            "Setores: " + ", ".join(news.mentioned_sectors),
            "Países: " + ", ".join(news.mentioned_countries),
            "Eventos: " + ", ".join(event_tags),
        ]
        return "passage: " + "\n".join(part for part in parts if part.strip())

    def content_hash(self, news: NewsItem, events: list[str] | None = None) -> str:
        payload = {
            "model": self.model_name,
            "text": self.document_text(news, events),
        }
        return hashlib.sha256(
            json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

    def encode_documents(self, items: list[NewsItem]) -> list[list[float]]:
        if not items:
            return []
        texts = [self.document_text(item) for item in items]
        # document_text already includes the E5 passage prefix.
        vectors = self._get_model().encode(
            texts, normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
        )
        result = [vector.astype(float).tolist() for vector in vectors]
        self._validate(result)
        return result
