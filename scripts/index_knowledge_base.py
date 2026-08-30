from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.knowledge_service import KnowledgeService


def main() -> int:
    parser = argparse.ArgumentParser(description="Index the Operum financial knowledge base in Supabase pgvector.")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--category", default=None)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    result = KnowledgeService().index(
        force=args.force,
        dry_run=args.dry_run,
        category=args.category,
        limit=args.limit,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") in {"ok", "dry_run", "disabled"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
