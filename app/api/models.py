import logging
from copy import deepcopy
from datetime import timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.auth import require_current_user
from app.services.forecast_service import ForecastService
from app.services.news_clustering_service import NewsClusteringService
from app.services.news_ingestion_service import NewsIngestionService
from app.services.asset_analysis_service import AssetAnalysisService
from app.services.llm_service import LLMService
from app.services.portfolio_opinion_service import PortfolioOpinionService
from app.services.portfolio_analytics_service import PortfolioAnalyticsService
from app.services.market_data_service import MarketDataService
from app.services.portfolio_service import PortfolioService
from app.services.prediction_repository import PredictionRepository
from app.services.predictive_analysis_service import PredictiveAnalysisService

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
llm_service = LLMService()
prediction_repository = PredictionRepository()
predictive_analysis_service = PredictiveAnalysisService(repository=prediction_repository)


def _portfolio_context(portfolio, position, payload: dict) -> dict:
    current_price = float(payload.get("last_price") or 0.0)
    market_value = current_price * float(position.quantity)
    invested_value = (
        float(position.avg_price) * float(position.quantity)
        if position.avg_price is not None
        else None
    )
    known_values = []
    for item in portfolio.positions:
        if item.ticker.upper() == position.ticker.upper():
            value = market_value
        else:
            quote = market_service.get_cached_current_price(item.ticker) or {}
            price = quote.get("price") or item.avg_price or 0.0
            value = float(price) * float(item.quantity)
        known_values.append(value)
    total_value = sum(known_values)
    weight = market_value / total_value if total_value > 0 else 0.0
    one_month = payload["horizons"]["1m"]
    return {
        "quantity": float(position.quantity),
        "average_price": float(position.avg_price) if position.avg_price is not None else None,
        "current_price": current_price or None,
        "market_value": round(market_value, 2),
        "weight": round(weight, 6),
        "unrealized_pnl": round(market_value - invested_value, 2) if invested_value is not None else None,
        "unrealized_pnl_pct": (
            round(market_value / invested_value - 1.0, 6)
            if invested_value and invested_value > 0
            else None
        ),
        "risk_contribution": round(
            weight
            * (
                float(one_month["return_range"]["favorable"])
                - float(one_month["return_range"]["adverse"])
            )
            / 2,
            6,
        ),
    }


def _with_legacy_compatibility(
    payload: dict,
    *,
    portfolio_id: str,
    position,
    history_horizon: str,
    outlook_horizon: str,
) -> dict:
    result = deepcopy(payload)
    selected = outlook_horizon if outlook_horizon in {"1m", "2m", "3m"} else "1m"
    horizon = result["horizons"][selected]
    messages = result["friendly_message"]["by_horizon"]
    result.update(
        {
            "portfolio_id": portfolio_id,
            "asset_name": position.ticker,
            "asset_class": position.asset_class,
            "recomputed_at": result["generated_at"],
            "confidence": horizon["confidence"]["label"],
            "status": horizon["direction"],
            "selected_history_horizon": history_horizon,
            "selected_outlook_horizon": outlook_horizon,
            "current_snapshot": {
                "current_price": result.get("last_price"),
                "currency": position.currency,
                "weight_pct": round(result["portfolio_context"]["weight"] * 100, 4),
                "sector": "",
                "country": "BR",
            },
            "historical_window": {
                "start_date": (result.get("historical_series") or [{}])[0].get("date", ""),
                "end_date": (result.get("historical_series") or [{}])[-1].get("date", ""),
                "news_count": len(result.get("sources", [])),
                "has_price_history": bool(result.get("historical_series")),
            },
            "forecast_series": [
                {
                    "date": (pd.Timestamp(result["data_cutoff"]) + timedelta(days=days)).date().isoformat(),
                    "value": item["price_range"]["base"],
                }
                for days, item in ((30, result["horizons"]["1m"]), (60, result["horizons"]["2m"]), (90, result["horizons"]["3m"]))
            ],
            "forecast_anchor_points": [
                {
                    "date": (pd.Timestamp(result["data_cutoff"]) + timedelta(days=days)).date().isoformat(),
                    "horizon_days": item["horizon_days"],
                    "predicted_price": item["price_range"]["base"],
                    "predicted_return": item["expected_return"],
                    "confidence": item["confidence"]["score"],
                }
                for days, item in ((30, result["horizons"]["1m"]), (60, result["horizons"]["2m"]), (90, result["horizons"]["3m"]))
            ],
            "recent_performance": {
                "forecast_return_selected_pct": round(float(horizon["expected_return"]) * 100, 4),
                "forecast_price_selected": horizon["price_range"]["base"],
                "forecast_confidence_selected": horizon["confidence"]["score"],
                "forecast_news_adjustment_pct": round(float(result.get("news_signal", {}).get("signal", 0)) * 100, 4),
            },
            "outlook_3m": {"scenario": result["horizons"]["3m"]["direction"], "dominant_topics": []},
            "analysis_sections": {
                "current": result["friendly_message"]["summary"],
                "recent": result["friendly_message"]["confidence_note"],
                "outlook": messages[selected],
                "recent_by_horizon": messages,
                "outlook_by_horizon": messages,
                "box_history_by_horizon": {**messages, "1w": messages["1m"]},
                "box_current": result["friendly_message"]["summary"],
                "box_outlook_by_horizon": {**messages, "1w": messages["1m"]},
                "scenarios": horizon["scenarios"],
                "what_to_watch": [],
                "data_quality_warnings": result.get("data_quality_warnings", []),
                "conclusion": messages[selected],
            },
            "source_groups": [],
            "used_news_count": len(result.get("sources", [])),
        }
    )
    return result


