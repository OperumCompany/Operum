from datetime import datetime, timezone

from app.schemas.news import NewsItem
from app.services.asset_analysis_service import AssetAnalysisService
from app.services.news_ingestion_service import NewsIngestionService
from app.services.news_summary_service import NewsSummaryService


def test_summary_generates_two_paragraphs_and_cleans_noise():
    service = NewsSummaryService()
    summary = service.summarize(
        "Quina hoje, concurso 7039: Confira o resultado sorteado neste sábado (30)",
        "Os sorteios ocorrem de segunda-feira a sábado The post Quina hoje, concurso 7039: Confira o resultado sorteado neste sábado (30) appeared first on InfoMoney.",
        [],
        mentioned_sectors=["Economia"],
        full_text="A loteria teve novo sorteio neste sábado. O resultado movimentou a cobertura de serviços ao leitor. O texto é informativo e não altera diretamente empresas listadas."
    )
    parts = [part.strip() for part in summary.split("\n\n") if part.strip()]
    assert len(parts) == 2
    assert "appeared first on" not in summary.lower()


def test_parse_infomoney_listing_extracts_article_urls():
    html = """
    <a href="https://www.infomoney.com.br/mercados/noticia-1/"><h2>Noticia 1</h2></a>
    <a href="https://www.infomoney.com.br/mercados/noticia-2/"><h2>Noticia 2</h2></a>
    <a href="https://www.infomoney.com.br/mercados/"><h2>Mercados</h2></a>
    """
    service = NewsIngestionService()
    urls = service._parse_infomoney_listing(html)
    assert "https://www.infomoney.com.br/mercados/noticia-1/" in urls
    assert "https://www.infomoney.com.br/mercados/noticia-2/" in urls
    assert "https://www.infomoney.com.br/mercados/" not in urls


def test_editorial_filter_blocks_obvious_noise():
    service = NewsIngestionService()
    infomoney_source = service._sources["infomoney"]
    assert service._is_editorial_item_allowed(
        infomoney_source,
        {
            "title": "Petroleo sobe com tensao no Oriente Medio",
            "link": "https://www.infomoney.com.br/mercados/petroleo-sobe-com-tensao/",
        },
    )
    assert not service._is_editorial_item_allowed(
        infomoney_source,
        {
            "title": "Quando Joao Fonseca volta a jogar?",
            "link": "https://www.infomoney.com.br/esportes/quando-joao-fonseca-volta-a-jogar/",
        },
    )


def test_related_news_mix_prefers_official_but_keeps_macro_context():
    service = AssetAnalysisService()
    service._asset_meta = lambda ticker: {
        "ticker": "PETR4",
        "name": "Petrobras PN",
        "asset_class": "BR_STOCK",
        "country": "BR",
        "sector": "Petroleo e Gas",
        "sub_type": "",
    }
    service.news.get_all_raw = lambda: [
        NewsItem(
            id="official-1",
            title="Petrobras anuncia reducao no preco do diesel",
            subtitle=None,
            content_preview="Companhia informou ajuste em diesel.",
            full_text_if_available=None,
            source_id="b3_comunicados",
            source_name="B3 - Oficios e Comunicados",
            source_type="official_listing",
            is_official=True,
            source_category="exchange",
            source_url="https://example.com/official",
            published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            language="pt",
            tags=["Mercado"],
            mentioned_assets=["PETR4"],
            mentioned_countries=["BR"],
            mentioned_sectors=["Petroleo e Gas"],
            sentiment_score=0.1,
            relevance_score=0.8,
            impact_score=0.7,
            summary="A companhia anunciou ajuste de preco.",
            cluster_id=None,
            created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        ),
        NewsItem(
            id="press-1",
            title="Petroleo sobe com risco geopolitico e mercado monitora cambio",
            subtitle=None,
            content_preview="Contexto macro afeta o setor.",
            full_text_if_available=None,
            source_id="investing_br",
            source_name="Investing.com Brasil",
            source_type="rss",
            is_official=False,
            source_category="press",
            source_url="https://example.com/press",
            published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            language="pt",
            tags=["Economia"],
            mentioned_assets=[],
            mentioned_countries=["BR"],
            mentioned_sectors=["Economia"],
            sentiment_score=0.0,
            relevance_score=0.7,
            impact_score=0.8,
            summary="Petroleo e cambio seguem no radar.",
            cluster_id=None,
            created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        ),
    ]
    results = service.get_related_news("PETR4", limit=10, days_back=120)
    assert len(results) == 2
    assert results[0]["id"] == "official-1"
    assert results[0]["context_role"] == "asset"
    assert results[0]["is_official"] is True
    assert any(item["context_role"] == "macro" for item in results)
