import logging
from collections import defaultdict

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

from app.schemas.news import NewsItem

logger = logging.getLogger(__name__)


class NewsClusteringService:
    def __init__(self, n_clusters: int = 8):
        self.n_clusters = n_clusters
        self.vectorizer = TfidfVectorizer(
            max_features=3000, ngram_range=(1, 2), stop_words="english"
        )
        self.kmeans: KMeans | None = None

    def cluster(self, news_list: list[NewsItem]) -> list[NewsItem]:
        if len(news_list) < self.n_clusters:
            for i, n in enumerate(news_list):
                n.cluster_id = 0
            return news_list

        texts = [
            f"{n.title} {n.content_preview} {n.subtitle or ''}" for n in news_list
        ]

        try:
            X = self.vectorizer.fit_transform(texts)
            self.kmeans = KMeans(
                n_clusters=min(self.n_clusters, len(news_list)),
                random_state=42,
                n_init="auto",
            )
            labels = self.kmeans.fit_predict(X)

            for i, n in enumerate(news_list):
                n.cluster_id = int(labels[i])

            logger.info(
                f"Clusterização: {len(news_list)} notícias em {self.kmeans.n_clusters} clusters"
            )
        except Exception as e:
            logger.warning(f"Erro na clusterização: {e}")
            for n in news_list:
                n.cluster_id = 0

        return news_list

    def get_cluster_summary(
        self, news_list: list[NewsItem]
    ) -> dict[int, dict]:
        clusters: dict[int, list[NewsItem]] = defaultdict(list)
        for n in news_list:
            clusters[n.cluster_id].append(n)

        result: dict[int, dict] = {}
        for cid, items in clusters.items():
            top = sorted(items, key=lambda x: x.impact_score, reverse=True)[:3]
            sectors = set()
            assets = set()
            for item in items:
                sectors.update(item.mentioned_sectors)
                assets.update(item.mentioned_assets)
            result[cid] = {
                "id": cid,
                "size": len(items),
                "top_assets": list(assets)[:5],
                "top_sectors": list(sectors)[:3],
                "avg_sentiment": sum(n.sentiment_score for n in items) / len(items),
                "avg_impact": sum(n.impact_score for n in items) / len(items),
                "headlines": [n.title for n in top],
            }

        return result
