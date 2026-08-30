import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import DATA_DIR, SUPABASE_DB_SCHEMA
from app.db.postgres import PostgresClient


DEFAULT_TOPICS = ["Inflação", "Juros", "Ações", "Exterior"]
USER_NAMESPACE = uuid.UUID("6f035d3f-5279-47c9-a5fc-74eb8a04c23a")


def load_json(path: Path):
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def parse_dt(value: str | None):
    if not value:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def stable_user_uuid(email: str) -> str:
    return str(uuid.uuid5(USER_NAMESPACE, email.strip().lower()))


def main():
    db = PostgresClient(schema=SUPABASE_DB_SCHEMA)
    if not db.enabled:
        raise SystemExit("SUPABASE_DB_URL nao configurada. Configure a connection string primeiro.")

    data_dir = Path(os.environ.get("OPERUM_DATA_DIR") or DATA_DIR)
    users_path = data_dir / "auth" / "users.json"
    sessions_path = data_dir / "auth" / "sessions.json"
    prefs_dir = data_dir / "auth" / "preferences"
    portfolios_dir = data_dir / "portfolios"

    raw_users = load_json(users_path) or []
    raw_sessions = load_json(sessions_path) or []

    user_id_map: dict[str, str] = {}
    email_map: dict[str, dict] = {}
    for item in raw_users:
        email = item["email"].strip().lower()
        user_uuid = stable_user_uuid(email)
        user_id_map[item["id"]] = user_uuid
        email_map[email] = item
        db.execute(
            """
            insert into public.app_users (id, name, email, password_hash, created_at, updated_at)
            values (%s::uuid, %s, %s, %s, %s, %s)
            on conflict (email) do update set
              name = excluded.name,
              password_hash = excluded.password_hash,
              updated_at = excluded.updated_at
            """,
            (
                user_uuid,
                item["name"],
                email,
                item["password_hash"],
                parse_dt(item.get("created_at")),
                parse_dt(item.get("updated_at")),
            ),
        )

    for item in raw_sessions:
        mapped_user_id = user_id_map.get(item.get("user_id"))
        if not mapped_user_id:
            continue
        db.execute(
            """
            insert into public.auth_sessions (token, user_id, created_at)
            values (%s, %s::uuid, %s)
            on conflict (token) do update set
              user_id = excluded.user_id,
              created_at = excluded.created_at
            """,
            (
                item["token"],
                mapped_user_id,
                parse_dt(item.get("created_at")),
            ),
        )

    if prefs_dir.exists():
        for pref_file in prefs_dir.glob("*.json"):
            legacy_user_id = pref_file.stem
            mapped_user_id = user_id_map.get(legacy_user_id)
            if not mapped_user_id:
                continue
            prefs = load_json(pref_file) or {}
            db.execute(
                """
                insert into public.user_preferences (user_id, topics, compact_mode, notifications)
                values (%s::uuid, %s::jsonb, %s, %s)
                on conflict (user_id) do update set
                  topics = excluded.topics,
                  compact_mode = excluded.compact_mode,
                  notifications = excluded.notifications
                """,
                (
                    mapped_user_id,
                    json.dumps(prefs.get("topics") or DEFAULT_TOPICS, ensure_ascii=False),
                    bool(prefs.get("compactMode", False)),
                    bool(prefs.get("notifications", True)),
                ),
            )

    if portfolios_dir.exists():
        for portfolio_file in portfolios_dir.glob("*.json"):
            item = load_json(portfolio_file)
            if not item:
                continue
            owner_id = item.get("owner_id")
            mapped_owner_id = user_id_map.get(owner_id) if owner_id else None
            if mapped_owner_id is None and owner_id is not None:
                continue
            settings = item.get("settings") or {}
            db.execute(
                """
                insert into public.portfolios (
                    id, owner_id, name, base_currency, risk_profile, forecast_horizon_days, created_at, updated_at
                )
                values (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)
                on conflict (id) do update set
                  owner_id = excluded.owner_id,
                  name = excluded.name,
                  base_currency = excluded.base_currency,
                  risk_profile = excluded.risk_profile,
                  forecast_horizon_days = excluded.forecast_horizon_days,
                  updated_at = excluded.updated_at
                """,
                (
                    item["id"],
                    mapped_owner_id,
                    item["name"],
                    item.get("base_currency", "BRL"),
                    settings.get("risk_profile", "moderado"),
                    settings.get("forecast_horizon_days", 5),
                    parse_dt(item.get("created_at")),
                    parse_dt(item.get("updated_at")),
                ),
            )
            for pos in item.get("positions") or []:
                db.execute(
                    """
                    insert into public.portfolio_positions (
                        id, portfolio_id, asset_id, ticker, asset_class, quantity, avg_price, currency, manual_notes,
                        created_at, updated_at
                    )
                    values (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict (portfolio_id, ticker) do update set
                      asset_id = excluded.asset_id,
                      asset_class = excluded.asset_class,
                      quantity = excluded.quantity,
                      avg_price = excluded.avg_price,
                      currency = excluded.currency,
                      manual_notes = excluded.manual_notes,
                      updated_at = excluded.updated_at
                    """,
                    (
                        str(uuid.uuid5(uuid.UUID(item["id"]), pos["ticker"].upper())),
                        item["id"],
                        pos.get("asset_id", pos["ticker"]),
                        pos["ticker"].upper(),
                        pos["asset_class"],
                        pos["quantity"],
                        pos.get("avg_price"),
                        pos.get("currency", "BRL"),
                        pos.get("manual_notes", ""),
                        parse_dt(item.get("created_at")),
                        parse_dt(item.get("updated_at")),
                    ),
                )

    print("Migracao local -> Supabase concluida com sucesso.")


if __name__ == "__main__":
    main()
