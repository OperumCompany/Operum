from __future__ import annotations

import threading

from app.core.config import (
    NEWS_EMBEDDING_DIMENSIONS,
    NEWS_EMBEDDING_MODEL,
    NEWS_EMBEDDINGS_ENABLED,
)


class EmbeddingService:
    _models: dict[str, object] = {}
    _model_lock = threading.Lock()

    def __init__(self):
        self.enabled = NEWS_EMBEDDINGS_ENABLED
        self.model_name = NEWS_EMBEDDING_MODEL
        self.dimensions = NEWS_EMBEDDING_DIMENSIONS

    def _get_model(self):
        if not self.enabled:
            raise RuntimeError("Embeddings are disabled")
        if self.model_name not in self.__class__._models:
            with self.__class__._model_lock:
                if self.model_name not in self.__class__._models:
                    from sentence_transformers import SentenceTransformer

                    self.__class__._models[self.model_name] = SentenceTransformer(self.model_name)
        return self.__class__._models[self.model_name]

    def encode_passages(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._get_model().encode(
            [f"passage: {text.strip()}" for text in texts],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        result = [vector.astype(float).tolist() for vector in vectors]
        self._validate(result)
        return result

    def encode_query(self, query: str) -> list[float]:
        vectors = self._get_model().encode(
            [f"query: {query.strip()}"],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        result = vectors[0].astype(float).tolist()
        self._validate([result])
        return result

    def _validate(self, vectors: list[list[float]]) -> None:
        if any(len(vector) != self.dimensions for vector in vectors):
            raise ValueError(f"Embedding dimension mismatch: expected {self.dimensions}")
