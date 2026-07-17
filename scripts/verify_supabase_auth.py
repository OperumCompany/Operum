import asyncio
import sys
import time
from pathlib import Path

from httpx import ASGITransport, AsyncClient

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.db.postgres import PostgresClient
from app.main import app


TEST_PASSWORD = "Operum123"


async def main() -> int:
    db = PostgresClient()
    if not db.enabled:
        print("SKIP: SUPABASE_DB_URL ausente ou OPERUM_STORAGE_MODE=local.")
        return 1

    health = db.healthcheck()
    if health.get("status") != "ok":
        print(f"FAIL: Postgres indisponivel: {health}")
        return 1

    email = f"e2e-auth-{int(time.time())}@operum.app"
    user_id = None
    register_token = None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        try:
            register = await client.post(
                "/api/auth/register",
                json={"name": "E2E Auth Supabase", "email": email, "password": TEST_PASSWORD},
            )
            assert register.status_code == 200, register.text
            register_payload = register.json()
            assert "password_hash" not in register_payload
            register_token = register_payload["token"]
            user_id = register_payload["user"]["id"]

            user_row = db.fetch_one(
                "select id::text as id, email, password_hash from public.app_users where email = %s",
                (email,),
            )
            assert user_row is not None, "Usuario nao encontrado em app_users"
            assert user_row["id"] == user_id
            assert user_row["email"] == email
            assert user_row["password_hash"] and TEST_PASSWORD not in user_row["password_hash"]

            session_row = db.fetch_one(
                "select token, user_id::text as user_id from public.auth_sessions where token = %s",
                (register_token,),
            )
            assert session_row is not None, "Sessao de cadastro nao encontrada em auth_sessions"
            assert session_row["user_id"] == user_id

            me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {register_token}"})
            assert me.status_code == 200, me.text
            assert me.json()["email"] == email
            assert "password_hash" not in me.json()

            invalid_login = await client.post(
                "/api/auth/login",
                json={"email": email, "password": "senha-errada"},
            )
            assert invalid_login.status_code == 401, invalid_login.text

            login = await client.post(
                "/api/auth/login",
                json={"email": email, "password": TEST_PASSWORD},
            )
            assert login.status_code == 200, login.text
            login_token = login.json()["token"]
            assert login_token != register_token

            old_session = db.fetch_one(
                "select token from public.auth_sessions where token = %s",
                (register_token,),
            )
            assert old_session is None, "Login deveria substituir a sessao anterior do usuario"

            logout = await client.post("/api/auth/logout", headers={"Authorization": f"Bearer {login_token}"})
            assert logout.status_code == 200, logout.text
            removed_session = db.fetch_one(
                "select token from public.auth_sessions where token = %s",
                (login_token,),
            )
            assert removed_session is None, "Logout nao removeu sessao"

            for table in ["app_users", "auth_sessions", "user_preferences", "portfolios", "portfolio_positions"]:
                rls = db.fetch_one(
                    """
                    select c.relrowsecurity, coalesce(count(p.polname), 0) as policy_count
                    from pg_class c
                    join pg_namespace n on n.oid = c.relnamespace
                    left join pg_policy p on p.polrelid = c.oid
                    where n.nspname = 'public' and c.relname = %s
                    group by c.relrowsecurity
                    """,
                    (table,),
                )
                assert rls and rls["relrowsecurity"] is True, f"RLS nao esta ativo em {table}"

            print("OK: cadastro, login, sessao, logout e RLS validados no Supabase.")
            return 0
        finally:
            if user_id:
                db.execute("delete from public.app_users where id = %s::uuid", (user_id,))
            else:
                db.execute("delete from public.app_users where email = %s", (email,))


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
