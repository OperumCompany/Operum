import logging
import math
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import pandas as pd

from app.core.config import AI_ENHANCE_ASSET_ANALYSIS
from app.schemas.news import NewsItem
from app.schemas.portfolio import Portfolio, Position
from app.services.asset_universe_service import AssetUniverseService
from app.services.forecast_service import FORECAST_HORIZONS, ForecastService
from app.services.llm_prompts import ASSET_ANALYSIS_REFINER_PROMPT
from app.services.llm_service import LLMService
from app.services.local_storage_service import LocalStorageService
from app.services.market_data_service import MarketDataService
from app.services.news_ingestion_service import NewsIngestionService

HISTORY_WINDOW_DAYS = {"1w": 5, "1m": 21, "2m": 42, "3m": 63}
OUTLOOK_WINDOW_DAYS = {"1w": 5, "1m": 21, "2m": 42, "3m": 63}
logger = logging.getLogger(__name__)


class AssetAnalysisService:
    def __init__(self):
        self.storage = LocalStorageService()
        self.market = MarketDataService()
        self.news = NewsIngestionService()
        self.assets = AssetUniverseService()
        self.forecast = ForecastService()
        self.llm = LLMService()
        self._config_path = "ai/asset_analysis_config.json"
        self._cache_dir = "ai/asset_analysis_cache"
        self._config = self._load_or_init_config()

    def _load_or_init_config(self) -> dict:
        defaults = {
            "weights": {
                "direct_match": 0.36,
                "name_alias": 0.2,
                "sector_match": 0.1,
                "country_match": 0.08,
                "recency": 0.08,
                "source_confidence": 0.08,
                "macro_context": 0.1,
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
                "PETR4": ["petrobras", "petroleo brasileiro"],
            },
            "source_confidence": {
                "official_notice_feed": 1.0,
                "official_listing": 0.95,
                "rss": 0.72,
                "editorial_listing": 0.75,
                "api_proxy": 0.45,
            },
            "class_templates": {
                "FII": "O ativo e um fundo imobiliario e depende de renda, qualidade do portfolio e sensibilidade a juros.",
                "CRYPTO": "O ativo pertence ao bloco cripto, com potencial de assimetria e volatilidade estruturalmente elevada.",
                "US_STOCK": "O ativo esta exposto ao mercado americano e ao ciclo global de juros, dolar e crescimento.",
                "BR_STOCK": "O ativo esta exposto ao ambiente domestico, incluindo juros, fluxo para a bolsa e atividade economica local.",
                "BDR": "O ativo e um BDR e combina a tese da empresa estrangeira com variacao cambial e fluxo local.",
            },
            "topic_synonyms": {
                "juros": ["juros", "selic", "copom", "fed", "treasury", "rates"],
                "inflacao": ["inflacao", "inflacao", "ipca", "cpi", "inflation"],
                "cambio": ["dolar", "dolar", "cambio", "fx", "real"],
                "commodities": ["petroleo", "brent", "commodity", "commodities", "minerio", "oil"],
                "fiscal/politica": ["fiscal", "governo", "congresso", "tribut", "arcabouco", "eleicao"],
                "geopolitica": ["guerra", "iran", "israel", "russia", "ucrania", "tarifa", "tariffs"],
                "dividendos": ["dividend", "dividendo", "provento", "yield"],
                "resultados": ["resultado", "lucro", "receita", "ebitda", "balanco", "balanco"],
            },
        }
        config = self.storage.load_json(self._config_path)
        if not config:
            self.storage.save_json(self._config_path, defaults)
            return defaults

        merged = defaults.copy()
        for key, value in config.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value
        self.storage.save_json(self._config_path, merged)
        return merged

    def _cache_key(self, portfolio_id: str, ticker: str) -> str:
        return f"{self._cache_dir}/{portfolio_id}_{ticker.upper()}.json"

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
        base = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii")
        return base.lower()

    def _safe_dt(self, dt: datetime) -> datetime:
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    def _source_confidence_weight(self, news: NewsItem) -> float:
        source_type = getattr(news, "source_type", "") or ""
        is_official = bool(getattr(news, "is_official", False))
        source_map = self._config.get("source_confidence", {})
        base = float(source_map.get(source_type, 0.6))
        if is_official:
            return min(1.0, max(base, 0.9))
        return base

    def _macro_context_weight(self, text: str, meta: dict) -> float:
        asset_class = meta.get("asset_class", "")
        country = meta.get("country", "")
        sector = self._normalize_text(meta.get("sector", ""))

        keywords = {
            "BR": ["juros", "selic", "copom", "fiscal", "governo", "congresso", "ibovespa", "real", "dolar", "cambio", "inflacao"],
            "US": ["fed", "treasury", "payroll", "sp500", "s&p", "nasdaq", "wall street", "inflation", "rates", "tariffs"],
            "GLOBAL": ["guerra", "geopolitica", "petroleo", "commodity", "commodities", "china", "opep"],
            "CRYPTO": ["bitcoin", "ethereum", "etf", "stablecoin", "regulacao", "liquidez", "halving"],
        }

        score = 0.0
        if any(term in text for term in keywords["GLOBAL"]):
            score += 0.45
        if country == "BR" and any(term in text for term in keywords["BR"]):
            score += 0.55
        if country == "US" and any(term in text for term in keywords["US"]):
            score += 0.55
        if asset_class == "CRYPTO" and any(term in text for term in keywords["CRYPTO"]):
            score += 0.55
        if "petroleo" in sector and any(term in text for term in ["petroleo", "brent", "opep"]):
            score += 0.3
        if "financeiro" in sector and any(term in text for term in ["banco", "credito", "inadimplencia"]):
            score += 0.2
        return min(1.0, score)

    def _matches_asset(self, news: NewsItem, meta: dict) -> tuple[bool, float, str, float, float]:
        ticker = meta["ticker"].upper()
        text = self._normalize_text(
            f"{news.title} {news.summary} {news.content_preview} {news.full_text_if_available or ''}"
        )
        aliases = [a.lower() for a in self._config.get("aliases", {}).get(ticker, [])]
        weights = self._config["weights"]

        score = 0.0
        has_direct_match = ticker in [a.upper() for a in news.mentioned_assets]
        if has_direct_match:
            score += weights["direct_match"]
        has_alias_match = any(alias in text for alias in aliases)
        if has_alias_match:
            score += weights["name_alias"]

        sector = self._normalize_text(meta.get("sector", ""))
        has_sector_match = sector and any(sector in self._normalize_text(s) for s in news.mentioned_sectors)
        if has_sector_match:
            score += weights["sector_match"]

        country = self._normalize_text(meta.get("country", ""))
        has_country_match = country and any(country in self._normalize_text(c) for c in news.mentioned_countries)
        if has_country_match:
            score += weights["country_match"]

        published = self._safe_dt(news.published_at)
        age_days = max(0.0, (datetime.now(timezone.utc) - published).total_seconds() / 86400)
        recency_score = math.exp(-age_days / 28.0)
        score += recency_score * weights["recency"]
        source_confidence = self._source_confidence_weight(news)
        score += source_confidence * weights["source_confidence"]
        macro_context = self._macro_context_weight(text, meta)
        score += macro_context * weights["macro_context"]

        if has_direct_match or has_alias_match:
            context_role = "asset"
        elif has_sector_match:
            context_role = "sector"
        elif macro_context > 0.2 or has_country_match:
            context_role = "macro"
        else:
            context_role = "asset"

        return score > 0.18, round(min(score, 1.0), 4), context_role, round(source_confidence, 4), round(macro_context, 4)

    def get_related_news(self, ticker: str, limit: int = 25, days_back: int | None = None) -> list[dict]:
        meta = self._asset_meta(ticker)
        now = datetime.now(timezone.utc)
        matches: list[dict] = []
        for news in self.news.get_all_raw():
            matched, match_score, context_role, source_confidence_weight, macro_context_weight = self._matches_asset(news, meta)
            if not matched:
                continue
            published = self._safe_dt(news.published_at)
            if days_back is not None and published < now - timedelta(days=days_back):
                continue
            context_priority = {"asset": 1.0, "sector": 0.72, "macro": 0.58}.get(context_role, 0.5)
            rank_score = (
                match_score * 0.52
                + news.impact_score * 0.15
                + news.relevance_score * 0.1
                + source_confidence_weight * 0.1
                + macro_context_weight * 0.08
                + context_priority * 0.05
            )
            matches.append(
                {
                    "match_score": match_score,
                    "rank_score": round(rank_score, 4),
                    "context_role": context_role,
                    "source_confidence_weight": source_confidence_weight,
                    "macro_context_weight": macro_context_weight,
                    "news": news,
                    "published": published,
                }
            )

        matches.sort(
            key=lambda item: (
                item["rank_score"],
                item["match_score"],
                item["news"].impact_score,
                item["news"].relevance_score,
                item["published"],
            ),
            reverse=True,
        )

        results = []
        seen_event_keys: set[str] = set()
        for item in matches:
            news = item["news"]
            event_key = self._normalize_text(news.title)[:120]
            if event_key in seen_event_keys:
                continue
            seen_event_keys.add(event_key)
            results.append(
                {
                    "id": news.id,
                    "title": news.title,
                    "source_name": news.source_name,
                    "source_url": news.source_url,
                    "published_at": item["published"].isoformat(),
                    "summary": news.summary,
                    "sentiment_score": news.sentiment_score,
                    "impact_score": news.impact_score,
                    "relevance_score": news.relevance_score,
                    "match_score": item["match_score"],
                    "rank_score": item["rank_score"],
                    "source_category": getattr(news, "source_category", None),
                    "is_official": bool(getattr(news, "is_official", False)),
                    "context_role": item["context_role"],
                    "source_confidence_weight": item["source_confidence_weight"],
                }
            )
            if len(results) >= limit:
                break
        return results

    def _get_history_dataframe(self, ticker: str) -> pd.DataFrame | None:
        history = self.market.get_history(ticker, period="1y", interval="1d")
        if not history or not history.get("prices"):
            return None
        df = pd.DataFrame(history["prices"])
        if df.empty or "close" not in df.columns:
            return None
        df["date"] = pd.to_datetime(df["date"])
        return df

    def _benchmark_for_meta(self, meta: dict) -> str:
        if meta.get("asset_class") == "FII":
            return "IFIX"
        if meta.get("asset_class") == "CRYPTO":
            return "BTC"
        if meta.get("country") == "US":
            return "SP500"
        return "IBOV"

    def _performance_snapshot(self, ticker: str, avg_price: float | None, history_window: str) -> dict:
        current = self.market.get_current_price(ticker)
        df = self._get_history_dataframe(ticker)
        meta = self._asset_meta(ticker)

        current_price = float(current["price"]) if current and current.get("price") is not None else avg_price
        currency = current.get("currency", "BRL") if current else "BRL"

        window_days = HISTORY_WINDOW_DAYS.get(history_window, 63)

        def pct_change(window: int) -> float | None:
            if df is None or len(df) <= window:
                return None
            base = float(df["close"].iloc[-window - 1])
            last = float(df["close"].iloc[-1])
            if base == 0:
                return None
            return ((last / base) - 1.0) * 100

        selected_change = pct_change(window_days)
        month_1 = pct_change(21)
        month_2 = pct_change(42)
        month_3 = pct_change(63)
        month_12 = pct_change(252)
        volatility_selected = None
        drawdown_selected = None
        beta_selected = None
        correlation_selected = None

        benchmark_ticker = self._benchmark_for_meta(meta)

        if df is not None and len(df) > 5:
            returns = df["close"].pct_change().dropna().tail(window_days)
            if not returns.empty:
                volatility_selected = float(returns.std() * math.sqrt(252) * 100)

        if df is not None and len(df) > window_days:
            closes = df["close"].astype(float).tail(window_days + 1)
            peak = closes.cummax()
            dd = ((closes / peak) - 1.0) * 100
            if not dd.empty:
                drawdown_selected = float(dd.min())

        if df is not None and len(df) > window_days + 5 and benchmark_ticker != ticker.upper():
            benchmark_history = self.market.get_history(benchmark_ticker, period="1y", interval="1d")
            if benchmark_history and benchmark_history.get("prices"):
                benchmark_df = pd.DataFrame(benchmark_history["prices"])
                if not benchmark_df.empty and "close" in benchmark_df.columns:
                    asset_ret = df["close"].astype(float).pct_change().dropna().tail(window_days).reset_index(drop=True)
                    bench_ret = benchmark_df["close"].astype(float).pct_change().dropna().tail(window_days).reset_index(drop=True)
                    aligned = pd.concat([asset_ret, bench_ret], axis=1).dropna()
                    if len(aligned) >= 10:
                        asset_series = aligned.iloc[:, 0]
                        bench_series = aligned.iloc[:, 1]
                        bench_var = float(bench_series.var())
                        if bench_var > 0:
                            beta_selected = float(asset_series.cov(bench_series) / bench_var)
                        correlation_selected = float(asset_series.corr(bench_series))

        return {
            "current_price": current_price,
            "currency": currency,
            "change_selected_pct": round(selected_change, 2) if selected_change is not None else None,
            "change_1m_pct": round(month_1, 2) if month_1 is not None else None,
            "change_2m_pct": round(month_2, 2) if month_2 is not None else None,
            "change_3m_pct": round(month_3, 2) if month_3 is not None else None,
            "change_12m_pct": round(month_12, 2) if month_12 is not None else None,
            "volatility_selected_pct": round(volatility_selected, 2) if volatility_selected is not None else None,
            "drawdown_selected_pct": round(drawdown_selected, 2) if drawdown_selected is not None else None,
            "beta_selected": round(beta_selected, 2) if beta_selected is not None else None,
            "correlation_selected": round(correlation_selected, 2) if correlation_selected is not None else None,
            "benchmark_ticker": benchmark_ticker,
            "has_history": df is not None and len(df) > 5,
            "has_selected_history": df is not None and len(df) > window_days,
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

    def _scenario_label(self, perf: dict, news_list: list[dict], meta: dict, weight_pct: float | None, forecast_signal: float | None) -> str:
        sentiment = 0.0
        impact = 0.0
        if news_list:
            sentiment = sum(n["sentiment_score"] for n in news_list) / len(news_list)
            impact = sum(n["impact_score"] for n in news_list) / len(news_list)
        momentum = perf.get("change_selected_pct") or perf.get("change_1m_pct") or 0.0
        forecast_signal = forecast_signal or 0.0

        if meta.get("asset_class") == "CRYPTO":
            return "volatil" if abs(momentum) > 8 or impact > 0.6 or abs(forecast_signal) > 0.08 else "cauteloso"
        if weight_pct and weight_pct >= 25:
            return "concentrado"
        if sentiment > 0.2 and momentum > 3 and forecast_signal > 0:
            return "positivo"
        if sentiment < -0.2 or momentum < -5 or forecast_signal < -0.05:
            return "pressionado"
        if abs(momentum) >= 6 or impact > 0.7 or abs(forecast_signal) > 0.07:
            return "volatil"
        return "neutro"

    def _confidence(self, perf: dict, news_list: list[dict], forecast_prediction: dict | None) -> str:
        has_price = perf.get("current_price") is not None
        has_history = perf.get("has_history")
        unique_sources = len({item.get("source_name") for item in news_list})
        official_ratio = (
            sum(1 for item in news_list if item.get("is_official")) / len(news_list)
            if news_list
            else 0.0
        )
        sentiment_values = [item["sentiment_score"] for item in news_list]
        dispersion = 0.0
        if len(sentiment_values) >= 2:
            avg = sum(sentiment_values) / len(sentiment_values)
            dispersion = sum(abs(value - avg) for value in sentiment_values) / len(sentiment_values)
        forecast_conf = float(forecast_prediction.get("confidence", 0.0)) if forecast_prediction else 0.0
        if has_price and has_history and len(news_list) >= 6 and unique_sources >= 3 and forecast_conf >= 0.55 and (official_ratio >= 0.2 or dispersion <= 0.45):
            return "alta"
        if has_price and (has_history or len(news_list) >= 3 or forecast_conf >= 0.4):
            return "media"
        return "baixa"

    def _dominant_topics(self, news_list: list[dict]) -> list[str]:
        topics = []
        synonyms = self._config.get("topic_synonyms", {})
        for item in news_list:
            text = self._normalize_text(f"{item['title']} {item.get('summary', '')}")
            for topic, words in synonyms.items():
                if any(word in text for word in words):
                    topics.append(topic)
        return [topic for topic, _ in Counter(topics).most_common(4)]

    def _classify_news_category(self, item: dict, meta: dict) -> str:
        text = self._normalize_text(f"{item.get('title', '')} {item.get('summary', '')}")
        if any(term in text for term in ["resultado", "lucro", "receita", "ebitda", "balanco", "dividendo", "guidance", "margem", "inadimplencia", "vacancia", "provisao", "provisoes", "credito", "alavancagem", "divida"]):
            return "fundamento"
        if any(term in text for term in ["juros", "selic", "copom", "fed", "inflacao", "ipca", "dolar", "cambio", "fiscal", "governo", "guerra", "geopolitica", "china", "petroleo", "brent", "commodity"]):
            return "macro"
        if item.get("context_role") == "sector" or any(term in text for term in ["tarifaria", "tarifa", "regulacao", "setor", "logistica", "shoppings", "credito imobiliario", "cri", "agronegocio", "bolsa", "ipo"]):
            return "setorial"
        return "fluxo"

    def _categorize_news(self, news_list: list[dict], meta: dict) -> list[dict]:
        categorized = []
        for item in news_list:
            cloned = dict(item)
            cloned["analysis_category"] = self._classify_news_category(item, meta)
            categorized.append(cloned)
        return categorized

    def _infer_asset_function(self, meta: dict, weight_pct: float | None) -> str:
        asset_class = meta.get("asset_class")
        sector = self._normalize_text(meta.get("sector", ""))
        if asset_class == "FII":
            return "renda"
        if asset_class == "CRYPTO":
            return "assimetria/alto_risco"
        if asset_class in {"US_STOCK", "BDR"}:
            return "crescimento"
        if "ouro" in sector or meta.get("ticker") == "GOLD11":
            return "protecao"
        if any(word in sector for word in ["energia", "saneamento", "financeiro", "seguridade"]) or (weight_pct and weight_pct > 12):
            return "estabilidade"
        return "crescimento"

    def _news_adjustment(self, news_list: list[dict], meta: dict, outlook_days: int) -> tuple[float, dict]:
        if not news_list:
            return 0.0, {"fundamento": 0, "macro": 0, "setorial": 0, "fluxo": 0}
        category_weights = {"fundamento": 0.45, "macro": 0.3, "setorial": 0.18, "fluxo": 0.07}
        category_counts = Counter(item.get("analysis_category", "fluxo") for item in news_list)
        weighted_signal = 0.0
        total_weight = 0.0
        for item in news_list:
            category = item.get("analysis_category", "fluxo")
            base_weight = category_weights.get(category, 0.05)
            weighted_signal += float(item.get("sentiment_score", 0.0)) * float(item.get("impact_score", 0.0)) * base_weight
            total_weight += base_weight
        signal = (weighted_signal / total_weight) if total_weight else 0.0
        class_multiplier = 1.0
        if meta.get("asset_class") == "CRYPTO":
            class_multiplier = 1.35
        elif meta.get("asset_class") == "FII":
            class_multiplier = 0.8
        horizon_multiplier = min(1.2, max(0.65, outlook_days / 21.0))
        adjustment = signal * 0.06 * class_multiplier * horizon_multiplier
        return round(adjustment, 6), dict(category_counts)

    def _apply_news_adjustment(self, forecast_bundle: dict | None, adjustment_pct: float) -> dict | None:
        if not forecast_bundle:
            return None
        adjusted = {
            **forecast_bundle,
            "predictions": [],
            "forecast_anchor_points": [],
            "forecast_series": [],
        }
        for prediction in forecast_bundle.get("predictions", []):
            adjusted_return = float(prediction["predicted_return"]) + adjustment_pct
            last_price = float(forecast_bundle["last_price"])
            adjusted_price = round(last_price * (1 + adjusted_return), 2)
            adjusted_prediction = {
                **prediction,
                "predicted_return": round(adjusted_return, 6),
                "predicted_price": adjusted_price,
            }
            adjusted["predictions"].append(adjusted_prediction)
            adjusted["forecast_anchor_points"].append(
                {
                    "date": prediction["horizon_label"],
                    "horizon_days": prediction["horizon_days"],
                    "predicted_price": adjusted_price,
                    "predicted_return": round(adjusted_return, 6),
                    "confidence": prediction["confidence"],
                }
            )
        generated_at = datetime.fromisoformat(forecast_bundle["generated_at"].replace("Z", "+00:00"))
        adjusted["forecast_series"] = self.forecast._interpolate_series(
            float(forecast_bundle["last_price"]),
            generated_at,
            adjusted["predictions"],
        )
        adjusted["news_adjustment_pct"] = round(adjustment_pct * 100, 2)
        return adjusted

    def _history_label(self, history_horizon: str) -> str:
        return {
            "1w": "ultima semana",
            "1m": "ultimo mes",
            "2m": "ultimos 2 meses",
            "3m": "ultimos 3 meses",
        }.get(history_horizon, "ultimos 3 meses")

    def _outlook_label(self, outlook_horizon: str) -> str:
        return {"1w": "1 semana", "1m": "1 mes", "2m": "2 meses", "3m": "3 meses"}.get(outlook_horizon, "3 meses")

    def _current_section(
        self,
        meta: dict,
        perf: dict,
        news_list: list[dict],
        weight_pct: float | None,
        forecast_prediction: dict | None,
        outlook_horizon: str,
        asset_function: str,
        category_counts: dict,
        forecast_adjustment_pct: float | None,
    ) -> str:
        class_hint = self._config["class_templates"].get(meta.get("asset_class"), "O ativo deve ser interpretado dentro do seu contexto especifico.")
        parts = [class_hint]
        parts.append(f"Dentro da carteira, a funcao principal deste ativo hoje e {asset_function.replace('_', ' ')}.")
        if perf.get("current_price") is not None:
            parts.append(f"Cotacao atual aproximada em {perf['currency']} {perf['current_price']:.2f}.")
        if weight_pct is not None:
            parts.append(f"Hoje representa cerca de {weight_pct:.1f}% da carteira.")
        if perf.get("change_1m_pct") is not None:
            parts.append(f"No curto prazo, o momentum de 1 mes esta em {perf['change_1m_pct']:+.1f}%.")
        if forecast_prediction:
            direction = "alta" if forecast_prediction["predicted_return"] > 0.015 else "queda" if forecast_prediction["predicted_return"] < -0.015 else "estabilidade"
            parts.append(
                f"O modelo de {self._outlook_label(outlook_horizon)} hoje aponta {direction}, com retorno estimado de {forecast_prediction['predicted_return'] * 100:+.1f}% e confianca de {forecast_prediction['confidence'] * 100:.0f}%."
            )
        if forecast_adjustment_pct:
            parts.append(f"O ajuste contextual das noticias adiciona {forecast_adjustment_pct:+.1f}% ao cenario-base projetado.")
        if news_list:
            avg_impact = sum(n["impact_score"] for n in news_list) / len(news_list)
            avg_sent = sum(n["sentiment_score"] for n in news_list) / len(news_list)
            direction = "positivo" if avg_sent > 0.15 else "negativo" if avg_sent < -0.15 else "misto"
            parts.append(f"As noticias recentes tem vies {direction} e impacto medio de {avg_impact:.2f}.")
            parts.append(
                f"Nesse conjunto, o peso informacional esta distribuido em fundamento ({category_counts.get('fundamento', 0)}), macro ({category_counts.get('macro', 0)}), setorial ({category_counts.get('setorial', 0)}) e fluxo ({category_counts.get('fluxo', 0)})."
            )
        else:
            parts.append("Ha pouca noticia especifica recente, entao a leitura depende mais do comportamento de preco e da classe do ativo.")
        return " ".join(parts)

    def _recent_section(
        self,
        perf: dict,
        historical_news: list[dict],
        history_horizon: str,
        asset_function: str,
    ) -> str:
        label = self._history_label(history_horizon)
        snippets = []
        if perf.get("change_selected_pct") is not None:
            snippets.append(f"No recorte dos {label}, o ativo variou {perf['change_selected_pct']:+.1f}%.")
        elif perf.get("change_12m_pct") is not None:
            snippets.append(f"Sem serie completa do periodo escolhido, o historico mais longo de 12 meses aponta {perf['change_12m_pct']:+.1f}%.")
        if perf.get("volatility_selected_pct") is not None:
            snippets.append(f"A volatilidade anualizada equivalente ficou perto de {perf['volatility_selected_pct']:.1f}%.")
        if perf.get("drawdown_selected_pct") is not None:
            snippets.append(f"No mesmo intervalo, o drawdown observado foi de {perf['drawdown_selected_pct']:.1f}%.")
        if perf.get("beta_selected") is not None and perf.get("benchmark_ticker"):
            snippets.append(
                f"Contra {perf['benchmark_ticker']}, o beta estimado da janela ficou em {perf['beta_selected']:.2f}, com correlacao de {perf.get('correlation_selected', 0):.2f}."
            )

        if historical_news:
            avg_sent = sum(n["sentiment_score"] for n in historical_news) / len(historical_news)
            avg_impact = sum(n["impact_score"] for n in historical_news) / len(historical_news)
            direction = "mais positivo" if avg_sent > 0.15 else "mais negativo" if avg_sent < -0.15 else "misto"
            topics = self._dominant_topics(historical_news)
            categories = Counter(item.get("analysis_category", "fluxo") for item in historical_news)
            if topics:
                snippets.append(f"No noticiario do periodo, os temas mais recorrentes foram {', '.join(topics)}.")
            snippets.append(
                f"Houve {len(historical_news)} evento(s) relevante(s), com vies {direction} e impacto medio de {avg_impact:.2f}."
            )
            if categories:
                dominant_category = categories.most_common(1)[0][0]
                snippets.append(
                    f"A leitura desse intervalo foi puxada principalmente por noticias de {dominant_category}, o que ajuda a entender como o ativo cumpriu sua funcao de {asset_function.replace('_', ' ')}."
                )
            latest_titles = [n["title"] for n in historical_news[:3]]
            if latest_titles:
                snippets.append(f"Os destaques desse intervalo incluem: {'; '.join(latest_titles)}.")

        if not snippets:
            return f"Sem base robusta de preco e sem noticias historicas suficientes para montar um retrospecto confiavel dos {label}."
        return " ".join(snippets)

    def _outlook_section(
        self,
        scenario: str,
        news_list: list[dict],
        meta: dict,
        confidence: str,
        forecast_prediction: dict | None,
        outlook_horizon: str,
        asset_function: str,
        forecast_adjustment_pct: float | None,
    ) -> str:
        topics = self._dominant_topics(news_list)
        topics_text = f" Os temas dominantes agora sao {', '.join(topics)}." if topics else ""
        horizon_label = self._outlook_label(outlook_horizon)
        forecast_text = ""
        if forecast_prediction:
            forecast_text = (
                f" O modelo para {horizon_label} projeta retorno de {forecast_prediction['predicted_return'] * 100:+.1f}% e preco estimado perto de {forecast_prediction['predicted_price']:.2f}."
            )
        adjustment_text = ""
        if forecast_adjustment_pct:
            adjustment_text = f" O contexto de noticias ajusta essa leitura em {forecast_adjustment_pct:+.1f}%, com maior peso para fatos de fundamento e macro."
        scenario_map = {
            "positivo": f"A perspectiva de {horizon_label} e construtiva, com espaco para continuidade se fluxo e noticiario permanecerem favoraveis.",
            "pressionado": f"A perspectiva de {horizon_label} pede cautela, porque o ativo segue sensivel a novas revisoes negativas de cenario ou resultados.",
            "volatil": f"A perspectiva de {horizon_label} e de oscilacao elevada, com possibilidade de movimentos rapidos em ambas as direcoes.",
            "concentrado": f"A perspectiva de {horizon_label} precisa ser lida junto com o peso elevado na carteira, porque qualquer oscilacao tera impacto relevante no conjunto.",
            "cauteloso": f"A perspectiva de {horizon_label} e cautelosa, com premio de risco alto e dependencia forte do humor de mercado.",
            "neutro": f"A perspectiva de {horizon_label} e neutra a levemente construtiva, dependendo mais do ambiente macro e do fluxo do que de um gatilho isolado.",
        }
        base = scenario_map.get(scenario, scenario_map["neutro"])
        class_tail = ""
        if meta.get("asset_class") == "FII":
            class_tail = " Para FIIs, juros, qualidade do credito e nivel de distribuicao seguem centrais."
        elif meta.get("asset_class") == "CRYPTO":
            class_tail = " Para cripto, liquidez global e apetite a risco continuam pesando mais do que fundamentos tradicionais."
        function_tail = f" Dentro da carteira, a expectativa e avaliar se o ativo continua cumprindo bem a funcao de {asset_function.replace('_', ' ')}."
        confidence_tail = {
            "alta": " A confianca dessa leitura e alta para o horizonte selecionado.",
            "media": " A confianca dessa leitura e moderada.",
            "baixa": " A confianca dessa leitura e baixa por limitacao de dados.",
        }[confidence]
        return f"{base}{forecast_text}{adjustment_text}{topics_text}{class_tail}{function_tail}{confidence_tail}"

    def _build_source_groups(self, sources: list[dict]) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for item in sources:
            grouped[item["source_name"]].append(item)
        groups = []
        for source_name, items in grouped.items():
            groups.append({"source_name": source_name, "count": len(items), "items": items})
        groups.sort(key=lambda group: (group["count"], group["source_name"]), reverse=True)
        return groups

    def _build_historical_series(self, ticker: str, history_horizon: str) -> list[dict]:
        df = self._get_history_dataframe(ticker)
        if df is None or df.empty:
            return []
        window_days = HISTORY_WINDOW_DAYS.get(history_horizon, 63)
        window = df.tail(window_days + 1)
        return [
            {"date": row["date"].date().isoformat(), "value": round(float(row["close"]), 2)}
            for _, row in window.iterrows()
        ]

    def _windowed_news(self, news_items: list[dict], days_back: int) -> list[dict]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(days_back * 2, 30))
        filtered = []
        seen_keys = set()
        for item in news_items:
            published = self._safe_dt(datetime.fromisoformat(item["published_at"].replace("Z", "+00:00")))
            if published < cutoff:
                continue
            event_key = self._normalize_text(item["title"])[:120]
            if event_key in seen_keys:
                continue
            seen_keys.add(event_key)
            filtered.append(item)
        return filtered

    def generate_asset_analysis(
        self,
        portfolio: Portfolio,
        ticker: str,
        history_horizon: str = "3m",
        outlook_horizon: str = "3m",
    ) -> dict:
        position = self._resolve_position(portfolio, ticker)
        if position is None:
            return {
                "portfolio_id": portfolio.id,
                "ticker": ticker.upper(),
                "status": "not_found",
                "analysis_sections": {},
                "sources": [],
                "source_groups": [],
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        history_horizon = history_horizon if history_horizon in HISTORY_WINDOW_DAYS else "3m"
        outlook_horizon = outlook_horizon if outlook_horizon in OUTLOOK_WINDOW_DAYS else "3m"

        meta = self._asset_meta(ticker)
        history_days = HISTORY_WINDOW_DAYS[history_horizon]
        outlook_days = OUTLOOK_WINDOW_DAYS[outlook_horizon]
        all_related_news = self.get_related_news(ticker, limit=25, days_back=120)
        current_news = self._categorize_news(all_related_news[:6], meta)
        historical_news = self._categorize_news(self._windowed_news(all_related_news, history_days)[:12], meta)
        outlook_news = sorted(
            self._categorize_news(self._windowed_news(all_related_news, outlook_days)[:10], meta),
            key=lambda item: (item.get("rank_score", item["match_score"]), item["impact_score"]),
            reverse=True,
        )[:6]

        for item in current_news:
            item["role"] = "current"
        for item in historical_news:
            item["role"] = item.get("role", "historical")
        for item in outlook_news:
            item["role"] = item.get("role", "outlook")

        used_news_map = {}
        for item in current_news + historical_news + outlook_news:
            used_news_map[item["id"]] = item
        used_news = sorted(
            used_news_map.values(),
            key=lambda item: (
                item.get("rank_score", item["match_score"]),
                item["match_score"],
                item["impact_score"],
                item["published_at"],
            ),
            reverse=True,
        )

        perf = self._performance_snapshot(ticker, position.avg_price, history_horizon)
        weight_pct = self._compute_weight_pct(portfolio, ticker)
        asset_function = self._infer_asset_function(meta, weight_pct)

        forecast_bundle = self.forecast.predict_multi(ticker, requested_horizons=sorted(set(OUTLOOK_WINDOW_DAYS.values())))
        news_adjustment_pct, category_counts = self._news_adjustment(outlook_news or used_news, meta, outlook_days)
        adjusted_forecast_bundle = self._apply_news_adjustment(forecast_bundle, news_adjustment_pct)
        forecast_lookup = {
            item["horizon_days"]: item
            for item in (adjusted_forecast_bundle.get("predictions", []) if adjusted_forecast_bundle else [])
        }
        forecast_prediction = forecast_lookup.get(outlook_days)
        scenario = self._scenario_label(
            perf,
            outlook_news or used_news,
            meta,
            weight_pct,
            forecast_prediction.get("predicted_return") if forecast_prediction else None,
        )
        confidence = self._confidence(perf, used_news, forecast_prediction)
        now = datetime.now(timezone.utc)

        recent_by_horizon = {}
        for horizon_key in ["1w", "1m", "2m", "3m"]:
            recent_perf = self._performance_snapshot(ticker, position.avg_price, horizon_key)
            recent_news = self._categorize_news(self._windowed_news(all_related_news, HISTORY_WINDOW_DAYS[horizon_key])[:12], meta)
            recent_by_horizon[horizon_key] = self._recent_section(recent_perf, recent_news, horizon_key, asset_function)

        outlook_by_horizon = {}
        for horizon_key in ["1w", "1m", "2m", "3m"]:
            pred = forecast_lookup.get(OUTLOOK_WINDOW_DAYS[horizon_key])
            scenario_for_horizon = self._scenario_label(
                perf,
                outlook_news or used_news,
                meta,
                weight_pct,
                pred.get("predicted_return") if pred else None,
            )
            horizon_news = self._categorize_news(self._windowed_news(all_related_news, OUTLOOK_WINDOW_DAYS[horizon_key])[:8], meta)
            horizon_adjustment_pct, _ = self._news_adjustment(horizon_news or used_news, meta, OUTLOOK_WINDOW_DAYS[horizon_key])
            outlook_by_horizon[horizon_key] = self._outlook_section(
                scenario_for_horizon,
                horizon_news or used_news,
                meta,
                confidence,
                pred,
                horizon_key,
                asset_function,
                round(horizon_adjustment_pct * 100, 2) if horizon_adjustment_pct else None,
            )

        payload = {
            "portfolio_id": portfolio.id,
            "ticker": meta["ticker"],
            "asset_name": meta["name"],
            "asset_class": meta["asset_class"],
            "generated_at": now.isoformat(),
            "recomputed_at": now.isoformat(),
            "confidence": confidence,
            "status": "ok" if perf.get("current_price") is not None or used_news else "insufficient_data",
            "selected_history_horizon": history_horizon,
            "selected_outlook_horizon": outlook_horizon,
            "asset_function": asset_function,
            "current_snapshot": {
                "current_price": perf.get("current_price"),
                "currency": perf.get("currency"),
                "weight_pct": weight_pct,
                "sector": meta.get("sector"),
                "country": meta.get("country"),
                "asset_function": asset_function,
            },
            "historical_window": {
                "start_date": (now - timedelta(days=history_days * 2)).date().isoformat(),
                "end_date": now.date().isoformat(),
                "news_count": len(historical_news),
                "has_price_history": bool(perf.get("has_selected_history")),
            },
            "historical_series": self._build_historical_series(ticker, history_horizon),
            "forecast_series": adjusted_forecast_bundle.get("forecast_series", []) if adjusted_forecast_bundle else [],
            "forecast_anchor_points": adjusted_forecast_bundle.get("forecast_anchor_points", []) if adjusted_forecast_bundle else [],
            "recent_performance": {
                "change_selected_pct": perf.get("change_selected_pct"),
                "change_1m_pct": perf.get("change_1m_pct"),
                "change_2m_pct": perf.get("change_2m_pct"),
                "change_3m_pct": perf.get("change_3m_pct"),
                "change_12m_pct": perf.get("change_12m_pct"),
                "volatility_selected_pct": perf.get("volatility_selected_pct"),
                "drawdown_selected_pct": perf.get("drawdown_selected_pct"),
                "beta_selected": perf.get("beta_selected"),
                "correlation_selected": perf.get("correlation_selected"),
                "benchmark_ticker": perf.get("benchmark_ticker"),
                "forecast_return_selected_pct": round(forecast_prediction["predicted_return"] * 100, 2) if forecast_prediction else None,
                "forecast_price_selected": forecast_prediction["predicted_price"] if forecast_prediction else None,
                "forecast_confidence_selected": forecast_prediction["confidence"] if forecast_prediction else None,
                "forecast_news_adjustment_pct": round(news_adjustment_pct * 100, 2) if news_adjustment_pct else 0.0,
            },
            "outlook_3m": {
                "scenario": scenario,
                "dominant_topics": self._dominant_topics(outlook_news or used_news),
            },
            "analysis_sections": {
                "current": self._current_section(
                    meta,
                    perf,
                    current_news or used_news,
                    weight_pct,
                    forecast_prediction,
                    outlook_horizon,
                    asset_function,
                    category_counts,
                    round(news_adjustment_pct * 100, 2) if news_adjustment_pct else None,
                ),
                "recent": recent_by_horizon[history_horizon],
                "outlook": outlook_by_horizon[outlook_horizon],
                "recent_by_horizon": recent_by_horizon,
                "outlook_by_horizon": outlook_by_horizon,
            },
            "used_news_count": len(used_news),
            "sources": used_news,
            "source_groups": self._build_source_groups(used_news),
        }
        payload = self._refine_analysis_sections(payload, history_horizon, outlook_horizon)
        self._save_cached_analysis(portfolio, ticker, payload)
        return payload

    def _refine_analysis_sections(self, payload: dict, history_horizon: str, outlook_horizon: str) -> dict:
        if not self.llm.enabled or not AI_ENHANCE_ASSET_ANALYSIS:
            return payload

        refined = self.llm.chat_json(
            ASSET_ANALYSIS_REFINER_PROMPT,
            {
                "current_snapshot": payload.get("current_snapshot"),
                "recent_performance": payload.get("recent_performance"),
                "outlook_3m": payload.get("outlook_3m"),
                "confidence": payload.get("confidence"),
                "used_news_count": payload.get("used_news_count"),
                "source_summary": [
                    {"source_name": group.get("source_name"), "count": group.get("count")}
                    for group in payload.get("source_groups", [])[:6]
                ],
                "analysis_sections": {
                    "current": payload["analysis_sections"].get("current"),
                    "recent_by_horizon": payload["analysis_sections"].get("recent_by_horizon"),
                    "outlook_by_horizon": payload["analysis_sections"].get("outlook_by_horizon"),
                },
            },
            temperature=0.15,
            max_tokens=1200,
        )
        if not refined:
            return payload

        sections = payload.get("analysis_sections", {})
        if isinstance(refined.get("current"), str) and refined["current"].strip():
            sections["current"] = refined["current"].strip()

        if isinstance(refined.get("recent_by_horizon"), dict):
            merged_recent = dict(sections.get("recent_by_horizon", {}))
            for key, value in refined["recent_by_horizon"].items():
                if key in merged_recent and isinstance(value, str) and value.strip():
                    merged_recent[key] = value.strip()
            sections["recent_by_horizon"] = merged_recent
            sections["recent"] = merged_recent.get(history_horizon, sections.get("recent"))

        if isinstance(refined.get("outlook_by_horizon"), dict):
            merged_outlook = dict(sections.get("outlook_by_horizon", {}))
            for key, value in refined["outlook_by_horizon"].items():
                if key in merged_outlook and isinstance(value, str) and value.strip():
                    merged_outlook[key] = value.strip()
            sections["outlook_by_horizon"] = merged_outlook
            sections["outlook"] = merged_outlook.get(outlook_horizon, sections.get("outlook"))

        payload["analysis_sections"] = sections
        return payload
