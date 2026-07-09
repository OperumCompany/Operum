import os
import logging
import sys
from pathlib import Path


def _load_local_env() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    env_path = repo_root / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value and ((value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'"))):
            value = value[1:-1]
        os.environ.setdefault(key, value)


_load_local_env()

DATA_DIR = os.environ.get("OPERUM_DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data"))
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",")
API_PREFIX = "/api"
SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_PUBLISHABLE_KEY = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
SUPABASE_SECRET_KEY = os.environ.get("SUPABASE_SECRET_KEY", "")
SUPABASE_DB_SCHEMA = os.environ.get("SUPABASE_DB_SCHEMA", "public")
SUPABASE_DB_URL = os.environ.get("SUPABASE_DB_URL", "")
OPERUM_STORAGE_MODE = os.environ.get("OPERUM_STORAGE_MODE", "auto")
OPERUM_ENABLE_NEWS_INGEST_ON_STARTUP = os.environ.get("OPERUM_ENABLE_NEWS_INGEST_ON_STARTUP", "true").lower() == "true"
OPERUM_ENABLE_NEWS_BACKFILL_ON_STARTUP = os.environ.get("OPERUM_ENABLE_NEWS_BACKFILL_ON_STARTUP", "true").lower() == "true"
OPERUM_ENABLE_PRICE_WARMUP_ON_STARTUP = os.environ.get("OPERUM_ENABLE_PRICE_WARMUP_ON_STARTUP", "true").lower() == "true"
OPERUM_SEED_DEMO_USER = os.environ.get("OPERUM_SEED_DEMO_USER", "true").lower() == "true"

LOG_DIR = os.path.join(DATA_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "operum.log"), encoding="utf-8"),
    ],
)
