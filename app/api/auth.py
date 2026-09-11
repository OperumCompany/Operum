from fastapi import APIRouter, Cookie, Header, HTTPException, Response

from app.schemas.auth import (
    AccountDeletionRequest,
    AuthSessionResponse,
    LoginRequest,
    PasswordUpdateRequest,
    RegisterRequest,
    UserPreferences,
)
from app.core.config import OPERUM_SESSION_COOKIE
from app.core.security import clear_session_cookie, set_session_cookie
from app.services.auth_service import AuthService
from app.services.exceptions import ServiceUnavailableError

router = APIRouter(prefix="/auth", tags=["auth"])
service = AuthService()


def _extract_token(authorization: str | None, session_cookie: str | None = None) -> str:
    if session_cookie:
        return session_cookie.strip()
    if authorization and authorization.startswith("Bearer "):
        return authorization.split(" ", 1)[1].strip()
    raise HTTPException(status_code=401, detail="Nao autenticado")


def require_current_user(
    authorization: str | None = Header(default=None),
    session_cookie: str | None = Cookie(default=None, alias=OPERUM_SESSION_COOKIE),
):
    token = _extract_token(authorization, session_cookie)
    try:
        user = service.get_user_by_token(token)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if user is None:
        raise HTTPException(status_code=401, detail="Sessao invalida")
    return {"token": token, "user": user}


@router.post("/register", response_model=AuthSessionResponse)
def register(data: RegisterRequest, response: Response):
    try:
        auth = service.register(data)
        set_session_cookie(response, auth.token)
        return {"user": auth.user}
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/login", response_model=AuthSessionResponse)
def login(data: LoginRequest, response: Response):
    try:
        auth = service.login(data)
        set_session_cookie(response, auth.token)
        return {"user": auth.user}
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/logout")
def logout(
    response: Response,
    ctx=Header(default=None, alias="Authorization"),
    session_cookie: str | None = Cookie(default=None, alias=OPERUM_SESSION_COOKIE),
):
    token = _extract_token(ctx, session_cookie)
    try:
        service.logout(token)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/me")
def me(
    session=Header(default=None, alias="Authorization"),
    session_cookie: str | None = Cookie(default=None, alias=OPERUM_SESSION_COOKIE),
):
    token = _extract_token(session, session_cookie)
    try:
        user = service.get_user_by_token(token)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if user is None:
        raise HTTPException(status_code=401, detail="Sessao invalida")
    return user.model_dump(mode="json")


@router.put("/password")
def update_password(
    data: PasswordUpdateRequest,
    session=Header(default=None, alias="Authorization"),
    session_cookie: str | None = Cookie(default=None, alias=OPERUM_SESSION_COOKIE),
):
    token = _extract_token(session, session_cookie)
    try:
        user = service.update_password(token, data)
        return user.model_dump(mode="json")
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/account")
def delete_account(
    data: AccountDeletionRequest,
    response: Response,
    session=Header(default=None, alias="Authorization"),
    session_cookie: str | None = Cookie(default=None, alias=OPERUM_SESSION_COOKIE),
):
    token = _extract_token(session, session_cookie)
    try:
        service.delete_account(token, data)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/preferences")
def get_preferences(
    session=Header(default=None, alias="Authorization"),
    session_cookie: str | None = Cookie(default=None, alias=OPERUM_SESSION_COOKIE),
):
    token = _extract_token(session, session_cookie)
    try:
        user = service.get_user_by_token(token)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if user is None:
        raise HTTPException(status_code=401, detail="Sessao invalida")
    try:
        prefs = service.get_preferences(user.id)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return prefs.model_dump(mode="json")


@router.put("/preferences")
def update_preferences(
    data: UserPreferences,
    session=Header(default=None, alias="Authorization"),
    session_cookie: str | None = Cookie(default=None, alias=OPERUM_SESSION_COOKIE),
):
    token = _extract_token(session, session_cookie)
    try:
        user = service.get_user_by_token(token)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if user is None:
        raise HTTPException(status_code=401, detail="Sessao invalida")
    try:
        prefs = service.update_preferences(user.id, data)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return prefs.model_dump(mode="json")
