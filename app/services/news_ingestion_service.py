import re
import uuid
import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional
import yfinance as yf
import feedparser
import requests

from app.services.local_storage_service import LocalStorageService
from app.services.news_scoring_service import NewsScoringService
from app.services.news_summary_service import NewsSummaryService
from app.schemas.news import NewsItem

logger = logging.getLogger(__name__)

# RSS feeds gratuitos de notícias financeiras
RSS_FEEDS = [
    "https://feeds.folha.uol.com.br/mercado/rss.xml",
    "https://www.infomoney.com.br/feed/",
    "https://br.investing.com/rss/news.rss",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
]

# Ticker keywords for mapping news text to assets
TICKER_KEYWORDS: dict[str, list[str]] = {
    "PETR4": ["petrobras", "petrobrás", "petr4"],
    "VALE3": ["vale", "vale3"],
    "ITUB4": ["itaú", "itau", "itub4"],
    "BBDC4": ["bradesco", "bbdc4"],
    "BBAS3": ["banco do brasil", "bbas3"],
    "ABEV3": ["ambev", "abev3"],
    "WEGE3": ["weg", "wege3"],
    "ELET3": ["eletrobras", "eletrobrás", "elet3"],
    "B3SA3": ["b3", "b3sa3"],
    "MGLU3": ["magazine luiza", "mglu3"],
    "JBSS3": ["jbs", "jbss3"],
    "BTC": ["bitcoin", "btc"],
    "ETH": ["ethereum", "eth"],
    "SOL": ["solana"],
}

SECTOR_KEYWORDS: dict[str, list[str]] = {
    "Petróleo e Gás": ["petróleo", "petroleo", "gas", "gás", "petrobras", "pré-sal"],
    "Mineração": ["mineração", "mineracao", "minério", "minerio", "ferro"],
    "Financeiro": ["banco", "bancos", "juros", "selic", "crédito", "credito"],
    "Tecnologia": ["tecnologia", "big tech", "ia", "inteligência artificial"],
    "Criptomoedas": ["bitcoin", "cripto", "blockchain", "ethereum", "criptomoeda"],
    "Energia Elétrica": ["energia", "elétrica", "eletrica", "eletrobras"],
    "Varejo": ["varejo", "magazine luiza", "americanas"],
    "Alimentos": ["alimentos", "jbs", "marfrig", "carne", "frigorífico"],
    "Economia": ["inflação", "inflacao", "pib", "fiscal", "economia", "dólar", "dolar"],
    "Renda Fixa": ["renda fixa", "tesouro", "cdb", "debênture", "debenture"],
}

COUNTRY_KEYWORDS: dict[str, list[str]] = {
    "BR": ["brasil", "brasil", "ibovespa", "real", "b3", "bolsa brasileira"],
    "US": ["eua", "estados unidos", "fed", "s&p", "wall street", "dólar", "dolar"],
}


