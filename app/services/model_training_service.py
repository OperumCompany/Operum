import logging
import os
import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

try:
    import lightgbm as lgb
    _HAS_LGB = True
except ImportError:
    _HAS_LGB = False

from app.services.news_ingestion_service import NewsIngestionService
from app.services.forecast_service import ForecastService

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "models"
)
DATASET_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "datasets",
    "train",
)


class ModelTrainingService:
    def __init__(self):
        self.news_service = NewsIngestionService()
        self.forecast_service = ForecastService()

    def train_news_model(self) -> dict:
        all_news = self.news_service.get_all_raw()
        if len(all_news) < 10:
            return {"status": "error", "error": "Poucas notícias para treino"}

        texts = [
            f"{n.title} {n.content_preview} {n.subtitle or ''}" for n in all_news
        ]

        # Generate labels based on impact_score > 0.5 as positive
        labels = [1 if n.impact_score >= 0.5 else 0 for n in all_news]

        vectorizer = TfidfVectorizer(max_features=5000, ngram_range=(1, 2))
        X = vectorizer.fit_transform(texts)

        model = LogisticRegression(max_iter=500, class_weight="balanced")
        model.fit(X, labels)
        accuracy = float(model.score(X, labels))

        os.makedirs(MODEL_DIR, exist_ok=True)
        joblib.dump(
            model,
            os.path.join(MODEL_DIR, "news_relevance.pkl"),
        )
        joblib.dump(
            vectorizer,
            os.path.join(MODEL_DIR, "news_vectorizer.pkl"),
        )

        return {
            "status": "trained",
            "model_type": "logistic_regression",
            "samples": len(texts),
            "accuracy": round(accuracy, 4),
        }

    def train_forecast_batch(self, tickers: list[str]) -> dict:
        results = {}
        for ticker in tickers:
            result = self.forecast_service.train(ticker)
            results[ticker] = result
        return {
            "status": "batch_complete",
            "total": len(tickers),
            "results": results,
        }

    def get_training_history(self) -> list[dict]:
        history_path = os.path.join(MODEL_DIR, "training_history.json")
        try:
            import json
            with open(history_path) as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def log_training(self, record: dict):
        history = self.get_training_history()
        history.append(record)
        os.makedirs(MODEL_DIR, exist_ok=True)
        import json
        with open(os.path.join(MODEL_DIR, "training_history.json"), "w") as f:
            json.dump(history[-100:], f, default=str)
