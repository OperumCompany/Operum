from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from app.core.config import SUPABASE_DB_SCHEMA
from app.db.postgres import PostgresClient
from app.schemas.chat import ChatConversation, ChatSource, StoredChatMessage
from app.services.local_storage_service import LocalStorageService


class ChatRepository:
    def __init__(self, db: PostgresClient | None = None):
        self.db = db or PostgresClient(schema=SUPABASE_DB_SCHEMA)
        self.storage = LocalStorageService()

    def _path(self, owner_id: str) -> str:
        return f"chat/{owner_id}.json"

    def _load_local(self, owner_id: str) -> dict:
        return self.storage.load_json(self._path(owner_id)) or {"conversations": [], "messages": []}

    def _save_local(self, owner_id: str, data: dict) -> None:
        self.storage.save_json(self._path(owner_id), data)

    @staticmethod
    def _conversation(row: dict) -> ChatConversation:
        return ChatConversation(**row)

    @staticmethod
    def _message(row: dict) -> StoredChatMessage:
        if isinstance(row.get("sources"), str):
            row["sources"] = json.loads(row["sources"])
        if isinstance(row.get("retrieval"), str):
            row["retrieval"] = json.loads(row["retrieval"])
        return StoredChatMessage(**row)

    def list_conversations(self, owner_id: str) -> list[ChatConversation]:
        if self.db.enabled:
            rows = self.db.fetch_all(
                """
                select c.id::text, c.owner_id::text, c.title, c.summary,
                       c.portfolio_id::text, c.use_all_portfolios, c.created_at, c.updated_at,
                       count(m.id)::integer as message_count
                from public.chat_conversations c
                left join public.chat_messages m on m.conversation_id = c.id
                where c.owner_id = %s::uuid
                group by c.id
                order by c.updated_at desc
                limit 100
                """,
                (owner_id,),
            )
            return [self._conversation(row) for row in rows]
        data = self._load_local(owner_id)
        counts = {}
        for message in data["messages"]:
            counts[message["conversation_id"]] = counts.get(message["conversation_id"], 0) + 1
        rows = [{**row, "message_count": counts.get(row["id"], 0)} for row in data["conversations"]]
        return sorted((self._conversation(row) for row in rows), key=lambda item: item.updated_at, reverse=True)

    def get_conversation(self, conversation_id: str, owner_id: str) -> ChatConversation | None:
        if self.db.enabled:
            row = self.db.fetch_one(
                """
                select c.id::text, c.owner_id::text, c.title, c.summary,
                       c.portfolio_id::text, c.use_all_portfolios, c.created_at, c.updated_at,
                       count(m.id)::integer as message_count
                from public.chat_conversations c
                left join public.chat_messages m on m.conversation_id = c.id
                where c.id = %s::uuid and c.owner_id = %s::uuid
                group by c.id
                """,
                (conversation_id, owner_id),
            )
            return self._conversation(row) if row else None
        return next((item for item in self.list_conversations(owner_id) if item.id == conversation_id), None)

    def get_conversation_with_messages(
        self, conversation_id: str, owner_id: str, message_limit: int = 8,
    ) -> tuple[ChatConversation | None, list[StoredChatMessage]]:
        if not self.db.enabled:
            conversation = self.get_conversation(conversation_id, owner_id)
            return conversation, self.list_messages(conversation_id, owner_id) if conversation else []
        with self.db.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    select c.id::text, c.owner_id::text, c.title, c.summary,
                           c.portfolio_id::text, c.use_all_portfolios, c.created_at, c.updated_at,
                           (select count(*)::integer from public.chat_messages m where m.conversation_id = c.id) as message_count
                    from public.chat_conversations c
                    where c.id = %s::uuid and c.owner_id = %s::uuid
                    """,
                    (conversation_id, owner_id),
                )
                row = cur.fetchone()
                if row is None:
                    return None, []
                cur.execute(
                    """
                    select id::text, conversation_id::text, role, content, mode, sources, retrieval, created_at
                    from (
                      select * from public.chat_messages
                      where conversation_id = %s::uuid order by created_at desc limit %s
                    ) recent order by created_at asc
                    """,
                    (conversation_id, message_limit),
                )
                messages = [self._message(item) for item in cur.fetchall()]
        return self._conversation(row), messages

    def create_conversation(
        self, owner_id: str, title: str = "Nova conversa", portfolio_id: str | None = None,
        use_all_portfolios: bool = False,
    ) -> ChatConversation:
        now = datetime.now(timezone.utc)
        conversation = ChatConversation(
            id=str(uuid.uuid4()), owner_id=owner_id, title=title.strip() or "Nova conversa",
            portfolio_id=portfolio_id, use_all_portfolios=use_all_portfolios,
            created_at=now, updated_at=now,
        )
        if self.db.enabled:
            self.db.execute(
                """
                insert into public.chat_conversations
                  (id, owner_id, title, portfolio_id, use_all_portfolios, created_at, updated_at)
                values (%s::uuid, %s::uuid, %s, %s::uuid, %s, %s, %s)
                """,
                (conversation.id, owner_id, conversation.title, portfolio_id,
                 use_all_portfolios, now, now),
            )
        else:
            data = self._load_local(owner_id)
            data["conversations"].append(conversation.model_dump(mode="json"))
            self._save_local(owner_id, data)
        return conversation

    def update_title(self, conversation_id: str, owner_id: str, title: str) -> ChatConversation | None:
        conversation = self.get_conversation(conversation_id, owner_id)
        if not conversation:
            return None
        title = title.strip()[:100] or "Nova conversa"
        now = datetime.now(timezone.utc)
        if self.db.enabled:
            self.db.execute(
                "update public.chat_conversations set title = %s, updated_at = %s where id = %s::uuid and owner_id = %s::uuid",
                (title, now, conversation_id, owner_id),
            )
        else:
            data = self._load_local(owner_id)
            for row in data["conversations"]:
                if row["id"] == conversation_id:
                    row.update({"title": title, "updated_at": now.isoformat()})
            self._save_local(owner_id, data)
        return self.get_conversation(conversation_id, owner_id)

    def update_summary(self, conversation_id: str, owner_id: str, summary: str) -> None:
        if self.db.enabled:
            self.db.execute(
                "update public.chat_conversations set summary = %s where id = %s::uuid and owner_id = %s::uuid",
                (summary, conversation_id, owner_id),
            )
            return
        data = self._load_local(owner_id)
        for row in data["conversations"]:
            if row["id"] == conversation_id:
                row["summary"] = summary
        self._save_local(owner_id, data)

    def delete_conversation(self, conversation_id: str, owner_id: str) -> bool:
        if not self.get_conversation(conversation_id, owner_id):
            return False
        if self.db.enabled:
            self.db.execute(
                "delete from public.chat_conversations where id = %s::uuid and owner_id = %s::uuid",
                (conversation_id, owner_id),
            )
        else:
            data = self._load_local(owner_id)
            data["conversations"] = [row for row in data["conversations"] if row["id"] != conversation_id]
            data["messages"] = [row for row in data["messages"] if row["conversation_id"] != conversation_id]
            self._save_local(owner_id, data)
        return True

    def list_messages(self, conversation_id: str, owner_id: str) -> list[StoredChatMessage]:
        if self.db.enabled:
            rows = self.db.fetch_all(
                """
                select m.id::text, m.conversation_id::text, m.role, m.content,
                       m.mode, m.sources, m.retrieval, m.created_at
                from public.chat_messages m
                join public.chat_conversations c on c.id = m.conversation_id
                where m.conversation_id = %s::uuid and c.owner_id = %s::uuid
                order by m.created_at asc limit 500
                """,
                (conversation_id, owner_id),
            )
            return [self._message(row) for row in rows]
        data = self._load_local(owner_id)
        rows = [row for row in data["messages"] if row["conversation_id"] == conversation_id]
        return [self._message(row) for row in sorted(rows, key=lambda row: row["created_at"])]

    def add_exchange(
        self, conversation: ChatConversation, user_content: str, assistant_content: str,
        mode: str, sources: list[dict], retrieval: dict,
    ) -> tuple[StoredChatMessage, StoredChatMessage, ChatConversation]:
        now = datetime.now(timezone.utc)
        user_message = StoredChatMessage(
            id=str(uuid.uuid4()), conversation_id=conversation.id, role="user",
            content=user_content, created_at=now,
        )
        assistant_message = StoredChatMessage(
            id=str(uuid.uuid4()), conversation_id=conversation.id, role="assistant",
            content=assistant_content, mode=mode, sources=sources, retrieval=retrieval,
            created_at=now,
        )
        next_title = conversation.title
        if next_title == "Nova conversa":
            next_title = " ".join(user_content.strip().split())[:60] or next_title
        if self.db.enabled:
            with self.db.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "select 1 from public.chat_conversations where id = %s::uuid and owner_id = %s::uuid",
                        (conversation.id, conversation.owner_id),
                    )
                    if cur.fetchone() is None:
                        raise ValueError("Conversa nao encontrada")
                    cur.executemany(
                        """
                        insert into public.chat_messages
                          (id, conversation_id, role, content, mode, sources, retrieval, created_at)
                        values (%s::uuid, %s::uuid, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                        """,
                        [
                            (user_message.id, conversation.id, "user", user_content, None, "[]", "{}", now),
                            (assistant_message.id, conversation.id, "assistant", assistant_content, mode,
                             json.dumps(sources, ensure_ascii=False), json.dumps(retrieval, ensure_ascii=False), now),
                        ],
                    )
                    cur.execute(
                        "update public.chat_conversations set title = %s, updated_at = %s where id = %s::uuid and owner_id = %s::uuid",
                        (next_title, now, conversation.id, conversation.owner_id),
                    )
        else:
            data = self._load_local(conversation.owner_id)
            data["messages"].extend([
                user_message.model_dump(mode="json"), assistant_message.model_dump(mode="json")
            ])
            for row in data["conversations"]:
                if row["id"] == conversation.id:
                    row.update({"title": next_title, "updated_at": now.isoformat()})
            self._save_local(conversation.owner_id, data)
        updated = conversation.model_copy(update={
            "title": next_title, "updated_at": now, "message_count": conversation.message_count + 2,
        })
        return user_message, assistant_message, updated

    def add_message(
        self, conversation_id: str, owner_id: str, role: str, content: str,
        mode: str | None = None, sources: list[dict] | list[ChatSource] | None = None,
        retrieval: dict | None = None,
    ) -> StoredChatMessage:
        if not self.get_conversation(conversation_id, owner_id):
            raise ValueError("Conversa nao encontrada")
        now = datetime.now(timezone.utc)
        source_payload = [item.model_dump(mode="json") if isinstance(item, ChatSource) else item for item in (sources or [])]
        message = StoredChatMessage(
            id=str(uuid.uuid4()), conversation_id=conversation_id, role=role, content=content,
            mode=mode, sources=source_payload, retrieval=retrieval or {}, created_at=now,
        )
        if self.db.enabled:
            self.db.execute(
                """
                insert into public.chat_messages
                  (id, conversation_id, role, content, mode, sources, retrieval, created_at)
                values (%s::uuid, %s::uuid, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                """,
                (message.id, conversation_id, role, content, mode,
                 json.dumps(source_payload, ensure_ascii=False), json.dumps(retrieval or {}, ensure_ascii=False), now),
            )
            self.db.execute(
                "update public.chat_conversations set updated_at = %s where id = %s::uuid and owner_id = %s::uuid",
                (now, conversation_id, owner_id),
            )
        else:
            data = self._load_local(owner_id)
            data["messages"].append(message.model_dump(mode="json"))
            for row in data["conversations"]:
                if row["id"] == conversation_id:
                    row["updated_at"] = now.isoformat()
            self._save_local(owner_id, data)
        return message
