import json
import os
import pandas as pd
from datetime import datetime


class LocalStorageService:
    def __init__(self, base_dir: str = None):
        if base_dir is None:
            base_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
        self.base_dir = base_dir

    def _ensure_dir(self, path: str):
        full = os.path.join(self.base_dir, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        return full

    def save_json(self, path: str, data: dict | list) -> None:
        full = self._ensure_dir(path)
        with open(full, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    def load_json(self, path: str) -> dict | list | None:
        full = os.path.join(self.base_dir, path)
        if not os.path.exists(full):
            return None
        with open(full, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_dataframe(self, path: str, df: pd.DataFrame) -> None:
        full = self._ensure_dir(path)
        df.to_parquet(full, index=False)

    def load_dataframe(self, path: str) -> pd.DataFrame | None:
        full = os.path.join(self.base_dir, path)
        if not os.path.exists(full):
            return None
        return pd.read_parquet(full)

    def append_event(self, path: str, event: dict) -> None:
        existing = self.load_json(path)
        if existing is None:
            existing = []
        existing.append(event)
        self.save_json(path, existing)

    def list_files(self, path: str, extension: str = ".json") -> list[str]:
        full = os.path.join(self.base_dir, path)
        if not os.path.exists(full):
            return []
        return sorted([
            f for f in os.listdir(full)
            if f.endswith(extension)
        ])

    def delete_file(self, path: str) -> bool:
        full = os.path.join(self.base_dir, path)
        if os.path.exists(full):
            os.remove(full)
            return True
        return False
