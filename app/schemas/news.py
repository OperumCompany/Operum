from datetime import datetime
from pydantic import BaseModel


class NewsItem(BaseModel):
    id: str
    title: str
    subtitle: str | None = None
    content_preview: str = ""
    full_text_if_available: str | None = None
    source_id: str = "unknown"
    source_name: str
    source_type: str = "rss"
    is_official: bool = False
    source_category: str | None = None
    source_url: str
    published_at: datetime
    language: str = "pt"
    tags: list[str] = []
    mentioned_assets: list[str] = []
    mentioned_countries: list[str] = []
    mentioned_sectors: list[str] = []
    sentiment_score: float = 0.0
    relevance_score: float = 0.0
    impact_score: float = 0.0
    summary: str = ""
    cluster_id: int | None = None
    created_at: datetime
