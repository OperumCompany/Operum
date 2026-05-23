import re
import logging

logger = logging.getLogger(__name__)


class NewsSummaryService:
    def extractive_summary(self, text: str, max_sentences: int = 3) -> str:
        if not text or not text.strip():
            return ""

        # Simple extractive: take first meaningful sentences
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        meaningful = [s.strip() for s in sentences if len(s.strip()) > 20]

        if not meaningful:
            return text[:200]

        summary = " ".join(meaningful[:max_sentences])
        if len(summary) > 500:
            summary = summary[:497] + "..."

        return summary

    def template_summary(self, title: str, preview: str, assets: list[str]) -> str:
        asset_part = ""
        if assets:
            if len(assets) == 1:
                asset_part = f" Notícia menciona {assets[0]}."
            else:
                asset_part = f" Notícia menciona {', '.join(assets[:3])}."

        # Use preview or fallback to title-based summary
        if preview and len(preview) > 30:
            summary = preview[:200]
            if len(preview) > 200:
                summary += "..."
            return summary + asset_part

        return f"{title.strip('.')}.{asset_part}"

    def summarize(self, news_title: str, news_preview: str, mentioned_assets: list[str]) -> str:
        return self.template_summary(news_title, news_preview, mentioned_assets)
