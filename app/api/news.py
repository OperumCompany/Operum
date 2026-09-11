import logging
import os
from fastapi import APIRouter, Header, HTTPException, Query
from datetime import datetime, timezone

from app.schemas.news import NewsItem
from app.services.news_ingestion_service import NewsIngestionService
from app.services.news_scoring_service import NewsScoringService
from app.services.news_semantic_service import NewsSemanticService
from app.services.news_summary_service import NewsSummaryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/news", tags=["news"])

ingestion_service = NewsIngestionService()
scoring_service = NewsScoringService()
summary_service = NewsSummaryService()
semantic_service = NewsSemanticService()
ADMIN_REFRESH_TOKEN = os.environ.get("OPERUM_REFRESH_TOKEN", "")


def _require_admin_token(authorization: str | None):
    if not ADMIN_REFRESH_TOKEN:
        raise HTTPException(status_code=503, detail="Token administrativo nao configurado")
    if not authorization or authorization != f"Bearer {ADMIN_REFRESH_TOKEN}":
        raise HTTPException(status_code=401, detail="Token administrativo invalido")


@router.get("", response_model=dict)
def list_news(
    q: str | None = Query(None, description="Busca textual"),
    ticker: str | None = Query(None, description="Filtrar por ticker"),
    asset_class: str | None = Query(None, description="Filtrar por classe de ativo"),
    sector: str | None = Query(None, description="Filtrar por setor"),
    country: str | None = Query(None, description="Filtrar por país"),
    sentiment: str | None = Query(None, description="positive|negative|neutral"),
    impact: str | None = Query(None, description="high|medium|low"),
    date_from: str | None = Query(None, description="Data inicial ISO"),
    date_to: str | None = Query(None, description="Data final ISO"),
    portfolio_id: str | None = Query(None, description="Filtrar por carteira"),
    macro_only: bool = Query(False, description="Apenas macroeconomia"),
    search_mode: str = Query("hybrid", pattern="^(hybrid|keyword|semantic)$"),
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
):
    all_news = ingestion_service.get_all_raw()

    # Apply filters
    filtered = all_news

    if ticker:
        filtered = [n for n in filtered if ticker.upper() in [a.upper() for a in n.mentioned_assets]]

    if sector:
        filtered = [n for n in filtered if any(sector.lower() in s.lower() for s in n.mentioned_sectors)]

    if country:
        filtered = [n for n in filtered if any(country.lower() in c.lower() for c in n.mentioned_countries)]

    if sentiment:
        if sentiment == "positive":
            filtered = [n for n in filtered if n.sentiment_score > 0.2]
        elif sentiment == "negative":
            filtered = [n for n in filtered if n.sentiment_score < -0.2]
        elif sentiment == "neutral":
            filtered = [n for n in filtered if -0.2 <= n.sentiment_score <= 0.2]

    if impact:
        if impact == "high":
            filtered = [n for n in filtered if n.impact_score >= 0.7]
        elif impact == "medium":
            filtered = [n for n in filtered if 0.4 <= n.impact_score < 0.7]
        elif impact == "low":
            filtered = [n for n in filtered if n.impact_score < 0.4]

    def to_utc(dt):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    parsed_date_from = None
    parsed_date_to = None
    if date_from:
        try:
            parsed_date_from = to_utc(datetime.fromisoformat(date_from))
            filtered = [n for n in filtered if to_utc(n.published_at) >= parsed_date_from]
        except ValueError:
            pass

    if date_to:
        try:
            parsed_date_to = to_utc(datetime.fromisoformat(date_to))
            filtered = [n for n in filtered if to_utc(n.published_at) <= parsed_date_to]
        except ValueError:
            pass

    if macro_only:
        filtered = [n for n in filtered if "Economia" in n.mentioned_sectors]

    search_mode_used = "chronological"
    semantic_available = semantic_service.available
    if q:
        filtered, search_mode_used, semantic_available = semantic_service.hybrid_search(
            filtered,
            q,
            search_mode=search_mode,
            semantic_filters={
                "date_from": parsed_date_from,
                "date_to": parsed_date_to,
                "tickers": [ticker] if ticker else None,
                "sectors": [sector] if sector else None,
                "countries": [country] if country else None,
            },
        )

    # Sort by published_at descending (make all offset-aware for comparison)
    def safe_dt(n):
        dt = n.published_at
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    if not q:
        filtered.sort(key=safe_dt, reverse=True)

    total = len(filtered)
    start = (page - 1) * page_size
    end = start + page_size
    items = filtered[start:end]

    return {
        "items": [n.model_dump(mode="json") for n in items],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if page_size else 0,
        "search_mode_used": search_mode_used,
        "semantic_available": semantic_available,
    }


@router.get("/{news_id}", response_model=NewsItem)
def get_news(news_id: str):
    all_news = ingestion_service.get_all_raw()
    for n in all_news:
        if n.id == news_id:
            return n
    raise HTTPException(status_code=404, detail="Notícia não encontrada")


@router.post("/reindex")
def reindex_news(authorization: str | None = Header(default=None)):
    _require_admin_token(authorization)
    count = ingestion_service.ingest()
    return {"status": "ok", "ingested": count}


@router.post("/backfill")
def backfill_news(
    start_date: str = Query("2026-05-01", description="Data inicial ISO"),
    source_id: str | None = Query(None, description="Fonte especifica para backfill"),
    authorization: str | None = Header(default=None),
):
    _require_admin_token(authorization)
    result = ingestion_service.backfill_history(start_date=start_date, source_id=source_id)
    return {"status": "ok", **result}


@router.post("/summarize/{news_id}")
def summarize_news(news_id: str):
    all_news = ingestion_service.get_all_raw()
    news = None
    for n in all_news:
        if n.id == news_id:
            news = n
            break
    if news is None:
        raise HTTPException(status_code=404, detail="Notícia não encontrada")

    summary = summary_service.summarize(
        news.title,
        news.content_preview,
        news.mentioned_assets,
        mentioned_sectors=news.mentioned_sectors,
        full_text=news.full_text_if_available,
    )
    return {"id": news_id, "summary": summary}
