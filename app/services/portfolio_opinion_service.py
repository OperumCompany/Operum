import logging
from collections import Counter
from datetime import datetime, timezone

import pandas as pd

from app.core.config import AI_ENHANCE_PORTFOLIO_ANALYSIS
from app.schemas.portfolio import Portfolio
from app.services.asset_analysis_service import AssetAnalysisService
from app.services.asset_universe_service import AssetUniverseService
from app.services.forecast_service import ForecastService
from app.services.llm_prompts import PORTFOLIO_ANALYSIS_REFINER_PROMPT
from app.services.llm_service import LLMService
from app.services.news_ingestion_service import NewsIngestionService
from app.services.portfolio_analytics_service import PortfolioAnalyticsService
from app.services.portfolio_composition_diagnosis_service import PortfolioCompositionDiagnosisService

logger = logging.getLogger(__name__)

ANALYSIS_HORIZON_DAYS = {"1m": 21, "2m": 42, "3m": 63}


def _group_sources_by_origin(sources: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = {}
    for source in sources:
        source_name = source.get("source_name", "Fonte")
        grouped.setdefault(source_name, []).append(source)
    return [
        {"source_name": source_name, "count": len(items), "items": items}
        for source_name, items in grouped.items()
    ]


class PortfolioOpinionService:
    def __init__(self):
        self.analytics = PortfolioAnalyticsService()
        self.news_service = NewsIngestionService()
        self.asset_analysis = AssetAnalysisService()
        self.assets = AssetUniverseService()
        self.forecast = ForecastService()
        self.llm = LLMService()
        self.composition_diagnosis = PortfolioCompositionDiagnosisService()

    def generate_opinion(
        self,
        portfolio: Portfolio,
        analysis: dict | None = None,
        prices_data: dict | None = None,
        analysis_horizon: str = "3m",
    ) -> dict:
        analysis_horizon = analysis_horizon if analysis_horizon in ANALYSIS_HORIZON_DAYS else "3m"
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
        composition_diagnosis = self.composition_diagnosis.diagnose(portfolio, analysis, prices_data or {})
        composition_score = float(composition_diagnosis.get("overall_score", 0)) / 100.0

        base_score = (
            0.28 * diversification_score
            + 0.22 * (1.0 - correlation_risk)
            + 0.2 * (1.0 - news_impact)
            + 0.15 * (1.0 - macro_sensitivity)
            + 0.15 * (1.0 - forecast_risk)
        )
        portfolio_score = 0.75 * base_score + 0.25 * composition_score
        portfolio_score = max(0.0, min(1.0, portfolio_score))

        opinion = self._generate_text(
            portfolio_score,
            concentration,
            correlation_risk,
            forecast_risk,
            portfolio,
            analysis,
            prices_data or {},
            analysis_horizon,
        )
        opinion["composition_diagnosis"] = composition_diagnosis
        opinion = self._refine_opinion_text(opinion, analysis, analysis_horizon)

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
            "composition_diagnosis": opinion["composition_diagnosis"],
            "benchmark": opinion["benchmark"],
            "selected_analysis_horizon": analysis_horizon,
            "portfolio_id": portfolio.id,
            "generated_at": opinion["generated_at"],
        }

    def _refine_opinion_text(self, opinion: dict, analysis: dict, analysis_horizon: str) -> dict:
        if not self.llm.enabled or not AI_ENHANCE_PORTFOLIO_ANALYSIS:
            return opinion

        refined = self.llm.chat_json(
            PORTFOLIO_ANALYSIS_REFINER_PROMPT,
            {
                "components": analysis.get("components"),
                "weights": analysis.get("weights"),
                "class_weights": analysis.get("class_weights"),
                "benchmark": opinion.get("benchmark"),
                "selected_analysis_horizon": analysis_horizon,
                "headline": opinion.get("headline"),
                "composition_summary": opinion.get("composition_summary"),
                "strengths": opinion.get("strengths"),
                "overlaps": opinion.get("overlaps"),
                "block_reviews": opinion.get("block_reviews"),
                "final_diagnosis": opinion.get("final_diagnosis"),
                "conclusion": opinion.get("conclusion"),
                "composition_diagnosis": opinion.get("composition_diagnosis"),
                "source_summary": [
                    {"source_name": group.get("source_name"), "count": group.get("count")}
                    for group in opinion.get("source_groups", [])[:6]
                ],
            },
            temperature=0.15,
            max_tokens=1200,
        )
        if not refined:
            return opinion

        for key in ["headline", "composition_summary", "final_diagnosis", "conclusion"]:
            value = refined.get(key)
            if isinstance(value, str) and value.strip():
                opinion[key] = value.strip()

        for key in ["strengths", "overlaps"]:
            value = refined.get(key)
            if isinstance(value, list):
                cleaned = [item.strip() for item in value if isinstance(item, str) and item.strip()]
                if cleaned:
                    opinion[key] = cleaned

        block_reviews = refined.get("block_reviews")
        if isinstance(block_reviews, list):
            cleaned_blocks = []
            for item in block_reviews:
                if not isinstance(item, dict):
                    continue
                title = item.get("title")
                assessment = item.get("assessment")
                highlights = item.get("highlights")
                if all(isinstance(part, str) and part.strip() for part in [title, assessment, highlights]):
                    cleaned_blocks.append(
                        {
                            "title": title.strip(),
                            "assessment": assessment.strip(),
                            "highlights": highlights.strip(),
                        }
                    )
            if cleaned_blocks:
                opinion["block_reviews"] = cleaned_blocks

        return opinion

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
            if cls in ("BR_STOCK", "US_STOCK", "CRYPTO", "BDR"):
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

    def _asset_function(self, asset) -> str:
        if asset is None:
            return "diversificacao"
        if asset.asset_class == "FII":
            return "renda"
        if asset.asset_class == "CRYPTO":
            return "assimetria"
        if asset.asset_class in {"US_STOCK", "BDR"}:
            return "crescimento global"
        if any(term in (asset.sector or "").lower() for term in ["energia", "financeiro", "seguridade", "saneamento"]):
            return "estabilidade"
        return "crescimento"

    def _portfolio_return_for_window(self, portfolio: Portfolio, analysis: dict, prices_data: dict, horizon_days: int) -> float | None:
        weights = analysis.get("weights", {})
        returns = []
        for position in portfolio.positions:
            df = prices_data.get(position.ticker)
            if df is None or df.empty or len(df) <= horizon_days:
                continue
            closes = df["close"].astype(float).reset_index(drop=True)
            base = float(closes.iloc[-horizon_days - 1])
            last = float(closes.iloc[-1])
            if base == 0:
                continue
            ret = ((last / base) - 1.0) * 100
            returns.append(ret * float(weights.get(position.ticker, 0.0)))
        if not returns:
            return None
        return sum(returns)

    def _block_return_for_window(self, positions: list, analysis: dict, prices_data: dict, horizon_days: int) -> float | None:
        weights = analysis.get("weights", {})
        weighted = []
        total_weight = 0.0
        for position in positions:
            df = prices_data.get(position.ticker)
            if df is None or df.empty or len(df) <= horizon_days:
                continue
            closes = df["close"].astype(float).reset_index(drop=True)
            base = float(closes.iloc[-horizon_days - 1])
            last = float(closes.iloc[-1])
            if base == 0:
                continue
            weight = float(weights.get(position.ticker, 0.0))
            total_weight += weight
            weighted.append((((last / base) - 1.0) * 100) * weight)
        if not weighted or total_weight == 0:
            return None
        return sum(weighted) / total_weight

    def _generate_text(
        self,
        score: float,
        concentration: float,
        correlation_risk: float,
        forecast_risk: float,
        portfolio: Portfolio,
        analysis: dict,
        prices_data: dict,
        analysis_horizon: str,
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
        horizon_days = ANALYSIS_HORIZON_DAYS[analysis_horizon]
        horizon_label = {"1m": "1 mes", "2m": "2 meses", "3m": "3 meses"}[analysis_horizon]

        us_weight = sum(
            weight
            for ticker, weight in weights.items()
            if all_assets.get(ticker) and all_assets[ticker].country == "US"
        )
        crypto_weight = class_weights.get("CRYPTO", 0.0)
        fii_weight = class_weights.get("FII", 0.0)

        benchmark = analysis.get("benchmark", {})
        benchmark_return = benchmark.get(
            {"1m": "return_21d_pct", "2m": "return_42d_pct", "3m": "return_63d_pct"}[analysis_horizon],
            benchmark.get("return_63d_pct"),
        )
        portfolio_return_window = self._portfolio_return_for_window(portfolio, analysis, prices_data, horizon_days)

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
        if us_weight > 0.15:
            strengths.append("A exposicao internacional amplia o acesso a dolar e a motores de crescimento fora do mercado domestico.")
        if any(all_assets.get(ticker) and all_assets[ticker].asset_class == "BR_STOCK" for ticker in weights):
            strengths.append("A parte brasileira traz ativos geradores de caixa e setores conhecidos pelo investidor local.")
        if portfolio_return_window is not None and benchmark_return is not None and portfolio_return_window >= benchmark_return:
            strengths.append(f"No recorte de {horizon_label}, a carteira acompanha ou supera o benchmark principal.")
        top_functions = Counter(
            self._asset_function(all_assets.get(pos.ticker))
            for pos in positions[: min(8, len(positions))]
        )
        if top_functions:
            dominant_functions = ", ".join(name for name, _ in top_functions.most_common(3))
            strengths.append(f"As maiores posicoes cumprem funcoes relativamente claras dentro da carteira, com destaque para {dominant_functions}.")
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
        function_overlap = Counter(
            self._asset_function(all_assets.get(pos.ticker))
            for pos in positions
        )
        repeated_functions = [name for name, count in function_overlap.items() if count >= 3]
        if repeated_functions:
            overlaps.append(f"Existe repeticao de funcao economica em {', '.join(repeated_functions[:3])}, o que diminui a diversificacao efetiva.")

        block_reviews = []
        br_positions = [pos for pos in positions if pos.asset_class == "BR_STOCK"]
        if br_positions:
            sectors_br = Counter(
                (all_assets.get(pos.ticker).sector if all_assets.get(pos.ticker) else "Desconhecido")
                for pos in br_positions
            )
            top_sector, _ = sectors_br.most_common(1)[0]
            block_return = self._block_return_for_window(br_positions, analysis, prices_data, horizon_days)
            block_reviews.append(
                {
                    "title": "Acoes brasileiras",
                    "assessment": "Bloco com perfil de renda e estabilidade, mas ainda sensivel ao ambiente domestico e a concentracao setorial."
                    if len(sectors_br) <= 4
                    else "Bloco razoavelmente distribuido entre setores locais, ainda dependente de macro Brasil.",
                    "highlights": f"Maior concentracao setorial em {top_sector}. O bloco funciona hoje como base domestica de renda/estabilidade. Retorno em {horizon_label}: {block_return:+.1f}%."
                    if block_return is not None
                    else f"Maior concentracao setorial em {top_sector}.",
                }
            )

        fii_positions = [pos for pos in positions if pos.asset_class == "FII"]
        if fii_positions:
            credit_like = 0
            for pos in fii_positions:
                sector = all_assets.get(pos.ticker).sector if all_assets.get(pos.ticker) else ""
                if any(word in sector.lower() for word in ["credito", "hibrido"]):
                    credit_like += 1
            block_return = self._block_return_for_window(fii_positions, analysis, prices_data, horizon_days)
            block_reviews.append(
                {
                    "title": "FIIs",
                    "assessment": "Bom para renda mensal, mas com atencao ao risco de credito e ao comportamento dos juros."
                    if credit_like
                    else "Bloco de FIIs mais equilibrado entre renda e tijolo.",
                    "highlights": (
                        f"{credit_like} fundo(s) tem perfil mais proximo de credito ou hibrido. O risco escondido aqui esta mais em credito/indexadores do que em simples oscilacao de tela. Retorno em {horizon_label}: {block_return:+.1f}%."
                        if block_return is not None
                        else f"{credit_like} fundo(s) tem perfil mais proximo de credito ou hibrido."
                    ),
                }
            )

        us_positions = [pos for pos in positions if pos.asset_class in ("US_STOCK", "BDR")]
        if us_positions:
            block_return = self._block_return_for_window(us_positions, analysis, prices_data, horizon_days)
            block_reviews.append(
                {
                    "title": "Exterior",
                    "assessment": "Bloco importante para diversificacao geografica, mas sensivel ao ciclo de juros e ao peso excessivo em indices parecidos."
                    if us_weight >= 0.3
                    else "Bloco externo ajuda a diversificar sem dominar a carteira.",
                    "highlights": (
                        f"Peso agregado aproximado de {us_weight * 100:.1f}% em ativos ligados aos EUA. O bloco cumpre funcao de crescimento global, mas pode estar redundante em indices muito parecidos. Retorno em {horizon_label}: {block_return:+.1f}%."
                        if block_return is not None
                        else f"Peso agregado aproximado de {us_weight * 100:.1f}% em ativos ligados aos EUA."
                    ),
                }
            )

        if crypto_weight > 0:
            block_reviews.append(
                {
                    "title": "Cripto",
                    "assessment": "Bloco com potencial de assimetria, mas com volatilidade estruturalmente alta.",
                    "highlights": f"Peso aproximado de {crypto_weight * 100:.1f}% em criptoativos.",
                }
            )

        headline_risks = []
        if us_weight >= 0.35:
            headline_risks.append("renda variavel global")
        if fii_weight >= 0.20:
            headline_risks.append("FIIs")
        if crypto_weight >= 0.08:
            headline_risks.append("cripto")
        suffix = f", mas com risco concentrado em {', '.join(headline_risks)}" if headline_risks else ""

        if score >= 0.7:
            headline = f"A avaliacao final da carteira em {horizon_label} e: boa, diversificada em classes de ativos{suffix}."
        elif score >= 0.45:
            headline = f"A avaliacao final da carteira em {horizon_label} e: razoavel, com bons ativos, porem com sobreposicoes e riscos que merecem ajuste{suffix}."
        else:
            headline = f"A avaliacao final da carteira em {horizon_label} e: fragil na construcao atual, com concentracao e correlacao elevadas{suffix}."

        summary_parts = [
            "Nao e uma carteira ruim.",
            f"Ela combina {len(class_weights)} classe(s) de ativos e hoje tem seus maiores pesos em {', '.join(top_tickers[:4])}.",
        ]
        if portfolio_return_window is not None:
            summary_parts.append(
                f"No recorte de {horizon_label}, o retorno agregado estimado da carteira ficou em {portfolio_return_window:+.1f}%."
            )
        if benchmark_return is not None and benchmark.get("label"):
            summary_parts.append(
                f"No mesmo periodo, o benchmark de referencia {benchmark.get('label')} variou {benchmark_return:+.1f}%."
            )
        if overlaps:
            summary_parts.append("O principal ponto de atencao esta na sobreposicao entre ativos com funcao parecida e no risco escondido em alguns blocos, especialmente quando varios ativos parecem diversificacao, mas respondem ao mesmo motor.")
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

        conclusion = f"O maior ajuste conceitual para o recorte de {horizon_label} e reduzir redundancias, explicitar a funcao de cada bloco e limitar os riscos que hoje parecem diversificacao, mas ainda representam exposicao repetida. A pergunta central passa a ser se cada ativo continua cumprindo bem a funcao que deveria cumprir dentro da carteira."

        sources = []
        seen_ids = set()
        for pos in positions[: min(6, len(positions))]:
            asset_result = self.asset_analysis.generate_asset_analysis(
                portfolio,
                pos.ticker,
                history_horizon=analysis_horizon,
                outlook_horizon=analysis_horizon,
            )
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
