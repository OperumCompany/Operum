from datetime import datetime, timezone

from fastapi import APIRouter

from app.core.config import (
    NEWS_EMBEDDING_DIMENSIONS,
    NEWS_EMBEDDINGS_ENABLED,
    OPERUM_STORAGE_MODE,
    SUPABASE_DB_SCHEMA,
)
from app.db.postgres import PostgresClient
from app.services.local_storage_service import LocalStorageService
from app.services.knowledge_repository import KnowledgeRepository
from app.services.knowledge_service import KnowledgeService
from app.services.news_ingestion_service import NewsIngestionService
from app.services.processed_news_repository import ProcessedNewsRepository

router = APIRouter(prefix="/status", tags=["status"])
storage = LocalStorageService()
news = NewsIngestionService()
db = PostgresClient(schema=SUPABASE_DB_SCHEMA)
processed_news = ProcessedNewsRepository(db)
knowledge_repository = KnowledgeRepository(db)
knowledge_service = KnowledgeService(knowledge_repository)


@router.get("")
def get_status():
    meta = news.storage.load_json("news/raw/meta.json") or {}
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
        "news_raw_storage": news.storage.healthcheck(),
        "news_embeddings": {
            **processed_news.status(len(all_news)),
            "configured": NEWS_EMBEDDINGS_ENABLED,
            "dimensions": NEWS_EMBEDDING_DIMENSIONS,
        },
        "knowledge_base": {
            **knowledge_repository.status(),
            "local_documents": len(knowledge_service.load_documents()),
        },
        "postgres": db_status,
    }
