import hashlib
import logging
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Optional
from urllib.parse import quote, urljoin

import feedparser
import requests
import yfinance as yf

from app.schemas.news import NewsItem
from app.services.local_storage_service import LocalStorageService
from app.services.news_scoring_service import NewsScoringService
from app.services.news_summary_service import NewsSummaryService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NewsSource:
    source_id: str
    source_name: str
    source_type: str
    language: str
    base_url: str
    is_official: bool
    source_category: str | None = None
    feed_url: str | None = None
    listing_url: str | None = None
    tags_default: list[str] = field(default_factory=list)
    country_default: list[str] = field(default_factory=list)
    enabled: bool = True
    supports_backfill: bool = False
    max_items: int = 20


OFFICIAL_NEWS_SOURCES: list[NewsSource] = [
    NewsSource(
        source_id="cvm_decisoes",
        source_name="CVM - Decisoes do Colegiado",
        source_type="official_notice_feed",
        language="pt",
        base_url="https://www.cvm.gov.br",
        feed_url="http://www.cvm.gov.br/feed/decisoes.xml",
        is_official=True,
        source_category="regulator",
        tags_default=["Regulacao", "Mercado de Capitais"],
        country_default=["BR"],
        max_items=25,
    ),
    NewsSource(
        source_id="cvm_legislacao",
        source_name="CVM - Legislacao",
        source_type="official_notice_feed",
        language="pt",
        base_url="https://www.cvm.gov.br",
        feed_url="http://www.cvm.gov.br/feed/legislacao.xml",
        is_official=True,
        source_category="regulator",
        tags_default=["Regulacao", "Mercado de Capitais"],
        country_default=["BR"],
        max_items=25,
    ),
    NewsSource(
        source_id="cvm_audiencias",
        source_name="CVM - Audiencias Publicas",
        source_type="official_notice_feed",
        language="pt",
        base_url="https://www.cvm.gov.br",
        feed_url="http://www.cvm.gov.br/feed/audiencias.xml",
        is_official=True,
        source_category="regulator",
        tags_default=["Regulacao", "Audiencia Publica"],
        country_default=["BR"],
        max_items=20,
    ),
    NewsSource(
        source_id="cvm_sancionadores",
        source_name="CVM - Sancionadores",
        source_type="official_notice_feed",
        language="pt",
        base_url="https://www.cvm.gov.br",
        feed_url="http://www.cvm.gov.br/feed/sancionadores.xml",
        is_official=True,
        source_category="regulator",
        tags_default=["Regulacao", "Fiscalizacao"],
        country_default=["BR"],
        max_items=20,
    ),
    NewsSource(
        source_id="cvm_despachos",
        source_name="CVM - Despachos",
        source_type="official_notice_feed",
        language="pt",
        base_url="https://www.cvm.gov.br",
        feed_url="http://www.cvm.gov.br/feed/despachos.xml",
        is_official=True,
        source_category="regulator",
        tags_default=["Regulacao", "Fiscalizacao"],
        country_default=["BR"],
        max_items=20,
    ),
    NewsSource(
        source_id="cvm_informativos",
        source_name="CVM - Informativos do Colegiado",
        source_type="official_notice_feed",
        language="pt",
        base_url="https://www.cvm.gov.br",
        feed_url="http://www.cvm.gov.br/feed/informativos_colegiado.xml",
        is_official=True,
        source_category="regulator",
        tags_default=["Regulacao", "Mercado de Capitais"],
        country_default=["BR"],
        max_items=20,
    ),
    NewsSource(
        source_id="bcb_copom",
        source_name="Banco Central - Comunicados Copom",
        source_type="official_listing",
        language="pt",
        base_url="https://www.bcb.gov.br",
        listing_url="https://www.bcb.gov.br/controleinflacao/comunicadoscopom",
        is_official=True,
        source_category="regulator",
        tags_default=["Juros", "Politica Monetaria", "Copom"],
        country_default=["BR"],
        max_items=12,
    ),
    NewsSource(
        source_id="bcb_noticias",
        source_name="Banco Central - Noticias do Site",
        source_type="official_listing",
        language="pt",
        base_url="https://www.bcb.gov.br",
        listing_url="https://www.bcb.gov.br/noticias/Noticias",
        is_official=True,
        source_category="regulator",
        tags_default=["Economia", "Sistema Financeiro"],
        country_default=["BR"],
        max_items=12,
    ),
    NewsSource(
        source_id="b3_comunicados",
        source_name="B3 - Oficios e Comunicados",
        source_type="official_listing",
        language="pt",
        base_url="https://www.b3.com.br",
        listing_url="https://www.b3.com.br/pt_br/regulacao/oficios-e-comunicados/oficios-e-comunicados/",
        is_official=True,
        source_category="exchange",
        tags_default=["B3", "Mercado de Capitais"],
        country_default=["BR"],
        supports_backfill=True,
        max_items=30,
    ),
]

