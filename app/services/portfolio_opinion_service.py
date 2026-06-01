import logging
from collections import Counter
from datetime import datetime, timezone

from app.schemas.portfolio import Portfolio
from app.services.asset_analysis_service import AssetAnalysisService
from app.services.asset_universe_service import AssetUniverseService
from app.services.news_ingestion_service import NewsIngestionService
from app.services.portfolio_analytics_service import PortfolioAnalyticsService

logger = logging.getLogger(__name__)


def _group_sources_by_origin(sources: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for source in sources:
        source_name = source.get("source_name", "Fonte")
        grouped.setdefault(source_name, []).append(source)

    return [
        {
            "source_name": source_name,
            "count": len(items),
            "items": items,
        }
        for source_name, items in grouped.items()
    ]


class PortfolioOpinionService:
    def __init__(self):
        self.analytics = PortfolioAnalyticsService()
        self.news_service = NewsIngestionService()
        self.asset_analysis = AssetAnalysisService()
        self.assets = AssetUniverseService()

    def generate_opinion(
        self,
        portfolio: Portfolio,
        analysis: dict | None = None,
        prices_data: dict | None = None,
    ) -> dict:
        if analysis is None:
            analysis = self.analytics.analyze(portfolio, prices_data)

        concentration = analysis.get("concentration", 1.0)
        diversification_score = 1.0 - concentration

        corr_matrix = analysis.get("correlation_matrix")
        correlation_risk = 0.0
        if corr_matrix and len(corr_matrix) > 1:
            flat = [c for row in corr_matrix for c in row]
            avg_corr = sum(abs(c) for c in flat) / len(flat) if flat else 0.0
            correlation_risk = min(1.0, avg_corr)

        news_impact = self._compute_news_impact(portfolio)
        macro_sensitivity = self._compute_macro_sensitivity(analysis)
        var_95 = analysis.get("var_95")
        forecast_risk = min(1.0, abs(var_95) * 5) if var_95 is not None else 0.5

        portfolio_score = (
            0.30 * diversification_score
            + 0.20 * (1.0 - correlation_risk)
            + 0.20 * (1.0 - news_impact)
            + 0.15 * (1.0 - macro_sensitivity)
            + 0.15 * (1.0 - forecast_risk)
        )
        portfolio_score = max(0.0, min(1.0, portfolio_score))

        opinion = self._generate_text(
            portfolio_score,
            concentration,
            correlation_risk,
            forecast_risk,
            portfolio,
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
            "opinion": opinion["composition_summary"],
            "headline": opinion["headline"],
            "composition_grade": opinion["composition_grade"],
            "composition_summary": opinion["composition_summary"],
            "strengths": opinion["strengths"],
            "overlaps": opinion["overlaps"],
            "block_reviews": opinion["block_reviews"],
            "final_diagnosis": opinion["final_diagnosis"],
            "conclusion": opinion["conclusion"],
            "sources": opinion["sources"],
            "source_groups": opinion["source_groups"],
            "portfolio_id": portfolio.id,
            "generated_at": opinion["generated_at"],
        }

    def _compute_news_impact(self, portfolio: Portfolio) -> float:
        try:
            all_news = self.news_service.get_all_raw()
        except Exception:
            return 0.5

        portfolio_tickers = {p.ticker.upper() for p in portfolio.positions}
        relevant = [
            n for n in all_news if any(a.upper() in portfolio_tickers for a in n.mentioned_assets)
        ]
        if not relevant:
            return 0.3

        avg_impact = sum(n.impact_score for n in relevant) / len(relevant)
        return min(1.0, avg_impact)

    def _compute_macro_sensitivity(self, analysis: dict) -> float:
        class_weights = analysis.get("class_weights", {})
        macro_exposed = 0.0
        total = 0.0
        for cls, weight in class_weights.items():
            if cls in ("BR_STOCK", "US_STOCK", "CRYPTO"):
                macro_exposed += weight
            total += weight
        return macro_exposed / total if total > 0 else 0.5

    def _generate_text(
        self,
        score: float,
        concentration: float,
        correlation_risk: float,
        forecast_risk: float,
        portfolio: Portfolio,
        analysis: dict,
    ) -> dict:
        all_assets = {asset.ticker: asset for asset in self.assets.get_all()}
        positions = sorted(
            portfolio.positions,
            key=lambda pos: analysis.get("weights", {}).get(pos.ticker, 0),
            reverse=True,
        )
        weights = analysis.get("weights", {})
        class_weights = analysis.get("class_weights", {})
        top_tickers = [pos.ticker for pos in positions[:5]]

        us_weight = sum(
            weight
            for ticker, weight in weights.items()
            if all_assets.get(ticker) and all_assets[ticker].country == "US"
        )
        crypto_weight = class_weights.get("CRYPTO", 0.0)
        fii_weight = class_weights.get("FII", 0.0)
        fixed_weight = class_weights.get("FIXED_INCOME", 0.0)

        if score >= 0.78:
            grade = "8,5 / 10"
        elif score >= 0.68:
            grade = "7,5 / 10"
        elif score >= 0.55:
            grade = "6,5 / 10"
        elif score >= 0.4:
            grade = "5,5 / 10"
        else:
            grade = "4,5 / 10"

        strengths = []
        if len(class_weights) >= 4:
            strengths.append("A carteira tem boa diversificação entre classes de ativos, o que reduz a dependência de um único mercado.")
        if fixed_weight > 0:
            strengths.append("Existe um bloco mais defensivo em renda fixa ou caixa, o que ajuda a suavizar a volatilidade do conjunto.")
        if any(all_assets.get(ticker) and all_assets[ticker].asset_class == "US_STOCK" for ticker in weights):
            strengths.append("A exposição internacional amplia o acesso a dólar e a motores de crescimento fora do mercado doméstico.")
        if any(all_assets.get(ticker) and all_assets[ticker].asset_class == "BR_STOCK" for ticker in weights):
            strengths.append("A parte brasileira traz ativos geradores de caixa e setores conhecidos pelo investidor local.")
        if not strengths:
            strengths.append("A carteira tem uma lógica básica de diversificação, mas ainda depende bastante de poucos vetores.")

        overlaps = []
        function_groups = {
            "S&P 500": {"IVV", "VOO", "SPY", "IVVB11", "GPUS11"},
            "Dividendos EUA": {"SCHD", "SPYI11", "DIVO11"},
            "Cripto major": {"BTC", "ETH", "SOL"},
        }
        for label, tickers in function_groups.items():
            matched = [ticker for ticker in weights if ticker.upper() in tickers]
            if len(matched) >= 2:
                overlaps.append(f"Há sobreposição funcional em {label}: {', '.join(matched)}.")
        if correlation_risk > 0.6:
            overlaps.append("A correlação média entre ativos está elevada, o que reduz o ganho efetivo de diversificação.")
        if concentration > 0.25:
            overlaps.append("A carteira ainda concentra peso demais em poucos ativos relevantes.")
        if us_weight >= 0.35:
            overlaps.append("A exposição aos Estados Unidos é maior do que parece quando se somam ativos globais, ETFs e BDRs.")
        if fii_weight >= 0.25:
            overlaps.append("O bloco de FIIs já exige cuidado para não mascarar risco de crédito ou sensibilidade a juros.")

        block_reviews = []
        br_positions = [pos for pos in positions if pos.asset_class == "BR_STOCK"]
        if br_positions:
            sectors = Counter(
                (all_assets.get(pos.ticker).sector if all_assets.get(pos.ticker) else "Desconhecido")
                for pos in br_positions
            )
            top_sector, _ = sectors.most_common(1)[0]
            block_reviews.append({
                "title": "Ações brasileiras",
                "assessment": "Bom para renda e estabilidade, mas ainda concentrado em setores dominantes da carteira."
                if len(sectors) <= 4 else "Bloco razoavelmente distribuído entre setores locais.",
                "highlights": f"Maior concentração setorial em {top_sector}.",
            })

        fii_positions = [pos for pos in positions if pos.asset_class == "FII"]
        if fii_positions:
            credit_like = 0
            for pos in fii_positions:
                sector = all_assets.get(pos.ticker).sector if all_assets.get(pos.ticker) else ""
                if any(word in sector.lower() for word in ["crédito", "credito", "híbrido", "hibrido"]):
                    credit_like += 1
            block_reviews.append({
                "title": "FIIs",
                "assessment": "Bom para renda mensal, mas com atenção ao risco de crédito e ao comportamento dos juros."
                if credit_like else "Bloco de FIIs mais equilibrado entre renda e tijolo.",
                "highlights": f"{credit_like} fundo(s) têm perfil mais próximo de crédito ou híbrido.",
            })

        us_positions = [pos for pos in positions if pos.asset_class == "US_STOCK"]
        if us_positions:
            block_reviews.append({
                "title": "Exterior",
                "assessment": "Bloco importante para diversificação geográfica, mas sensível ao ciclo de juros e ao peso excessivo em índices parecidos."
                if us_weight >= 0.3 else "Bloco externo ajuda a diversificar sem dominar a carteira.",
                "highlights": f"Peso agregado aproximado de {us_weight * 100:.1f}% em ativos ligados aos EUA.",
            })

        if fixed_weight > 0:
            block_reviews.append({
                "title": "Renda fixa",
                "assessment": "Bloco defensivo útil para equilíbrio da carteira.",
                "highlights": f"Peso aproximado de {fixed_weight * 100:.1f}% na composição.",
            })

        if crypto_weight > 0:
            block_reviews.append({
                "title": "Cripto",
                "assessment": "Bloco com potencial de assimetria, mas com volatilidade estruturalmente alta.",
                "highlights": f"Peso aproximado de {crypto_weight * 100:.1f}% em criptoativos.",
            })

        headline_risks = []
        if us_weight >= 0.35:
            headline_risks.append("renda variável global")
        if fii_weight >= 0.20:
            headline_risks.append("FIIs")
        if crypto_weight >= 0.08:
            headline_risks.append("cripto")
        suffix = f", mas com risco concentrado em {', '.join(headline_risks)}" if headline_risks else ""

        if score >= 0.7:
            headline = f"A avaliação final da carteira é: boa, diversificada em classes de ativos{suffix}."
        elif score >= 0.45:
            headline = f"A avaliação final da carteira é: razoável, com bons ativos, porém com sobreposições e riscos que merecem ajuste{suffix}."
        else:
            headline = f"A avaliação final da carteira é: frágil na construção atual, com concentração e correlação elevadas{suffix}."

        summary_parts = [
            "Não é uma carteira ruim.",
            f"Ela combina {len(class_weights)} classe(s) de ativos e hoje tem seus maiores pesos em {', '.join(top_tickers[:4])}.",
        ]
        if overlaps:
            summary_parts.append("O principal ponto de atenção está na sobreposição entre ativos com função parecida e no risco escondido em alguns blocos.")
        if forecast_risk > 0.5:
            summary_parts.append("A leitura quantitativa de risco ainda pede monitoramento de volatilidade e concentração.")

        final_diag_parts = []
        if concentration > 0.3:
            final_diag_parts.append("a carteira está concentrada em poucos nomes")
        if correlation_risk > 0.6:
            final_diag_parts.append("muitos ativos tendem a se mover juntos")
        if crypto_weight > 0.1:
            final_diag_parts.append("o peso de cripto já aumenta bastante a oscilação potencial")
        if not final_diag_parts:
            final_diag_parts.append("a carteira está funcional, mas ainda pode ficar mais limpa e coerente")

        conclusion = "O maior ajuste conceitual é reduzir redundâncias, explicitar a função de cada bloco e limitar os riscos que hoje parecem diversificação, mas ainda representam exposição repetida."

        sources = []
        seen_ids = set()
        for pos in positions[: min(6, len(positions))]:
            asset_result = self.asset_analysis.generate_asset_analysis(portfolio, pos.ticker)
            for source in asset_result.get("sources", [])[:3]:
                if source["id"] in seen_ids:
                    continue
                seen_ids.add(source["id"])
                sources.append(source)
            if len(sources) >= 15:
                break

        source_groups = _group_sources_by_origin(sources[:15])

        return {
            "headline": headline,
            "composition_grade": grade,
            "composition_summary": " ".join(summary_parts),
            "strengths": strengths[:4],
            "overlaps": overlaps[:5],
            "block_reviews": block_reviews,
            "final_diagnosis": "No diagnóstico final, " + "; ".join(final_diag_parts) + ".",
            "conclusion": conclusion,
            "sources": sources[:15],
            "source_groups": source_groups,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
