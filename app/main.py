from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import CORS_ORIGINS
from app.api import health, assets, portfolios, news, market, models

app = FastAPI(
    title="Operum API",
    description="Backend do Operum — notícias, carteiras e IA financeira",
    version="2.0.0",
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
