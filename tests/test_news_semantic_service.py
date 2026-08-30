from datetime import datetime, timezone

from app.schemas.news import NewsItem
from app.services.news_semantic_service import NewsSemanticService


def make_news(news_id: str, title: str, summary: str = "") -> NewsItem:
    return NewsItem(
        id=news_id,
        title=title,
        subtitle=None,
        content_preview=summary,
        full_text_if_available=None,
        source_id="test",
        source_name="Fonte teste",
        source_type="rss",
        is_official=False,
        source_category="press",
        source_url=f"https://example.com/{news_id}",
        published_at=datetime.now(timezone.utc),
        language="pt",
        tags=[],
        mentioned_assets=[],
        mentioned_countries=["BR"],
        mentioned_sectors=["Financeiro"],
        sentiment_score=0.0,
        relevance_score=0.8,
        impact_score=0.7,
        summary=summary,
        cluster_id=None,
        created_at=datetime.now(timezone.utc),
    )


class FakeEmbedder:
    enabled = True
    model_name = "fake-e5"

    def encode_query(self, query: str) -> list[float]:
        return [0.1, 0.2]

    def encode_documents(self, items: list[NewsItem]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in items]

    def detect_events(self, news: NewsItem) -> list[str]:
        return []

    def content_hash(self, news: NewsItem, events=None) -> str:
        return f"hash-{news.id}-{news.title}"


class FakeRepository:
    enabled = True

    def __init__(self):
        self.hashes = {}
        self.saved = []

    def semantic_search(self, query_vector, **kwargs):
        return [{"id": "semantic", "similarity": 0.84}]

    def existing_hashes(self, ids=None):
        return dict(self.hashes)

    def upsert_batch(self, items, vectors, embedder):
        self.saved.extend(item.id for item in items)
        for item in items:
            self.hashes[item.id] = embedder.content_hash(item, [])
        return len(items)


def test_hybrid_search_finds_semantic_match_without_literal_words(monkeypatch):
    monkeypatch.setattr(
        "app.services.news_semantic_service.NEWS_EMBEDDINGS_ENABLED",
        True,
    )
    service = NewsSemanticService(FakeEmbedder(), FakeRepository())
    semantic = make_news(
        "semantic",
        "Bancos elevam provisões após aumento do crédito vencido",
    )
    unrelated = make_news("other", "Petroleo fecha em alta")

    results, mode, available = service.hybrid_search(
        [unrelated, semantic],
        "impacto da inadimplência nos bancos",
        search_mode="hybrid",
    )

    assert [item.id for item in results] == ["semantic"]
    assert mode == "hybrid"
    assert available is True


def test_hybrid_search_falls_back_to_keyword_when_embeddings_are_disabled():
    service = NewsSemanticService(FakeEmbedder(), FakeRepository())
    service.embedder.enabled = False
    news = make_news("keyword", "Copom mantém juros")

    results, mode, available = service.hybrid_search(
        [news],
        "Copom",
        search_mode="hybrid",
    )

    assert [item.id for item in results] == ["keyword"]
    assert mode == "keyword"
    assert available is False


def test_embedding_index_is_idempotent(monkeypatch):
    monkeypatch.setattr(
        "app.services.news_semantic_service.NEWS_EMBEDDINGS_ENABLED",
        True,
    )
    repository = FakeRepository()
    service = NewsSemanticService(FakeEmbedder(), repository)
    items = [make_news("one", "Resultado trimestral")]

    first = service.index_news(items)
    second = service.index_news(items)

    assert first["indexed"] == 1
    assert second["indexed"] == 0
    assert repository.saved == ["one"]
