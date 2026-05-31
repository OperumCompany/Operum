import logging

from fastapi import APIRouter, HTTPException

from app.services.forecast_service import ForecastService
from app.services.news_clustering_service import NewsClusteringService
from app.services.news_ingestion_service import NewsIngestionService
from app.services.asset_analysis_service import AssetAnalysisService
from app.services.portfolio_opinion_service import PortfolioOpinionService
from app.services.portfolio_analytics_service import PortfolioAnalyticsService
from app.services.market_data_service import MarketDataService
from app.services.portfolio_service import PortfolioService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])

forecast_service = ForecastService()
clustering_service = NewsClusteringService()
opinion_service = PortfolioOpinionService()
analytics_service = PortfolioAnalyticsService()
market_service = MarketDataService()
portfolio_service = PortfolioService()
news_service = NewsIngestionService()
asset_analysis_service = AssetAnalysisService()


@router.get("/status")
def get_models_status():
    trained = forecast_service.list_trained()
    return {
        "forecast_models": trained,
        "forecast_count": len(trained),
        "news_scoring": "fallback",
        "clustering": "available",
        "opinion": "available",
    }


@router.post("/train/forecast/{ticker}")
def train_forecast(ticker: str):
    result = forecast_service.train(ticker.upper())
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("error", "Erro no treino"))
    return result


@router.get("/forecast/{ticker}")
def get_forecast(ticker: str):
    result = forecast_service.predict(ticker.upper())
    if result is None:
        raise HTTPException(status_code=404, detail="Previsão não disponível. Treine o modelo primeiro.")
    return result


@router.get("/forecast/trained")
def list_trained_forecasts():
    return {"tickers": forecast_service.list_trained()}


@router.post("/cluster/news")
def cluster_news():
    all_news = news_service.get_all_raw()
    if not all_news:
        raise HTTPException(status_code=404, detail="Nenhuma notícia disponível")
    clustered = clustering_service.cluster(all_news)
    summary = clustering_service.get_cluster_summary(clustered)
    return {
        "status": "ok",
        "num_news": len(clustered),
        "num_clusters": len(summary),
        "clusters": summary,
    }


@router.get("/opinion/{portfolio_id}")
def get_portfolio_opinion(portfolio_id: str):
    portfolio = portfolio_service.get_by_id(portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")

    prices_data = {}
    for pos in portfolio.positions:
        hist = market_service.get_history(pos.ticker, period="1y", interval="1d")
        if hist and hist.get("prices"):
            import pandas as pd
            df = pd.DataFrame(hist["prices"])
            prices_data[pos.ticker] = df

    analysis = analytics_service.analyze(portfolio, prices_data if prices_data else None)
    opinion = opinion_service.generate_opinion(portfolio, analysis, prices_data if prices_data else None)
    return opinion


@router.get("/opinion/{portfolio_id}/positions/{ticker}")
def get_position_opinion(portfolio_id: str, ticker: str):
    portfolio = portfolio_service.get_by_id(portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira nÃ£o encontrada")

    result = asset_analysis_service.generate_asset_analysis(portfolio, ticker.upper())
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Ativo nÃ£o encontrado na carteira")
    return result