EDITORIAL_NEWS_SOURCES: list[NewsSource] = [
    NewsSource(
        source_id="folha_mercado",
        source_name="Folha.com - Mercado - Principal",
        source_type="rss",
        language="pt",
        base_url="https://www1.folha.uol.com.br",
        feed_url="https://feeds.folha.uol.com.br/mercado/rss091.xml",
        is_official=False,
        source_category="press",
        tags_default=["Economia", "Mercado"],
        country_default=["BR"],
        max_items=25,
    ),
    NewsSource(
        source_id="infomoney",
        source_name="InfoMoney",
        source_type="editorial_listing",
        language="pt",
        base_url="https://www.infomoney.com.br",
        listing_url="https://www.infomoney.com.br/mercados/",
        is_official=False,
        source_category="press",
        tags_default=["Economia", "Mercado"],
        country_default=["BR"],
        max_items=20,
    ),
    NewsSource(
        source_id="investing_br",
        source_name="Investing.com Brasil",
        source_type="rss",
        language="pt",
        base_url="https://br.investing.com",
        feed_url="https://br.investing.com/rss/news.rss",
        is_official=False,
        source_category="press",
        tags_default=["Mercado", "Macroeconomia"],
        country_default=["BR", "US"],
        max_items=20,
    ),
]

ALL_NEWS_SOURCES: list[NewsSource] = OFFICIAL_NEWS_SOURCES + EDITORIAL_NEWS_SOURCES

TICKER_KEYWORDS: dict[str, list[str]] = {
    "PETR4": ["petrobras", "petr4"],
    "VALE3": ["vale", "vale3"],
    "ITUB4": ["itau", "itub4", "itaÃº"],
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
    "Petroleo e Gas": ["petroleo", "petrÃ³leo", "gas", "gÃ¡s", "petrobras", "pre-sal", "prÃ©-sal"],
    "Mineracao": ["mineracao", "mineraÃ§Ã£o", "minerio", "minÃ©rio", "ferro"],
    "Financeiro": ["banco", "bancos", "juros", "selic", "credito", "crÃ©dito"],
    "Tecnologia": ["tecnologia", "big tech", "ia", "inteligencia artificial", "inteligÃªncia artificial"],
    "Criptomoedas": ["bitcoin", "cripto", "blockchain", "ethereum", "criptomoeda"],
    "Energia Eletrica": ["energia", "eletrica", "elÃ©trica", "eletrobras"],
    "Varejo": ["varejo", "magazine luiza", "americanas"],
    "Alimentos": ["alimentos", "jbs", "marfrig", "carne", "frigorifico", "frigorÃ­fico"],
    "Economia": ["inflacao", "inflaÃ§Ã£o", "pib", "fiscal", "economia", "dolar", "dÃ³lar"],
    "Regulacao": ["resolucao", "resoluÃ§Ã£o", "colegiado", "audiencia", "audiÃªncia", "comunicado", "oficio", "ofÃ­cio"],
}

