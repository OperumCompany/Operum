import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import CORS_ORIGINS
from app.api import health, assets, portfolios, news, market, models

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Inicializando Operum — buscando notícias e preços...")
    try:
        from app.services.news_ingestion_service import NewsIngestionService
        ing = NewsIngestionService()
        count = ing.ingest()
        logger.info(f"Ingestão automática: {count} notícias novas")
    except Exception as e:
        logger.warning(f"Falha na ingestão automática de notícias: {e}")
    try:
        from app.services.market_data_service import MarketDataService
        mkt = MarketDataService()
        from app.services.asset_universe_service import AssetUniverseService
        assets_svc = AssetUniverseService()
        universe = assets_svc.get_all()
        updated = 0
        for asset in universe[:20]:
            price = mkt.get_current_price(asset.ticker)
            if price:
                updated += 1
        logger.info(f"Cache de preços atualizado para {updated} ativos")
    except Exception as e:
        logger.warning(f"Falha na atualização de cache de preços: {e}")
    yield

app = FastAPI(
    title="Operum API",
    description="Backend do Operum — notícias, carteiras e IA financeira",
    version="2.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(portfolios.router, prefix="/api")
app.include_router(news.router, prefix="/api")
app.include_router(market.router, prefix="/api")
app.include_router(models.router, prefix="/api")
