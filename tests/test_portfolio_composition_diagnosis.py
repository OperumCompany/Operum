from datetime import datetime, timezone

from app.schemas.portfolio import Portfolio, Position
from app.services.portfolio_composition_diagnosis_service import PortfolioCompositionDiagnosisService


def make_portfolio(positions: list[Position]) -> Portfolio:
    return Portfolio(
        id="portfolio-test",
        owner_id="user-test",
        name="Carteira teste",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        positions=positions,
    )


def weights_for(tickers: list[str], weights: list[float]) -> dict:
    return {"weights": dict(zip(tickers, weights))}


def get_check(result: dict, check_id: str) -> dict:
    return next(check for check in result["checks"] if check["id"] == check_id)


def test_single_asset_is_critical_by_concentration():
    service = PortfolioCompositionDiagnosisService()
    portfolio = make_portfolio([
        Position(asset_id="PETR4", ticker="PETR4", asset_class="BR_STOCK", quantity=10),
    ])

    result = service.diagnose(portfolio, weights_for(["PETR4"], [1.0]))

    assert result["overall_status"] == "critico"
    assert result["metrics"]["top_position"]["weight_pct"] == 100.0
    assert get_check(result, "top_position_weight")["status"] == "critico"


def test_two_assets_with_top_weight_above_60_is_critical():
    service = PortfolioCompositionDiagnosisService()
    portfolio = make_portfolio([
        Position(asset_id="ITUB4", ticker="ITUB4", asset_class="BR_STOCK", quantity=10),
        Position(asset_id="HGLG11", ticker="HGLG11", asset_class="FII", quantity=10),
    ])

    result = service.diagnose(portfolio, weights_for(["ITUB4", "HGLG11"], [0.7, 0.3]))

    assert result["overall_status"] == "critico"
    assert get_check(result, "top_position_weight")["status"] == "critico"
    assert get_check(result, "top3_weight")["status"] == "critico"


def test_ten_to_fifteen_direct_equities_is_healthy_count():
    service = PortfolioCompositionDiagnosisService()
    tickers = ["PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "ABEV3", "WEGE3", "ELET3", "LREN3", "SUZB3", "RENT3", "VIVT3"]
    portfolio = make_portfolio([
        Position(asset_id=ticker, ticker=ticker, asset_class="BR_STOCK", quantity=10)
        for ticker in tickers
    ])

    result = service.diagnose(portfolio, weights_for(tickers, [1 / len(tickers)] * len(tickers)))

    assert result["metrics"]["direct_equity_count"] == 12
    assert get_check(result, "direct_equity_count")["status"] == "saudavel"


def test_asset_class_above_90_is_critical():
    service = PortfolioCompositionDiagnosisService()
    portfolio = make_portfolio([
        Position(asset_id="PETR4", ticker="PETR4", asset_class="BR_STOCK", quantity=10),
        Position(asset_id="VALE3", ticker="VALE3", asset_class="BR_STOCK", quantity=10),
        Position(asset_id="BTC", ticker="BTC", asset_class="CRYPTO", quantity=0.01),
    ])

    result = service.diagnose(portfolio, weights_for(["PETR4", "VALE3", "BTC"], [0.45, 0.45, 0.10]))

    assert get_check(result, "asset_class_balance")["status"] == "critico"


def test_sector_above_45_is_critical():
    service = PortfolioCompositionDiagnosisService()
    portfolio = make_portfolio([
        Position(asset_id="ITUB4", ticker="ITUB4", asset_class="BR_STOCK", quantity=10),
        Position(asset_id="BBDC4", ticker="BBDC4", asset_class="BR_STOCK", quantity=10),
        Position(asset_id="VALE3", ticker="VALE3", asset_class="BR_STOCK", quantity=10),
    ])

    result = service.diagnose(portfolio, weights_for(["ITUB4", "BBDC4", "VALE3"], [0.3, 0.25, 0.45]))

    assert get_check(result, "sector_balance")["status"] == "critico"


def test_crypto_above_20_is_critical():
    service = PortfolioCompositionDiagnosisService()
    portfolio = make_portfolio([
        Position(asset_id="BTC", ticker="BTC", asset_class="CRYPTO", quantity=0.05),
        Position(asset_id="ITUB4", ticker="ITUB4", asset_class="BR_STOCK", quantity=10),
    ])

    result = service.diagnose(portfolio, weights_for(["BTC", "ITUB4"], [0.25, 0.75]))

    assert get_check(result, "crypto_weight")["status"] == "critico"
