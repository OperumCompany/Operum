"""Protege tabelas internas expostas no schema public do Supabase.

O backend acessa o banco com a conexao de servidor. Clientes anonimos e
autenticados do PostgREST nao devem ter acesso direto a estas tabelas.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.postgres import PostgresClient


SECURITY_TABLES = (
    "portfolio_transactions",
    "model_versions",
    "asset_analysis_snapshots",
    "analysis_jobs",
    "prediction_outcomes",
)

SECURITY_SQL = """
do $$
declare
  target_table text;
begin
  foreach target_table in array array[
    'portfolio_transactions',
    'model_versions',
    'asset_analysis_snapshots',
    'analysis_jobs',
    'prediction_outcomes'
  ] loop
    if to_regclass(format('public.%%I', target_table)) is not null then
      execute format('alter table public.%%I enable row level security', target_table);
      execute format('revoke all privileges on table public.%%I from anon, authenticated', target_table);
    end if;
  end loop;
end;
$$;
"""


def security_rows(db: PostgresClient) -> list[dict]:
    return db.fetch_all(
        """
        select c.relname, c.relrowsecurity,
               has_table_privilege('anon', c.oid, 'select,insert,update,delete') as anon_has_access,
               has_table_privilege('authenticated', c.oid, 'select,insert,update,delete') as authenticated_has_access
        from pg_class c
        join pg_namespace n on n.oid = c.relnamespace
        where n.nspname = 'public' and c.relname = any(%s)
        order by c.relname
        """,
        (list(SECURITY_TABLES),),
    )


def main() -> int:
    db = PostgresClient()
    if not db.enabled:
        print("SKIP: SUPABASE_DB_URL ausente ou OPERUM_STORAGE_MODE=local.")
        return 1

    db.execute(SECURITY_SQL)
    rows = security_rows(db)
    rows_by_name = {row["relname"]: row for row in rows}
    missing = set(SECURITY_TABLES) - set(rows_by_name)
    insecure = [
        name for name, row in rows_by_name.items()
        if not row["relrowsecurity"] or row["anon_has_access"] or row["authenticated_has_access"]
    ]
    if missing or insecure:
        print(f"FAIL: tabelas ausentes={sorted(missing)}, inseguras={sorted(insecure)}")
        return 1

    print("OK: RLS ativo e privilegios de anon/authenticated revogados em:")
    for name in SECURITY_TABLES:
        print(f"  - public.{name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