COUNTRY_KEYWORDS: dict[str, list[str]] = {
    "BR": ["brasil", "ibovespa", "real", "b3", "bolsa brasileira", "copom", "cvm", "tesouro"],
    "US": ["eua", "estados unidos", "fed", "s&p", "wall street", "dolar", "dÃ³lar"],
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
        self._sources = {source.source_id: source for source in ALL_NEWS_SOURCES}

    def _generate_id(self, title: str, source: str, published_at: str | datetime | None = None) -> str:
        published_key = ""
        if isinstance(published_at, datetime):
            published_key = published_at.isoformat()
        elif isinstance(published_at, str):
            published_key = published_at.strip()
        raw = f"{title.strip().lower()}|{source.strip().lower()}|{published_key.lower()}"
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
        text = unescape(text)
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

    def _normalize_text(self, text: str) -> str:
        return self._clean_text(text).lower()

    def _parse_published(self, published: str | datetime | None) -> datetime:
        if isinstance(published, datetime):
            return published if published.tzinfo else published.replace(tzinfo=timezone.utc)
        if isinstance(published, str) and published:
            normalized = (
                published.replace("Z", "+00:00")
                .replace(" Ã s ", " ")
                .replace(" at ", " ")
                .strip()
            )
            for fmt in (
                None,
                "%d/%m/%Y",
                "%d/%m/%Y %Hh%M",
                "%d/%m/%Y %H:%M",
                "%d/%m/%y",
                "%d/%m/%y %Hh%M",
            ):
                try:
                    dt = datetime.fromisoformat(normalized) if fmt is None else datetime.strptime(normalized, fmt)
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    continue
            try:
                dt = parsedate_to_datetime(normalized)
                return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError, IndexError):
                pass
        return datetime.now(timezone.utc)

    def _normalize_item(self, item: dict) -> Optional[NewsItem]:
        try:
            title = self._clean_text(item.get("title") or "")
            if not title:
                return None

            raw_preview = self._clean_text(item.get("summary") or item.get("description") or "")
            full_text = self._clean_text(item.get("full_text") or "")
            source_id = self._clean_text(item.get("source_id") or "unknown") or "unknown"
            source_name = self._clean_text(item.get("source") or item.get("source_name") or "desconhecida")
            source_type = self._clean_text(item.get("source_type") or "rss") or "rss"
            source_url = item.get("link") or item.get("source_url") or ""
            published_dt = self._parse_published(item.get("published") or item.get("published_at"))
            source_category = item.get("source_category")
            tags_default = [self._clean_text(tag) for tag in item.get("tags_default", []) if self._clean_text(tag)]
            country_default = [self._clean_text(country) for country in item.get("country_default", []) if self._clean_text(country)]

            text_for_analysis = f"{title} {raw_preview} {full_text}"
            mentioned_assets = self._detect_assets(text_for_analysis)
            mentioned_sectors = sorted(set(self._detect_sectors(text_for_analysis) + tags_default))
            mentioned_countries = sorted(set(self._detect_countries(text_for_analysis) + country_default))
            news_id = self._generate_id(title, source_name, published_dt)

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
                content_preview=(full_text or raw_preview)[:900],
                full_text_if_available=full_text or None,
                source_id=source_id,
                source_name=source_name,
                source_type=source_type,
                is_official=bool(item.get("is_official", False)),
                source_category=source_category,
                source_url=source_url,
                published_at=published_dt,
                language=item.get("language") or "pt",
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
            logger.warning(f"Erro ao normalizar noticia: {e}")
            return None

    def _deduplicate(self, items: list[NewsItem]) -> list[NewsItem]:
        seen = set()
        unique = []
        for item in items:
            if item.id in seen:
                continue
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
            if news.id in existing_ids:
                continue
            existing_ids.add(news.id)
            existing.append(news)
            new_count += 1
        existing = self._deduplicate(existing)
        self._save_news_collection(existing)
        return new_count

    def _request_text(self, url: str) -> str:
        response = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        return response.text

    def _clean_feed_link(self, link: str) -> str:
        link = self._clean_text(link)
        if "redir.folha.com.br" in link and "*http" in link:
            link = link.split("*", 1)[1]
        return link

    def _build_source_payload(self, source: NewsSource, extra: dict | None = None) -> dict:
        payload = {
            "source_id": source.source_id,
            "source_name": source.source_name,
            "source_type": source.source_type,
            "is_official": source.is_official,
            "source_category": source.source_category,
            "language": source.language,
            "tags_default": source.tags_default,
            "country_default": source.country_default,
        }
        if extra:
            payload.update(extra)
        return payload

    def _fetch_rss_source(self, source: NewsSource) -> list[dict]:
        if not source.feed_url:
            return []
        items = []
        try:
            feed = feedparser.parse(source.feed_url)
            for entry in feed.entries[: source.max_items]:
                link = self._clean_feed_link(entry.get("link", ""))
                items.append(
                    self._build_source_payload(
                        source,
                        {
                            "title": entry.get("title", ""),
                            "summary": entry.get("summary", "") or entry.get("description", ""),
                            "link": link,
                            "published": entry.get("published", "") or entry.get("updated", ""),
                            "source": source.source_name,
                        },
                    )
                )
        except Exception as e:
            logger.debug(f"RSS error for {source.source_id}: {e}")
        return items

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

    def _fetch_infomoney_listing(self, source: NewsSource) -> list[dict]:
        if not source.listing_url:
            return []
        items = []
        try:
            html = self._request_text(source.listing_url)
            pattern = re.compile(
                r'<h2[^>]*>\s*<a href="(?P<link>https://www\.infomoney\.com\.br/mercados/[^"]+/)"[^>]*(?:aria-label="(?P<aria>[^"]+)")?[^>]*>(?P<title>.*?)</a>\s*</h2>',
                re.IGNORECASE | re.DOTALL,
            )
            seen_links = set()
            for match in pattern.finditer(html):
                link = self._clean_text(match.group("link"))
                if link in seen_links or "/page/" in link or "/feed/" in link:
                    continue
                seen_links.add(link)
                title = self._clean_text(match.group("aria") or match.group("title"))
                if not title:
                    continue
                items.append(
                    self._build_source_payload(
                        source,
                        {
                            "title": title,
                            "summary": title,
                            "link": link,
                            "published": None,
                            "source": source.source_name,
                        },
                    )
                )
                if len(items) >= source.max_items:
                    break
        except Exception as e:
            logger.debug(f"InfoMoney listing error for {source.source_id}: {e}")
        return items

    def _is_editorial_item_allowed(self, source: NewsSource, item: dict) -> bool:
        title = self._normalize_text(item.get("title", ""))
        link = self._normalize_text(item.get("link", ""))

        if source.source_id == "investing_br":
            allowed_sections = (
                "/news/commodities-news/",
                "/news/economic-indicators/",
                "/news/stock-market-news/",
                "/news/forex-news/",
                "/news/cryptocurrency-news/",
                "/news/world-news/",
            )
            if not any(section in link for section in allowed_sections):
                return False

        if source.source_id == "infomoney":
            blocked_terms = (
                "/esportes/",
                "/consumo/",
                "/saude/",
                "/educacao/",
                "/cultura/",
                "/turismo/",
                "/guia/",
                "/planilhas/",
                "/conteudos/",
                "/cursos/",
                "/ebooks/",
            )
            if any(term in link for term in blocked_terms):
                return False

        generic_spam_terms = (
            "onde assistir",
            "resultado sorteado",
            "quina hoje",
            "loteria",
        )
        if any(term in title for term in generic_spam_terms):
            return False

        return True

    def _fetch_b3_listing(self, source: NewsSource) -> list[dict]:
        if not source.listing_url:
            return []
        items = []
        try:
            html = self._request_text(source.listing_url)
            pattern = re.compile(
                r'<div class="least-content">(?P<date>\d{2}/\d{2}/\d{2})</div>.*?'
                r'<p class="primary-text[^"]*">(?P<title>.*?)</p>.*?'
                r'<p class="resumo-oficio">(?P<summary>.*?)</p>.*?'
                r'href="(?P<link>/data/files/[^"]+\.pdf)"',
                re.IGNORECASE | re.DOTALL,
            )
            for match in pattern.finditer(html):
                items.append(
                    self._build_source_payload(
                        source,
                        {
                            "title": self._clean_text(match.group("title")),
                            "summary": self._clean_text(match.group("summary")),
                            "link": urljoin(source.base_url, match.group("link")),
                            "published": match.group("date"),
                            "source": source.source_name,
                        },
                    )
                )
                if len(items) >= source.max_items:
                    break
        except Exception as e:
            logger.debug(f"B3 listing error for {source.source_id}: {e}")
        return items

    def _fetch_tesouro_listing(self, source: NewsSource, offset: int = 0) -> list[dict]:
        if not source.listing_url:
            return []
        items = []
        try:
            url = source.listing_url if offset == 0 else f"{source.listing_url}?b_start:int={offset}"
            html = self._request_text(url)
            pattern = re.compile(
                r'<h2 class="tileHeadline">\s*<a class="summary url" href="(?P<link>[^"]+)".*?>(?P<title>.*?)</a>.*?'
                r'<span class="description">(?P<summary>.*?)</span>.*?'
                r'<span class="summary-view-icon">\s*<i class="icon-day"></i>\s*(?P<date>\d{2}/\d{2}/\d{4})',
                re.IGNORECASE | re.DOTALL,
            )
            for match in pattern.finditer(html):
                items.append(
                    self._build_source_payload(
                        source,
                        {
                            "title": self._clean_text(match.group("title")),
                            "summary": self._clean_text(match.group("summary")),
                            "link": self._clean_text(match.group("link")),
                            "published": match.group("date"),
                            "source": source.source_name,
                        },
                    )
                )
                if len(items) >= source.max_items:
                    break
        except Exception as e:
            logger.debug(f"Tesouro listing error for {source.source_id}: {e}")
        return items

    def _fetch_bcb_listing(self, source: NewsSource) -> list[dict]:
        # O portal atual do BCB e servido por SPA e nao expÃµe facilmente os links
        # de RSS/HTML estruturados em requests simples. Mantemos o conector oficial
        # preparado, retornando vazio quando o conteudo nao puder ser extraido de forma segura.
        if not source.listing_url:
            return []
        items = []
        try:
            html = self._request_text(source.listing_url)
            if "/assets/" in html and "<app-root></app-root>" in html:
                logger.debug(f"BCB listing {source.source_id} depende de SPA; sem extracao segura nesta fase")
                return []
            pattern = re.compile(
                r'<a[^>]+href="(?P<link>[^"]+)"[^>]*>\s*(?P<title>[^<]{20,})\s*</a>.*?(?P<date>\d{2}/\d{2}/\d{4})?',
                re.IGNORECASE | re.DOTALL,
            )
            for match in pattern.finditer(html):
                link = match.group("link")
                if not link.startswith("http"):
                    link = urljoin(source.base_url, link)
                items.append(
                    self._build_source_payload(
                        source,
                        {
                            "title": self._clean_text(match.group("title")),
                            "summary": self._clean_text(match.group("title")),
                            "link": link,
                            "published": match.group("date"),
                            "source": source.source_name,
                        },
                    )
                )
                if len(items) >= source.max_items:
                    break
        except Exception as e:
            logger.debug(f"BCB listing error for {source.source_id}: {e}")
        return items

    def _fetch_listing_source(self, source: NewsSource) -> list[dict]:
        if source.source_id == "infomoney":
            return self._fetch_infomoney_listing(source)
        if source.source_id.startswith("b3_"):
            return self._fetch_b3_listing(source)
        if source.source_id.startswith("tesouro_"):
            return self._fetch_tesouro_listing(source)
        if source.source_id.startswith("bcb_"):
            return self._fetch_bcb_listing(source)
        return []

    def fetch_from_yfinance(self) -> list[dict]:
        news_list = []
        tickers = [
            "PETR4.SA", "VALE3.SA", "ITUB4.SA", "BBDC4.SA", "ABEV3.SA",
            "WEGE3.SA", "B3SA3.SA", "MGLU3.SA", "BBAS3.SA", "ELET3.SA",
            "AAPL34.SA", "^BVSP", "BTC-USD",
        ]
        for ticker in tickers:
            try:
                tk = yf.Ticker(ticker)
                news = tk.news
                if not news:
                    continue
                for entry in news[:5]:
                    news_list.append(
                        {
                            "title": entry.get("title", ""),
                            "summary": entry.get("summary", ""),
                            "link": entry.get("link", ""),
                            "source": "YFinance",
                            "source_id": "yfinance",
                            "source_name": "YFinance",
                            "source_type": "api_proxy",
                            "source_category": "press",
                            "is_official": False,
                            "published": datetime.fromtimestamp(
                                entry.get("providerPublishTime", 0),
                                tz=timezone.utc,
                            ).isoformat() if entry.get("providerPublishTime") else None,
                            "language": "en",
                            "country_default": ["US"],
                        }
                    )
            except Exception as e:
                logger.debug(f"YFinance error for {ticker}: {e}")
        return news_list

    def fetch_from_sources(self) -> list[dict]:
        raw_items = []
        for source in ALL_NEWS_SOURCES:
            if not source.enabled:
                continue
            if source.feed_url:
                raw_items.extend(
                    item for item in self._fetch_rss_source(source)
                    if self._is_editorial_item_allowed(source, item)
                )
            elif source.listing_url:
                raw_items.extend(
                    item for item in self._fetch_listing_source(source)
                    if self._is_editorial_item_allowed(source, item)
                )
        return raw_items

    def _normalize_and_score(self, raw_items: list[dict]) -> list[NewsItem]:
        normalized = []
        for item in raw_items:
            news = self._normalize_item(item)
            if news:
                normalized.append(self.scoring.score_news(news))
        return self._deduplicate(normalized)

    def _update_backfill_meta(
        self,
        source_ids: list[str],
        start_date: str,
        normalized_count: int,
        new_count: int,
        oldest_date_loaded: str | None,
    ) -> None:
        meta = self._load_meta()
        by_source = meta.get("backfill_sources", {})
        now_iso = datetime.now(timezone.utc).isoformat()
        for source_id in source_ids:
            by_source[source_id] = {
                "completed": True,
                "start_date": start_date,
                "last_run_at": now_iso,
                "oldest_date_loaded": oldest_date_loaded,
                "items_found": normalized_count,
                "new_count": new_count,
            }
        meta["backfill_sources"] = by_source
        self.storage.save_json(self._meta_path, meta)

    def _run_source_backfill(self, source: NewsSource, start_day: date) -> list[dict]:
        if source.source_id.startswith("tesouro_"):
            collected = []
            for offset in (0, 20, 40, 60):
                batch = self._fetch_tesouro_listing(source, offset=offset)
                if not batch:
                    break
                eligible = []
                for item in batch:
                    published_day = self._parse_published(item.get("published")).date()
                    if published_day >= start_day:
                        eligible.append(item)
                collected.extend(eligible)
                if len(eligible) < len(batch):
                    break
            return collected
        if source.source_id.startswith("b3_"):
            batch = self._fetch_b3_listing(source)
            return [item for item in batch if self._parse_published(item.get("published")).date() >= start_day]
        if source.feed_url:
            batch = self._fetch_rss_source(source)
            return [item for item in batch if self._parse_published(item.get("published")).date() >= start_day]
        return []

    def backfill_history(
        self,
        start_date: str = "2026-05-01",
        max_pages: int = 12,
        source_id: str | None = None,
    ) -> dict:
        del max_pages
        start_day = date.fromisoformat(start_date)
        sources = [
            self._sources[source_id]
        ] if source_id and source_id in self._sources else [
            source for source in OFFICIAL_NEWS_SOURCES if source.supports_backfill
        ]

        if source_id and source_id not in self._sources:
            return {"normalized": 0, "new_count": 0, "sources": [], "error": "source_not_found"}

        collected: list[dict] = []
        processed_source_ids: list[str] = []
        for source in sources:
            processed_source_ids.append(source.source_id)
            collected.extend(self._run_source_backfill(source, start_day))

        normalized = self._normalize_and_score(collected)
        new_count = self._merge_and_store(normalized)
        oldest_date_loaded = None
        if normalized:
            oldest_date_loaded = min(item.published_at.date().isoformat() for item in normalized)
        self._update_backfill_meta(
            processed_source_ids,
            start_date,
            len(normalized),
            new_count,
            oldest_date_loaded,
        )
        return {
            "normalized": len(normalized),
            "new_count": new_count,
            "sources": processed_source_ids,
            "oldest_date_loaded": oldest_date_loaded,
        }

    def maybe_backfill(self, start_date: str = "2026-05-01") -> dict | None:
        meta = self._load_meta()
        backfill_meta = meta.get("backfill_sources", {})
        source_ids = [source.source_id for source in OFFICIAL_NEWS_SOURCES if source.supports_backfill]
        if source_ids and all(
            backfill_meta.get(source_id, {}).get("completed") and backfill_meta.get(source_id, {}).get("start_date") == start_date
            for source_id in source_ids
        ):
            return None
        return self.backfill_history(start_date=start_date)

    def ingest(self) -> int:
        raw_items = self.fetch_from_sources() + self.fetch_from_yfinance()
        normalized = self._normalize_and_score(raw_items)
        new_count = self._merge_and_store(normalized)
        logger.info(f"Ingestao: {new_count} noticias novas de {len(normalized)} unicas")
        return new_count

    def get_all_raw(self) -> list[NewsItem]:
        data = self._load_archive()
        return [NewsItem(**item) for item in data]
