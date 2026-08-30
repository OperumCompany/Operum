from __future__ import annotations

import logging
import math
import re
import threading
import unicodedata
from datetime import datetime, timezone

from app.core.config import (
    NEWS_EMBEDDING_BATCH_SIZE,
    NEWS_EMBEDDINGS_ENABLED,
    NEWS_EMBEDDINGS_INDEX_ON_INGEST,
    NEWS_SEMANTIC_CANDIDATES,
    NEWS_SEMANTIC_MIN_SIMILARITY,
)
from app.schemas.news import NewsItem
from app.services.news_embedding_service import NewsEmbeddingService
from app.services.processed_news_repository import ProcessedNewsRepository

logger = logging.getLogger(__name__)
_INDEX_LOCK = threading.Lock()


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).lower()


class NewsSemanticService:
    def __init__(
        self,
        embedder: NewsEmbeddingService | None = None,
        repository: ProcessedNewsRepository | None = None,
    ):
        self.embedder = embedder or NewsEmbeddingService()
        self.repository = repository or ProcessedNewsRepository()

    @property
    def available(self) -> bool:
        return bool(
            NEWS_EMBEDDINGS_ENABLED
            and self.embedder.enabled
            and self.repository.enabled
        )

    def index_news(
        self,
        items: list[NewsItem],
        *,
        force: bool = False,
        batch_size: int | None = None,
        limit: int | None = None,
        dry_run: bool = False,
        upload_raw=None,
    ) -> dict:
        if not self.available:
            return {"status": "disabled", "indexed": 0, "pending": len(items)}
        if not _INDEX_LOCK.acquire(blocking=False):
            return {"status": "already_running", "indexed": 0, "pending": len(items)}
        try:
            selected = items[:limit] if limit else items
            hashes = {} if force else self.repository.existing_hashes([item.id for item in selected])
            pending = [
                item
                for item in selected
                if force
                or hashes.get(item.id)
                != self.embedder.content_hash(item, self.embedder.detect_events(item))
            ]
            if dry_run:
                return {
                    "status": "dry_run",
                    "indexed": 0,
                    "pending": len(pending),
                    "total": len(selected),
                }
            indexed = 0
            size = max(1, batch_size or NEWS_EMBEDDING_BATCH_SIZE)
            for offset in range(0, len(pending), size):
                batch = pending[offset : offset + size]
                if upload_raw:
                    for item in batch:
                        upload_raw(item)
                vectors = self.embedder.encode_documents(batch)
                indexed += self.repository.upsert_batch(batch, vectors, self.embedder)
            return {
                "status": "ok",
                "indexed": indexed,
                "pending": max(0, len(pending) - indexed),
                "total": len(selected),
            }
        finally:
            _INDEX_LOCK.release()

    def semantic_scores(
        self,
        query: str,
        *,
        limit: int = NEWS_SEMANTIC_CANDIDATES,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        tickers: list[str] | None = None,
        sectors: list[str] | None = None,
        countries: list[str] | None = None,
        events: list[str] | None = None,
    ) -> dict[str, float]:
        if not self.available or not query.strip():
            return {}
        try:
            vector = self.embedder.encode_query(query)
            rows = self.repository.semantic_search(
                vector,
                limit=limit,
                date_from=date_from,
                date_to=date_to,
                tickers=tickers,
                sectors=sectors,
                countries=countries,
                events=events,
            )
            return {
                row["id"]: max(0.0, min(1.0, float(row["similarity"])))
                for row in rows
                if float(row["similarity"]) >= NEWS_SEMANTIC_MIN_SIMILARITY
            }
        except Exception as exc:
            logger.warning("Busca semantica indisponivel; usando fallback textual: %s", exc)
            return {}

    @staticmethod
    def _text_score(news: NewsItem, query: str) -> float:
        query_normalized = _normalize(query).strip()
        text = _normalize(
            f"{news.title} {news.summary} {news.content_preview} "
            f"{news.full_text_if_available or ''} "
            f"{' '.join(news.mentioned_assets)} {' '.join(news.mentioned_sectors)}"
        )
        if not query_normalized:
            return 0.0
        if query_normalized in text:
            return 1.0
        stopwords = {
            "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do",
            "dos", "e", "em", "na", "nas", "no", "nos", "o", "os", "para",
            "por", "que", "um", "uma",
        }
        tokens = {
            token for token in re.findall(r"[\w.-]+", query_normalized)
            if len(token) > 2 and token not in stopwords
        }
        if not tokens:
            return 0.0
        matched = sum(1 for token in tokens if token in text)
        title = _normalize(news.title)
        title_matched = sum(1 for token in tokens if token in title)
        return min(1.0, matched / len(tokens) + (0.15 if title_matched else 0.0))

    @staticmethod
    def is_searchable(news: NewsItem) -> bool:
        title = _normalize(news.title).strip()
        blocked_fragments = {
            "ebooks gratuitos",
            "baixe agora",
            "onde assistir",
            "resultado sorteado",
            "loteria",
        }
        generic_titles = {"global", "mercados", "economia", "noticias", "ultimas noticias"}
        return bool(
            news.source_url
            and title not in generic_titles
            and not any(fragment in title for fragment in blocked_fragments)
        )

    @staticmethod
    def _recency_score(news: NewsItem) -> float:
        published = news.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (datetime.now(timezone.utc) - published).total_seconds() / 86400)
        return math.exp(-age_days / 90)

    def hybrid_search(
        self,
        items: list[NewsItem],
        query: str,
        *,
        search_mode: str = "hybrid",
        semantic_filters: dict | None = None,
    ) -> tuple[list[NewsItem], str, bool]:
        mode = search_mode if search_mode in {"hybrid", "keyword", "semantic"} else "hybrid"
        semantic_scores = {}
        if mode in {"hybrid", "semantic"}:
            semantic_scores = self.semantic_scores(query, **(semantic_filters or {}))
        semantic_available = bool(semantic_scores)

        ranked: list[tuple[float, NewsItem]] = []
        query_normalized = _normalize(query)
        query_events = set(NewsEmbeddingService.detect_events_text(query))
        for news in items:
            if not self.is_searchable(news):
                continue
            text_score = self._text_score(news, query)
            semantic_score = semantic_scores.get(news.id, 0.0)
            if mode == "keyword" and text_score <= 0:
                continue
            if mode == "semantic" and semantic_score <= 0:
                continue
            if mode == "hybrid" and text_score <= 0 and semantic_score <= 0:
                continue

            news_events = NewsEmbeddingService.detect_events(news)
            metadata_text = _normalize(
                " ".join(
                    news.mentioned_assets
                    + news.mentioned_sectors
                    + news.mentioned_countries
                    + news_events
                )
            )
            metadata_match = any(
                token in metadata_text
                for token in query_normalized.split()
                if len(token) > 2
            )
            metadata_score = 1.0 if metadata_match or query_events.intersection(news_events) else 0.0
            quality_score = min(
                1.0,
                news.relevance_score * 0.45
                + news.impact_score * 0.35
                + (0.2 if news.is_official else 0.0),
            )
            if mode == "keyword":
                score = text_score * 0.75 + self._recency_score(news) * 0.15 + quality_score * 0.1
            elif mode == "semantic":
                score = semantic_score * 0.8 + self._recency_score(news) * 0.1 + quality_score * 0.1
            else:
                score = (
                    semantic_score * 0.45
                    + text_score * 0.30
                    + self._recency_score(news) * 0.10
                    + quality_score * 0.10
                    + metadata_score * 0.05
                )
            ranked.append((score, news))

        ranked.sort(
            key=lambda item: (
                item[0],
                item[1].published_at.timestamp()
                if item[1].published_at.tzinfo
                else item[1].published_at.replace(tzinfo=timezone.utc).timestamp(),
            ),
            reverse=True,
        )
        mode_used = mode
        if mode in {"hybrid", "semantic"} and not semantic_available:
            fallback = [
                news for news in items
                if self.is_searchable(news) and self._text_score(news, query) > 0
            ]
            fallback.sort(
                key=lambda news: (
                    news.published_at.timestamp()
                    if news.published_at.tzinfo
                    else news.published_at.replace(tzinfo=timezone.utc).timestamp()
                ),
                reverse=True,
            )
            return fallback, "keyword", False
        return [news for _, news in ranked], mode_used, semantic_available


def schedule_news_indexing(items: list[NewsItem], upload_raw=None) -> bool:
    if not NEWS_EMBEDDINGS_ENABLED or not NEWS_EMBEDDINGS_INDEX_ON_INGEST:
        return False

    def run() -> None:
        try:
            result = NewsSemanticService().index_news(items, upload_raw=upload_raw)
            logger.info("Indexacao semantica de noticias: %s", result)
        except Exception as exc:
            logger.warning("Falha na indexacao semantica de noticias: %s", exc)

    threading.Thread(target=run, daemon=True, name="news-embeddings").start()
    return True
