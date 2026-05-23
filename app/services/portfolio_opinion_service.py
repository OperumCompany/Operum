import logging
from collections import defaultdict

from app.services.portfolio_analytics_service import PortfolioAnalyticsService
from app.services.news_ingestion_service import NewsIngestionService
from app.schemas.portfolio import Portfolio

logger = logging.getLogger(__name__)


class PortfolioOpinionService:
    def __init__(self):
        self.analytics = PortfolioAnalyticsService()
        self.news_service = NewsIngestionService()

    def generate_opinion(
        self,
        portfolio: Portfolio,
        analysis: dict | None = None,
        prices_data: dict | None = None,
    ) -> dict:
        if analysis is None:
            analysis = self.analytics.analyze(portfolio, prices_data)

        # 1. Diversification score (based on concentration)
        concentration = analysis.get("concentration", 1.0)
        diversification_score = 1.0 - concentration

        # 2. Correlation risk
        corr_matrix = analysis.get("correlation_matrix")
        correlation_risk = 0.0
        if corr_matrix and len(corr_matrix) > 1:
            flat = [c for row in corr_matrix for c in row]
            avg_corr = sum(abs(c) for c in flat) / len(flat) if flat else 0.0
            correlation_risk = min(1.0, avg_corr)

        # 3. News impact on portfolio assets
        news_impact = self._compute_news_impact(portfolio)

        # 4. Macro sensitivity (based on sectors)
        macro_sensitivity = self._compute_macro_sensitivity(analysis)

        # 5. Forecast risk (from VaR)
        var_95 = analysis.get("var_95")
        forecast_risk = min(1.0, abs(var_95) * 5) if var_95 is not None else 0.5

        # Composite score
        portfolio_score = (
            0.30 * diversification_score
            + 0.20 * (1.0 - correlation_risk)
            + 0.20 * (1.0 - news_impact)
            + 0.15 * (1.0 - macro_sensitivity)
            + 0.15 * (1.0 - forecast_risk)
        )

        # Clamp to 0-1
        portfolio_score = max(0.0, min(1.0, portfolio_score))

        opinion = self._generate_text(
            portfolio_score,
            concentration,
            correlation_risk,
            news_impact,
            macro_sensitivity,
            forecast_risk,
            analysis,
        )

        return {
            "score": round(portfolio_score, 4),
            "components": {
                "diversification": round(diversification_score, 4),
                "correlation_risk": round(correlation_risk, 4),
                "news_impact": round(news_impact, 4),
                "macro_sensitivity": round(macro_sensitivity, 4),
                "forecast_risk": round(forecast_risk, 4),
            },
            "opinion": opinion,
            "portfolio_id": portfolio.id,
            "generated_at": None,
        }

    def _compute_news_impact(self, portfolio: Portfolio) -> float:
        try:
            all_news = self.news_service.get_all_raw()
        except Exception:
            return 0.5

        portfolio_tickers = {p.ticker.upper() for p in portfolio.positions}
        relevant = [
            n
            for n in all_news
            if any(a.upper() in portfolio_tickers for a in n.mentioned_assets)
        ]
        if not relevant:
            return 0.3

        avg_impact = sum(n.impact_score for n in relevant) / len(relevant)
        return min(1.0, avg_impact)

    def _compute_macro_sensitivity(self, analysis: dict) -> float:
        class_weights = analysis.get("class_weights", {})
        macro_exposed = 0.0
        total = 0.0
        for cls, w in class_weights.items():
            if cls in ("BR_STOCK", "US_STOCK", "CRYPTO"):
                macro_exposed += w
            total += w
        return macro_exposed / total if total > 0 else 0.5

    def _generate_text(
        self,
        score: float,
        concentration: float,
        correlation_risk: float,
        news_impact: float,
        macro_sensitivity: float,
        forecast_risk: float,
        analysis: dict,
    ) -> str:
        parts: list[str] = []

        if score >= 0.7:
            parts.append("Carteira bem estruturada com boa diversificação e perfil de risco equilibrado.")
        elif score >= 0.4:
            parts.append("Carteira com exposições moderadas que merecem monitoramento.")
        else:
            parts.append("Carteira concentrada com riscos elevados — atenção à alocação.")

        conc_label = analysis.get("concentration_label", "")
        if "Alta" in conc_label:
            parts.append("A concentração em poucos ativos aumenta o risco idiossincrático.")
        elif "moderada" in conc_label:
            parts.append("A diversificação é razoável, mas pode ser melhorada.")

        if correlation_risk > 0.6:
            parts.append("Ativos com alta correlação entre si reduzem o benefício da diversificação.")

        tickers = list(analysis.get("weights", {}).keys())
        if tickers:
            parts.append(f"Composição: {', '.join(tickers[:5])}.")

        if news_impact > 0.5:
            parts.append("Notícias recentes podem impactar ativos da carteira.")

        return " ".join(parts)
