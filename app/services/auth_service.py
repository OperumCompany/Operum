import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timezone

from app.core.config import OPERUM_SEED_DEMO_USER, SUPABASE_DB_SCHEMA
from app.db.postgres import PostgresClient
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    PasswordUpdateRequest,
    RegisterRequest,
    UserPreferences,
    UserPublic,
    UserRecord,
)
from app.services.local_storage_service import LocalStorageService


class AuthService:
    def __init__(self):
        self.storage = LocalStorageService()
        self.db = PostgresClient(schema=SUPABASE_DB_SCHEMA)
        self._users_path = "auth/users.json"
        self._sessions_path = "auth/sessions.json"
        self._preferences_dir = "auth/preferences"
        self._demo_email = "demo@operum.app"
        self._demo_password = "Operum123"

    def _ensure_seed_user(self, users: list[UserRecord]) -> list[UserRecord]:
        if not OPERUM_SEED_DEMO_USER:
            return users
        if any(user.email == self._demo_email for user in users):
            return users

        now = datetime.now(timezone.utc)
        users.append(UserRecord(
            id=secrets.token_hex(16),
            name="Demo Operum",
            email=self._demo_email,
            password_hash=self._hash_password(self._demo_password),
            created_at=now,
            updated_at=now,
        ))
        self._save_users(users)
        return users

    def _load_users(self) -> list[UserRecord]:
        if self.db.enabled:
            if OPERUM_SEED_DEMO_USER:
                self._ensure_seed_user_db()
            rows = self.db.fetch_all(
                """
                select id::text as id, name, email, password_hash, created_at, updated_at
                from public.app_users
                order by created_at asc
                """
            )
            return [UserRecord(**item) for item in rows]
        raw = self.storage.load_json(self._users_path) or []
        users = [UserRecord(**item) for item in raw]
        return self._ensure_seed_user(users)

    def _save_users(self, users: list[UserRecord]) -> None:
        if self.db.enabled:
            for user in users:
                self.db.execute(
                    """
                    insert into public.app_users (id, name, email, password_hash, created_at, updated_at)
                    values (%s::uuid, %s, %s, %s, %s, %s)
                    on conflict (id) do update set
                      name = excluded.name,
                      email = excluded.email,
                      password_hash = excluded.password_hash,
                      updated_at = excluded.updated_at
                    """,
                    (user.id, user.name, user.email, user.password_hash, user.created_at, user.updated_at),
                )
            return
        self.storage.save_json(self._users_path, [user.model_dump(mode="json") for user in users])

    def _load_sessions(self) -> list[dict]:
        if self.db.enabled:
            return self.db.fetch_all(
                """
                select token, user_id::text as user_id, created_at
                from public.auth_sessions
                order by created_at asc
                """
            )
        return list(self.storage.load_json(self._sessions_path) or [])

    def _save_sessions(self, sessions: list[dict]) -> None:
        if self.db.enabled:
            existing = {item["token"] for item in self._load_sessions()}
            next_tokens = {item["token"] for item in sessions}
            tokens_to_delete = existing - next_tokens
            if tokens_to_delete:
                self.db.execute(
                    "delete from public.auth_sessions where token = any(%s)",
                    (list(tokens_to_delete),),
                )
            for session in sessions:
                self.db.execute(
                    """
                    insert into public.auth_sessions (token, user_id, created_at)
                    values (%s, %s::uuid, %s)
                    on conflict (token) do update set
                      user_id = excluded.user_id,
                      created_at = excluded.created_at
                    """,
                    (session["token"], session["user_id"], session["created_at"]),
                )
            return
        self.storage.save_json(self._sessions_path, sessions)

    def _hash_password(self, password: str, salt: str | None = None) -> str:
        password = password.strip()
        salt = salt or secrets.token_hex(16)
        derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 150000)
        return f"{salt}${derived.hex()}"

    def _verify_password(self, password: str, password_hash: str) -> bool:
        try:
            salt, current_hash = password_hash.split("$", 1)
        except ValueError:
            return False
        candidate = self._hash_password(password, salt).split("$", 1)[1]
        return hmac.compare_digest(candidate, current_hash)

    def _to_public(self, user: UserRecord) -> UserPublic:
        return UserPublic(
            id=user.id,
            name=user.name,
            email=user.email,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    def _ensure_seed_user_db(self) -> None:
        row = self.db.fetch_one("select id from public.app_users where email = %s", (self._demo_email,))
        if row:
            return
        now = datetime.now(timezone.utc)
        self.db.execute(
            """
            insert into public.app_users (id, name, email, password_hash, created_at, updated_at)
            values (%s::uuid, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid.uuid4()),
                "Demo Operum",
                self._demo_email,
                self._hash_password(self._demo_password),
                now,
                now,
            ),
        )

    def register(self, data: RegisterRequest) -> AuthResponse:
        users = self._load_users()
        email = data.email.strip().lower()
        if any(user.email == email for user in users):
            raise ValueError("Ja existe uma conta cadastrada com este e-mail.")

        now = datetime.now(timezone.utc)
        user = UserRecord(
            id=str(uuid.uuid4()) if self.db.enabled else secrets.token_hex(16),
            name=data.name.strip(),
            email=email,
            password_hash=self._hash_password(data.password),
            created_at=now,
            updated_at=now,
        )
        users.append(user)
        self._save_users(users)
        return self._create_session(user)

    def login(self, data: LoginRequest) -> AuthResponse:
        email = data.email.strip().lower()
        users = self._load_users()
        user = next((candidate for candidate in users if candidate.email == email), None)
        if user is None or not self._verify_password(data.password, user.password_hash):
            raise ValueError("Credenciais invalidas.")
        user.updated_at = datetime.now(timezone.utc)
        self._save_users(users)
        return self._create_session(user)

    def _create_session(self, user: UserRecord) -> AuthResponse:
        token = secrets.token_urlsafe(32)
        sessions = self._load_sessions()
        sessions = [session for session in sessions if session.get("user_id") != user.id]
        sessions.append({
            "token": token,
            "user_id": user.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        self._save_sessions(sessions)
        return AuthResponse(token=token, user=self._to_public(user))

    def logout(self, token: str) -> None:
        sessions = self._load_sessions()
        sessions = [session for session in sessions if session.get("token") != token]
        self._save_sessions(sessions)

    def get_user_by_token(self, token: str) -> UserPublic | None:
        sessions = self._load_sessions()
        session = next((item for item in sessions if item.get("token") == token), None)
        if session is None:
            return None
        users = self._load_users()
        user = next((candidate for candidate in users if candidate.id == session.get("user_id")), None)
        return self._to_public(user) if user else None

    def get_user_record_by_token(self, token: str) -> UserRecord | None:
        sessions = self._load_sessions()
        session = next((item for item in sessions if item.get("token") == token), None)
        if session is None:
            return None
        users = self._load_users()
        return next((candidate for candidate in users if candidate.id == session.get("user_id")), None)

    def update_password(self, token: str, data: PasswordUpdateRequest) -> UserPublic:
        users = self._load_users()
        record = self.get_user_record_by_token(token)
        if record is None:
            raise ValueError("Sessao invalida.")
        if not self._verify_password(data.current_password, record.password_hash):
            raise ValueError("Senha atual incorreta.")

        updated_users: list[UserRecord] = []
        for user in users:
            if user.id == record.id:
                user.password_hash = self._hash_password(data.new_password)
                user.updated_at = datetime.now(timezone.utc)
                record = user
            updated_users.append(user)
        self._save_users(updated_users)
        return self._to_public(record)

    def get_preferences(self, user_id: str) -> UserPreferences:
        if self.db.enabled:
            raw = self.db.fetch_one(
                """
                select topics, compact_mode, notifications
                from public.user_preferences
                where user_id = %s::uuid
                """,
                (user_id,),
            )
            if not raw:
                return UserPreferences(
                    topics=["InflaÃ§Ã£o", "Juros", "AÃ§Ãµes", "Exterior"],
                    compactMode=False,
                    notifications=True,
                )
            return UserPreferences(
                topics=raw.get("topics") or [],
                compactMode=bool(raw.get("compact_mode")),
                notifications=bool(raw.get("notifications")),
            )
        raw = self.storage.load_json(f"{self._preferences_dir}/{user_id}.json")
        if not raw:
            return UserPreferences(
                topics=["Inflação", "Juros", "Ações", "Exterior"],
                compactMode=False,
                notifications=True,
            )
        return UserPreferences(**raw)

    def update_preferences(self, user_id: str, prefs: UserPreferences) -> UserPreferences:
        if self.db.enabled:
            self.db.execute(
                """
                insert into public.user_preferences (user_id, topics, compact_mode, notifications)
                values (%s::uuid, %s::jsonb, %s, %s)
                on conflict (user_id) do update set
                  topics = excluded.topics,
                  compact_mode = excluded.compact_mode,
                  notifications = excluded.notifications
                """,
                (user_id, json.dumps(prefs.topics, ensure_ascii=False), prefs.compactMode, prefs.notifications),
            )
            return prefs
        self.storage.save_json(f"{self._preferences_dir}/{user_id}.json", prefs.model_dump(mode="json"))
        return prefs
