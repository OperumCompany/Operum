from __future__ import annotations

import json
import logging
import threading
from urllib.parse import quote

import requests

from app.core.config import (
    NEWS_RAW_BUCKET,
    NEWS_RAW_STORAGE,
    SUPABASE_SECRET_KEY,
    SUPABASE_URL,
)
from app.schemas.news import NewsItem
from app.services.local_storage_service import LocalStorageService

logger = logging.getLogger(__name__)


class NewsRawStorageService:
    def __init__(self):
        self.local = LocalStorageService()
        self.mode = NEWS_RAW_STORAGE if NEWS_RAW_STORAGE in {"local", "supabase"} else "local"
        self.bucket = NEWS_RAW_BUCKET
        self.base_url = SUPABASE_URL.rstrip("/")
        self.secret_key = SUPABASE_SECRET_KEY.strip()
        self._bucket_ready = False
        self._bucket_lock = threading.Lock()

    @property
    def remote_enabled(self) -> bool:
        return self.mode == "supabase" and bool(self.base_url and self.secret_key and self.bucket)

    def _headers(self, content_type: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self.secret_key,
            "Authorization": f"Bearer {self.secret_key}",
        }
        if content_type:
            headers["Content-Type"] = content_type
        return headers

    def ensure_bucket(self) -> bool:
        if not self.remote_enabled:
            return False
        if self._bucket_ready:
            return True
        with self._bucket_lock:
            if self._bucket_ready:
                return True
            existing = requests.get(
                f"{self.base_url}/storage/v1/bucket/{quote(self.bucket, safe='')}",
                headers=self._headers(),
                timeout=15,
            )
            if existing.status_code == 200:
                self._bucket_ready = True
                return True
            response = requests.post(
                f"{self.base_url}/storage/v1/bucket",
                headers=self._headers("application/json"),
                json={"id": self.bucket, "name": self.bucket, "public": False},
                timeout=15,
            )
            if response.status_code in {200, 201, 409}:
                self._bucket_ready = True
                return True
            logger.warning("Falha ao preparar bucket de noticias: status=%s", response.status_code)
            return False

    def _upload_json(self, path: str, payload: dict | list) -> bool:
        if not self.remote_enabled:
            return False
        encoded_path = quote(path.replace("\\", "/").lstrip("/"), safe="/")
        response = requests.post(
            f"{self.base_url}/storage/v1/object/{quote(self.bucket, safe='')}/{encoded_path}",
            headers={**self._headers("application/json"), "x-upsert": "true"},
            data=json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8"),
            timeout=30,
        )
        if response.status_code in {200, 201}:
            return True
        logger.warning(
            "Falha ao salvar noticia no Supabase Storage: path=%s status=%s",
            path,
            response.status_code,
        )
        return False

    def _download_json(self, path: str) -> dict | list | None:
        if not self.remote_enabled:
            return None
        encoded_path = quote(path.replace("\\", "/").lstrip("/"), safe="/")
        response = requests.get(
            f"{self.base_url}/storage/v1/object/{quote(self.bucket, safe='')}/{encoded_path}",
            headers=self._headers(),
            timeout=30,
        )
        if response.status_code == 200:
            return response.json()
        if response.status_code not in {400, 404}:
            logger.warning(
                "Falha ao carregar noticia do Supabase Storage: path=%s status=%s",
                path,
                response.status_code,
            )
        return None

    def save_json(self, path: str, payload: dict | list) -> None:
        self.local.save_json(path, payload)
        if self.remote_enabled and self.ensure_bucket():
            self._upload_json(path, payload)

    def load_json(self, path: str) -> dict | list | None:
        if self.remote_enabled:
            remote = self._download_json(path)
            if remote is not None:
                return remote
        return self.local.load_json(path)

    @staticmethod
    def item_path(news: NewsItem) -> str:
        published = news.published_at
        return f"news/raw/items/{published:%Y}/{published:%m}/{news.id}.json"

    def save_item(self, news: NewsItem) -> str:
        path = self.item_path(news)
        self.local.save_json(path, news.model_dump(mode="json"))
        if self.remote_enabled:
            self.upload_item(news)
        return path

    def upload_item(self, news: NewsItem) -> bool:
        if not self.remote_enabled or not self.ensure_bucket():
            return False
        return self._upload_json(self.item_path(news), news.model_dump(mode="json"))

    def healthcheck(self) -> dict:
        if not self.remote_enabled:
            return {"mode": self.mode, "remote_enabled": False, "status": "local"}
        try:
            response = requests.get(
                f"{self.base_url}/storage/v1/bucket/{quote(self.bucket, safe='')}",
                headers=self._headers(),
                timeout=10,
            )
            return {
                "mode": self.mode,
                "remote_enabled": True,
                "bucket": self.bucket,
                "status": "ok" if response.status_code == 200 else "error",
            }
        except requests.RequestException as exc:
            return {
                "mode": self.mode,
                "remote_enabled": True,
                "bucket": self.bucket,
                "status": "error",
                "error": str(exc),
            }
