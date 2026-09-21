from app.services.analysis_execution import start_analysis_executor, stop_analysis_executor

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import assets, auth, chat, health, market, models, news, portfolios, status
from app.core.config import (
    CORS_ORIGINS,
    OPERUM_ENABLE_NEWS_BACKFILL_ON_STARTUP,
    OPERUM_ENABLE_NEWS_INGEST_ON_STARTUP,
    OPERUM_ENABLE_NEWS_SCHEDULER,
    OPERUM_ENABLE_PRICE_WARMUP_ON_STARTUP,
    OPERUM_NEWS_SCHEDULER_INTERVAL_HOURS,
)
from app.core.security import SecurityMiddleware

logger = logging.getLogger(__name__)
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

_news_scheduler_stop = threading.Event()
_news_scheduler_thread: threading.Thread | None = None

STARTUP_PRICE_TICKERS = [
    "PETR4",
    "VALE3",
    "ITUB4",
    "BBDC4",
    "BBAS3",
    "ABEV3",
    "WEGE3",
    "B3SA3",
    "HGLG11",
    "KNRI11",
    "AAPL34",
    "BTC",
]


def _run_news_ingest_async():
    if not OPERUM_ENABLE_NEWS_INGEST_ON_STARTUP:
        logger.info("Ingestao automatica de noticias desabilitada por configuracao")
        return
    try:
        from app.services.news_ingestion_service import NewsIngestionService

        ing = NewsIngestionService()
        count = ing.ingest()
        logger.info(f"Ingestao automatica: {count} noticias novas")
    except Exception as e:
        logger.warning(f"Falha na ingestao automatica de noticias: {e}")


def _run_news_backfill_async():
    if not OPERUM_ENABLE_NEWS_BACKFILL_ON_STARTUP:
        logger.info("Backfill automatico desabilitado por configuracao")
        return
    try:
        from app.services.news_ingestion_service import NewsIngestionService

        ing = NewsIngestionService()
        backfill = ing.maybe_backfill(start_date="2026-05-01")
        if backfill:
            logger.info(f"Backfill automatico: {backfill.get('new_count', 0)} noticias novas")
    except Exception as e:
        logger.warning(f"Falha no backfill automatico de noticias: {e}")


def _run_news_scheduler(stop_event: threading.Event):
    interval_seconds = max(OPERUM_NEWS_SCHEDULER_INTERVAL_HOURS, 0.25) * 60 * 60
    logger.info(
        "Scheduler de noticias habilitado; intervalo %.2f hora(s)",
        OPERUM_NEWS_SCHEDULER_INTERVAL_HOURS,
    )
    while not stop_event.is_set():
        try:
            from app.services.news_ingestion_service import NewsIngestionService

            ing = NewsIngestionService()
            count = ing.ingest()
            logger.info("Scheduler de noticias: %s noticia(s) nova(s)", count)
        except Exception as e:
            logger.warning("Falha no scheduler de noticias: %s", e)
        stop_event.wait(interval_seconds)


def _start_news_scheduler():
    global _news_scheduler_thread
    if not OPERUM_ENABLE_NEWS_SCHEDULER:
        logger.info("Scheduler de noticias desabilitado por configuracao")
        return
    if _news_scheduler_thread and _news_scheduler_thread.is_alive():
        return
    _news_scheduler_stop.clear()
    _news_scheduler_thread = threading.Thread(
        target=_run_news_scheduler,
        args=(_news_scheduler_stop,),
        daemon=True,
        name="operum-news-scheduler",
    )
    _news_scheduler_thread.start()


def _stop_news_scheduler():
    if not _news_scheduler_thread:
        return
    _news_scheduler_stop.set()
    _news_scheduler_thread.join(timeout=5)


def _warm_prices_async():
    if not OPERUM_ENABLE_PRICE_WARMUP_ON_STARTUP:
        logger.info("Aquecimento de precos desabilitado por configuracao")
        return
    try:
        from app.services.market_data_service import MarketDataService

        mkt = MarketDataService()
        updated = 0
        for ticker in STARTUP_PRICE_TICKERS:
            price = mkt.get_current_price(ticker)
            if price:
                updated += 1
        logger.info(f"Cache de precos atualizado para {updated} ativos")
    except Exception as e:
        logger.warning(f"Falha na atualizacao de cache de precos: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando Operum - buscando noticias e precos...")
    _start_news_scheduler()
    if OPERUM_ENABLE_NEWS_INGEST_ON_STARTUP:
        threading.Thread(target=_run_news_ingest_async, daemon=True).start()
    else:
        logger.info("Ingestao automatica de noticias desabilitada por configuracao")

    if OPERUM_ENABLE_NEWS_BACKFILL_ON_STARTUP:
        threading.Thread(target=_run_news_backfill_async, daemon=True).start()
    if OPERUM_ENABLE_PRICE_WARMUP_ON_STARTUP:
        threading.Thread(target=_warm_prices_async, daemon=True).start()
    start_analysis_executor()
    try:
        yield
    finally:
        _stop_news_scheduler()
        stop_analysis_executor()


app = FastAPI(
    title="Operum API",
    description="Backend do Operum - noticias, carteiras e IA financeira",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(SecurityMiddleware)

app.include_router(health.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(portfolios.router, prefix="/api")
app.include_router(news.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(models.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(status.router, prefix="/api")
