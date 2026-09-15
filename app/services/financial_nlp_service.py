from __future__ import annotations

import logging
import hashlib
import json
from pathlib import Path
from typing import Callable

import numpy as np
from sklearn.metrics import accuracy_score, f1_score

from app.services.news_scoring_service import NewsScoringService

logger = logging.getLogger(__name__)
APPROVED_MODEL_LICENSES = {
    "apache-2.0",
    "mit",
    "bsd",
    "bsd-2-clause",
    "bsd-3-clause",
    "cc-by-4.0",
}


def audit_offline_model(model_name: str) -> dict:
    try:
        from huggingface_hub import snapshot_download

        path = Path(snapshot_download(model_name, local_files_only=True))
    except Exception as exc:
        return {"available_offline": False, "license": None, "checksum": None, "error": str(exc)}
    license_name = None
    config_path = path / "config.json"
    if config_path.exists():
        license_name = json.loads(config_path.read_text(encoding="utf-8")).get("license")
    readme = path / "README.md"
    if not license_name and readme.exists():
        for line in readme.read_text(encoding="utf-8-sig", errors="replace").splitlines()[:50]:
            if line.lower().startswith("license:"):
                license_name = line.split(":", 1)[1].strip()
                break
    digest = hashlib.sha256()
    files = sorted(item for item in path.rglob("*") if item.is_file())
    for item in files:
        digest.update(str(item.relative_to(path)).replace("\\", "/").encode("utf-8"))
        digest.update(hashlib.sha256(item.read_bytes()).digest())
    return {
        "available_offline": True,
        "license": license_name,
        "license_verified": bool(license_name),
        "license_approved": str(license_name or "").lower() in APPROVED_MODEL_LICENSES,
        "checksum": digest.hexdigest(),
        "files": len(files),
    }


def _default_pipeline_loader(*args, **kwargs):
    from transformers import pipeline

    return pipeline(*args, **kwargs)


def benchmark_predictions(records: list[dict], predictions: list[str]) -> dict:
    if len(records) != len(predictions):
        raise ValueError("Quantidade de previsoes difere do conjunto de referencia")
    if not records or any(item.get("review_status") != "reviewed" for item in records):
        raise ValueError("O benchmark exige rotulos integralmente revisados")
    truth = [str(item["label"]).lower() for item in records]
    predicted = [str(value).lower() for value in predictions]
    return {
        "samples": len(records),
        "accuracy": round(float(accuracy_score(truth, predicted)), 6),
        "macro_f1": round(float(f1_score(truth, predicted, average="macro", zero_division=0)), 6),
    }


class FinancialNLPService:
    def __init__(
        self,
        model_name: str,
        *,
        pipeline_loader: Callable | None = None,
    ):
        self.model_name = model_name
        self.pipeline_loader = pipeline_loader or _default_pipeline_loader
        self._classifier = None
        self._load_attempted = False
        self._fallback = NewsScoringService()

    def _load(self):
        if self._load_attempted:
            return self._classifier
        self._load_attempted = True
        try:
            from huggingface_hub import snapshot_download

            local_path = snapshot_download(self.model_name, local_files_only=True)
            self._classifier = self.pipeline_loader(
                "text-classification",
                model=local_path,
                tokenizer=local_path,
                model_kwargs={"local_files_only": True},
                device=-1,
            )
        except Exception as exc:
            logger.info("Modelo NLP financeiro nao disponivel offline (%s): %s", self.model_name, exc)
            self._classifier = None
        return self._classifier

    @staticmethod
    def _normalize_label(label: str) -> str:
        normalized = label.lower()
        if "pos" in normalized:
            return "positive"
        if "neg" in normalized:
            return "negative"
        return "neutral"

    def score(self, text: str) -> dict:
        classifier = self._load()
        if classifier is None:
            score = float(np.clip(self._fallback.score_sentiment(text), -1.0, 1.0))
            label = "positive" if score > 0.1 else "negative" if score < -0.1 else "neutral"
            return {
                "label": label,
                "sentiment_score": round(score, 6),
                "confidence": 0.0,
                "source": "deterministic_fallback",
                "model": None,
            }
        raw = classifier(text, truncation=True, max_length=256)
        item = raw[0] if isinstance(raw, list) else raw
        label = self._normalize_label(str(item.get("label", "neutral")))
        confidence = float(np.clip(item.get("score", 0.0), 0.0, 1.0))
        signed = confidence if label == "positive" else -confidence if label == "negative" else 0.0
        return {
            "label": label,
            "sentiment_score": round(signed, 6),
            "confidence": round(confidence, 6),
            "source": "financial_nlp",
            "model": self.model_name,
        }

    def predict_labels(self, records: list[dict]) -> list[str]:
        return [self.score(str(item["text"]))["label"] for item in records]
