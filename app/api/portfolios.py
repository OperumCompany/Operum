from fastapi import APIRouter, Depends, HTTPException
from app.api.auth import require_current_user
from app.services.asset_analysis_service import AssetAnalysisService
from app.services.portfolio_service import PortfolioService
from app.services.portfolio_analytics_service import PortfolioAnalyticsService
from app.services.market_data_service import MarketDataService
from app.schemas.portfolio import ExamplePortfolioCreateResponse, Portfolio, PortfolioBulkDelete, PortfolioCreate, PortfolioHistoryResponse, PortfolioUpdate, PositionAdd

router = APIRouter(prefix="/portfolios", tags=["portfolios"])
service = PortfolioService()
analytics_service = PortfolioAnalyticsService()
market_service = MarketDataService()
asset_analysis_service = AssetAnalysisService()


@router.get("", response_model=list[Portfolio])
def list_portfolios(current=Depends(require_current_user)):
    return service.list_all(current["user"].id)


@router.post("", response_model=Portfolio, status_code=201)
def create_portfolio(data: PortfolioCreate, current=Depends(require_current_user)):
    try:
        return service.create(data, current["user"].id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/example", response_model=ExamplePortfolioCreateResponse)
def create_example_portfolio(current=Depends(require_current_user)):
    try:
        portfolio, created = service.create_example(current["user"].id)
        return {"portfolio": portfolio, "created": created}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/bulk-delete")
def bulk_delete_portfolios(data: PortfolioBulkDelete, current=Depends(require_current_user)):
    if not data.portfolio_ids:
        raise HTTPException(status_code=400, detail="Nenhuma carteira foi selecionada")
    return service.delete_many(data.portfolio_ids, current["user"].id)


@router.get("/{portfolio_id}", response_model=Portfolio)
def get_portfolio(portfolio_id: str, current=Depends(require_current_user)):
    portfolio = service.get_by_id(portfolio_id, current["user"].id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")
    return portfolio


@router.put("/{portfolio_id}", response_model=Portfolio)
def update_portfolio(portfolio_id: str, data: PortfolioUpdate, current=Depends(require_current_user)):
    portfolio = service.update(portfolio_id, data.model_dump(exclude_none=True, exclude_unset=True), current["user"].id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")
    return portfolio


@router.delete("/{portfolio_id}")
def delete_portfolio(portfolio_id: str, current=Depends(require_current_user)):
    deleted = service.delete(portfolio_id, current["user"].id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")
    return {"status": "deleted"}


@router.post("/{portfolio_id}/positions", response_model=Portfolio)
def add_position(portfolio_id: str, data: PositionAdd, current=Depends(require_current_user)):
    portfolio = service.add_position(portfolio_id, data, current["user"].id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")
    return portfolio


@router.delete("/{portfolio_id}/positions/{ticker}", response_model=Portfolio)
def remove_position(portfolio_id: str, ticker: str, current=Depends(require_current_user)):
    portfolio = service.remove_position(portfolio_id, ticker, current["user"].id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")
    return portfolio


@router.get("/{portfolio_id}/analysis")
def get_portfolio_analysis(portfolio_id: str, current=Depends(require_current_user)):
    portfolio = service.get_by_id(portfolio_id, current["user"].id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")

    if portfolio.kind == "example":
        return service.examples.analysis(portfolio)

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


@router.get("/{portfolio_id}/prices")
def get_portfolio_prices(
    portfolio_id: str,
    include_sparkline: bool = True,
    current=Depends(require_current_user),
):
    portfolio = service.get_by_id(portfolio_id, current["user"].id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")

    if portfolio.kind == "example":
        return service.examples.prices(portfolio, include_sparkline=include_sparkline)

    results = []
    total_value = 0.0
    total_unrealized = 0.0
    for pos in portfolio.positions:
        price_data = market_service.get_current_price(pos.ticker)
        sparkline = []
        if include_sparkline:
            history = market_service.get_history(pos.ticker, period="1mo", interval="1d")
            if history and history.get("prices"):
                sparkline = [round(float(item.get("close", 0.0)), 2) for item in history["prices"][-20:]]
        if price_data and price_data.get("price"):
            price = float(price_data["price"])
            value = price * pos.quantity
            unrealized = None
            unrealized_pct = None
            if pos.avg_price is not None:
                unrealized = (price - float(pos.avg_price)) * pos.quantity
                total_unrealized += unrealized
                if pos.avg_price != 0:
                    unrealized_pct = ((price / float(pos.avg_price)) - 1.0) * 100
            total_value += value
            results.append({
                "ticker": pos.ticker,
                "asset_class": pos.asset_class,
                "quantity": pos.quantity,
                "avg_price": pos.avg_price,
                "current_price": price,
                "currency": price_data.get("currency", "BRL"),
                "total_value": round(value, 2),
                "name": price_data.get("name", pos.ticker),
                "unrealized_pnl": round(unrealized, 2) if unrealized is not None else None,
                "unrealized_pnl_pct": round(unrealized_pct, 2) if unrealized_pct is not None else None,
                "sparkline_20d": sparkline,
            })
        else:
            results.append({
                "ticker": pos.ticker,
                "asset_class": pos.asset_class,
                "quantity": pos.quantity,
                "avg_price": pos.avg_price,
                "current_price": None,
                "currency": "BRL",
                "total_value": None,
                "name": pos.ticker,
                "unrealized_pnl": None,
                "unrealized_pnl_pct": None,
                "sparkline_20d": sparkline,
            })

    # Add weight % based on total
    if total_value > 0:
        for r in results:
            if r["total_value"] is not None:
                r["weight_pct"] = round(r["total_value"] / total_value * 100, 2)
            else:
                r["weight_pct"] = None

    return {
        "portfolio_id": portfolio_id,
        "portfolio_name": portfolio.name,
        "total_value": round(total_value, 2) if total_value > 0 else None,
        "total_unrealized_pnl": round(total_unrealized, 2) if results else None,
        "positions": results,
    }


@router.get("/{portfolio_id}/history", response_model=PortfolioHistoryResponse)
def get_portfolio_history(
    portfolio_id: str,
    period: str = "6m",
    ticker: str | None = None,
    current=Depends(require_current_user),
):
    if period not in {"1m", "6m", "1y", "max"}:
        raise HTTPException(status_code=400, detail="Período inválido. Use 1m, 6m, 1y ou max.")
    portfolio = service.get_by_id(portfolio_id, current["user"].id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")
    service.transactions.ensure_opening_transactions(portfolio)
    available = {item.ticker.upper() for item in service.transactions.list_for_portfolio(portfolio.id)}
    if ticker and ticker.upper() not in available:
        raise HTTPException(status_code=404, detail="Ativo não encontrado no histórico da carteira")
    if portfolio.kind == "example":
        return service.examples.history(portfolio, period, ticker)
    return service.transactions.build_history(portfolio, period, ticker)


@router.get("/{portfolio_id}/news")
def get_portfolio_news(portfolio_id: str, current=Depends(require_current_user)):
    portfolio = service.get_by_id(portfolio_id, current["user"].id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="Carteira nÃ£o encontrada")

    if portfolio.kind == "example":
        return {"items": [], "total": 0, "is_demo": True}

    by_id: dict[str, dict] = {}
    for pos in portfolio.positions:
        for item in asset_analysis_service.get_related_news(pos.ticker, limit=5):
            existing = by_id.get(item["id"])
            if existing is None or item["match_score"] > existing["match_score"]:
                enriched = dict(item)
                enriched["ticker"] = pos.ticker
                by_id[item["id"]] = enriched

    items = sorted(
        by_id.values(),
        key=lambda item: (item["match_score"], item["impact_score"], item["published_at"]),
        reverse=True,
    )
    return {"items": items, "total": len(items)}
