from __future__ import annotations

import hashlib
import math
from datetime import date, datetime, timedelta, timezone

from app.schemas.portfolio import Portfolio, Position


EXAMPLE_VERSION = 1


class ExamplePortfolioService:
    """Owns deterministic demonstration data. It never calls external services."""

    _TEMPLATE = (
        ("PETR4", "BR_STOCK", 120, 29.40), ("VALE3", "BR_STOCK", 80, 62.10),
        ("ITUB4", "BR_STOCK", 150, 28.60), ("BBAS3", "BR_STOCK", 90, 47.20),
        ("ABEV3", "BR_STOCK", 180, 13.80), ("WEGE3", "BR_STOCK", 70, 35.90),
        ("ELET3", "BR_STOCK", 75, 38.40), ("RENT3", "BR_STOCK", 50, 51.30),
        ("LREN3", "BR_STOCK", 100, 16.20), ("SUZB3", "BR_STOCK", 65, 52.70),
        ("GGBR4", "BR_STOCK", 110, 20.40), ("B3SA3", "BR_STOCK", 160, 11.80),
        ("HGLG11", "FII", 24, 158.50), ("KNRI11", "FII", 22, 145.10),
        ("MXRF11", "FII", 300, 10.20), ("XPLG11", "FII", 28, 101.40),
        ("VISC11", "FII", 25, 108.70), ("BTLG11", "FII", 26, 104.20),
        ("HGCR11", "FII", 30, 98.60), ("VINO11", "FII", 40, 8.70),
        ("AAPL", "US_STOCK", 18, 920.00), ("MSFT", "US_STOCK", 12, 1880.00),
        ("NVDA", "US_STOCK", 20, 610.00), ("GOOGL", "US_STOCK", 16, 780.00),
        ("AMZN", "US_STOCK", 14, 890.00), ("META", "US_STOCK", 8, 2320.00),
        ("TSLA", "US_STOCK", 10, 1120.00), ("JPM", "US_STOCK", 12, 970.00),
        ("BTC", "CRYPTO", 0.075, 285000.00), ("ETH", "CRYPTO", 1.6, 15200.00),
        ("SOL", "CRYPTO", 24, 680.00),
        ("AAPL34", "US_STOCK", 80, 52.40), ("MSFT34", "US_STOCK", 55, 83.60),
        ("GOOG34", "US_STOCK", 70, 61.20), ("AMZO34", "US_STOCK", 65, 48.90),
        ("NVDC34", "US_STOCK", 60, 72.30),
    )

    def template_positions(self) -> list[Position]:
        return [
            Position(
                asset_id=ticker,
                ticker=ticker,
                asset_class=asset_class,
                quantity=quantity,
                avg_price=avg_price,
                currency="BRL",
                manual_notes="Posição demonstrativa com dados simulados.",
            )
            for ticker, asset_class, quantity, avg_price in self._TEMPLATE
        ]

    @staticmethod
    def _factor(ticker: str) -> float:
        seed = int(hashlib.sha256(ticker.upper().encode("utf-8")).hexdigest()[:8], 16)
        return 0.88 + (seed % 29) / 100

    def price_for(self, position: Position) -> float:
        basis = float(position.avg_price or max(10.0, len(position.ticker) * 9.0))
        return round(basis * self._factor(position.ticker), 2)

    def prices(self, portfolio: Portfolio) -> dict:
        rows = []
        total_value = 0.0
        total_unrealized = 0.0
        for position in portfolio.positions:
            current = self.price_for(position)
            value = current * position.quantity
            pnl = None if position.avg_price is None else (current - float(position.avg_price)) * position.quantity
            pnl_pct = None if not position.avg_price else ((current / float(position.avg_price)) - 1) * 100
            total_value += value
            if pnl is not None:
                total_unrealized += pnl
            sparkline = [round(current * (0.96 + index * 0.004 + math.sin(index / 3) * 0.008), 2) for index in range(20)]
            rows.append({
                "ticker": position.ticker, "asset_class": position.asset_class,
                "quantity": position.quantity, "avg_price": position.avg_price,
                "current_price": current, "currency": "BRL", "total_value": round(value, 2),
                "name": position.ticker, "unrealized_pnl": round(pnl, 2) if pnl is not None else None,
                "unrealized_pnl_pct": round(pnl_pct, 2) if pnl_pct is not None else None,
                "sparkline_20d": sparkline,
            })
        for row in rows:
            row["weight_pct"] = round(row["total_value"] / total_value * 100, 2) if total_value else None
        return {
            "portfolio_id": portfolio.id, "portfolio_name": portfolio.name,
            "total_value": round(total_value, 2) if rows else None,
            "total_unrealized_pnl": round(total_unrealized, 2) if rows else None,
            "positions": rows, "is_demo": True,
        }

    def history(self, portfolio: Portfolio, period: str, ticker: str | None = None) -> dict:
        selected = [p for p in portfolio.positions if ticker is None or p.ticker.upper() == ticker.upper()]
        prices = {p.ticker: self.price_for(p) for p in selected}
        invested = sum((p.avg_price or 0) * p.quantity for p in selected)
        current = sum(prices[p.ticker] * p.quantity for p in selected)
        months = {"1m": 1, "6m": 6, "1y": 12, "max": 12}[period]
        end = date.today()
        points = []
        for index in range(months + 1):
            day = end - timedelta(days=30 * (months - index))
            progress = index / max(months, 1)
            wave = math.sin(index * 1.7) * current * 0.012
            market_value = current * (0.82 + 0.18 * progress) + wave
            points.append({
                "date": day.isoformat(), "market_value": round(market_value, 2),
                "invested_value": round(invested * (0.76 + 0.24 * progress), 2),
                "quantity": round(sum(p.quantity for p in selected), 8) if ticker else None,
                "contribution_value": round(invested * 0.02, 2) if index and index % 3 == 0 else None,
                "contribution_quantity": 0.0,
            })
        return {
            "portfolio_id": portfolio.id, "period": period, "ticker": ticker.upper() if ticker else None,
            "currency": "BRL", "points": points,
            "available_tickers": sorted(p.ticker for p in portfolio.positions),
            "warnings": ["Dados demonstrativos: valores e evolução são simulados pela Operum."],
        }

    def analysis(self, portfolio: Portfolio) -> dict:
        price_payload = self.prices(portfolio)
        values = {row["ticker"]: row["total_value"] for row in price_payload["positions"]}
        total = sum(values.values())
        weights = {key: value / total for key, value in values.items()} if total else {}
        class_values: dict[str, float] = {}
        for row in price_payload["positions"]:
            class_values[row["asset_class"]] = class_values.get(row["asset_class"], 0) + row["total_value"]
        return {
            "weights": weights,
            "class_weights": {key: value / total for key, value in class_values.items()} if total else {},
            "concentration": sum(value * value for value in weights.values()),
            "concentration_label": "Diversificada" if len(weights) >= 10 else "Concentrada",
            "correlation_matrix": None, "volatility": 0.142, "volatility_window_days": 252,
            "portfolio_return": 0.118, "var_95": -0.021, "cvar_95": -0.032, "beta": 0.91,
            "benchmark": {"ticker": "IBOV", "label": "Ibovespa (demonstração)", "return_21d_pct": 1.8,
                          "return_42d_pct": 3.2, "return_63d_pct": 4.7, "return_252d_pct": 9.4},
            "num_assets": len(portfolio.positions), "num_classes": len(class_values), "is_demo": True,
        }

    def portfolio_opinion(self, portfolio: Portfolio, analysis_horizon: str) -> dict:
        prices = self.prices(portfolio)
        largest = max(prices["positions"], key=lambda item: item["weight_pct"] or 0, default=None)
        class_count = len({position.asset_class for position in portfolio.positions})
        return {
            "score": 0.78,
            "components": {"diversification": 0.86, "correlation_risk": 0.72, "news_impact": 0.7,
                           "macro_sensitivity": 0.76, "forecast_risk": 0.74},
            "opinion": "Carteira demonstrativa diversificada entre mercados e classes.",
            "headline": "Uma composição ampla para explorar os recursos do Operum",
            "composition_grade": "Boa diversificação demonstrativa",
            "composition_summary": "A carteira combina ativos brasileiros, fundos, exposição internacional e criptoativos. Todos os valores desta análise são simulados.",
            "strengths": ["Diversificação entre classes", "Exposição local e internacional"],
            "overlaps": ["Algumas posições de tecnologia aparecem em ações dos EUA e BDRs."],
            "block_reviews": [],
            "final_diagnosis": "A composição demonstra como o Operum organiza concentração, classes e evolução patrimonial.",
            "conclusion": "Use esta carteira para conhecer a plataforma. Esta análise não constitui recomendação de investimento.",
            "composition_diagnosis": {
                "overall_status": "saudavel", "overall_score": 78,
                "summary": "Distribuição demonstrativa entre diferentes classes de ativos.",
                "metrics": {"total_assets": len(portfolio.positions), "direct_equity_count": sum(p.asset_class in {"BR_STOCK", "US_STOCK"} for p in portfolio.positions),
                            "class_count": class_count, "sector_count": 12,
                            "top_position": {"ticker": largest["ticker"] if largest else None, "weight_pct": largest["weight_pct"] if largest else 0},
                            "top3_weight_pct": round(sum(sorted((p["weight_pct"] or 0 for p in prices["positions"]), reverse=True)[:3]), 2),
                            "top_class": {"name": "Ações", "weight_pct": 55.0},
                            "top_sector": {"name": "Tecnologia", "weight_pct": 22.0}, "international_weight_pct": 38.0},
                "checks": [{"id": "demo-diversification", "label": "Diversificação", "status": "saudavel",
                            "value": f"{len(portfolio.positions)} ativos", "target": "Ambiente demonstrativo",
                            "message": "A carteira foi montada para apresentar diferentes recursos do Operum."}],
                "strengths": ["Diversificação entre classes"], "weaknesses": ["Dados não representam o mercado real"],
                "watch_points": ["Compare os pesos das classes e a evolução simulada"],
                "data_quality_warnings": ["Dados integralmente simulados."],
            },
            "sources": [], "source_groups": [], "selected_analysis_horizon": analysis_horizon,
            "portfolio_id": portfolio.id, "generated_at": datetime.now(timezone.utc).isoformat(), "is_demo": True,
        }

    def position_opinion(self, portfolio: Portfolio, ticker: str, history_horizon: str, outlook_horizon: str) -> dict:
        position = next((item for item in portfolio.positions if item.ticker.upper() == ticker.upper()), None)
        if position is None:
            return {"status": "not_found"}
        current = self.price_for(position)
        now = datetime.now(timezone.utc)
        horizon_days = {"1w": 7, "1m": 30, "2m": 60, "3m": 90}
        history_days = horizon_days[history_horizon]
        outlook_days = horizon_days[outlook_horizon]
        historical = [
            {"date": (date.today() - timedelta(days=history_days - index * history_days / 6)).isoformat(),
             "value": round(current * (0.91 + index * 0.015 + math.sin(index) * 0.006), 2)}
            for index in range(7)
        ]
        forecast = [
            {"date": (date.today() + timedelta(days=index * outlook_days / 4)).isoformat(),
             "value": round(current * (1 + index * 0.008), 2)}
            for index in range(1, 5)
        ]
        history_boxes = {key: f"No período demonstrativo de {key}, {position.ticker} apresentou oscilação simulada." for key in ("1w", "1m", "2m", "3m")}
        outlook_boxes = {key: f"Para {key}, o cenário-base simulado mantém variação moderada. Não é uma projeção real." for key in ("1w", "1m", "2m", "3m")}
        return {
            "portfolio_id": portfolio.id, "ticker": position.ticker, "asset_name": position.ticker,
            "asset_class": position.asset_class, "asset_function": "Diversificação demonstrativa",
            "generated_at": now.isoformat(), "recomputed_at": now.isoformat(), "confidence": "demonstrativa",
            "status": "ok", "selected_history_horizon": history_horizon, "selected_outlook_horizon": outlook_horizon,
            "current_snapshot": {"current_price": current, "currency": "BRL", "weight_pct": None,
                                 "sector": "Demonstrativo", "country": "Simulado", "asset_function": "Diversificação demonstrativa"},
            "historical_window": {"start_date": (date.today() - timedelta(days=history_days)).isoformat(),
                                  "end_date": date.today().isoformat(), "news_count": 0, "has_price_history": True},
            "historical_series": historical, "forecast_series": forecast, "forecast_anchor_points": [],
            "recent_performance": {"change_selected_pct": 9.0, "change_1m_pct": 2.2, "change_2m_pct": 4.5,
                                   "change_3m_pct": 6.8, "change_12m_pct": 11.4, "volatility_selected_pct": 14.2,
                                   "drawdown_selected_pct": -6.1, "beta_selected": 0.91, "correlation_selected": 0.64,
                                   "benchmark_ticker": "IBOV", "forecast_return_selected_pct": 3.2,
                                   "forecast_price_selected": forecast[-1]["value"], "forecast_confidence_selected": 0.7,
                                   "forecast_news_adjustment_pct": 0.0},
            "outlook_3m": {"scenario": "Cenário demonstrativo", "dominant_topics": ["Dados simulados"]},
            "analysis_sections": {
                "current": f"{position.ticker} representa uma posição simulada dentro da Carteira Exemplo.",
                "recent": history_boxes[history_horizon], "outlook": outlook_boxes[outlook_horizon],
                "recent_by_horizon": history_boxes, "outlook_by_horizon": outlook_boxes,
                "box_history_by_horizon": history_boxes, "box_current": "Preço, quantidade e participação são demonstrativos.",
                "box_outlook_by_horizon": outlook_boxes,
                "visual_summary": {"asset_status": "Demonstrativo", "fundamentals": "Não avaliados", "price_trend": "Simulada",
                                   "news_sentiment": "Não utilizado", "position_size": "Educativa", "portfolio_risk": "Simulado",
                                   "main_reason": "Exploração da plataforma", "confidence": "Demonstração"},
                "summary": "Análise pré-estabelecida para apresentar a experiência do Operum.",
                "what_happened": history_boxes[history_horizon], "company_situation": "Dados fundamentais reais não são consultados.",
                "asset_price_situation": "A trajetória exibida é determinística e simulada.",
                "current_situation": "Posição ativa na Carteira Exemplo.",
                "portfolio_impact": "Contribui para demonstrar a diversificação entre classes.",
                "scenarios": {"favorable": "Valorização simulada.", "base": "Oscilação moderada simulada.", "adverse": "Queda simulada."},
                "what_to_watch": ["Compare a participação do ativo com as demais classes."],
                "conclusion": "Conteúdo educativo e demonstrativo, sem recomendação de investimento.",
                "data_quality_warnings": ["Dados integralmente simulados."],
            },
            "used_news_count": 0, "sources": [], "source_groups": [], "is_demo": True,
        }
