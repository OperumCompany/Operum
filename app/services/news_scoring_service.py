import os
import joblib
import logging
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

try:
    import lightgbm as lgb

    _HAS_LGB = True
except ImportError:
    _HAS_LGB = False

from app.schemas.news import NewsItem

logger = logging.getLogger(__name__)

MODEL_PATH = "data/models/news_relevance.pkl"
VECTORIZER_PATH = "data/models/news_vectorizer.pkl"


class NewsScoringService:
    def __init__(self):
        self.model: Pipeline | None = None
        self.vectorizer: TfidfVectorizer | None = None
        self._load_or_init()

    def _load_or_init(self):
        model_full = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), MODEL_PATH
        )
        vec_full = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), VECTORIZER_PATH
        )
        if os.path.exists(model_full) and os.path.exists(vec_full):
            try:
                self.model = joblib.load(model_full)
                self.vectorizer = joblib.load(vec_full)
                logger.info("Modelo de relevância carregado")
                return
            except Exception:
                logger.warning("Falha ao carregar modelo, usando fallback")

        # Fallback: simple TF-IDF pipeline
        self.vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
        self.model = Pipeline([
            ("tfidf", self.vectorizer),
            ("clf", LogisticRegression(max_iter=500, class_weight="balanced")),
        ])
        logger.info("Modelo de relevância inicializado (fallback)")

    def train(self, texts: list[str], labels: list[int]):
        if len(texts) < 10:
            logger.warning("Poucos exemplos para treino, pulando")
            return
        self.vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
        X = self.vectorizer.fit_transform(texts)
        self.model = LogisticRegression(max_iter=500, class_weight="balanced")
        self.model.fit(X, labels)
        logger.info(f"Modelo de relevância treinado com {len(texts)} exemplos")

        # Save
        base = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        joblib.dump(self.model, os.path.join(base, MODEL_PATH))
        joblib.dump(self.vectorizer, os.path.join(base, VECTORIZER_PATH))
        logger.info("Modelo salvo em disco")

    def train_ranker(self, texts: list[str], labels: list[int], group_sizes: list[int]):
        if not _HAS_LGB:
            logger.warning("LightGBM não instalado, usando LogisticRegression")
            return self.train(texts, labels)
        if len(texts) < 20:
            logger.warning("Poucos exemplos para ranker, pulando")
            return
        self.vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
        X = self.vectorizer.fit_transform(texts)

        train_data = lgb.Dataset(
            X, label=np.array(labels), group=np.array(group_sizes)
        )
        params = {
            "objective": "lambdarank",
            "metric": "ndcg",
            "ndcg_eval_at": [1, 3, 5],
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "verbose": -1,
        }
        self.model = lgb.train(
            params, train_data, num_boost_round=100, valid_sets=[train_data]
        )
        logger.info(f"Ranker LightGBM treinado com {len(texts)} exemplos")

    def score_relevance(self, text: str) -> float:
        if self.model is None:
            return 0.5
        try:
            if _HAS_LGB and hasattr(self.model, "predict"):
                proba = self.model.predict(self.vectorizer.transform([text]))
                return float(proba[0])
            proba = self.model.predict_proba([text])[0]
            return float(proba[1]) if len(proba) > 1 else float(proba[0])
        except Exception:
            return 0.5

    def score_sentiment(self, text: str) -> float:
        simple_keywords_pos = [
            "alta", "crescimento", "lucro", "ganho", "positivo", "valorização",
            "recuperação", "expansão", "otimismo", "recuperacao", "expansao",
            "high", "growth", "profit", "gain", "positive", "optimism",
            "sobe", "sobem", "sobeu", "valorizou", "avanço", "avanco",
            "upside", "recorde", "dividendo", "jcp", "dividend",
        ]
        simple_keywords_neg = [
            "queda", "perda", "negativo", "crise", "risco", "instabilidade",
            "recessão", "baixa", "preocupação", "recessao", "preocupacao",
            "fall", "loss", "negative", "crisis", "risk", "uncertainty",
            "desemprego", "inflação", "inflacao", "juros", "endividamento",
            "default", "calote", "tarifa", "tributo", "imposto",
        ]
        text_lower = text.lower()
        pos_count = sum(1 for kw in simple_keywords_pos if kw in text_lower)
        neg_count = sum(1 for kw in simple_keywords_neg if kw in text_lower)
        total = pos_count + neg_count
        if total == 0:
            return -0.1  # neutral by default, slightly negative
        return (pos_count - neg_count) / total

    def score_impact(self, relevance: float, sentiment: float, has_assets: bool) -> float:
        base = (relevance * 0.5) + (abs(sentiment) * 0.3)
        if has_assets:
            base += 0.2
        return min(1.0, base)

    def score_news(self, news: NewsItem) -> NewsItem:
        text = f"{news.title} {news.content_preview} {news.subtitle or ''}"
        news.relevance_score = self.score_relevance(text)
        news.sentiment_score = self.score_sentiment(text)
        news.impact_score = self.score_impact(
            news.relevance_score, news.sentiment_score, len(news.mentioned_assets) > 0
        )
        return news
