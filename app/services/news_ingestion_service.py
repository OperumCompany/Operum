import hashlib
import logging
import re
from datetime import date, datetime, timezone
from typing import Optional
from urllib.parse import quote

import feedparser
import requests
import yfinance as yf

from app.schemas.news import NewsItem
from app.services.local_storage_service import LocalStorageService
from app.services.news_scoring_service import NewsScoringService
from app.services.news_summary_service import NewsSummaryService

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "https://feeds.folha.uol.com.br/mercado/rss.xml",
    "https://www.infomoney.com.br/feed/",
    "https://br.investing.com/rss/news.rss",
    "https://feeds.bbci.co.uk/news/business/rss.xml",
]

TICKER_KEYWORDS: dict[str, list[str]] = {
    "PETR4": ["petrobras", "petrobrás", "petr4"],
    "VALE3": ["vale", "vale3"],
    "ITUB4": ["itaú", "itau", "itub4"],
    "BBDC4": ["bradesco", "bbdc4"],
    "BBAS3": ["banco do brasil", "bbas3"],
    "ABEV3": ["ambev", "abev3"],
    "WEGE3": ["weg", "wege3"],
    "ELET3": ["eletrobras", "elet3"],
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
    "BR": ["brasil", "ibovespa", "real", "b3", "bolsa brasileira"],
    "US": ["eua", "estados unidos", "fed", "s&p", "wall street", "dólar", "dolar"],
}


