from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatInputMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=8000)


class ChatRequest(BaseModel):
    messages: list[ChatInputMessage]
    portfolio_id: str | None = None
    use_all_portfolios: bool = False


class ChatSource(BaseModel):
    id: str
    type: str = Field(default="news", pattern="^(knowledge|news)$")
    title: str
    source_name: str
    source_url: str
    published_at: str | None = None
    similarity: float | None = None


class ChatResponse(BaseModel):
    message: str
    mode: str
    used_portfolio_context: bool
    sources: list[ChatSource] = Field(default_factory=list)
    retrieval: dict[str, Any] = Field(default_factory=dict)


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    portfolio_id: str | None = None
    use_all_portfolios: bool = False


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=100)


class ConversationMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=8000)
    portfolio_id: str | None = None
    use_all_portfolios: bool | None = None


class ChatConversation(BaseModel):
    id: str
    owner_id: str
    title: str
    summary: str = ""
    portfolio_id: str | None = None
    use_all_portfolios: bool = False
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class StoredChatMessage(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    mode: str | None = None
    sources: list[ChatSource] = Field(default_factory=list)
    retrieval: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ConversationMessageResponse(BaseModel):
    conversation: ChatConversation
    user_message: StoredChatMessage
    assistant_message: StoredChatMessage
