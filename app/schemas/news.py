from datetime import datetime
from pydantic import BaseModel


class NewsItem(BaseModel):
    id: str
    title: str
    subtitle: str | None = None
    content_preview: str = ""
    full_text_if_available: str | None = None
    source_name: str
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
