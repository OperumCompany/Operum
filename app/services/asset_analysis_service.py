import math
import unicodedata
from collections import Counter, defaultdict
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
            },
            "source_confidence": {
                "official_notice_feed": 1.0,
                "official_listing": 0.95,
                "rss": 0.72,
                "editorial_listing": 0.75,
                "api_proxy": 0.45,
            },
            "class_templates": {
                "FII": "O ativo é um fundo imobiliário e depende de renda, qualidade do portfólio e sensibilidade a juros.",
                "CRYPTO": "O ativo pertence ao bloco cripto, com potencial de assimetria e volatilidade estruturalmente elevada.",
                "FIXED_INCOME": "O ativo pertence à renda fixa, com comportamento mais ligado a juros, duration e previsibilidade do fluxo.",
                "US_STOCK": "O ativo está exposto ao mercado americano e ao ciclo global de juros, dólar e crescimento.",
                "BR_STOCK": "O ativo está exposto ao ambiente doméstico, incluindo juros, fluxo para a bolsa e atividade econômica local.",
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
            "BR": ["juros", "selic", "copom", "fiscal", "governo", "congresso", "ibovespa", "real", "dolar", "dólar", "inflacao", "inflação"],
            "US": ["fed", "treasury", "payroll", "sp500", "s&p", "nasdaq", "wall street", "inflation", "rates", "tariffs"],
            "GLOBAL": ["guerra", "geopolitica", "geopolítica", "petroleo", "petróleo", "commodity", "commodities", "china", "opep"],
            "CRYPTO": ["bitcoin", "ethereum", "etf", "stablecoin", "regulacao", "regulação", "liquidez", "halving"],
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
        if "petroleo" in sector or "petróleo" in sector:
            if "petroleo" in text or "petróleo" in text or "brent" in text:
                score += 0.25
        if "financeiro" in sector and any(term in text for term in ["banco", "credito", "crédito", "inadimplencia", "inadimplência"]):
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
        recency_score = math.exp(-age_days / 30.0)
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

    def get_related_news(self, ticker: str, limit: int = 20, days_back: int | None = None) -> list[dict]:
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
                match_score * 0.55
                + news.impact_score * 0.15
                + news.relevance_score * 0.1
                + source_confidence_weight * 0.1
                + macro_context_weight * 0.05
                + context_priority * 0.05
            )
            matches.append({
                "match_score": match_score,
                "rank_score": round(rank_score, 4),
                "context_role": context_role,
                "source_confidence_weight": source_confidence_weight,
                "macro_context_weight": macro_context_weight,
                "news": news,
                "published": published,
            })

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
        for item in matches[:limit]:
            news = item["news"]
            event_key = self._normalize_text(news.title)[:120]
            if event_key in seen_event_keys:
                continue
            seen_event_keys.add(event_key)
            results.append({
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
        meta = self._asset_meta(ticker)

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
        drawdown_90d = None
        beta_63d = None
        correlation_63d = None
        if df is not None and len(df) > 22:
            returns = df["close"].pct_change().dropna().tail(21)
            if not returns.empty:
                volatility_21d = float(returns.std() * math.sqrt(21) * 100)
        if df is not None and len(df) > 30:
            closes = df["close"].astype(float)
            rolling = closes.tail(90)
            peak = rolling.cummax()
            dd = ((rolling / peak) - 1.0) * 100
            if not dd.empty:
                drawdown_90d = float(dd.min())
        benchmark_ticker = "IBOV"
        if meta.get("asset_class") == "FII":
            benchmark_ticker = "IFIX"
        elif meta.get("asset_class") == "CRYPTO":
            benchmark_ticker = "BTC"
        elif meta.get("country") == "US":
            benchmark_ticker = "SP500"
        if df is not None and len(df) > 64 and benchmark_ticker != ticker.upper():
            benchmark_history = self.market.get_history(benchmark_ticker, period="1y", interval="1d")
            if benchmark_history and benchmark_history.get("prices"):
                benchmark_df = pd.DataFrame(benchmark_history["prices"])
                if not benchmark_df.empty and "close" in benchmark_df.columns:
                    asset_ret = df["close"].astype(float).pct_change().dropna().tail(63).reset_index(drop=True)
                    bench_ret = benchmark_df["close"].astype(float).pct_change().dropna().tail(63).reset_index(drop=True)
                    aligned = pd.concat([asset_ret, bench_ret], axis=1).dropna()
                    if len(aligned) >= 20:
                        asset_series = aligned.iloc[:, 0]
                        bench_series = aligned.iloc[:, 1]
                        bench_var = float(bench_series.var())
                        if bench_var > 0:
                            beta_63d = float(asset_series.cov(bench_series) / bench_var)
                        correlation_63d = float(asset_series.corr(bench_series))

        return {
            "current_price": current_price,
            "currency": currency,
            "change_1m_pct": round(month_1, 2) if month_1 is not None else None,
            "change_3m_pct": round(month_3, 2) if month_3 is not None else None,
            "change_12m_pct": round(month_12, 2) if month_12 is not None else None,
            "volatility_21d_pct": round(volatility_21d, 2) if volatility_21d is not None else None,
            "drawdown_90d_pct": round(drawdown_90d, 2) if drawdown_90d is not None else None,
            "beta_63d": round(beta_63d, 2) if beta_63d is not None else None,
            "correlation_63d": round(correlation_63d, 2) if correlation_63d is not None else None,
            "benchmark_ticker": benchmark_ticker,
            "has_history": df is not None and len(df) > 5,
            "has_3m_history": df is not None and len(df) > 63,
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
        unique_sources = len({item.get("source_name") for item in news_list})
        official_ratio = (
            sum(1 for item in news_list if item.get("is_official")) / len(news_list)
            if news_list else 0.0
        )
        sentiment_values = [item["sentiment_score"] for item in news_list]
        dispersion = 0.0
        if len(sentiment_values) >= 2:
            avg = sum(sentiment_values) / len(sentiment_values)
            dispersion = sum(abs(value - avg) for value in sentiment_values) / len(sentiment_values)
        if has_price and has_history and len(news_list) >= 5 and unique_sources >= 3 and (official_ratio >= 0.2 or dispersion <= 0.45):
            return "alta"
        if has_price and (has_history or len(news_list) >= 2):
            return "media"
        return "baixa"

    def _dominant_topics(self, news_list: list[dict]) -> list[str]:
        terms = []
        for item in news_list:
            text = self._normalize_text(f"{item['title']} {item.get('summary', '')}")
            if "juros" in text or "selic" in text or "fed" in text:
                terms.append("juros")
            if "inflacao" in text or "inflação" in text:
                terms.append("inflacao")
            if "dolar" in text or "dólar" in text or "cambio" in text or "câmbio" in text:
                terms.append("cambio")
            if "petroleo" in text or "petróleo" in text or "brent" in text or "commodity" in text:
                terms.append("commodities")
            if "fiscal" in text or "governo" in text or "congresso" in text or "tribut" in text:
                terms.append("fiscal/politica")
            if "guerra" in text or "iran" in text or "israel" in text or "geopolit" in text:
                terms.append("geopolitica")
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

    def _recent_section(self, perf: dict, historical_news: list[dict]) -> str:
        snippets = []
        if perf.get("change_1m_pct") is not None:
            snippets.append(f"No ultimo mes, variou {perf['change_1m_pct']:+.1f}%.")
        if perf.get("change_3m_pct") is not None:
            snippets.append(f"Em 3 meses, acumulou {perf['change_3m_pct']:+.1f}%.")
        elif perf.get("change_12m_pct") is not None:
            snippets.append(f"Sem serie completa de 3 meses, o historico de 12 meses indica {perf['change_12m_pct']:+.1f}%.")
        if perf.get("volatility_21d_pct") is not None:
            snippets.append(f"A volatilidade curta esta em torno de {perf['volatility_21d_pct']:.1f}% anualizada.")
        if perf.get("drawdown_90d_pct") is not None:
            snippets.append(f"O drawdown recente de 90 dias ficou perto de {perf['drawdown_90d_pct']:.1f}%.")
        if perf.get("beta_63d") is not None and perf.get("benchmark_ticker"):
            snippets.append(f"Contra {perf['benchmark_ticker']}, o beta de curto prazo esta em torno de {perf['beta_63d']:.2f}.")

        if historical_news:
            avg_sent = sum(n["sentiment_score"] for n in historical_news) / len(historical_news)
            avg_impact = sum(n["impact_score"] for n in historical_news) / len(historical_news)
            direction = "mais positivo" if avg_sent > 0.15 else "mais negativo" if avg_sent < -0.15 else "misto"
            topics = self._dominant_topics(historical_news)
            topic_text = f" Os temas que mais apareceram foram {', '.join(topics)}." if topics else ""
            snippets.append(
                f"No retrospecto de noticias do periodo, houve {len(historical_news)} evento(s) relevante(s), com vies {direction} e impacto medio de {avg_impact:.2f}.{topic_text}"
            )
            latest_titles = [n["title"] for n in historical_news[:2]]
            if latest_titles:
                snippets.append(f"Os destaques recentes nesse intervalo incluem: {'; '.join(latest_titles)}.")

        if not snippets:
            return "Sem base robusta de preco e sem noticias historicas suficientes para montar um retrospecto confiavel dos ultimos 3 meses."
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

    def _build_source_groups(self, sources: list[dict]) -> list[dict]:
        grouped: dict[str, list[dict]] = defaultdict(list)
        for item in sources:
            grouped[item["source_name"]].append(item)
        groups = []
        for source_name, items in grouped.items():
            groups.append({
                "source_name": source_name,
                "count": len(items),
                "items": items,
            })
        groups.sort(key=lambda group: (group["count"], group["source_name"]), reverse=True)
        return groups

    def generate_asset_analysis(self, portfolio: Portfolio, ticker: str) -> dict:
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

        meta = self._asset_meta(ticker)
        all_related_news = self.get_related_news(ticker, limit=25, days_back=120)
        current_news = all_related_news[:6]
        historical_news = [item for item in all_related_news if self._safe_dt(datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))) >= datetime.now(timezone.utc) - timedelta(days=90)][:12]
        outlook_news = sorted(all_related_news[:10], key=lambda item: (item.get("rank_score", item["match_score"]), item["impact_score"]), reverse=True)[:6]

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

        perf = self._performance_snapshot(ticker, position.avg_price)
        weight_pct = self._compute_weight_pct(portfolio, ticker)
        confidence = self._confidence(perf, used_news)
        scenario = self._scenario_label(perf, outlook_news or used_news, meta, weight_pct)
        now = datetime.now(timezone.utc)

        payload = {
            "portfolio_id": portfolio.id,
            "ticker": meta["ticker"],
            "asset_name": meta["name"],
            "asset_class": meta["asset_class"],
            "generated_at": now.isoformat(),
            "recomputed_at": now.isoformat(),
            "confidence": confidence,
            "status": "ok" if perf.get("current_price") is not None or used_news else "insufficient_data",
            "current_snapshot": {
                "current_price": perf.get("current_price"),
                "currency": perf.get("currency"),
                "weight_pct": weight_pct,
                "sector": meta.get("sector"),
                "country": meta.get("country"),
            },
            "historical_window": {
                "start_date": (now - timedelta(days=90)).date().isoformat(),
                "end_date": now.date().isoformat(),
                "news_count": len(historical_news),
                "has_price_history": bool(perf.get("has_3m_history")),
            },
            "recent_performance": {
                "change_1m_pct": perf.get("change_1m_pct"),
                "change_3m_pct": perf.get("change_3m_pct"),
                "change_12m_pct": perf.get("change_12m_pct"),
                "volatility_21d_pct": perf.get("volatility_21d_pct"),
                "drawdown_90d_pct": perf.get("drawdown_90d_pct"),
                "beta_63d": perf.get("beta_63d"),
                "correlation_63d": perf.get("correlation_63d"),
                "benchmark_ticker": perf.get("benchmark_ticker"),
            },
            "outlook_3m": {
                "scenario": scenario,
                "dominant_topics": self._dominant_topics(outlook_news or used_news),
            },
            "analysis_sections": {
                "current": self._current_section(meta, perf, current_news or used_news, weight_pct),
                "recent": self._recent_section(perf, historical_news or used_news),
                "outlook": self._outlook_section(scenario, outlook_news or used_news, meta, confidence),
            },
            "used_news_count": len(used_news),
            "sources": used_news,
            "source_groups": self._build_source_groups(used_news),
        }
        self._save_cached_analysis(portfolio, ticker, payload)
        return payload
