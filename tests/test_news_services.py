from datetime import datetime, timezone
import os

os.environ["OPERUM_STORAGE_MODE"] = "local"

from app.schemas.news import NewsItem
from app.services.asset_analysis_service import AssetAnalysisService
from app.services.news_ingestion_service import NewsIngestionService
from app.services.news_summary_service import NewsSummaryService


class FakeInvalidLLM:
    enabled = True

    def chat_json(self, *args, **kwargs):
        return {
            "summary": "Recomendo comprar este ativo agora.",
            "visual_summary": {"asset_status": "positivo"},
        }


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
        NewsItem(
            id="incidental-1",
            title="Lojas Renner: Itau BBA eleva recomendacao para compra",
            subtitle=None,
            content_preview="Relatorio comenta LREN3 e varejo.",
            full_text_if_available=None,
            source_id="infomoney",
            source_name="InfoMoney",
            source_type="rss",
            is_official=False,
            source_category="press",
            source_url="https://example.com/renner",
            published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            language="pt",
            tags=["Mercado"],
            mentioned_assets=[],
            mentioned_countries=["BR"],
            mentioned_sectors=["Varejo"],
            sentiment_score=0.2,
            relevance_score=0.7,
            impact_score=0.7,
            summary="Banco comenta outra companhia.",
            cluster_id=None,
            created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        ),
    ]
    results = service.get_related_news("PETR4", limit=10, days_back=120)
    assert len(results) == 2
    assert {item["id"] for item in results} == {"official-1", "press-1"}
    assert results[0]["id"] == "official-1"
    assert results[0]["context_role"] == "asset"
    assert results[0]["is_official"] is True
    assert any(item["context_role"] == "macro" for item in results)


def test_related_news_ignores_incidental_analyst_brand_mentions():
    service = AssetAnalysisService()
    service._asset_meta = lambda ticker: {
        "ticker": "ITUB4",
        "name": "Itau Unibanco PN",
        "asset_class": "BR_STOCK",
        "country": "BR",
        "sector": "Financeiro",
        "sub_type": "",
    }
    service.news.get_all_raw = lambda: [
        NewsItem(
            id="itub-direct",
            title="Itau Unibanco divulga resultado trimestral",
            subtitle=None,
            content_preview="Banco reporta novos dados operacionais.",
            full_text_if_available=None,
            source_id="b3_comunicados",
            source_name="B3 - Oficios e Comunicados",
            source_type="official_listing",
            is_official=True,
            source_category="exchange",
            source_url="https://example.com/itub",
            published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            language="pt",
            tags=["Mercado"],
            mentioned_assets=["ITUB4"],
            mentioned_countries=["BR"],
            mentioned_sectors=["Financeiro"],
            sentiment_score=0.1,
            relevance_score=0.8,
            impact_score=0.7,
            summary="Banco divulga resultado.",
            cluster_id=None,
            created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        ),
        NewsItem(
            id="renner-report",
            title="Lojas Renner: Itau BBA eleva recomendacao para compra",
            subtitle=None,
            content_preview="Relatorio comenta LREN3 e varejo.",
            full_text_if_available=None,
            source_id="infomoney",
            source_name="InfoMoney",
            source_type="rss",
            is_official=False,
            source_category="press",
            source_url="https://example.com/renner",
            published_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
            language="pt",
            tags=["Mercado"],
            mentioned_assets=[],
            mentioned_countries=["BR"],
            mentioned_sectors=["Varejo"],
            sentiment_score=0.2,
            relevance_score=0.7,
            impact_score=0.7,
            summary="Banco comenta outra companhia.",
            cluster_id=None,
            created_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        ),
    ]

    results = service.get_related_news("ITUB4", limit=10, days_back=120)

    assert [item["id"] for item in results] == ["itub-direct"]