class NewsIngestionService:
    def __init__(self):
        self.storage = LocalStorageService()
        self.scoring = NewsScoringService()
        self.summarizer = NewsSummaryService()
        self._raw_dir = "news/raw"
        self._processed_dir = "news/processed"

    def _generate_id(self, title: str, source: str) -> str:
        raw = f"{title.strip().lower()}|{source.strip().lower()}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _detect_assets(self, text: str) -> list[str]:
        text_lower = text.lower()
        found = []
        for ticker, keywords in TICKER_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                found.append(ticker)
        return found

    def _detect_sectors(self, text: str) -> list[str]:
        text_lower = text.lower()
        found = []
        for sector, keywords in SECTOR_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                found.append(sector)
        return found

    def _detect_countries(self, text: str) -> list[str]:
        text_lower = text.lower()
        found = []
        for country, keywords in COUNTRY_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                found.append(country)
        return found

    def _strip_html(self, text: str) -> str:
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"&amp;", "&", text)
        text = re.sub(r"&lt;", "<", text)
        text = re.sub(r"&gt;", ">", text)
        text = re.sub(r"&quot;", '"', text)
        text = re.sub(r"&#\d+;", "", text)
        return text.strip()

    def _clean_text(self, text: str) -> str:
        if not text:
            return ""
        try:
            text = text.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        text = self._strip_html(text)
        text = text.replace("\ufffd", "").strip()
        return text

    def _normalize_item(self, item: dict) -> Optional[NewsItem]:
        try:
            title = self._clean_text(item.get("title") or "")
            if not title:
                return None

            raw_summary = self._clean_text(item.get("summary") or item.get("description") or "")
            summary = raw_summary[:500]
            source_name = self._clean_text(item.get("source") or item.get("source_name") or "desconhecida")
            source_url = item.get("link") or item.get("source_url") or ""

            published = item.get("published") or item.get("published_at") or datetime.now(timezone.utc).isoformat()
            if isinstance(published, str):
                try:
                    published_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except ValueError:
                    published_dt = datetime.now(timezone.utc)
            else:
                published_dt = published

            text_for_analysis = f"{title} {summary}"
            mentioned_assets = self._detect_assets(text_for_analysis)
            mentioned_sectors = self._detect_sectors(text_for_analysis)
            mentioned_countries = self._detect_countries(text_for_analysis)

            news_id = self._generate_id(title, source_name)

            return NewsItem(
                id=news_id,
                title=title,
                subtitle=item.get("subtitle"),
                content_preview=summary[:300],
                full_text_if_available=item.get("full_text"),
                source_name=source_name,
                source_url=source_url,
                published_at=published_dt,
                language="pt" if source_name != "YFinance" else "en",
                tags=mentioned_sectors,
                mentioned_assets=mentioned_assets,
                mentioned_countries=mentioned_countries,
                mentioned_sectors=mentioned_sectors,
                sentiment_score=0.0,
                relevance_score=0.0,
                impact_score=0.0,
                summary=summary[:200],
                cluster_id=None,
                created_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.warning(f"Erro ao normalizar notícia: {e}")
            return None

    def _deduplicate(self, items: list[NewsItem]) -> list[NewsItem]:
        seen = set()
        unique = []
        for item in items:
            if item.id not in seen:
                seen.add(item.id)
                unique.append(item)
        return unique

    def fetch_from_yfinance(self) -> list[dict]:
        news_list = []
        tickers = ["PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "ABEV3.SA",
                   "WEGE3.SA", "B3SA3.SA", "MGLU3.SA", "BBAS3.SA", "ELET3.SA",
                   "AAPL34.SA", "^BVSP", "BTC-USD"]
        for ticker in tickers:
            try:
                tk = yf.Ticker(ticker)
                news = tk.news
                if news:
                    for n in news[:5]:
                        news_list.append({
                            "title": n.get("title", ""),
                            "summary": n.get("summary", ""),
                            "link": n.get("link", ""),
                            "source": "YFinance",
                            "published": datetime.fromtimestamp(
                                n.get("providerPublishTime", 0), tz=timezone.utc
                            ).isoformat() if n.get("providerPublishTime") else None,
                        })
            except Exception as e:
                logger.debug(f"YFinance error for {ticker}: {e}")
        return news_list

    def fetch_from_rss(self) -> list[dict]:
        news_list = []
        for feed_url in RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:10]:
                    news_list.append({
                        "title": entry.get("title", ""),
                        "summary": entry.get("summary", ""),
                        "link": entry.get("link", ""),
                        "source": feed.feed.get("title", feed_url),
                        "published": entry.get("published", ""),
                    })
            except Exception as e:
                logger.debug(f"RSS error for {feed_url}: {e}")
        return news_list

    def ingest(self) -> int:
        raw_items = self.fetch_from_yfinance() + self.fetch_from_rss()
        normalized = []
        for item in raw_items:
            news = self._normalize_item(item)
            if news:
                normalized.append(news)

        unique = self._deduplicate(normalized)

        # Score and summarize each news item
        scored = []
        for news in unique:
            scored_news = self.scoring.score_news(news)
            if not scored_news.summary:
                scored_news.summary = self.summarizer.summarize(
                    scored_news.title, scored_news.content_preview, scored_news.mentioned_assets
                )
            scored.append(scored_news)

        # Load existing to merge
        existing = self.storage.load_json(f"{self._raw_dir}/latest.json") or []
        existing_ids = {e.get("id") for e in existing}

        new_count = 0
        for news in scored:
            if news.id not in existing_ids:
                existing_ids.add(news.id)
                existing.append(news.model_dump(mode="json"))
                new_count += 1

        # Keep only latest 500
        existing = existing[-500:]

        self.storage.save_json(f"{self._raw_dir}/latest.json", existing)
        logger.info(f"Ingestão: {new_count} notícias novas de {len(unique)} únicas")
        return new_count

    def get_all_raw(self) -> list[NewsItem]:
        data = self.storage.load_json(f"{self._raw_dir}/latest.json") or []
        return [NewsItem(**item) for item in data]
