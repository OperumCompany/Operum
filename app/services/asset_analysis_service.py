import math
from collections import Counter
from datetime import datetime, timedelta, timezone

import pandas as pd

from app.schemas.news import NewsItem
from app.schemas.portfolio import Portfolio, Position
from app.services.asset_universe_service import AssetUniverseService
from app.services.local_storage_service import LocalStorageService
from app.services.market_data_service import MarketDataService
from app.services.news_ingestion_service import NewsIngestionService


class AssetAnalysisService:
    def __init__(self):
        self.storage = LocalStorageService()
        self.market = MarketDataService()
        self.news = NewsIngestionService()
        self.assets = AssetUniverseService()
        self._config_path = "ai/asset_analysis_config.json"
        self._cache_dir = "ai/asset_analysis_cache"
        self._config = self._load_or_init_config()

    def _load_or_init_config(self) -> dict:
        config = self.storage.load_json(self._config_path)
        if config:
            return config

        config = {
            "weights": {
                "direct_match": 0.45,
                "name_alias": 0.25,
                "sector_match": 0.1,
                "country_match": 0.1,
                "recency": 0.1,
            },
            "aliases": {
                "B3SA3": ["b3", "bolsa brasileira", "bolsa de valores"],
                "BBAS3": ["banco do brasil"],
                "BTC": ["bitcoin", "btc"],
                "ETH": ["ethereum", "ether"],
                "SOL": ["solana"],
                "TAEE11": ["taesa"],
                "CXSE3": ["caixa seguridade"],
                "SAPR11": ["sanepar"],
                "CMIG4": ["cemig"],
                "CEEB3": ["coelba"],
            },
            "class_templates": {
                "FII": "O ativo é um fundo imobiliário e depende de renda, qualidade do portfólio e sensibilidade a juros.",
                "CRYPTO": "O ativo pertence ao bloco cripto, com potencial de assimetria e volatilidade estruturalmente elevada.",
                "FIXED_INCOME": "O ativo pertence à renda fixa, com comportamento mais ligado a juros, duration e previsibilidade do fluxo.",
                "US_STOCK": "O ativo está exposto ao mercado americano e ao ciclo global de juros, dólar e crescimento.",
                "BR_STOCK": "O ativo está exposto ao ambiente doméstico, incluindo juros, fluxo para a bolsa e atividade econômica local.",
            },
        }
        self.storage.save_json(self._config_path, config)
        return config

    def _cache_key(self, portfolio_id: str, ticker: str) -> str:
        return f"{self._cache_dir}/{portfolio_id}_{ticker.upper()}.json"

    def _get_cached_analysis(self, portfolio: Portfolio, ticker: str) -> dict | None:
        cached = self.storage.load_json(self._cache_key(portfolio.id, ticker))
        if not cached:
            return None
        try:
            generated_at = datetime.fromisoformat(str(cached.get("generated_at")).replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - generated_at > timedelta(hours=6):
                return None
            if cached.get("portfolio_updated_at") != portfolio.updated_at.isoformat():
                return None
        except Exception:
            return None
        return cached

    def _save_cached_analysis(self, portfolio: Portfolio, ticker: str, payload: dict) -> None:
        payload["portfolio_updated_at"] = portfolio.updated_at.isoformat()
        self.storage.save_json(self._cache_key(portfolio.id, ticker), payload)

    def _resolve_position(self, portfolio: Portfolio, ticker: str) -> Position | None:
        for pos in portfolio.positions:
            if pos.ticker.upper() == ticker.upper():
                return pos
        return None

    def _asset_meta(self, ticker: str) -> dict:
        asset = self.assets.get_by_ticker(ticker)
        if not asset:
            return {
                "ticker": ticker.upper(),
                "name": ticker.upper(),
                "asset_class": "UNKNOWN",
                "country": "",
                "sector": "",
                "sub_type": "",
            }
        return asset.model_dump()

    def _normalize_text(self, text: str) -> str:
        return (text or "").lower()

    def _matches_asset(self, news: NewsItem, meta: dict) -> tuple[bool, float]:
        ticker = meta["ticker"].upper()
        text = self._normalize_text(f"{news.title} {news.summary} {news.content_preview}")
        aliases = [a.lower() for a in self._config.get("aliases", {}).get(ticker, [])]
        weights = self._config["weights"]

        score = 0.0
        if ticker in [a.upper() for a in news.mentioned_assets]:
            score += weights["direct_match"]
        if any(alias in text for alias in aliases):
            score += weights["name_alias"]

        sector = self._normalize_text(meta.get("sector", ""))
        if sector and any(sector in self._normalize_text(s) for s in news.mentioned_sectors):
            score += weights["sector_match"]

        country = self._normalize_text(meta.get("country", ""))
        if country and any(country in self._normalize_text(c) for c in news.mentioned_countries):
            score += weights["country_match"]

        published = news.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (datetime.now(timezone.utc) - published).total_seconds() / 86400)
        recency_score = max(0.0, 1.0 - min(age_days / 30.0, 1.0))
        score += recency_score * weights["recency"]

        return score > 0.15, round(min(score, 1.0), 4)

    def get_related_news(self, ticker: str, limit: int = 5) -> list[dict]:
        meta = self._asset_meta(ticker)
        matches: list[dict] = []
        for news in self.news.get_all_raw():
            matched, match_score = self._matches_asset(news, meta)
            if not matched:
                continue
            matches.append({"match_score": match_score, "news": news})

        def safe_published(item: dict):
            published = item["news"].published_at
            if published.tzinfo is None:
                return published.replace(tzinfo=timezone.utc)
            return published

        matches.sort(
            key=lambda item: (
                item["match_score"],
                item["news"].impact_score,
                item["news"].relevance_score,
                safe_published(item),
            ),
            reverse=True,
        )

        results = []
        for item in matches[:limit]:
            news = item["news"]
            results.append({
                "id": news.id,
                "title": news.title,
                "source_name": news.source_name,
                "source_url": news.source_url,
                "published_at": news.published_at.isoformat(),
                "summary": news.summary,
                "sentiment_score": news.sentiment_score,
                "impact_score": news.impact_score,
                "relevance_score": news.relevance_score,
                "match_score": item["match_score"],
            })
        return results

    def _get_history_dataframe(self, ticker: str) -> pd.DataFrame | None:
        history = self.market.get_history(ticker, period="1y", interval="1d")
        if not history or not history.get("prices"):
            return None
        df = pd.DataFrame(history["prices"])
        if df.empty or "close" not in df.columns:
            return None
        return df

    def _performance_snapshot(self, ticker: str, avg_price: float | None) -> dict:
        current = self.market.get_current_price(ticker)
        df = self._get_history_dataframe(ticker)

        current_price = float(current["price"]) if current and current.get("price") is not None else avg_price
        currency = current.get("currency", "BRL") if current else "BRL"

        def pct_change(window: int) -> float | None:
            if df is None or len(df) <= window:
                return None
            base = float(df["close"].iloc[-window - 1])
            last = float(df["close"].iloc[-1])
            if base == 0:
                return None
            return ((last / base) - 1.0) * 100

        month_1 = pct_change(21)
        month_3 = pct_change(63)
        month_12 = pct_change(252)
        volatility_21d = None
        if df is not None and len(df) > 22:
            returns = df["close"].pct_change().dropna().tail(21)
            if not returns.empty:
                volatility_21d = float(returns.std() * math.sqrt(21) * 100)

        return {
            "current_price": current_price,
            "currency": currency,
            "change_1m_pct": round(month_1, 2) if month_1 is not None else None,
            "change_3m_pct": round(month_3, 2) if month_3 is not None else None,
            "change_12m_pct": round(month_12, 2) if month_12 is not None else None,
            "volatility_21d_pct": round(volatility_21d, 2) if volatility_21d is not None else None,
            "has_history": df is not None and len(df) > 5,
        }

    def _compute_weight_pct(self, portfolio: Portfolio, ticker: str) -> float | None:
        values = []
        target_value = None
        for pos in portfolio.positions:
            current = self.market.get_current_price(pos.ticker)
            price = None
            if current and current.get("price") is not None:
                price = float(current["price"])
            elif pos.avg_price is not None:
                price = float(pos.avg_price)
            if price is None:
                continue
            total_value = price * pos.quantity
            values.append(total_value)
            if pos.ticker.upper() == ticker.upper():
                target_value = total_value
        portfolio_total = sum(values)
        if portfolio_total <= 0 or target_value is None:
            return None
        return round((target_value / portfolio_total) * 100, 2)

    def _scenario_label(self, perf: dict, news_list: list[dict], meta: dict, weight_pct: float | None) -> str:
        sentiment = 0.0
        impact = 0.0
        if news_list:
            sentiment = sum(n["sentiment_score"] for n in news_list) / len(news_list)
            impact = sum(n["impact_score"] for n in news_list) / len(news_list)
        momentum = perf.get("change_3m_pct") or perf.get("change_1m_pct") or 0.0

        if meta.get("asset_class") == "CRYPTO":
            return "volatil" if abs(momentum) > 8 or impact > 0.6 else "cauteloso"
        if weight_pct and weight_pct >= 25:
            return "concentrado"
        if sentiment > 0.2 and momentum > 3:
            return "positivo"
        if sentiment < -0.2 or momentum < -5:
            return "pressionado"
        if abs(momentum) >= 6 or impact > 0.7:
            return "volatil"
        return "neutro"

    def _confidence(self, perf: dict, news_list: list[dict]) -> str:
        has_price = perf.get("current_price") is not None
        has_history = perf.get("has_history")
        if has_price and has_history and len(news_list) >= 2:
            return "alta"
        if has_price and (has_history or news_list):
            return "media"
        return "baixa"

    def _dominant_topics(self, news_list: list[dict]) -> list[str]:
        terms = []
        for item in news_list:
            text = self._normalize_text(item["title"])
            if "juros" in text or "selic" in text or "fed" in text:
                terms.append("juros")
            if "inflacao" in text or "inflação" in text:
                terms.append("inflacao")
            if "dolar" in text or "dólar" in text or "cambio" in text or "câmbio" in text:
                terms.append("cambio")
            if "dividend" in text or "dividendo" in text:
                terms.append("dividendos")
            if "resultado" in text or "lucro" in text or "receita" in text:
                terms.append("resultados")
        return [topic for topic, _ in Counter(terms).most_common(3)]

    def _current_section(self, meta: dict, perf: dict, news_list: list[dict], weight_pct: float | None) -> str:
        class_hint = self._config["class_templates"].get(meta.get("asset_class"), "O ativo deve ser interpretado dentro do seu contexto específico.")
        parts = [class_hint]
        if perf.get("current_price") is not None:
            parts.append(f"Cotacao atual aproximada em {perf['currency']} {perf['current_price']:.2f}.")
        if weight_pct is not None:
            parts.append(f"Hoje representa cerca de {weight_pct:.1f}% da carteira.")
        if news_list:
            avg_impact = sum(n["impact_score"] for n in news_list) / len(news_list)
            avg_sent = sum(n["sentiment_score"] for n in news_list) / len(news_list)
            direction = "positivo" if avg_sent > 0.15 else "negativo" if avg_sent < -0.15 else "misto"
            parts.append(f"As noticias recentes tem vies {direction} e impacto medio de {avg_impact:.2f}.")
        else:
            parts.append("Ha pouca noticia especifica recente, entao a leitura depende mais do comportamento de preco e da classe do ativo.")
        return " ".join(parts)

    def _recent_section(self, perf: dict) -> str:
        snippets = []
        if perf.get("change_1m_pct") is not None:
            snippets.append(f"No ultimo mes, variou {perf['change_1m_pct']:+.1f}%.")
        if perf.get("change_3m_pct") is not None:
            snippets.append(f"Em 3 meses, acumulou {perf['change_3m_pct']:+.1f}%.")
        if perf.get("change_12m_pct") is not None:
            snippets.append(f"Em 12 meses, esta em {perf['change_12m_pct']:+.1f}%.")
        if perf.get("volatility_21d_pct") is not None:
            snippets.append(f"A volatilidade curta esta em torno de {perf['volatility_21d_pct']:.1f}% anualizada.")
        if not snippets:
            return "Ainda nao ha historico suficiente para resumir os ultimos 3 meses com seguranca."
        return " ".join(snippets)

    def _outlook_section(self, scenario: str, news_list: list[dict], meta: dict, confidence: str) -> str:
        topics = self._dominant_topics(news_list)
        topics_text = f" Os temas dominantes hoje sao {', '.join(topics)}." if topics else ""
        scenario_map = {
            "positivo": "A perspectiva de 3 meses e construtiva, com espaco para continuidade se o fluxo e o noticiario permanecerem favoraveis.",
            "pressionado": "A perspectiva de 3 meses pede cautela, porque o ativo segue sensivel a novas revisoes negativas de cenario ou resultados.",
            "volatil": "A perspectiva de 3 meses e de oscilacao elevada, com possibilidade de movimentos rapidos em ambas as direcoes.",
            "concentrado": "A perspectiva de 3 meses precisa ser lida junto com o peso elevado na carteira, porque qualquer oscilacao tera impacto relevante no conjunto.",
            "cauteloso": "A perspectiva de 3 meses e cautelosa, com premio de risco alto e dependencia forte do humor de mercado.",
            "neutro": "A perspectiva de 3 meses e neutra a levemente construtiva, dependendo mais do ambiente macro e do fluxo do que de um gatilho isolado.",
        }
        base = scenario_map.get(scenario, scenario_map["neutro"])
        class_tail = ""
        if meta.get("asset_class") == "FII":
            class_tail = " Para FIIs, juros, qualidade do credito e nivel de distribuicao seguem centrais."
        elif meta.get("asset_class") == "FIXED_INCOME":
            class_tail = " Para renda fixa, a direcao de juros e a duration continuam sendo os vetores principais."
        elif meta.get("asset_class") == "CRYPTO":
            class_tail = " Para cripto, liquidez global e apetite a risco continuam pesando mais do que fundamentos tradicionais."

        confidence_tail = {
            "alta": " A confianca dessa leitura e alta para um horizonte curto.",
            "media": " A confianca dessa leitura e moderada.",
            "baixa": " A confianca dessa leitura e baixa por limitacao de dados.",
        }[confidence]
        return f"{base}{topics_text}{class_tail}{confidence_tail}"

    def generate_asset_analysis(self, portfolio: Portfolio, ticker: str) -> dict:
        cached = self._get_cached_analysis(portfolio, ticker)
        if cached:
            return cached

        position = self._resolve_position(portfolio, ticker)
        if position is None:
            return {
                "portfolio_id": portfolio.id,
                "ticker": ticker.upper(),
                "status": "not_found",
                "analysis_sections": {},
                "sources": [],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        meta = self._asset_meta(ticker)
        related_news = self.get_related_news(ticker, limit=5)
        perf = self._performance_snapshot(ticker, position.avg_price)
        weight_pct = self._compute_weight_pct(portfolio, ticker)
        confidence = self._confidence(perf, related_news)
        scenario = self._scenario_label(perf, related_news, meta, weight_pct)

        payload = {
            "portfolio_id": portfolio.id,
            "ticker": meta["ticker"],
            "asset_name": meta["name"],
            "asset_class": meta["asset_class"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "confidence": confidence,
            "status": "ok" if perf.get("current_price") is not None or related_news else "insufficient_data",
            "current_snapshot": {
                "current_price": perf.get("current_price"),
                "currency": perf.get("currency"),
                "weight_pct": weight_pct,
                "sector": meta.get("sector"),
                "country": meta.get("country"),
            },
            "recent_performance": {
                "change_1m_pct": perf.get("change_1m_pct"),
                "change_3m_pct": perf.get("change_3m_pct"),
                "change_12m_pct": perf.get("change_12m_pct"),
                "volatility_21d_pct": perf.get("volatility_21d_pct"),
            },
            "outlook_3m": {
                "scenario": scenario,
                "dominant_topics": self._dominant_topics(related_news),
            },
            "analysis_sections": {
                "current": self._current_section(meta, perf, related_news, weight_pct),
                "recent": self._recent_section(perf),
                "outlook": self._outlook_section(scenario, related_news, meta, confidence),
            },
            "sources": related_news,
        }
        self._save_cached_analysis(portfolio, ticker, payload)
        return payload
