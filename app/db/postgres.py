from __future__ import annotations

from contextlib import contextmanager
from typing import Any

from app.core.config import OPERUM_STORAGE_MODE, SUPABASE_DB_URL


class PostgresClient:
    def __init__(self, db_url: str | None = None, schema: str = "public"):
        self.db_url = (db_url or SUPABASE_DB_URL or "").strip()
        self.schema = schema
        self.storage_mode = OPERUM_STORAGE_MODE

    @property
    def enabled(self) -> bool:
        if self.storage_mode == "local":
            return False
        return bool(self.db_url)

    @contextmanager
    def connection(self):
        if not self.enabled:
            raise RuntimeError("Postgres client is disabled")
        try:
            from psycopg import connect
            from psycopg.rows import dict_row
        except ModuleNotFoundError as exc:
            raise RuntimeError("psycopg is not installed") from exc
        conn = connect(self.db_url, autocommit=True, row_factory=dict_row)
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        if not self.enabled:
            raise RuntimeError("Postgres client is disabled")
        try:
            from psycopg import connect
            from psycopg.rows import dict_row
        except ModuleNotFoundError as exc:
            raise RuntimeError("psycopg is not installed") from exc
        conn = connect(self.db_url, autocommit=False, row_factory=dict_row)
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def fetch_one(self, query: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return cur.fetchone()

    def fetch_all(self, query: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                return list(cur.fetchall())

    def execute(self, query: str, params: tuple[Any, ...] = ()) -> None:
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)

    def healthcheck(self) -> dict[str, Any]:
        if not self.enabled:
            return {"enabled": False, "status": "disabled"}
        try:
            row = self.fetch_one("select current_database() as database_name, now() as server_time")
        except Exception as exc:
            return {
                "enabled": True,
                "status": "error",
                "error": str(exc),
            }
        return {
            "enabled": True,
            "status": "ok" if row else "error",
            "database_name": row["database_name"] if row else None,
            "server_time": row["server_time"].isoformat() if row else None,
        }
