from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["NEWS_RAW_STORAGE"] = "supabase"

from app.services.news_ingestion_service import NewsIngestionService
from app.services.news_raw_storage_service import NewsRawStorageService


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy local raw news to the private Supabase Storage bucket."
    )
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ingestion = NewsIngestionService()
    storage = NewsRawStorageService()
    items = ingestion.get_all_raw()
    if args.limit:
        items = items[: args.limit]
    if args.dry_run:
        print(json.dumps({"status": "dry_run", "pending": len(items)}, indent=2))
        return 0
    if not storage.remote_enabled or not storage.ensure_bucket():
        print(json.dumps({"status": "error", "reason": "storage_unavailable"}))
        return 1

    uploaded = 0
    failed = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {executor.submit(storage.upload_item, item): item.id for item in items}
        for future in as_completed(futures):
            news_id = futures[future]
            try:
                if future.result():
                    uploaded += 1
                else:
                    failed.append({"id": news_id, "error": "upload_failed"})
            except Exception as exc:
                failed.append({"id": news_id, "error": str(exc)})

    for path in ("news/raw/archive.json", "news/raw/latest.json", "news/raw/meta.json"):
        payload = storage.local.load_json(path)
        if payload is not None:
            storage._upload_json(path, payload)

    print(
        json.dumps(
            {
                "status": "ok" if not failed else "partial",
                "uploaded": uploaded,
                "failed": len(failed),
                "failure_samples": failed[:10],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
