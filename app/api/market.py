from fastapi import APIRouter, HTTPException

from app.services.market_data_service import MarketDataService

router = APIRouter(prefix="/market", tags=["market"])
service = MarketDataService()


@router.get("/price/{ticker}")
def get_price(ticker: str):
    result = service.get_current_price(ticker.upper())
    if result is None:
        raise HTTPException(status_code=404, detail="Preço não disponível para este ativo")
    return result


@router.get("/history/{ticker}")
def get_history(ticker: str, period: str = "6mo", interval: str = "1d"):
    result = service.get_history(ticker.upper(), period, interval)
    if result is None:
        raise HTTPException(status_code=404, detail="Histórico não disponível para este ativo")
    return result