def test_asset_analysis_refiner_rejects_invalid_transactional_llm_payload():
    service = AssetAnalysisService()
    service.llm = FakeInvalidLLM()
    payload = {
        "current_snapshot": {"weight_pct": 68.1},
        "recent_performance": {},
        "outlook_3m": {"scenario": "neutro"},
        "confidence": "media",
        "used_news_count": 0,
        "source_groups": [],
        "analysis_sections": {
            "current": "Texto atual original.",
            "recent": "Texto recente original.",
            "outlook": "Texto de perspectiva original.",
            "recent_by_horizon": {"1w": "1w", "1m": "1m", "2m": "2m", "3m": "3m"},
            "outlook_by_horizon": {"1w": "1w", "1m": "1m", "2m": "2m", "3m": "3m"},
            "visual_summary": {
                "asset_status": "atencao",
                "fundamentals": "sem noticias suficientes",
                "price_trend": "negativa",
                "news_sentiment": "dados insuficientes",
                "position_size": "altamente concentrada",
                "portfolio_risk": "alto",
                "main_reason": "concentracao",
                "confidence": "moderada",
            },
            "summary": "Resumo original.",
            "what_happened": "O que aconteceu original.",
            "current_situation": "Situacao original.",
            "portfolio_impact": "Impacto original.",
            "scenarios": {"favorable": "Favoravel", "base": "Base", "adverse": "Adverso"},
            "what_to_watch": ["resultados"],
            "conclusion": "Conclusao original.",
            "data_quality_warnings": ["Aviso original."],
            "box_history_by_horizon": {"1w": "Historico 1w", "1m": "Historico 1m", "2m": "Historico 2m", "3m": "Historico 3m"},
            "box_current": "Situacao atual original.",
            "box_outlook_by_horizon": {"1w": "Perspectiva 1w", "1m": "Perspectiva 1m", "2m": "Perspectiva 2m", "3m": "Perspectiva 3m"},
        },
    }

    refined = service._refine_analysis_sections(payload, "3m", "3m")

    assert refined["analysis_sections"]["summary"] == "Resumo original."
    assert refined["analysis_sections"]["conclusion"] == "Conclusao original."


def test_friendly_asset_sections_include_scenarios_warnings_and_concentration_impact():
    service = AssetAnalysisService()
    sections = service._build_friendly_analysis_sections(
        meta={
            "ticker": "ITUB4",
            "name": "Itau Unibanco PN",
            "asset_class": "BR_STOCK",
            "sector": "Financeiro",
        },
        perf={
            "current_price": 42.3,
            "currency": "BRL",
            "change_selected_pct": -4.6,
            "drawdown_selected_pct": -11.8,
            "has_selected_history": True,
        },
        used_news=[],
        weight_pct=68.1,
        scenario="cauteloso",
        confidence="media",
        history_horizon="3m",
        outlook_horizon="3m",
        asset_function="estabilidade",
        historical_series=[{"date": "2026-07-01", "value": 42.1}],
        data_quality_warnings=["Dados fundamentais estruturados ainda nao estao disponiveis no MVP."],
    )

    assert sections["visual_summary"]["position_size"] == "altamente concentrada"
    assert sections["visual_summary"]["portfolio_risk"] == "muito alto"
    assert "queda de 10%" in sections["portfolio_impact"].lower()
    assert "-6,8%" in sections["portfolio_impact"]
    assert {"favorable", "base", "adverse"}.issubset(sections["scenarios"])
    assert sections["data_quality_warnings"]
    assert "não conclui" in sections["company_situation"].lower()


def test_box_sections_are_compact_and_do_not_expose_internal_terms():
    service = AssetAnalysisService()
    sections = service._build_box_sections(
        meta={
            "ticker": "ITUB4",
            "name": "Itau Unibanco PN",
            "asset_class": "BR_STOCK",
            "sector": "Financeiro",
        },
        perf={
            "current_price": 42.3,
            "currency": "BRL",
            "change_selected_pct": -4.6,
            "drawdown_selected_pct": -11.8,
            "volatility_selected_pct": 20.0,
            "has_selected_history": True,
        },
        current_news=[],
        all_related_news=[],
        used_news=[],
        weight_pct=67.3,
        scenario="concentrado",
        confidence="media",
        asset_function="estabilidade",
    )

    text = " ".join([
        *sections["box_history_by_horizon"].values(),
        sections["box_current"],
        *sections["box_outlook_by_horizon"].values(),
    ]).lower()

    assert set(sections["box_history_by_horizon"]) == {"1w", "1m", "2m", "3m"}
    assert set(sections["box_outlook_by_horizon"]) == {"1w", "1m", "2m", "3m"}
    for blocked in ["drawdown", "momentum", "impacto medio", "impacto médio", "peso informacional", "ajuste contextual", "beta estimado", "volatilidade anualizada"]:
        assert blocked not in text
    assert "cumpriu sua funcao" not in text
    assert "cenario de itub4 e concentrado" not in text
    assert "cauteloso" in sections["box_outlook_by_horizon"]["3m"].lower()
