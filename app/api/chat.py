import threading

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import require_current_user
from app.schemas.chat import (
    ChatConversation,
    ChatInputMessage,
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationMessageCreate,
    ConversationMessageResponse,
    ConversationUpdate,
    StoredChatMessage,
)
from app.services.chat_repository import ChatRepository
from app.services.chat_service import ChatService
from app.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/chat", tags=["chat"])

chat_service = ChatService()
chat_repository = ChatRepository()
portfolio_service = PortfolioService()


def _portfolio_context(owner_id: str, portfolio_id: str | None, use_all: bool):
    active = None
    consolidated = []
    demo_mode = False
    if portfolio_id:
        active = portfolio_service.get_by_id(portfolio_id, owner_id)
        if active is None:
            raise HTTPException(status_code=404, detail="Carteira não encontrada")
        if active.kind == "example":
            demo_mode = True
            active = None
    if use_all:
        all_portfolios = portfolio_service.list_all(owner_id)
        consolidated = [portfolio for portfolio in all_portfolios if portfolio.kind == "standard"]
        demo_mode = bool(all_portfolios) and not consolidated
    return active, consolidated, demo_mode


@router.get("/conversations", response_model=list[ChatConversation])
def list_conversations(current=Depends(require_current_user)):
    return chat_repository.list_conversations(current["user"].id)


@router.post("/conversations", response_model=ChatConversation, status_code=201)
def create_conversation(data: ConversationCreate, current=Depends(require_current_user)):
    owner_id = current["user"].id
    if data.portfolio_id and portfolio_service.get_by_id(data.portfolio_id, owner_id) is None:
        raise HTTPException(status_code=404, detail="Carteira não encontrada")
    return chat_repository.create_conversation(
        owner_id, data.title or "Nova conversa", data.portfolio_id, data.use_all_portfolios
    )


@router.patch("/conversations/{conversation_id}", response_model=ChatConversation)
def rename_conversation(conversation_id: str, data: ConversationUpdate, current=Depends(require_current_user)):
    conversation = chat_repository.update_title(conversation_id, current["user"].id, data.title)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    return conversation


@router.delete("/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, current=Depends(require_current_user)):
    if not chat_repository.delete_conversation(conversation_id, current["user"].id):
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    return {"status": "deleted"}


@router.get("/conversations/{conversation_id}/messages", response_model=list[StoredChatMessage])
def list_messages(conversation_id: str, current=Depends(require_current_user)):
    owner_id = current["user"].id
    if chat_repository.get_conversation(conversation_id, owner_id) is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")
    return chat_repository.list_messages(conversation_id, owner_id)


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessageResponse,
)
def send_message(conversation_id: str, data: ConversationMessageCreate, current=Depends(require_current_user)):
    owner_id = current["user"].id
    conversation, stored = chat_repository.get_conversation_with_messages(conversation_id, owner_id, 7)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversa não encontrada")

    portfolio_id = data.portfolio_id if data.portfolio_id is not None else conversation.portfolio_id
    use_all = data.use_all_portfolios if data.use_all_portfolios is not None else conversation.use_all_portfolios
    active, consolidated, demo_mode = _portfolio_context(owner_id, portfolio_id, use_all)
    input_messages = [ChatInputMessage(role=item.role, content=item.content) for item in stored]
    input_messages.append(ChatInputMessage(role="user", content=data.content))

    result = chat_service.answer(
        input_messages,
        active_portfolio=active,
        consolidated_portfolios=consolidated,
        conversation_summary=conversation.summary,
        demo_mode=demo_mode,
    )
    user_message, assistant_message, conversation = chat_repository.add_exchange(
        conversation, data.content, result["message"], result["mode"], result["sources"], result["retrieval"],
    )
    if not demo_mode and conversation.message_count >= 12 and conversation.message_count % 12 == 0:
        def update_summary():
            all_messages = chat_repository.list_messages(conversation_id, owner_id)
            summary = chat_service.summarize_conversation(
                [ChatInputMessage(role=item.role, content=item.content) for item in all_messages[-12:]]
            )
            if summary:
                chat_repository.update_summary(conversation_id, owner_id, summary)

        threading.Thread(target=update_summary, daemon=True, name="chat-summary").start()

    return ConversationMessageResponse(
        conversation=conversation,
        user_message=user_message,
        assistant_message=assistant_message,
    )


@router.post("", response_model=ChatResponse)
def chat(data: ChatRequest, current=Depends(require_current_user)):
    owner_id = current["user"].id
    active, consolidated, demo_mode = _portfolio_context(owner_id, data.portfolio_id, data.use_all_portfolios)
    result = chat_service.answer(
        data.messages,
        active_portfolio=active,
        consolidated_portfolios=consolidated,
        demo_mode=demo_mode,
    )
    return ChatResponse(**result)
