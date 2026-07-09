from pydantic import BaseModel, Field


class ChatInputMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[ChatInputMessage]
    portfolio_id: str | None = None
    use_all_portfolios: bool = False


class ChatResponse(BaseModel):
    message: str
    mode: str
    used_portfolio_context: bool
