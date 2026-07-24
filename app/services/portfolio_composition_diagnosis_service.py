from collections import Counter

from app.schemas.portfolio import Portfolio
from app.services.asset_universe_service import AssetUniverseService


DIRECT_EQUITY_CLASSES = {"BR_STOCK", "US_STOCK", "BDR"}


def _pct(value: float | None) -> float:
    return round(float(value or 0.0) * 100, 2)


def _status_rank(status: str) -> int:
    return {"info": 0, "saudavel": 1, "atencao": 2, "critico": 3}.get(status, 0)


class PortfolioCompositionDiagnosisService:
    """Deterministic portfolio composition checks used before any LLM refinement."""

    def __init__(self):
        self.assets = AssetUniverseService()

    def diagnose(self, portfolio: Portfolio, analysis: dict, prices_data: dict | None = None) -> dict:
        positions = list(portfolio.positions)
        all_assets = {asset.ticker.upper(): asset for asset in self.assets.get_all()}
        weights = self._weights(portfolio, analysis, prices_data or {})

        if not positions:
            return self._empty()

        sorted_weights = sorted(weights.items(), key=lambda item: item[1], reverse=True)
        top_position_ticker, top_position_weight = sorted_weights[0] if sorted_weights else (None, 0.0)
        top3_weight = sum(weight for _, weight in sorted_weights[:3])

        class_weights = self._weighted_counter(positions, weights, lambda pos: pos.asset_class or "Desconhecida")
        sector_weights = self._weighted_counter(
            positions,
            weights,
            lambda pos: (all_assets.get(pos.ticker.upper()).sector if all_assets.get(pos.ticker.upper()) else None)
            or "Desconhecido",
        )
        country_weights = self._weighted_counter(
            positions,
            weights,
            lambda pos: (all_assets.get(pos.ticker.upper()).country if all_assets.get(pos.ticker.upper()) else None)
            or "Desconhecido",
        )
        function_counts = Counter(self._asset_function(all_assets.get(pos.ticker.upper())) for pos in positions)

        direct_equity_count = sum(1 for pos in positions if pos.asset_class in DIRECT_EQUITY_CLASSES)
        top_class, top_class_weight = self._top_item(class_weights)
        top_sector, top_sector_weight = self._top_item(sector_weights)
        international_weight = sum(
            weight
            for country, weight in country_weights.items()
            if country not in {"BR", "Brasil", "Desconhecido"}
        )
        crypto_weight = class_weights.get("CRYPTO", 0.0)

        checks = [
            self._equity_count_check(direct_equity_count),
            self._top_position_check(top_position_ticker, top_position_weight),
            self._top3_check(top3_weight),
            self._asset_class_check(top_class, top_class_weight, len(class_weights)),
            self._sector_check(top_sector, top_sector_weight),
            self._crypto_check(crypto_weight),
            self._international_check(international_weight),
        ]
        checks.extend(self._redundancy_checks(weights, function_counts))

        score = self._score(checks)
        overall_status = self._overall_status(score, checks)

        strengths = self._strengths(checks, class_weights, direct_equity_count, international_weight)
        weaknesses = self._weaknesses(checks)
        watch_points = self._watch_points(checks, top_position_ticker, top_class, top_sector)
        warnings = self._data_quality_warnings(positions, weights, prices_data or {}, all_assets)

        return {
            "overall_status": overall_status,
            "overall_score": score,
            "summary": self._summary(overall_status, score, top_position_ticker, top_position_weight, len(class_weights)),
            "metrics": {
                "total_assets": len(positions),
                "direct_equity_count": direct_equity_count,
                "class_count": len(class_weights),
                "sector_count": len([sector for sector in sector_weights if sector != "Desconhecido"]),
                "top_position": {
                    "ticker": top_position_ticker,
                    "weight_pct": _pct(top_position_weight),
                },
                "top3_weight_pct": _pct(top3_weight),
                "top_class": {
                    "name": self._class_label(top_class),
                    "weight_pct": _pct(top_class_weight),
                },
                "top_sector": {
                    "name": top_sector,
                    "weight_pct": _pct(top_sector_weight),
                },
                "international_weight_pct": _pct(international_weight),
            },
            "checks": checks,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "watch_points": watch_points,
            "data_quality_warnings": warnings,
        }

    def _weights(self, portfolio: Portfolio, analysis: dict, prices_data: dict) -> dict[str, float]:
        positions = list(portfolio.positions)
        weights = analysis.get("weights") if isinstance(analysis.get("weights"), dict) else {}
        if weights:
            total = sum(max(0.0, float(weight or 0.0)) for weight in weights.values())
            if total > 0:
                return {ticker.upper(): max(0.0, float(weight or 0.0)) / total for ticker, weight in weights.items()}

        values = {}
        for position in positions:
            price = None
            df = prices_data.get(position.ticker)
            if df is not None and not getattr(df, "empty", True) and "close" in df.columns:
                price = float(df["close"].iloc[-1])
            elif position.avg_price:
                price = float(position.avg_price)
            else:
                price = 1.0
            values[position.ticker.upper()] = max(0.0, float(position.quantity) * price)
        total_value = sum(values.values())
        if total_value <= 0:
            equal = 1.0 / len(positions) if positions else 0.0
            return {position.ticker.upper(): equal for position in positions}
        return {ticker: value / total_value for ticker, value in values.items()}

    def _weighted_counter(self, positions: list, weights: dict[str, float], key_fn) -> dict[str, float]:
        result: dict[str, float] = {}
        for position in positions:
            key = str(key_fn(position) or "Desconhecido")
            result[key] = result.get(key, 0.0) + float(weights.get(position.ticker.upper(), 0.0))
        return result

    def _top_item(self, values: dict[str, float]) -> tuple[str, float]:
        if not values:
            return "Desconhecido", 0.0
        return max(values.items(), key=lambda item: item[1])

    def _check(self, check_id: str, label: str, status: str, value: str, target: str, message: str) -> dict:
        return {
            "id": check_id,
            "label": label,
            "status": status,
            "value": value,
            "target": target,
            "message": message,
        }

    def _equity_count_check(self, count: int) -> dict:
        if count == 0:
            return self._check("direct_equity_count", "Quantidade de ações", "info", "0", "10 a 15 ações diretas quando houver renda variável", "A carteira não tem ações diretas; essa regra não pesa contra a composição.")
        if count <= 4:
            return self._check("direct_equity_count", "Quantidade de ações", "critico", str(count), "10 a 15 ações diretas", "A exposição em ações está muito concentrada em poucos nomes.")
        if count <= 9:
            return self._check("direct_equity_count", "Quantidade de ações", "atencao", str(count), "10 a 15 ações diretas", "A carteira já tem alguma diversificação em ações, mas ainda abaixo da faixa de referência.")
        if count <= 15:
            return self._check("direct_equity_count", "Quantidade de ações", "saudavel", str(count), "10 a 15 ações diretas", "A quantidade de ações está dentro da faixa de referência para diversificação básica.")
        if count <= 25:
            return self._check("direct_equity_count", "Quantidade de ações", "saudavel", str(count), "10 a 15 como base, até 25 com controle", "A carteira tem diversificação ampla em ações, desde que os pesos e setores estejam controlados.")
        return self._check("direct_equity_count", "Quantidade de ações", "atencao", str(count), "Evitar complexidade excessiva", "A quantidade de ações pode dificultar acompanhamento e clareza da estratégia.")

    def _top_position_check(self, ticker: str | None, weight: float) -> dict:
        value = f"{ticker or '-'}: {_pct(weight):.1f}%"
        if weight > 0.35:
            status = "critico"
            message = "A maior posição domina a carteira e pode explicar boa parte do resultado total."
        elif weight > 0.20:
            status = "critico"
            message = "A maior posição tem peso alto e aumenta o risco específico da carteira."
        elif weight > 0.10:
            status = "atencao"
            message = "A maior posição é relevante e deve ser acompanhada com atenção."
        else:
            status = "saudavel"
            message = "Nenhum ativo isolado domina a carteira."
        return self._check("top_position_weight", "Maior posição", status, value, "Até 10% por ativo como referência", message)

    def _top3_check(self, weight: float) -> dict:
        if weight > 0.60:
            status = "critico"
            message = "As três maiores posições concentram parcela alta da carteira."
        elif weight > 0.40:
            status = "atencao"
            message = "As três maiores posições têm peso relevante no resultado da carteira."
        else:
            status = "saudavel"
            message = "O peso das três maiores posições está bem distribuído."
        return self._check("top3_weight", "Top 3 posições", status, f"{_pct(weight):.1f}%", "Até 40% como referência", message)

    def _asset_class_check(self, top_class: str, weight: float, class_count: int) -> dict:
        label = self._class_label(top_class)
        if weight > 0.80:
            status = "critico"
            message = f"A carteira depende quase toda de {label}."
        elif weight >= 0.60:
            status = "atencao"
            message = f"A classe {label} tem peso dominante na carteira."
        elif class_count >= 3:
            status = "saudavel"
            message = "A carteira combina classes diferentes de ativos."
        else:
            status = "atencao"
            message = "A carteira ainda tem poucas classes de ativos relevantes."
        return self._check("asset_class_balance", "Diversificação por classe", status, f"{label}: {_pct(weight):.1f}%", "Evitar uma classe acima de 60% a 80%", message)

    def _sector_check(self, top_sector: str, weight: float) -> dict:
        if top_sector == "Desconhecido":
            return self._check("sector_balance", "Diversificação setorial", "info", "Setor desconhecido", "Setores identificados", "Não há dados setoriais suficientes para avaliar esta parte.")
        if weight > 0.45:
            status = "critico"
            message = f"O setor {top_sector} concentra peso alto na carteira."
        elif weight >= 0.30:
            status = "atencao"
            message = f"O setor {top_sector} já tem peso relevante na composição."
        else:
            status = "saudavel"
            message = "Não há domínio setorial evidente."
        return self._check("sector_balance", "Diversificação setorial", status, f"{top_sector}: {_pct(weight):.1f}%", "Evitar setor acima de 30% a 45%", message)

    def _crypto_check(self, weight: float) -> dict:
        if weight > 0.20:
            status = "critico"
            message = "Cripto tem peso alto e pode ampliar bastante a oscilação total."
        elif weight > 0.10:
            status = "atencao"
            message = "Cripto já tem peso suficiente para afetar a volatilidade da carteira."
        elif weight > 0:
            status = "saudavel"
            message = "A exposição a cripto existe, mas não domina a carteira."
        else:
            status = "info"
            message = "A carteira não possui criptoativos."
        return self._check("crypto_weight", "Exposição a cripto", status, f"{_pct(weight):.1f}%", "Atenção acima de 10%; alto risco acima de 20%", message)

    def _international_check(self, weight: float) -> dict:
        if weight == 0:
            status = "atencao"
            message = "A carteira não tem diversificação geográfica identificada fora do Brasil."
        elif weight <= 0.35:
            status = "saudavel"
            message = "A exposição internacional ajuda a reduzir dependência do mercado local."
        elif weight > 0.50:
            status = "atencao"
            message = "A exposição externa é alta e aumenta dependência de moeda e mercado internacional."
        else:
            status = "saudavel"
            message = "A exposição internacional é relevante, sem dominar completamente a carteira."
        return self._check("international_weight", "Exposição internacional", status, f"{_pct(weight):.1f}%", "Entre 10% e 35% como referência inicial", message)

    def _redundancy_checks(self, weights: dict[str, float], function_counts: Counter) -> list[dict]:
        checks = []
        etf_groups = {
            "S&P 500": {"IVV", "VOO", "SPY", "IVVB11", "GPUS11"},
            "Dividendos EUA": {"SCHD", "DIVO11", "SPYI11"},
            "Cripto major": {"BTC", "ETH", "SOL"},
        }
        for label, tickers in etf_groups.items():
            matched = sorted(ticker for ticker in weights if ticker.upper() in tickers)
            if len(matched) >= 2:
                checks.append(self._check("functional_overlap", "Sobreposição funcional", "atencao", ", ".join(matched), "Evitar ativos com função idêntica", f"Há ativos com função parecida no bloco {label}."))
        repeated = [name for name, count in function_counts.items() if count >= 4]
        if repeated:
            checks.append(self._check("economic_function_overlap", "Funções econômicas repetidas", "atencao", ", ".join(repeated[:3]), "Funções claras e complementares", "Vários ativos parecem cumprir a mesma função econômica."))
        return checks

    def _score(self, checks: list[dict]) -> int:
        score = 100
        for check in checks:
            if check["status"] == "critico":
                score -= 18
            elif check["status"] == "atencao":
                score -= 9
        return max(0, min(100, score))

    def _overall_status(self, score: int, checks: list[dict]) -> str:
        if any(check["status"] == "critico" for check in checks) or score < 55:
            return "critico"
        if any(check["status"] == "atencao" for check in checks) or score < 75:
            return "atencao"
        return "saudavel"

    def _strengths(self, checks: list[dict], class_weights: dict[str, float], equity_count: int, international_weight: float) -> list[str]:
        strengths = []
        if len(class_weights) >= 3:
            strengths.append("A carteira combina classes diferentes de ativos, o que reduz a dependência de um único mercado.")
        if 10 <= equity_count <= 15:
            strengths.append("A quantidade de ações diretas está dentro da faixa de referência para diversificação básica.")
        if 0.10 <= international_weight <= 0.35:
            strengths.append("A exposição internacional contribui para diversificação geográfica.")
        healthy_checks = [check["message"] for check in checks if check["status"] == "saudavel"]
        strengths.extend(healthy_checks[: max(0, 3 - len(strengths))])
        return strengths[:4] or ["A carteira já possui uma estrutura mínima para análise, mas ainda precisa de mais equilíbrio entre pesos e blocos."]

    def _weaknesses(self, checks: list[dict]) -> list[str]:
        items = [check["message"] for check in checks if check["status"] in {"critico", "atencao"}]
        return items[:5] or ["Não há fragilidade estrutural dominante nas regras avaliadas."]

    def _watch_points(self, checks: list[dict], top_ticker: str | None, top_class: str, top_sector: str) -> list[str]:
        points = []
        if any(check["id"] == "top_position_weight" and check["status"] != "saudavel" for check in checks):
            points.append(f"Acompanhar se {top_ticker} continua pesando demais no resultado total.")
        if any(check["id"] == "asset_class_balance" and check["status"] != "saudavel" for check in checks):
            points.append(f"Observar se a dependência de {self._class_label(top_class)} está coerente com o objetivo da carteira.")
        if any(check["id"] == "sector_balance" and check["status"] != "saudavel" for check in checks) and top_sector != "Desconhecido":
            points.append(f"Monitorar notícias e resultados do setor {top_sector}, pois ele tem peso relevante.")
        if any(check["id"] == "crypto_weight" and check["status"] in {"critico", "atencao"} for check in checks):
            points.append("Acompanhar o peso de criptoativos, pois oscilações fortes podem contaminar a leitura da carteira.")
        points.append("Revisar periodicamente se cada ativo tem uma função clara e diferente dentro da carteira.")
        return points[:5]

    def _data_quality_warnings(self, positions: list, weights: dict[str, float], prices_data: dict, all_assets: dict) -> list[str]:
        warnings = []
        missing_assets = [pos.ticker for pos in positions if pos.ticker.upper() not in all_assets]
        if missing_assets:
            warnings.append(f"Alguns ativos não foram encontrados no universo interno: {', '.join(missing_assets[:5])}.")
        missing_prices = [pos.ticker for pos in positions if pos.ticker not in prices_data and not pos.avg_price]
        if missing_prices:
            warnings.append("Parte dos pesos pode ser aproximada porque há ativos sem preço atual ou preço médio informado.")
        if not weights:
            warnings.append("Não foi possível calcular pesos completos da carteira.")
        return warnings

    def _summary(self, status: str, score: int, top_ticker: str | None, top_weight: float, class_count: int) -> str:
        status_text = {
            "saudavel": "saudável",
            "atencao": "com pontos de atenção",
            "critico": "crítica na composição atual",
        }[status]
        return (
            f"A carteira está {status_text}, com nota estrutural {score}/100. "
            f"Ela combina {class_count} classe(s) de ativos e a maior posição é {top_ticker or '-'}, "
            f"com aproximadamente {_pct(top_weight):.1f}% do total."
        )

    def _asset_function(self, asset) -> str:
        if asset is None:
            return "diversificação"
        if asset.asset_class == "FII":
            return "renda"
        if asset.asset_class == "CRYPTO":
            return "assimetria"
        if asset.asset_class in {"US_STOCK", "BDR"}:
            return "crescimento global"
        if any(term in (asset.sector or "").lower() for term in ["energia", "financeiro", "seguridade", "saneamento"]):
            return "estabilidade"
        return "crescimento"

    def _class_label(self, asset_class: str) -> str:
        return {
            "BR_STOCK": "Ações brasileiras",
            "US_STOCK": "Ações internacionais",
            "BDR": "BDRs",
            "FII": "Fundos imobiliários",
            "CRYPTO": "Criptoativos",
        }.get(asset_class, asset_class or "Desconhecida")

    def _empty(self) -> dict:
        return {
            "overall_status": "critico",
            "overall_score": 0,
            "summary": "A carteira ainda não tem ativos suficientes para análise de composição.",
            "metrics": {
                "total_assets": 0,
                "direct_equity_count": 0,
                "class_count": 0,
                "sector_count": 0,
                "top_position": {"ticker": None, "weight_pct": 0.0},
                "top3_weight_pct": 0.0,
                "top_class": {"name": "Desconhecida", "weight_pct": 0.0},
                "top_sector": {"name": "Desconhecido", "weight_pct": 0.0},
                "international_weight_pct": 0.0,
            },
            "checks": [],
            "strengths": [],
            "weaknesses": ["Adicione ativos para permitir a leitura de composição."],
            "watch_points": ["Adicionar posições com quantidade e preço para calcular pesos reais."],
            "data_quality_warnings": [],
        }
