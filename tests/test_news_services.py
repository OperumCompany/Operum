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
