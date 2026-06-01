import logging
from collections import Counter
from datetime import datetime, timezone

from app.schemas.portfolio import Portfolio
from app.services.asset_analysis_service import AssetAnalysisService
from app.services.asset_universe_service import AssetUniverseService
from app.services.forecast_service import ForecastService
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
        self.forecast = ForecastService()

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
        forecast_risk = self._compute_forecast_risk(portfolio, analysis)

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
            "benchmark": opinion["benchmark"],
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

    def _compute_forecast_risk(self, portfolio: Portfolio, analysis: dict) -> float:
        volatility = abs(float(analysis.get("volatility") or 0.0))
        beta = abs(float(analysis.get("beta") or 0.0))
        var_95 = abs(float(analysis.get("var_95") or 0.0))
        structural_risk = min(1.0, volatility * 1.8 + var_95 * 2.4 + max(0.0, beta - 1.0) * 0.12)

        confidences = []
        for position in portfolio.positions[:8]:
            forecast = self.forecast.predict(position.ticker)
            if forecast and forecast.get("confidence") is not None:
                confidences.append(float(forecast["confidence"]))

        if not confidences:
            return round(min(1.0, 0.35 + structural_risk * 0.65), 4)

        predictability_penalty = 1.0 - (sum(confidences) / len(confidences))
        return round(min(1.0, structural_risk * 0.6 + predictability_penalty * 0.4), 4)

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
            strengths.append("A carteira tem boa diversificacao entre classes de ativos, o que reduz a dependencia de um unico mercado.")
        if fixed_weight > 0:
            strengths.append("Existe um bloco mais defensivo em renda fixa ou caixa, o que ajuda a suavizar a volatilidade do conjunto.")
        if any(all_assets.get(ticker) and all_assets[ticker].asset_class == "US_STOCK" for ticker in weights):
            strengths.append("A exposicao internacional amplia o acesso a dolar e a motores de crescimento fora do mercado domestico.")
        if any(all_assets.get(ticker) and all_assets[ticker].asset_class == "BR_STOCK" for ticker in weights):
            strengths.append("A parte brasileira traz ativos geradores de caixa e setores conhecidos pelo investidor local.")
        if not strengths:
            strengths.append("A carteira tem uma logica basica de diversificacao, mas ainda depende bastante de poucos vetores.")

        overlaps = []
        function_groups = {
            "S&P 500": {"IVV", "VOO", "SPY", "IVVB11", "GPUS11"},
            "Dividendos EUA": {"SCHD", "SPYI11", "DIVO11"},
            "Cripto major": {"BTC", "ETH", "SOL"},
        }
        for label, tickers in function_groups.items():
            matched = [ticker for ticker in weights if ticker.upper() in tickers]
            if len(matched) >= 2:
                overlaps.append(f"Ha sobreposicao funcional em {label}: {', '.join(matched)}.")
        if correlation_risk > 0.6:
            overlaps.append("A correlacao media entre ativos esta elevada, o que reduz o ganho efetivo de diversificacao.")
        if concentration > 0.25:
            overlaps.append("A carteira ainda concentra peso demais em poucos ativos relevantes.")
        if us_weight >= 0.35:
            overlaps.append("A exposicao aos Estados Unidos e maior do que parece quando se somam ativos globais, ETFs e BDRs.")
        if fii_weight >= 0.25:
            overlaps.append("O bloco de FIIs ja exige cuidado para nao mascarar risco de credito ou sensibilidade a juros.")
        sectors = Counter(
            (all_assets.get(pos.ticker).sector if all_assets.get(pos.ticker) else "Desconhecido")
            for pos in positions
        )
        repeated_sectors = [sector for sector, count in sectors.items() if sector != "Desconhecido" and count >= 2]
        if repeated_sectors:
            overlaps.append(f"Ha repeticao setorial relevante em {', '.join(repeated_sectors[:3])}.")
        countries = Counter(
            (all_assets.get(pos.ticker).country if all_assets.get(pos.ticker) else "Desconhecido")
            for pos in positions
        )
        if countries.get("US", 0) >= 3:
            overlaps.append("Existe sobreposicao geografica relevante em ativos ligados aos Estados Unidos.")

        block_reviews = []
        br_positions = [pos for pos in positions if pos.asset_class == "BR_STOCK"]
        if br_positions:
            sectors_br = Counter(
                (all_assets.get(pos.ticker).sector if all_assets.get(pos.ticker) else "Desconhecido")
                for pos in br_positions
            )
            top_sector, _ = sectors_br.most_common(1)[0]
            block_reviews.append({
                "title": "Acoes brasileiras",
                "assessment": "Bom para renda e estabilidade, mas ainda concentrado em setores dominantes da carteira."
                if len(sectors_br) <= 4 else "Bloco razoavelmente distribuido entre setores locais.",
                "highlights": f"Maior concentracao setorial em {top_sector}.",
            })

        fii_positions = [pos for pos in positions if pos.asset_class == "FII"]
        if fii_positions:
            credit_like = 0
            for pos in fii_positions:
                sector = all_assets.get(pos.ticker).sector if all_assets.get(pos.ticker) else ""
                if any(word in sector.lower() for word in ["credito", "hibrido"]):
                    credit_like += 1
            block_reviews.append({
                "title": "FIIs",
                "assessment": "Bom para renda mensal, mas com atencao ao risco de credito e ao comportamento dos juros."
                if credit_like else "Bloco de FIIs mais equilibrado entre renda e tijolo.",
                "highlights": f"{credit_like} fundo(s) tem perfil mais proximo de credito ou hibrido.",
            })

        us_positions = [pos for pos in positions if pos.asset_class == "US_STOCK"]
        if us_positions:
            block_reviews.append({
                "title": "Exterior",
                "assessment": "Bloco importante para diversificacao geografica, mas sensivel ao ciclo de juros e ao peso excessivo em indices parecidos."
                if us_weight >= 0.3 else "Bloco externo ajuda a diversificar sem dominar a carteira.",
                "highlights": f"Peso agregado aproximado de {us_weight * 100:.1f}% em ativos ligados aos EUA.",
            })

        if fixed_weight > 0:
            block_reviews.append({
                "title": "Renda fixa",
                "assessment": "Bloco defensivo util para equilibrio da carteira.",
                "highlights": f"Peso aproximado de {fixed_weight * 100:.1f}% na composicao.",
            })

        if crypto_weight > 0:
            block_reviews.append({
                "title": "Cripto",
                "assessment": "Bloco com potencial de assimetria, mas com volatilidade estruturalmente alta.",
                "highlights": f"Peso aproximado de {crypto_weight * 100:.1f}% em criptoativos.",
            })

        headline_risks = []
        if us_weight >= 0.35:
            headline_risks.append("renda variavel global")
        if fii_weight >= 0.20:
            headline_risks.append("FIIs")
        if crypto_weight >= 0.08:
            headline_risks.append("cripto")
        suffix = f", mas com risco concentrado em {', '.join(headline_risks)}" if headline_risks else ""

        if score >= 0.7:
            headline = f"A avaliacao final da carteira e: boa, diversificada em classes de ativos{suffix}."
        elif score >= 0.45:
            headline = f"A avaliacao final da carteira e: razoavel, com bons ativos, porem com sobreposicoes e riscos que merecem ajuste{suffix}."
        else:
            headline = f"A avaliacao final da carteira e: fragil na construcao atual, com concentracao e correlacao elevadas{suffix}."

        summary_parts = [
            "Nao e uma carteira ruim.",
            f"Ela combina {len(class_weights)} classe(s) de ativos e hoje tem seus maiores pesos em {', '.join(top_tickers[:4])}.",
        ]
        if overlaps:
            summary_parts.append("O principal ponto de atencao esta na sobreposicao entre ativos com funcao parecida e no risco escondido em alguns blocos.")
        if forecast_risk > 0.5:
            summary_parts.append("A leitura quantitativa de risco ainda pede monitoramento de volatilidade e concentracao.")

        final_diag_parts = []
        if concentration > 0.3:
            final_diag_parts.append("a carteira esta concentrada em poucos nomes")
        if correlation_risk > 0.6:
            final_diag_parts.append("muitos ativos tendem a se mover juntos")
        if crypto_weight > 0.1:
            final_diag_parts.append("o peso de cripto ja aumenta bastante a oscilacao potencial")
        if not final_diag_parts:
            final_diag_parts.append("a carteira esta funcional, mas ainda pode ficar mais limpa e coerente")

        conclusion = "O maior ajuste conceitual e reduzir redundancias, explicitar a funcao de cada bloco e limitar os riscos que hoje parecem diversificacao, mas ainda representam exposicao repetida."

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
            "final_diagnosis": "No diagnostico final, " + "; ".join(final_diag_parts) + ".",
            "conclusion": conclusion,
            "sources": sources[:15],
            "source_groups": source_groups,
            "benchmark": analysis.get("benchmark"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
