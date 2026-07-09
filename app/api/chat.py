from fastapi import APIRouter, Depends

from app.api.auth import require_current_user
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService
from app.services.portfolio_service import PortfolioService

router = APIRouter(prefix="/chat", tags=["chat"])

chat_service = ChatService()
portfolio_service = PortfolioService()


@router.post("", response_model=ChatResponse)
def chat(data: ChatRequest, current=Depends(require_current_user)):
    user = current["user"]
    active_portfolio = None
    consolidated_portfolios = []

    if data.portfolio_id:
        active_portfolio = portfolio_service.get_by_id(data.portfolio_id, user.id)
    if data.use_all_portfolios:
        consolidated_portfolios = portfolio_service.list_by_owner(user.id)

    result = chat_service.answer(
        data.messages,
        active_portfolio=active_portfolio,
        consolidated_portfolios=consolidated_portfolios,
    )
    return ChatResponse(**result)
