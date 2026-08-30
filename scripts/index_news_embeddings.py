from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.news_ingestion_service import NewsIngestionService
from app.services.news_semantic_service import NewsSemanticService


def main() -> int:
    parser = argparse.ArgumentParser(description="Index Operum news embeddings in Supabase pgvector.")
    parser.add_argument("--force", action="store_true", help="Reindex every selected news item.")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    ingestion = NewsIngestionService()
    items = ingestion.get_all_raw()
    result = NewsSemanticService().index_news(
        items,
        force=args.force,
        batch_size=args.batch_size,
        limit=args.limit,
        dry_run=args.dry_run,
        upload_raw=ingestion.storage.save_item,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"ok", "dry_run"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
