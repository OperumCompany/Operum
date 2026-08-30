from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np

from app.core.config import NEWS_EMBEDDING_MODEL, SUPABASE_DB_SCHEMA
from app.db.postgres import PostgresClient
from app.schemas.news import NewsItem
from app.services.news_embedding_service import NewsEmbeddingService
from app.services.news_raw_storage_service import NewsRawStorageService


class ProcessedNewsRepository:
    def __init__(self, db: PostgresClient | None = None):
        self.db = db or PostgresClient(schema=SUPABASE_DB_SCHEMA)

    @property
    def enabled(self) -> bool:
        return self.db.enabled

    @staticmethod
    def _register_vector(conn) -> None:
        from pgvector.psycopg import register_vector

        register_vector(conn)

    def existing_hashes(self, ids: list[str] | None = None) -> dict[str, str]:
        if not self.enabled:
            return {}
        if ids:
            rows = self.db.fetch_all(
                """
                select id, embedding_content_hash
                from public.processed_news
                where id = any(%s)
                """,
                (ids,),
            )
        else:
            rows = self.db.fetch_all(
                "select id, embedding_content_hash from public.processed_news"
            )
        return {row["id"]: row["embedding_content_hash"] for row in rows}

    def upsert_batch(
        self,
        items: list[NewsItem],
        vectors: list[list[float]],
        embedder: NewsEmbeddingService,
    ) -> int:
        if not items:
            return 0
        now = datetime.now(timezone.utc)
        rows = []
        for news, vector in zip(items, vectors, strict=True):
            events = embedder.detect_events(news)
            rows.append(
                (
                    news.id,
                    news.title,
                    news.summary,
                    news.content_preview[:1200],
                    news.source_id,
                    news.source_name,
                    news.source_type,
                    news.source_category,
                    news.source_url,
                    news.is_official,
                    news.published_at,
                    news.language,
                    news.tags,
                    news.mentioned_assets,
                    news.mentioned_sectors,
                    news.mentioned_countries,
                    events,
                    news.sentiment_score,
                    news.relevance_score,
                    news.impact_score,
                    NewsRawStorageService.item_path(news),
                    np.asarray(vector, dtype=np.float32),
                    embedder.model_name,
                    embedder.content_hash(news, events),
                    now,
                )
            )

        query = """
            insert into public.processed_news (
                id, title, summary, content_excerpt, source_id, source_name,
                source_type, source_category, source_url, is_official,
                published_at, language, tags, mentioned_assets,
                mentioned_sectors, mentioned_countries, event_tags,
                sentiment_score, relevance_score, impact_score,
                raw_storage_path, embedding, embedding_model,
                embedding_content_hash, embedded_at
            )
            values (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s
            )
            on conflict (id) do update set
                title = excluded.title,
                summary = excluded.summary,
                content_excerpt = excluded.content_excerpt,
                source_id = excluded.source_id,
                source_name = excluded.source_name,
                source_type = excluded.source_type,
                source_category = excluded.source_category,
                source_url = excluded.source_url,
                is_official = excluded.is_official,
                published_at = excluded.published_at,
                language = excluded.language,
                tags = excluded.tags,
                mentioned_assets = excluded.mentioned_assets,
                mentioned_sectors = excluded.mentioned_sectors,
                mentioned_countries = excluded.mentioned_countries,
                event_tags = excluded.event_tags,
                sentiment_score = excluded.sentiment_score,
                relevance_score = excluded.relevance_score,
                impact_score = excluded.impact_score,
                raw_storage_path = excluded.raw_storage_path,
                embedding = excluded.embedding,
                embedding_model = excluded.embedding_model,
                embedding_content_hash = excluded.embedding_content_hash,
                embedded_at = excluded.embedded_at
        """
        with self.db.connection() as conn:
            self._register_vector(conn)
            with conn.cursor() as cur:
                cur.executemany(query, rows)
        return len(rows)

    def semantic_search(
        self,
        query_vector: list[float],
        limit: int,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        tickers: list[str] | None = None,
        sectors: list[str] | None = None,
        countries: list[str] | None = None,
        events: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        clauses = ["embedding_model = %s"]
        params: list[Any] = [NEWS_EMBEDDING_MODEL]
        if date_from:
            clauses.append("published_at >= %s")
            params.append(date_from)
        if date_to:
            clauses.append("published_at <= %s")
            params.append(date_to)
        if tickers:
            clauses.append("mentioned_assets && %s::text[]")
            params.append([ticker.upper() for ticker in tickers])
        if sectors:
            clauses.append("mentioned_sectors && %s::text[]")
            params.append(sectors)
        if countries:
            clauses.append("mentioned_countries && %s::text[]")
            params.append(countries)
        if events:
            clauses.append("event_tags && %s::text[]")
            params.append(events)

        vector = np.asarray(query_vector, dtype=np.float32)
        where_sql = " and ".join(clauses)
        query = f"""
            select
                id,
                1 - (embedding <=> %s) as similarity
            from public.processed_news
            where {where_sql}
            order by embedding <=> %s
            limit %s
        """
        with self.db.connection() as conn:
            self._register_vector(conn)
            with conn.cursor() as cur:
                cur.execute(query, (vector, *params, vector, limit))
                return list(cur.fetchall())

    def status(self, local_total: int | None = None) -> dict:
        if not self.enabled:
            return {
                "enabled": False,
                "model": NEWS_EMBEDDING_MODEL,
                "indexed": 0,
                "pending": local_total,
                "status": "disabled",
            }
        try:
            row = self.db.fetch_one(
                """
                select
                    count(*)::integer as indexed,
                    max(embedded_at) as last_embedded_at
                from public.processed_news
                where embedding_model = %s
                """,
                (NEWS_EMBEDDING_MODEL,),
            )
            indexed = int(row["indexed"] if row else 0)
            return {
                "enabled": True,
                "model": NEWS_EMBEDDING_MODEL,
                "indexed": indexed,
                "pending": max(0, (local_total or 0) - indexed),
                "last_embedded_at": (
                    row["last_embedded_at"].isoformat()
                    if row and row.get("last_embedded_at")
                    else None
                ),
                "status": "ok",
            }
        except Exception as exc:
            return {
                "enabled": True,
                "model": NEWS_EMBEDDING_MODEL,
                "indexed": 0,
                "pending": local_total,
                "status": "error",
                "error": str(exc),
            }
