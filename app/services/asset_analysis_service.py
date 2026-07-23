import json
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

    def _is_incidental_asset_mention(self, news: NewsItem, meta: dict) -> bool:
        ticker = meta["ticker"].upper()
        mentioned_assets = {asset.upper() for asset in news.mentioned_assets}
        if ticker in mentioned_assets:
            return False

        title = self._normalize_text(news.title)
        text = self._normalize_text(f"{news.title} {news.summary} {news.content_preview}")
        aliases = [self._normalize_text(alias) for alias in self._config.get("aliases", {}).get(ticker, [])]
        aliases = [alias for alias in aliases if len(alias) >= 4]

        analyst_terms = [
            "recomenda",
            "recomendacao",
            "preco alvo",
            "eleva",
            "corta",
            "mantem",
            "reitera",
            "compra",
            "venda",
            "neutro",
            "outperform",
            "underperform",
        ]
        has_alias = any(alias in text for alias in aliases)
        if not has_alias or not any(term in text for term in analyst_terms):
            return False

        analyst_brands = ["bba", "corretora", "research", "analistas"]
        if any(f"{alias} bba" in text for alias in aliases) or any(term in text for term in analyst_brands):
            return True

        if ":" in news.title:
            before_colon = self._normalize_text(news.title.split(":", 1)[0])
            return not any(alias in before_colon for alias in aliases)

        return False

    def get_related_news(self, ticker: str, limit: int = 25, days_back: int | None = None) -> list[dict]:
        meta = self._asset_meta(ticker)
        now = datetime.now(timezone.utc)
        matches: list[dict] = []
        for news in self.news.get_all_raw():
            matched, match_score, context_role, source_confidence_weight, macro_context_weight = self._matches_asset(news, meta)
            if not matched:
                continue
            if context_role == "asset" and self._is_incidental_asset_mention(news, meta):
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
        return df.sort_values("date").reset_index(drop=True)

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

    def _fallback_forecast_bundle(self, ticker: str, perf: dict, requested_horizons: list[int]) -> dict | None:
        current_price = perf.get("current_price")
        if current_price is None:
            return None

        trend_pct = (
            perf.get("change_1m_pct")
            if perf.get("change_1m_pct") is not None
            else perf.get("change_selected_pct")
        )
        trend_pct = float(trend_pct or 0.0)
        generated_at = datetime.now(timezone.utc)
        predictions = []
        for horizon_days in sorted(set(requested_horizons)):
            scale = min(max(horizon_days / 21.0, 0.25), 3.0)
            predicted_return = max(-0.08, min(0.08, (trend_pct / 100.0) * scale * 0.25))
            predicted_price = round(float(current_price) * (1.0 + predicted_return), 2)
            if predicted_return > 0.015:
                direction = "alta"
            elif predicted_return < -0.015:
                direction = "queda"
            else:
                direction = "estabilidade"
            predictions.append(
                {
                    "horizon_days": horizon_days,
                    "horizon_label": f"{horizon_days}d",
                    "predicted_return": round(predicted_return, 6),
                    "predicted_price": predicted_price,
                    "direction": direction,
                    "confidence": 0.25,
                    "model_source": "deterministic_fallback",
                }
            )

        return {
            "ticker": ticker.upper(),
            "last_price": round(float(current_price), 2),
            "generated_at": generated_at.isoformat(),
            "predictions": predictions,
            "forecast_anchor_points": [
                {
                    "date": item["horizon_label"],
                    "horizon_days": item["horizon_days"],
                    "predicted_price": item["predicted_price"],
                    "predicted_return": item["predicted_return"],
                    "confidence": item["confidence"],
                }
                for item in predictions
            ],
            "forecast_series": self.forecast._interpolate_series(float(current_price), generated_at, predictions),
            "forecast_source": "deterministic_fallback",
        }

    def _history_label(self, history_horizon: str) -> str:
        return {
            "1w": "última semana",
            "1m": "último mês",
            "2m": "últimos 2 meses",
            "3m": "últimos 3 meses",
        }.get(history_horizon, "últimos 3 meses")

    def _outlook_label(self, outlook_horizon: str) -> str:
        return {"1w": "1 semana", "1m": "1 mês", "2m": "2 meses", "3m": "3 meses"}.get(outlook_horizon, "3 meses")

    def _plain_pct(self, value: float | None, digits: int = 1) -> str:
        if value is None:
            return "indisponível"
        sign = "+" if value > 0 else ""
        return f"{sign}{value:.{digits}f}%".replace(".", ",")

    def _unsigned_pct(self, value: float | None, digits: int = 1) -> str:
        if value is None:
            return "indisponível"
        return f"{abs(value):.{digits}f}%".replace(".", ",")

    def _plain_number(self, value: float | None, digits: int = 1) -> str:
        if value is None:
            return "indisponível"
        return f"{value:.{digits}f}".replace(".", ",")

    def _price_trend_label(self, perf: dict) -> str:
        change = perf.get("change_selected_pct")
        if change is None:
            return "sem dados suficientes"
        if change <= -3:
            return "de queda"
        if change >= 3:
            return "de alta"
        return "lateral ou indefinida"

    def _oscillation_label(self, perf: dict) -> str:
        volatility = perf.get("volatility_selected_pct")
        drawdown = perf.get("drawdown_selected_pct")
        max_drop = abs(drawdown) if drawdown is not None else None
        if (max_drop is not None and max_drop >= 12) or (volatility is not None and volatility >= 28):
            return "oscilações relevantes"
        if (max_drop is not None and max_drop >= 5) or (volatility is not None and volatility >= 14):
            return "oscilações moderadas"
        if max_drop is not None or volatility is not None:
            return "oscilações contidas"
        return "oscilação ainda difícil de medir"

    def _asset_status_label(self, scenario: str, perf: dict, weight_pct: float | None) -> str:
        change = perf.get("change_selected_pct")
        if scenario in {"pressionado", "cauteloso", "volatil"} or (change is not None and change <= -8):
            return "atenção"
        if weight_pct is not None and weight_pct >= 25:
            return "atenção por concentração"
        if scenario == "positivo":
            return "favorável, com acompanhamento"
        return "equilibrada"

    def _fundamentals_label(self, news_list: list[dict]) -> str:
        if not news_list:
            return "sem notícias suficientes"
        categories = Counter(item.get("analysis_category", "fluxo") for item in news_list)
        avg_sent = sum(item.get("sentiment_score", 0.0) for item in news_list) / len(news_list)
        if categories.get("fundamento", 0) and avg_sent < -0.2:
            return "pressionados pelas notícias recentes"
        if categories.get("fundamento", 0):
            return "com leitura específica a acompanhar"
        return "sem deterioração clara nas notícias avaliadas"

    def _portfolio_risk_label(self, weight_pct: float | None) -> str:
        if weight_pct is None:
            return "não calculado"
        if weight_pct >= 40:
            return "muito alto"
        if weight_pct >= 20:
            return "alto"
        if weight_pct >= 10:
            return "moderado"
        return "baixo"

    def _asset_class_label(self, asset_class: str | None) -> str:
        labels = {
            "BR_STOCK": "Ação brasileira",
            "US_STOCK": "Ação internacional",
            "FII": "Fundo imobiliário",
            "BDR": "BDR",
            "CRYPTO": "Criptoativo",
            "ETF": "Fundo de índice",
            "REIT": "Fundo imobiliário internacional",
        }
        return labels.get(asset_class or "", "Ativo financeiro")

    def _position_size_label(self, weight_pct: float | None) -> str:
        if weight_pct is None:
            return "dados insuficientes"
        if weight_pct >= 50:
            return "altamente concentrada"
        if weight_pct >= 25:
            return "concentrada"
        if weight_pct >= 12:
            return "relevante"
        if weight_pct >= 5:
            return "moderada"
        return "pequena"

    def _news_sentiment_label(self, news_list: list[dict]) -> str:
        if not news_list:
            return "dados insuficientes"
        avg_sent = sum(item.get("sentiment_score", 0.0) for item in news_list) / len(news_list)
        if avg_sent >= 0.35:
            return "positivo"
        if avg_sent >= 0.12:
            return "levemente positivo"
        if avg_sent <= -0.35:
            return "negativo"
        if avg_sent <= -0.12:
            return "levemente negativo"
        return "misto" if len(news_list) >= 2 else "neutro"

    def _data_quality_warnings(self, perf: dict, historical_series: list[dict], used_news: list[dict]) -> list[str]:
        warnings = []
        current_price = perf.get("current_price")
        if current_price is None:
            warnings.append("Preço atual indisponível para esta análise.")
        if not perf.get("has_selected_history"):
            warnings.append("Histórico de preço incompleto para o período selecionado.")
        if not historical_series:
            warnings.append("Série histórica vazia para o período selecionado.")
        if len(used_news) < 3:
            warnings.append("Quantidade baixa de notícias diretamente relacionadas ao ativo.")
        warnings.append("Dados fundamentais estruturados ainda não estão disponíveis no MVP; a leitura de fundamentos usa notícias, classe do ativo e contexto.")
        if current_price is not None and historical_series:
            last_value = historical_series[-1].get("value")
            if last_value:
                divergence = abs(float(current_price) - float(last_value)) / max(abs(float(current_price)), 0.01)
                if divergence > 0.2:
                    warnings.append("Preço atual e último ponto histórico apresentam diferença relevante; confira a data da cotação e a fonte do histórico.")
        return warnings

    def _confidence_with_warnings(self, confidence: str, warnings: list[str]) -> str:
        if not warnings:
            return confidence
        if len(warnings) >= 3 or any("Preço atual indisponível" in item or "Série histórica vazia" in item for item in warnings):
            return "baixa"
        if confidence == "alta":
            return "media"
        return confidence

    def _dominant_reason(self, weight_pct: float | None, perf: dict, news_list: list[dict]) -> str:
        if weight_pct is not None and weight_pct >= 25:
            return f"concentração de {self._unsigned_pct(weight_pct)} da carteira"
        topics = self._dominant_topics(news_list)
        if topics:
            return f"notícias ligadas a {', '.join(topics[:2])}"
        change = perf.get("change_selected_pct")
        if change is not None:
            return f"movimento recente de {self._plain_pct(change)} no preço"
        return "base limitada de dados recentes"

    def _watch_items(self, meta: dict, used_news: list[dict], asset_function: str) -> list[str]:
        items = []
        asset_class = meta.get("asset_class")
        sector = self._normalize_text(meta.get("sector", ""))
        if asset_class == "FII":
            items.extend(["vacância e qualidade dos imóveis", "nível de distribuição", "sensibilidade a juros"])
        elif asset_class == "CRYPTO":
            items.extend(["liquidez global", "apetite a risco", "oscilação do mercado cripto"])
        elif "financeiro" in sector or "banco" in sector:
            items.extend(["lucro e rentabilidade", "inadimplência", "crescimento da carteira de crédito"])
        elif any(word in sector for word in ["petroleo", "mineracao", "commodity"]):
            items.extend(["preço das commodities", "câmbio", "resultados operacionais"])
        else:
            items.extend(["resultados do próximo trimestre", "margens e crescimento", "endividamento"])

        topics = self._dominant_topics(used_news)
        for topic in topics[:3]:
            label = {
                "juros": "trajetória dos juros",
                "inflacao": "comportamento da inflação",
                "cambio": "movimento do câmbio",
                "commodities": "preços de commodities",
                "fiscal/politica": "cenário fiscal e político",
                "geopolitica": "eventos geopoliticos",
                "dividendos": "pagamento de dividendos",
                "resultados": "novos resultados divulgados",
            }.get(topic, topic)
            if label not in items:
                items.append(label)

        function_item = f"se o ativo segue adequado à função de {asset_function.replace('_', ' ')} na carteira"
        if function_item not in items:
            items.append(function_item)
        return items[:7]

    def _theme_text(self, news_list: list[dict]) -> str:
        topics = self._dominant_topics(news_list)
        if topics:
            labels = {
                "juros": "juros",
                "inflacao": "inflação",
                "cambio": "câmbio",
                "commodities": "commodities",
                "fiscal/politica": "cenário fiscal e político",
                "geopolitica": "geopolítica",
                "dividendos": "dividendos",
                "resultados": "resultados",
            }
            return ", ".join(labels.get(topic, topic) for topic in topics[:4])
        return "preço, setor e ambiente econômico"

    def _watch_text_for_meta(self, meta: dict, news_list: list[dict]) -> str:
        sector = self._normalize_text(meta.get("sector", ""))
        if "financeiro" in sector or "banco" in sector:
            return "lucro, rentabilidade, margem financeira, custo de crédito, inadimplência, crescimento da carteira de crédito e trajetória dos juros"
        if meta.get("asset_class") == "FII":
            return "vacância, qualidade dos imóveis, distribuição de rendimentos, custo da dívida e trajetória dos juros"
        if meta.get("asset_class") == "CRYPTO":
            return "liquidez global, apetite a risco, fluxo para criptoativos e comportamento do Bitcoin"
        return self._theme_text(news_list)

    def _box_history_text(
        self,
        ticker: str,
        perf: dict,
        historical_news: list[dict],
        history_horizon: str,
        asset_function: str,
    ) -> str:
        label = self._history_label(history_horizon)
        parts = []
        change = perf.get("change_selected_pct")
        if perf.get("change_selected_pct") is not None:
            if change <= -3:
                movement = "recuou"
                movement_pct = self._unsigned_pct(change)
            elif change >= 3:
                movement = "avançou"
                movement_pct = self._unsigned_pct(change)
            else:
                movement = "ficou praticamente estável"
                movement_pct = self._plain_pct(change)
            parts.append(f"Nos {label}, {ticker} {movement} {movement_pct}.")
        else:
            parts.append(f"Nos {label}, não há série de preço completa para medir com segurança o desempenho de {ticker}.")
        if perf.get("drawdown_selected_pct") is not None:
            parts.append(f"No pior momento da janela, ficou cerca de {self._unsigned_pct(perf['drawdown_selected_pct'])} abaixo do maior preço do período.")
        parts.append(f"O comportamento do preço mostrou {self._oscillation_label(perf)}, então a leitura deve considerar tanto a direção quanto a intensidade do movimento.")
        if historical_news:
            sentiment = self._news_sentiment_label(historical_news)
            parts.append(f"As notícias diretamente relacionadas ao ativo tiveram tom {sentiment}, com temas ligados a {self._theme_text(historical_news)}.")
        else:
            parts.append("O volume de notícias diretamente relacionadas foi baixo, o que reduz a confiança da leitura.")
        benchmark = perf.get("benchmark_ticker") or "índice de comparação"
        parts.append(f"Esse histórico não prova, sozinho, melhora ou piora do negócio. Sem comparação completa com {benchmark}, com pares do setor e com o restante da carteira, não é possível concluir se o ativo cumpriu sua função de {asset_function.replace('_', ' ')}.")
        return " ".join(parts)

    def _box_current_text(
        self,
        ticker: str,
        meta: dict,
        perf: dict,
        current_news: list[dict],
        weight_pct: float | None,
        asset_function: str,
    ) -> str:
        trend = self._price_trend_label(perf)
        sentiment = self._news_sentiment_label(current_news)
        parts = [
            f"Atualmente, a avaliação de {ticker} exige separar a situação da empresa, o comportamento do ativo negociado em bolsa e o impacto da posição na carteira."
        ]
        if current_news:
            parts.append(f"As notícias recentes têm tom {sentiment}, mas não bastam, sozinhas, para afirmar melhora ou deterioração dos fundamentos.")
        else:
            parts.append("No MVP, ainda não há dados fundamentalistas estruturados suficientes para avaliar lucro, margem, endividamento ou qualidade operacional com profundidade.")
        parts.append(f"O preço apresenta tendência recente {trend}, mas isso não deve ser confundido automaticamente com mudança na qualidade da empresa.")
        if weight_pct is not None:
            position_size = self._position_size_label(weight_pct)
            impact_10 = weight_pct * 0.10
            parts.append(f"A posição representa {self._unsigned_pct(weight_pct)} da carteira, caracterizando uma exposição {position_size}.")
            if weight_pct >= 25:
                parts.append(f"Por isso, qualquer oscilação relevante do ativo terá impacto elevado sobre o resultado total. Uma queda de 10% em {ticker} teria impacto aproximado de {self._unsigned_pct(impact_10)} sobre a carteira, considerando os demais ativos estáveis.")
            else:
                parts.append(f"Uma queda de 10% em {ticker} teria impacto aproximado de {self._unsigned_pct(impact_10)} sobre a carteira, considerando os demais ativos estáveis.")
        else:
            parts.append("O peso da posição na carteira não foi calculado, limitando a avaliação do impacto no conjunto.")
        parts.append(f"O ponto de acompanhamento é verificar se os próximos dados confirmam que o ativo continua coerente com a função de {asset_function.replace('_', ' ')}.")
        return " ".join(parts)

    def _box_outlook_text(
        self,
        ticker: str,
        meta: dict,
        scenario: str,
        news_list: list[dict],
        confidence: str,
        outlook_horizon: str,
        weight_pct: float | None,
        asset_function: str,
    ) -> str:
        scenario_label = scenario if scenario != "concentrado" else "cauteloso"
        horizon_label = self._outlook_label(outlook_horizon)
        sector = self._normalize_text(meta.get("sector", ""))
        if "financeiro" in sector or "banco" in sector:
            favorable = "rentabilidade saudável, controle da inadimplência e resultados dentro ou acima das expectativas"
            adverse = "aumento do custo de crédito, piora da inadimplência ou desaceleração da carteira de crédito"
        elif meta.get("asset_class") == "FII":
            favorable = "ocupação saudável, distribuição consistente e juros menos pressionados"
            adverse = "aumento da vacância, queda nas distribuições ou juros elevados por mais tempo"
        elif meta.get("asset_class") == "CRYPTO":
            favorable = "melhora da liquidez global e maior apetite a risco"
            adverse = "queda do apetite a risco, estresse de liquidez ou maior oscilação do mercado cripto"
        else:
            favorable = "resultados consistentes, notícias mais favoráveis e melhora do ambiente de mercado"
            adverse = "resultados abaixo do esperado, piora setorial ou ambiente econômico mais adverso"

        if outlook_horizon == "1w":
            focus_text = (
                "Neste prazo curto, a leitura deve dar mais peso a ruídos de mercado, variação diária do preço, notícias recentes e volatilidade de curto prazo. "
                "O movimento pode mudar rapidamente com fluxo, manchetes e ajustes técnicos, sem necessariamente indicar alteração nos fundamentos."
            )
            watch_text = "preço, volume negociado, notícias recentes, reação do mercado e volatilidade curta"
        elif outlook_horizon == "1m":
            focus_text = (
                "Em 1 mês, o ponto central é observar se o movimento recente ganha continuidade ou perde força. "
                "Próximos eventos, novas notícias e a reação do preço ajudam a indicar se o cenário está se sustentando."
            )
            watch_text = "continuidade do preço, próximos eventos, notícias relevantes, resultados parciais e reação do mercado"
        elif outlook_horizon == "2m":
            focus_text = (
                "Em 2 meses, a análise deve procurar sinais de confirmação ou reversão do cenário atual. "
                "Se os dados e notícias reforçarem a leitura, o cenário ganha consistência; se vierem em direção oposta, a leitura precisa ser revista."
            )
            watch_text = f"confirmação do cenário, sinais de reversão, evolução das notícias e {self._watch_text_for_meta(meta, news_list)}"
        else:
            focus_text = (
                "Em 3 meses, o foco deixa de ser apenas o ruído de curto prazo e passa a incluir fundamentos, resultados, ambiente macroeconômico e risco da posição na carteira. "
                "Esse horizonte é mais útil para avaliar se a tese continua coerente com a função definida para o ativo."
            )
            watch_text = self._watch_text_for_meta(meta, news_list)

        parts = [
            f"O cenário para os próximos {horizon_label} é {scenario_label}."
        ]
        parts.append(focus_text)
        parts.append(f"O ativo pode ser favorecido por {favorable}.")
        parts.append(f"Por outro lado, pode seguir pressionado se houver {adverse}.")
        parts.append(f"Os principais pontos a acompanhar são {watch_text}.")
        if weight_pct is not None and weight_pct >= 10:
            parts.append(f"Como a posição representa {self._unsigned_pct(weight_pct)} da carteira, movimentos fortes do ativo podem pesar no resultado do conjunto.")
        parts.append(f"A confiança dessa leitura é { {'alta': 'alta', 'media': 'moderada', 'baixa': 'baixa'}.get(confidence, confidence) }, pois o comportamento futuro ainda depende de dados e eventos que podem mudar.")
        return " ".join(parts)

    def _build_box_sections(
        self,
        meta: dict,
        perf: dict,
        current_news: list[dict],
        all_related_news: list[dict],
        used_news: list[dict],
        weight_pct: float | None,
        scenario: str,
        confidence: str,
        asset_function: str,
    ) -> dict:
        box_history_by_horizon = {}
        for horizon_key in ["1w", "1m", "2m", "3m"]:
            recent_perf = self._performance_snapshot(meta["ticker"], None, horizon_key)
            recent_news = self._categorize_news(self._windowed_news(all_related_news, HISTORY_WINDOW_DAYS[horizon_key])[:12], meta)
            box_history_by_horizon[horizon_key] = self._box_history_text(meta["ticker"], recent_perf, recent_news, horizon_key, asset_function)
        box_outlook_by_horizon = {}
        for horizon_key in ["1w", "1m", "2m", "3m"]:
            horizon_news = self._categorize_news(self._windowed_news(all_related_news, OUTLOOK_WINDOW_DAYS[horizon_key])[:8], meta)
            box_outlook_by_horizon[horizon_key] = self._box_outlook_text(
                meta["ticker"],
                meta,
                scenario,
                horizon_news or used_news,
                confidence,
                horizon_key,
                weight_pct,
                asset_function,
            )
        return {
            "box_history_by_horizon": box_history_by_horizon,
            "box_current": self._box_current_text(meta["ticker"], meta, perf, current_news or used_news, weight_pct, asset_function),
            "box_outlook_by_horizon": box_outlook_by_horizon,
        }

    def _build_friendly_analysis_sections(
        self,
        meta: dict,
        perf: dict,
        used_news: list[dict],
        weight_pct: float | None,
        scenario: str,
        confidence: str,
        history_horizon: str,
        outlook_horizon: str,
        asset_function: str,
        historical_series: list[dict],
        data_quality_warnings: list[str],
    ) -> dict:
        ticker = meta.get("ticker", "ativo")
        name = meta.get("name") or ticker
        label = self._history_label(history_horizon)
        outlook_label = self._outlook_label(outlook_horizon)
        change = perf.get("change_selected_pct")
        drawdown = perf.get("drawdown_selected_pct")
        trend = self._price_trend_label(perf)
        topics = self._dominant_topics(used_news)
        topic_text = f", especialmente {', '.join(topics[:3])}" if topics else ""
        has_price = perf.get("current_price") is not None
        has_news = bool(used_news)
        category_label = self._asset_class_label(meta.get("asset_class"))
        position_size = self._position_size_label(weight_pct)
        news_sentiment = self._news_sentiment_label(used_news)
        adjusted_confidence = self._confidence_with_warnings(confidence, data_quality_warnings)

        visual_summary = {
            "asset_status": self._asset_status_label(scenario, perf, weight_pct),
            "fundamentals": self._fundamentals_label(used_news),
            "price_trend": trend,
            "news_sentiment": news_sentiment,
            "position_size": position_size,
            "portfolio_risk": self._portfolio_risk_label(weight_pct),
            "main_reason": self._dominant_reason(weight_pct, perf, used_news),
            "confidence": {"alta": "alta", "media": "moderada", "baixa": "baixa"}.get(adjusted_confidence, adjusted_confidence),
        }

        if change is not None:
            summary_intro = f"Nos {label}, {ticker} apresentou variação de {self._plain_pct(change)}."
        else:
            summary_intro = f"Não há base de preço suficiente para medir com segurança o movimento de {ticker} nos {label}."
        if drawdown is not None:
            summary_intro += f" Nesse período, a maior queda em relação ao maior preço observado foi de aproximadamente {self._unsigned_pct(drawdown)}."

        business_read = (
            "As notícias avaliadas não indicam, por si só, uma deterioração clara do negócio ou da tese do ativo."
            if has_news
            else "Há poucas notícias específicas recentes, então esta leitura depende mais de preço, classe do ativo e contexto da carteira."
        )
        concentration_read = ""
        if weight_pct is not None:
            concentration_read = f" O ativo representa {self._unsigned_pct(weight_pct)} da carteira, ponto importante para entender o impacto de qualquer oscilação."
        summary = f"{summary_intro} {business_read}{concentration_read}".strip()

        what_happened = (
            f"O desempenho recente foi {trend}. Parte desse movimento pode estar ligada ao próprio mercado e a fatores externos{topic_text}, não necessariamente apenas a mudanças internas de {name}."
            if has_price or has_news
            else "Não há dados suficientes de preço e notícias para explicar com confiança o que aconteceu recentemente."
        )

        company_situation = (
            f"{name} pertence à categoria {category_label}. Dados fundamentais estruturados, como lucro, margens, endividamento ou indicadores operacionais, ainda não estão disponíveis de forma completa nesta análise. "
            "Por isso, o Operum não conclui que os fundamentos melhoraram ou pioraram apenas com base no movimento do preço ou no tom das notícias."
        )
        if has_news:
            company_situation += f" As notícias avaliadas apresentam tom {news_sentiment}, mas isso deve ser lido como contexto, não como prova isolada de mudança na qualidade do ativo."

        asset_price_situation = (
            f"No mercado, a tendência recente do preço é {trend} no recorte de {label}."
            if has_price or change is not None
            else f"Não há dados suficientes para avaliar a tendência recente do preço no recorte de {label}."
        )
        if drawdown is not None:
            asset_price_situation += f" A maior queda em relação ao maior preço do período foi de aproximadamente {self._unsigned_pct(drawdown)}."
        if perf.get("benchmark_ticker") and perf.get("beta_selected") is not None:
            asset_price_situation += f" A comparação com {perf['benchmark_ticker']} sugere que o ativo teve sensibilidade relevante ao movimento do índice de referência."

        current_situation = f"{company_situation} {asset_price_situation}"
        if adjusted_confidence == "baixa":
            current_situation += " Como a confiança está baixa, a conclusão deve ser lida como indicativa, não definitiva."

        if weight_pct is not None:
            impact_10 = weight_pct * 0.10
            impact_down_10 = -impact_10
            portfolio_impact = (
                f"Como {ticker} representa {self._unsigned_pct(weight_pct)} da carteira, a posição é classificada como {position_size}. Uma queda de 10% no ativo teria impacto aproximado de {self._plain_pct(impact_down_10)} no valor total da carteira, considerando os demais investimentos estáveis. "
                f"Uma alta de 10% teria impacto aproximado de {self._plain_pct(impact_10)}. A concentração aumenta tanto o potencial de ganho quanto o potencial de perda, e sua adequação depende do objetivo, prazo e tolerância a oscilações do usuário."
            )
        else:
            portfolio_impact = "Não foi possível calcular o peso do ativo na carteira. Sem esse dado, a leitura de risco fica incompleta, porque o impacto real depende do tamanho da posição."

        scenarios = {
            "favorable": (
                f"Nos próximos {outlook_label}, o cenário favorável depende de melhora nas notícias relevantes, ambiente de mercado mais construtivo e sinais de que o ativo segue adequado à função de {asset_function.replace('_', ' ')}. "
                "A confirmação viria de desempenho mais consistente do preço, notícias diretamente positivas e menor pressão dos fatores externos monitorados."
            ),
            "base": (
                f"O cenário-base para {outlook_label} é {scenario}. A leitura mais equilibrada é acompanhar se o movimento recente se sustenta ou se perde força, sem tratar a projeção como certeza de preço futuro."
            ),
            "adverse": (
                "O cenário adverso ocorreria com piora do ambiente macroeconômico, notícias negativas diretamente ligadas ao ativo, resultados abaixo do esperado ou aumento da aversão a risco. "
                "Nesse caso, o impacto para a carteira seria maior quanto maior for o peso da posição."
            ),
        }

        what_to_watch = self._watch_items(meta, used_news, asset_function)
        conclusion = (
            f"{ticker} exige acompanhamento porque combina movimento recente {trend} com risco de carteira {visual_summary['portfolio_risk']}. "
            "A leitura é educativa e não deve ser usada como ordem transacional. A decisão depende de objetivo, prazo, tolerância a risco e necessidade de diversificação."
        )

        return {
            "visual_summary": visual_summary,
            "summary": summary,
            "what_happened": what_happened,
            "company_situation": company_situation,
            "asset_price_situation": asset_price_situation,
            "current_situation": current_situation,
            "portfolio_impact": portfolio_impact,
            "scenarios": scenarios,
            "what_to_watch": what_to_watch,
            "conclusion": conclusion,
            "data_quality_warnings": data_quality_warnings,
        }

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
        category_label = self._asset_class_label(meta.get("asset_class")).lower()
        parts = [f"O ativo deve ser interpretado como {category_label}, sem misturar empresa, preço de tela e impacto na carteira."]
        parts.append(f"Dentro da carteira, a função principal definida para este ativo é {asset_function.replace('_', ' ')}.")
        if perf.get("current_price") is not None:
            parts.append(f"A cotação atual aproximada é {perf['currency']} {self._plain_number(perf['current_price'], 2)}.")
        if weight_pct is not None:
            parts.append(f"Hoje representa cerca de {self._unsigned_pct(weight_pct)} da carteira.")
        if perf.get("change_1m_pct") is not None:
            parts.append(f"No último mês, o preço teve variação de {self._plain_pct(perf['change_1m_pct'])}.")
        if forecast_prediction:
            direction = "alta" if forecast_prediction["predicted_return"] > 0.015 else "queda" if forecast_prediction["predicted_return"] < -0.015 else "estabilidade"
            parts.append(
                f"O modelo de {self._outlook_label(outlook_horizon)} aponta {direction}, mas essa projeção deve ser lida como referência estatística, não como certeza."
            )
        if forecast_adjustment_pct:
            parts.append("As notícias recentes alteram a leitura do cenário, mas não substituem dados fundamentalistas estruturados.")
        if news_list:
            avg_sent = sum(n["sentiment_score"] for n in news_list) / len(news_list)
            direction = "positivo" if avg_sent > 0.15 else "negativo" if avg_sent < -0.15 else "misto"
            parts.append(f"As notícias recentes têm tom {direction}, mas não permitem concluir, isoladamente, que os fundamentos melhoraram ou pioraram.")
        else:
            parts.append("Há poucas notícias específicas recentes, então a leitura depende mais do comportamento do preço e da classe do ativo.")
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
            snippets.append(f"No recorte dos {label}, o ativo variou {self._plain_pct(perf['change_selected_pct'])}.")
        elif perf.get("change_12m_pct") is not None:
            snippets.append(f"Sem série completa do período escolhido, o histórico mais longo de 12 meses aponta {self._plain_pct(perf['change_12m_pct'])}.")
        if perf.get("drawdown_selected_pct") is not None:
            snippets.append(f"No mesmo intervalo, a maior queda em relação ao maior preço do período foi de {self._unsigned_pct(perf['drawdown_selected_pct'])}.")
        if perf.get("beta_selected") is not None and perf.get("benchmark_ticker"):
            snippets.append(
                f"A comparação com {perf['benchmark_ticker']} sugere que o ativo acompanhou parte do movimento do índice de referência, mas esse dado não deve ser lido isoladamente."
            )

        if historical_news:
            avg_sent = sum(n["sentiment_score"] for n in historical_news) / len(historical_news)
            direction = "mais positivo" if avg_sent > 0.15 else "mais negativo" if avg_sent < -0.15 else "misto"
            topics = self._dominant_topics(historical_news)
            categories = Counter(item.get("analysis_category", "fluxo") for item in historical_news)
            if topics:
                snippets.append(f"No noticiário do período, os temas mais recorrentes foram {self._theme_text(historical_news)}.")
            snippets.append(
                f"Houve {len(historical_news)} evento(s) relevante(s), com viés {direction}."
            )
            if categories:
                dominant_category = categories.most_common(1)[0][0]
                snippets.append(
                    f"A leitura desse intervalo foi puxada principalmente por notícias de {dominant_category}, o que ajuda a entender o contexto do ativo dentro da função de {asset_function.replace('_', ' ')}."
                )

        if not snippets:
            return f"Sem base robusta de preço e sem notícias históricas suficientes para montar um retrospecto confiável dos {label}."
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
        topics_text = f" Os temas dominantes agora são {self._theme_text(news_list)}." if topics else ""
        horizon_label = self._outlook_label(outlook_horizon)
        forecast_text = ""
        if forecast_prediction:
            forecast_text = (
                f" O modelo para {horizon_label} aponta variação estimada de {self._plain_pct(forecast_prediction['predicted_return'] * 100)}, mas isso deve ser tratado como cenário, não como promessa de preço."
            )
        adjustment_text = ""
        if forecast_adjustment_pct:
            adjustment_text = " O contexto de notícias altera a leitura, mas ainda depende de confirmação por dados e eventos futuros."
        scenario_map = {
            "positivo": f"A perspectiva de {horizon_label} é construtiva, com espaço para continuidade se o fluxo e o noticiário permanecerem favoráveis.",
            "pressionado": f"A perspectiva de {horizon_label} pede cautela, porque o ativo segue sensível a novas revisões negativas de cenário ou resultados.",
            "volatil": f"A perspectiva de {horizon_label} é de oscilação elevada, com possibilidade de movimentos rápidos em ambas as direções.",
            "concentrado": f"A perspectiva de {horizon_label} é cautelosa; o peso elevado deve ser tratado como risco de carteira, não como cenário do ativo.",
            "cauteloso": f"A perspectiva de {horizon_label} é cautelosa, com dependência relevante do humor de mercado e dos próximos dados.",
            "neutro": f"A perspectiva de {horizon_label} é neutra a levemente construtiva, dependendo mais do ambiente macro e do fluxo do que de um gatilho isolado.",
        }
        base = scenario_map.get(scenario, scenario_map["neutro"])
        class_tail = ""
        if meta.get("asset_class") == "FII":
            class_tail = " Para FIIs, juros, qualidade do crédito e nível de distribuição seguem centrais."
        elif meta.get("asset_class") == "CRYPTO":
            class_tail = " Para cripto, liquidez global e apetite a risco continuam pesando mais do que fundamentos tradicionais."
        function_tail = f" Dentro da carteira, o acompanhamento deve verificar se o ativo segue adequado à função de {asset_function.replace('_', ' ')}."
        confidence_tail = {
            "alta": " A confiança dessa leitura é alta para o horizonte selecionado.",
            "media": " A confiança dessa leitura é moderada.",
            "baixa": " A confiança dessa leitura é baixa por limitação de dados.",
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
        window = df.sort_values("date").tail(window_days + 1)
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

        requested_forecast_horizons = sorted(set(OUTLOOK_WINDOW_DAYS.values()))
        forecast_bundle = self.forecast.predict_multi(ticker, requested_horizons=requested_forecast_horizons)
        if forecast_bundle is None:
            forecast_bundle = self._fallback_forecast_bundle(ticker, perf, requested_forecast_horizons)
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
        historical_series = self._build_historical_series(ticker, history_horizon)
        data_quality_warnings = self._data_quality_warnings(perf, historical_series, used_news)
        response_confidence = self._confidence_with_warnings(confidence, data_quality_warnings)

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

        friendly_sections = self._build_friendly_analysis_sections(
            meta,
            perf,
            used_news,
            weight_pct,
            scenario,
            confidence,
            history_horizon,
            outlook_horizon,
            asset_function,
            historical_series,
            data_quality_warnings,
        )
        box_sections = self._build_box_sections(
            meta,
            perf,
            current_news or used_news,
            all_related_news,
            used_news,
            weight_pct,
            scenario,
            response_confidence,
            asset_function,
        )

        payload = {
            "portfolio_id": portfolio.id,
            "ticker": meta["ticker"],
            "asset_name": meta["name"],
            "asset_class": meta["asset_class"],
            "generated_at": now.isoformat(),
            "recomputed_at": now.isoformat(),
            "confidence": response_confidence,
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
            "historical_series": historical_series,
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
                **friendly_sections,
                **box_sections,
            },
            "used_news_count": len(used_news),
            "sources": used_news,
            "source_groups": self._build_source_groups(used_news),
        }
        payload = self._refine_analysis_sections(payload, history_horizon, outlook_horizon)
        self._save_cached_analysis(portfolio, ticker, payload)
        return payload

    def _contains_transactional_recommendation(self, value) -> bool:
        text = json.dumps(value, ensure_ascii=False).lower() if not isinstance(value, str) else value.lower()
        blocked = [
            "recomendo comprar",
            "recomenda comprar",
            "deve comprar",
            "hora de comprar",
            "recomendo vender",
            "recomenda vender",
            "deve vender",
            "hora de vender",
            "deve manter",
            "recomendo manter",
            "mantenha",
            "manter a posicao",
            "manter a posição",
            "rebalancear para",
            "aumentar posicao",
            "aumentar posição",
            "reduzir posicao",
            "reduzir posição",
        ]
        return any(term in text for term in blocked)

    def _valid_refined_box_sections(self, refined: dict) -> bool:
        required = ["historico", "situacaoAtual", "perspectiva"]
        if self._contains_transactional_recommendation(refined):
            return False
        for key in required:
            value = refined.get(key)
            if not isinstance(value, str) or not value.strip():
                return False
            lowered = value.lower()
            if any(term in lowered for term in ["drawdown", "momentum", "impacto medio", "impacto médio", "peso informacional", "ajuste contextual", "beta estimado"]):
                return False
            if any(term in lowered for term in ["recuou +", "caiu +", "queda de +", "abaixo do maior preço"]):
                if "+" in lowered:
                    return False
            if "+%" in lowered or "+0," in lowered and "carteira" in lowered:
                return False
            if "+" in lowered and "% da carteira" in lowered:
                return False
            if any(marker in value for marker in ["\n-", "##", "**"]):
                return False
        return True

    def _valid_refined_friendly_sections(self, refined: dict) -> bool:
        required_text = ["summary", "what_happened", "company_situation", "asset_price_situation", "current_situation", "portfolio_impact", "conclusion"]
        required_visual = ["asset_status", "fundamentals", "price_trend", "news_sentiment", "position_size", "portfolio_risk", "main_reason", "confidence"]
        required_scenarios = ["favorable", "base", "adverse"]
        if self._contains_transactional_recommendation(refined):
            return False
        if not isinstance(refined.get("visual_summary"), dict):
            return False
        if any(not isinstance(refined["visual_summary"].get(key), str) or not refined["visual_summary"][key].strip() for key in required_visual):
            return False
        if not isinstance(refined.get("scenarios"), dict):
            return False
        if any(not isinstance(refined["scenarios"].get(key), str) or not refined["scenarios"][key].strip() for key in required_scenarios):
            return False
        if any(not isinstance(refined.get(key), str) or not refined[key].strip() for key in required_text):
            return False
        if not isinstance(refined.get("what_to_watch"), list):
            return False
        if not all(isinstance(item, str) and item.strip() for item in refined["what_to_watch"]):
            return False
        if not isinstance(refined.get("data_quality_warnings"), list):
            return False
        return all(isinstance(item, str) and item.strip() for item in refined["data_quality_warnings"])

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
                    "historico": payload["analysis_sections"].get("box_history_by_horizon", {}).get(history_horizon),
                    "situacaoAtual": payload["analysis_sections"].get("box_current"),
                    "perspectiva": payload["analysis_sections"].get("box_outlook_by_horizon", {}).get(outlook_horizon),
                },
            },
            temperature=0.15,
            max_tokens=900,
        )
        if not refined:
            return payload
        if self._contains_transactional_recommendation(refined):
            return payload

        sections = payload.get("analysis_sections", {})
        if self._valid_refined_box_sections(refined):
            merged_history = dict(sections.get("box_history_by_horizon", {}))
            merged_outlook = dict(sections.get("box_outlook_by_horizon", {}))
            merged_history[history_horizon] = refined["historico"].strip()
            merged_outlook[outlook_horizon] = refined["perspectiva"].strip()
            sections["box_history_by_horizon"] = merged_history
            sections["box_current"] = refined["situacaoAtual"].strip()
            sections["box_outlook_by_horizon"] = merged_outlook
            payload["analysis_sections"] = sections
            return payload

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

        if self._valid_refined_friendly_sections(refined):
            sections["visual_summary"] = {
                key: refined["visual_summary"][key].strip()
                for key in ["asset_status", "fundamentals", "price_trend", "news_sentiment", "position_size", "portfolio_risk", "main_reason", "confidence"]
            }
            for key in ["summary", "what_happened", "company_situation", "asset_price_situation", "current_situation", "portfolio_impact", "conclusion"]:
                sections[key] = refined[key].strip()
            sections["scenarios"] = {
                key: refined["scenarios"][key].strip()
                for key in ["favorable", "base", "adverse"]
            }
            sections["what_to_watch"] = [item.strip() for item in refined["what_to_watch"] if item.strip()]
            sections["data_quality_warnings"] = [item.strip() for item in refined["data_quality_warnings"] if item.strip()]

        payload["analysis_sections"] = sections
        return payload
