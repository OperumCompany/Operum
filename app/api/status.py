from datetime import datetime, timezone

from fastapi import APIRouter

from app.services.local_storage_service import LocalStorageService
from app.services.news_ingestion_service import NewsIngestionService

router = APIRouter(prefix="/status", tags=["status"])
storage = LocalStorageService()
news = NewsIngestionService()


@router.get("")
def get_status():
    meta = storage.load_json("news/raw/meta.json") or {}
    all_news = news.get_all_raw()
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "news_total": len(all_news),
        "news_sources": meta.get("sources", {}),
        "backfill": meta.get("backfill", {}),
        "data_dir": storage.base_dir,
    }