@router.get("/status")
def get_models_status():
    trained = forecast_service.list_trained()
    return {
        "forecast_models": trained,
        "forecast_count": len(trained),
        "news_scoring": "fallback",
        "clustering": "available",
        "opinion": "available",
        "ai_local": llm_service.status(),
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
def get_portfolio_opinion(
    portfolio_id: str,
    analysis_horizon: str = Query("3m", pattern="^(1m|2m|3m)$"),
    current=Depends(require_current_user),
):
    portfolio = portfolio_service.get_by_id(portfolio_id, current["user"].id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")

    if portfolio.kind == "example":
        return portfolio_service.examples.portfolio_opinion(portfolio, analysis_horizon)

    prices_data = {}
    for pos in portfolio.positions:
        hist = market_service.get_history(pos.ticker, period="1y", interval="1d")
        if hist and hist.get("prices"):
            import pandas as pd
            df = pd.DataFrame(hist["prices"])
            prices_data[pos.ticker] = df

    analysis = analytics_service.analyze(portfolio, prices_data if prices_data else None)
    opinion = opinion_service.generate_opinion(
        portfolio,
        analysis,
        prices_data if prices_data else None,
        analysis_horizon=analysis_horizon,
    )
    return opinion


@router.get("/opinion/{portfolio_id}/positions/{ticker}")
def get_position_opinion(
    portfolio_id: str,
    ticker: str,
    history_horizon: str = Query("3m", pattern="^(1w|1m|2m|3m)$"),
    outlook_horizon: str = Query("3m", pattern="^(1w|1m|2m|3m)$"),
    current=Depends(require_current_user),
):
    portfolio = portfolio_service.get_by_id(portfolio_id, current["user"].id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira nÃ£o encontrada")

    if portfolio.kind == "example":
        result = portfolio_service.examples.position_opinion(
            portfolio, ticker.upper(), history_horizon, outlook_horizon,
        )
        if result.get("status") == "not_found":
            raise HTTPException(status_code=404, detail="Ativo não encontrado na carteira")
        return result

    position = next(
        (item for item in portfolio.positions if item.ticker.upper() == ticker.upper()),
        None,
    )
    if position is None:
        raise HTTPException(status_code=404, detail="Ativo não encontrado na carteira")

    if position.asset_class in {"BR_STOCK", "FII"}:
        payload = predictive_analysis_service.get_or_bootstrap(
            ticker.upper(),
            position.asset_class,
        )
        payload = deepcopy(payload)
        payload["portfolio_context"] = _portfolio_context(portfolio, position, payload)
        return _with_legacy_compatibility(
            payload,
            portfolio_id=portfolio_id,
            position=position,
            history_horizon=history_horizon,
            outlook_horizon=outlook_horizon,
        )

    result = asset_analysis_service.generate_asset_analysis(
        portfolio,
        ticker.upper(),
        history_horizon=history_horizon,
        outlook_horizon=outlook_horizon,
    )
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Ativo nÃ£o encontrado na carteira")
    return result
