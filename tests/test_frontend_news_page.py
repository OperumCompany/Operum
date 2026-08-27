from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


def test_news_page_uses_editorial_topic_filters_and_twenty_items_per_page():
    source = (ROOT_DIR / "src" / "pages" / "NewsPage.tsx").read_text(encoding="utf-8")

    assert "const PAGE_SIZE = 20;" in source
    assert "Mercado" in source
    assert "Economia" in source
    assert "Tecnologia" in source
    assert "selectedSentiment" not in source
    assert "selectedImpact" not in source