class NewsIngestionService:
    def __init__(self):
        self.storage = LocalStorageService()
        self.scoring = NewsScoringService()
        self.summarizer = NewsSummaryService()
        self._raw_dir = "news/raw"
        self._latest_path = f"{self._raw_dir}/latest.json"
        self._archive_path = f"{self._raw_dir}/archive.json"
        self._meta_path = f"{self._raw_dir}/meta.json"

    def _generate_id(self, title: str, source: str) -> str:
        raw = f"{title.strip().lower()}|{source.strip().lower()}"
        return hashlib.md5(raw.encode()).hexdigest()

    def _detect_assets(self, text: str) -> list[str]:
        text_lower = text.lower()
        found = []
        for ticker, keywords in TICKER_KEYWORDS.items():
            if any(keyword in text_lower for keyword in keywords):
                found.append(ticker)
        return found

    def _detect_sectors(self, text: str) -> list[str]:
        text_lower = text.lower()
        found = []
        for sector, keywords in SECTOR_KEYWORDS.items():
            if any(keyword in text_lower for keyword in keywords):
                found.append(sector)
        return found

    def _detect_countries(self, text: str) -> list[str]:
        text_lower = text.lower()
        found = []
        for country, keywords in COUNTRY_KEYWORDS.items():
            if any(keyword in text_lower for keyword in keywords):
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
        text = re.sub(r"The post .*? appeared first on .*?\.?", "", text, flags=re.IGNORECASE)
        return text.strip()

    def _parse_published(self, published: str | datetime | None) -> datetime:
        if isinstance(published, datetime):
            return published if published.tzinfo else published.replace(tzinfo=timezone.utc)
        if isinstance(published, str) and published:
            try:
                dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        return datetime.now(timezone.utc)

    def _normalize_item(self, item: dict) -> Optional[NewsItem]:
        try:
            title = self._clean_text(item.get("title") or "")
            if not title:
                return None

            raw_preview = self._clean_text(item.get("summary") or item.get("description") or "")
            full_text = self._clean_text(item.get("full_text") or "")
            source_name = self._clean_text(item.get("source") or item.get("source_name") or "desconhecida")
            source_url = item.get("link") or item.get("source_url") or ""
            published_dt = self._parse_published(item.get("published") or item.get("published_at"))

            text_for_analysis = f"{title} {raw_preview} {full_text}"
            mentioned_assets = self._detect_assets(text_for_analysis)
            mentioned_sectors = self._detect_sectors(text_for_analysis)
            mentioned_countries = self._detect_countries(text_for_analysis)
            news_id = self._generate_id(title, source_name)

            summary = self.summarizer.summarize(
                title,
                raw_preview,
                mentioned_assets,
                mentioned_sectors=mentioned_sectors,
                full_text=full_text,
            )

            return NewsItem(
                id=news_id,
                title=title,
                subtitle=self._clean_text(item.get("subtitle") or "") or None,
                content_preview=(full_text or raw_preview)[:500],
                full_text_if_available=full_text or None,
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
                summary=summary,
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

    def _load_archive(self) -> list[dict]:
        archive = self.storage.load_json(self._archive_path)
        if isinstance(archive, list):
            return archive
        latest = self.storage.load_json(self._latest_path)
        if isinstance(latest, list):
            return latest
        return []

    def _load_meta(self) -> dict:
        meta = self.storage.load_json(self._meta_path)
        if isinstance(meta, dict):
            return meta
        return {}

    def _save_news_collection(self, items: list[NewsItem]) -> None:
        items.sort(
            key=lambda item: item.published_at if item.published_at.tzinfo else item.published_at.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        archive_payload = [item.model_dump(mode="json") for item in items]
        latest_payload = archive_payload[:200]
        self.storage.save_json(self._archive_path, archive_payload)
        self.storage.save_json(self._latest_path, latest_payload)

    def _merge_and_store(self, normalized: list[NewsItem]) -> int:
        existing = [NewsItem(**item) for item in self._load_archive()]
        existing_ids = {item.id for item in existing}
        new_count = 0
        for news in normalized:
            if news.id not in existing_ids:
                existing_ids.add(news.id)
                existing.append(news)
                new_count += 1
        existing = self._deduplicate(existing)
        self._save_news_collection(existing)
        return new_count

    def fetch_from_yfinance(self) -> list[dict]:
        news_list = []
        tickers = [
            "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "ABEV3.SA",
            "WEGE3.SA", "B3SA3.SA", "MGLU3.SA", "BBAS3.SA", "ELET3.SA",
            "AAPL34.SA", "^BVSP", "BTC-USD"
        ]
        for ticker in tickers:
            try:
                tk = yf.Ticker(ticker)
                news = tk.news
                if news:
                    for entry in news[:5]:
                        news_list.append({
                            "title": entry.get("title", ""),
                            "summary": entry.get("summary", ""),
                            "link": entry.get("link", ""),
                            "source": "YFinance",
                            "published": datetime.fromtimestamp(
                                entry.get("providerPublishTime", 0), tz=timezone.utc
                            ).isoformat() if entry.get("providerPublishTime") else None,
                        })
            except Exception as e:
                logger.debug(f"YFinance error for {ticker}: {e}")
        return news_list

    def fetch_from_rss(self) -> list[dict]:
        news_list = []
        for feed_url in RSS_FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:20]:
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

    def _parse_infomoney_listing(self, html: str) -> list[str]:
        pattern = r'href="(https://www\.infomoney\.com\.br/[^"]+/[^"]+/)"'
        urls = []
        for url in re.findall(pattern, html):
            if "/wp-content/" in url or url.rstrip("/").endswith("/mercados"):
                continue
            urls.append(url)
        deduped = []
        seen = set()
        for url in urls:
            if url in seen:
                continue
            seen.add(url)
            deduped.append(url)
        return deduped

    def _fetch_infomoney_article(self, url: str) -> dict | None:
        try:
            response = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
            if response.status_code != 200:
                return None
            html = response.text
            title_match = re.search(r'<meta property="og:title" content="(.*?)"', html)
            desc_match = re.search(r'<meta property="og:description" content="(.*?)"', html)
            time_match = re.search(r'<meta property="article:published_time" content="(.*?)"', html)
            title = self._clean_text(title_match.group(1)) if title_match else ""
            summary = self._clean_text(desc_match.group(1)) if desc_match else ""
            published = time_match.group(1) if time_match else None
            text_parts = re.findall(r"<p[^>]*>(.*?)</p>", html, flags=re.IGNORECASE | re.DOTALL)
            full_text = " ".join(self._clean_text(part) for part in text_parts[:8] if self._clean_text(part))
            return {
                "title": title,
                "summary": summary,
                "full_text": full_text[:2200],
                "link": url,
                "source": "InfoMoney",
                "published": published,
            }
        except Exception as e:
            logger.debug(f"Erro ao buscar artigo InfoMoney {url}: {e}")
            return None

    def backfill_history(self, start_date: str = "2026-05-01", max_pages: int = 12) -> dict:
        target = date.fromisoformat(start_date)
        collected: list[dict] = []
        found_target_range = False

        for page in range(1, max_pages + 1):
            url = "https://www.infomoney.com.br/mercados/" if page == 1 else f"https://www.infomoney.com.br/mercados/page/{page}/"
            try:
                response = requests.get(url, timeout=12, headers={"User-Agent": "Mozilla/5.0"})
                if response.status_code != 200:
                    continue
                article_urls = self._parse_infomoney_listing(response.text)
                if not article_urls:
                    continue

                page_has_target_range = False
                for article_url in article_urls:
                    article = self._fetch_infomoney_article(article_url)
                    if not article:
                        continue
                    published_dt = self._parse_published(article.get("published"))
                    published_day = published_dt.astimezone(timezone.utc).date()
                    if published_day < target:
                        continue
                    page_has_target_range = True
                    found_target_range = True
                    collected.append(article)

                if found_target_range and not page_has_target_range:
                    break
            except Exception as e:
                logger.debug(f"Erro no backfill da página {page}: {e}")

        normalized = []
        for item in collected:
            news = self._normalize_item(item)
            if news:
                normalized.append(self.scoring.score_news(news))
        normalized = self._deduplicate(normalized)
        new_count = self._merge_and_store(normalized)

        meta = self._load_meta()
        meta["history_backfill"] = {
            "source": "infomoney_open_pages",
            "start_date": start_date,
            "completed": True,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "pages_scanned": max_pages,
            "items_found": len(normalized),
        }
        self.storage.save_json(self._meta_path, meta)
        logger.info(f"Backfill concluído: {len(normalized)} itens normalizados, {new_count} novos")
        return {"normalized": len(normalized), "new_count": new_count}

    def maybe_backfill(self, start_date: str = "2026-05-01") -> dict | None:
        meta = self._load_meta()
        history_meta = meta.get("history_backfill", {})
        if history_meta.get("completed") and history_meta.get("start_date") == start_date:
            return None
        return self.backfill_history(start_date=start_date)

    def ingest(self) -> int:
        raw_items = self.fetch_from_yfinance() + self.fetch_from_rss()
        normalized = []
        for item in raw_items:
            news = self._normalize_item(item)
            if news:
                normalized.append(self.scoring.score_news(news))
        normalized = self._deduplicate(normalized)
        new_count = self._merge_and_store(normalized)
        logger.info(f"Ingestão: {new_count} notícias novas de {len(normalized)} únicas")
        return new_count

    def get_all_raw(self) -> list[NewsItem]:
        data = self._load_archive()
        return [NewsItem(**item) for item in data]
