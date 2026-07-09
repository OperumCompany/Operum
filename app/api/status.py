from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import OPERUM_STORAGE_MODE, SUPABASE_DB_SCHEMA
from app.db.postgres import PostgresClient
from app.services.local_storage_service import LocalStorageService
from app.services.news_ingestion_service import NewsIngestionService

router = APIRouter(prefix="/status", tags=["status"])
storage = LocalStorageService()
news = NewsIngestionService()
db = PostgresClient(schema=SUPABASE_DB_SCHEMA)


@router.get("")
def get_status():
    meta = storage.load_json("news/raw/meta.json") or {}
    all_news = news.get_all_raw()
    db_status = db.healthcheck()
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "news_total": len(all_news),
        "news_sources": meta.get("sources", {}),
        "backfill": meta.get("backfill", {}),
        "data_dir": storage.base_dir,
        "storage_mode": OPERUM_STORAGE_MODE,
        "postgres": db_status,
    }
