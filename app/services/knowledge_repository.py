from __future__ import annotations

import json
from typing import Any

import numpy as np

from app.core.config import NEWS_EMBEDDING_MODEL, SUPABASE_DB_SCHEMA
from app.db.postgres import PostgresClient


class KnowledgeRepository:
    def __init__(self, db: PostgresClient | None = None):
        self.db = db or PostgresClient(schema=SUPABASE_DB_SCHEMA)

    @property
    def enabled(self) -> bool:
        return self.db.enabled

    @staticmethod
    def _register_vector(conn) -> None:
        from pgvector.psycopg import register_vector

        register_vector(conn)

    def existing_hashes(self) -> dict[str, str]:
        if not self.enabled:
            return {}
        rows = self.db.fetch_all("select id, content_hash from public.knowledge_documents")
        return {row["id"]: row["content_hash"] for row in rows}

    def upsert_batch(self, entries: list[tuple[dict, list[float], str]]) -> int:
        if not entries:
            return 0
        document_rows = []
        chunk_rows = []
        for document, vector, embedding_hash in entries:
            document_rows.append((
                document["id"], document["slug"], document["title"], document["category"],
                document["aliases"], document["short_answer"], document["content"],
                json.dumps(document["sources"], ensure_ascii=False), document["version"],
                document["reviewed_at"], document["time_sensitive"], document["content_hash"],
            ))
            chunk_rows.append((
                f"{document['id']}:0", document["id"], document["search_text"],
                np.asarray(vector, dtype=np.float32), NEWS_EMBEDDING_MODEL, embedding_hash,
            ))
        with self.db.connection() as conn:
            self._register_vector(conn)
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    insert into public.knowledge_documents
                      (id, slug, title, category, aliases, short_answer, content, sources,
                       version, reviewed_at, time_sensitive, status, content_hash)
                    values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, 'published', %s)
                    on conflict (id) do update set
                      slug = excluded.slug, title = excluded.title, category = excluded.category,
                      aliases = excluded.aliases, short_answer = excluded.short_answer,
                      content = excluded.content, sources = excluded.sources,
                      version = excluded.version, reviewed_at = excluded.reviewed_at,
                      time_sensitive = excluded.time_sensitive, status = excluded.status,
                      content_hash = excluded.content_hash
                    """,
                    document_rows,
                )
                cur.executemany(
                    """
                    insert into public.knowledge_chunks
                      (id, document_id, chunk_index, content, embedding, embedding_model, embedding_content_hash)
                    values (%s, %s, 0, %s, %s, %s, %s)
                    on conflict (id) do update set
                      content = excluded.content, embedding = excluded.embedding,
                      embedding_model = excluded.embedding_model,
                      embedding_content_hash = excluded.embedding_content_hash
                    """,
                    chunk_rows,
                )
        return len(entries)

    def upsert(self, document: dict, vector: list[float], embedding_hash: str) -> None:
        self.upsert_batch([(document, vector, embedding_hash)])

    def semantic_search(self, query_vector: list[float], limit: int = 8) -> list[dict[str, Any]]:
        if not self.enabled:
            return []
        vector = np.asarray(query_vector, dtype=np.float32)
        with self.db.connection() as conn:
            self._register_vector(conn)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select d.id, 1 - (c.embedding <=> %s) as similarity
                    from public.knowledge_chunks c
                    join public.knowledge_documents d on d.id = c.document_id
                    where d.status = 'published' and c.embedding_model = %s
                    order by c.embedding <=> %s limit %s
                    """,
                    (vector, NEWS_EMBEDDING_MODEL, vector, limit),
                )
                return list(cur.fetchall())

    def status(self) -> dict:
        if not self.enabled:
            return {"enabled": False, "indexed": 0, "status": "disabled"}
        try:
            row = self.db.fetch_one(
                "select count(*)::integer as indexed from public.knowledge_documents where status = 'published'"
            )
            return {"enabled": True, "indexed": int(row["indexed"] if row else 0), "status": "ok"}
        except Exception as exc:
            return {"enabled": True, "indexed": 0, "status": "error", "error": str(exc)}
