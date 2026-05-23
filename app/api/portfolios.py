from fastapi import APIRouter, HTTPException
from app.services.portfolio_service import PortfolioService
from app.services.portfolio_analytics_service import PortfolioAnalyticsService
from app.services.market_data_service import MarketDataService
from app.schemas.portfolio import Portfolio, PortfolioCreate, PositionAdd

router = APIRouter(prefix="/portfolios", tags=["portfolios"])
service = PortfolioService()
analytics_service = PortfolioAnalyticsService()
market_service = MarketDataService()


@router.get("", response_model=list[Portfolio])
def list_portfolios():
    return service.list_all()


@router.post("", response_model=Portfolio, status_code=201)
def create_portfolio(data: PortfolioCreate):
    return service.create(data)


@router.get("/{portfolio_id}", response_model=Portfolio)
def get_portfolio(portfolio_id: str):
    portfolio = service.get_by_id(portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")
    return portfolio


@router.put("/{portfolio_id}", response_model=Portfolio)
def update_portfolio(portfolio_id: str, data: dict):
    portfolio = service.update(portfolio_id, data)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")
    return portfolio


@router.delete("/{portfolio_id}")
def delete_portfolio(portfolio_id: str):
    deleted = service.delete(portfolio_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")
    return {"status": "deleted"}


@router.post("/{portfolio_id}/positions", response_model=Portfolio)
def add_position(portfolio_id: str, data: PositionAdd):
    portfolio = service.add_position(portfolio_id, data)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")
    return portfolio


@router.delete("/{portfolio_id}/positions/{ticker}", response_model=Portfolio)
def remove_position(portfolio_id: str, ticker: str):
    portfolio = service.remove_position(portfolio_id, ticker)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")
    return portfolio


@router.get("/{portfolio_id}/analysis")
def get_portfolio_analysis(portfolio_id: str):
    portfolio = service.get_by_id(portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")

    # Get price history for assets with positions
    prices_data = {}
    for pos in portfolio.positions:
        hist = market_service.get_history(pos.ticker, period="1y", interval="1d")
        if hist and hist.get("prices"):
            import pandas as pd
            df = pd.DataFrame(hist["prices"])
            prices_data[pos.ticker] = df

    analysis = analytics_service.analyze(portfolio, prices_data if prices_data else None)
    return analysis
