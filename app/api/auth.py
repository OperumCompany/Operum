from fastapi import APIRouter, Header, HTTPException

from app.schemas.auth import (
    AccountDeletionRequest,
    LoginRequest,
    PasswordUpdateRequest,
    RegisterRequest,
    UserPreferences,
)
from app.services.auth_service import AuthService
from app.services.exceptions import ServiceUnavailableError

router = APIRouter(prefix="/auth", tags=["auth"])
service = AuthService()


def _extract_token(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Nao autenticado")
    return authorization.split(" ", 1)[1].strip()


def require_current_user(authorization: str | None = Header(default=None)):
    token = _extract_token(authorization)
    try:
        user = service.get_user_by_token(token)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if user is None:
        raise HTTPException(status_code=401, detail="Sessao invalida")
    return {"token": token, "user": user}


@router.post("/register")
def register(data: RegisterRequest):
    try:
        return service.register(data).model_dump(mode="json")
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/login")
def login(data: LoginRequest):
    try:
        return service.login(data).model_dump(mode="json")
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))


@router.post("/logout")
def logout(ctx=Header(default=None, alias="Authorization")):
    token = _extract_token(ctx)
    try:
        service.logout(token)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"status": "ok"}


@router.get("/me")
def me(session=Header(default=None, alias="Authorization")):
    token = _extract_token(session)
    try:
        user = service.get_user_by_token(token)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    if user is None:
        raise HTTPException(status_code=401, detail="Sessao invalida")
    return user.model_dump(mode="json")


@router.put("/password")
def update_password(data: PasswordUpdateRequest, session=Header(default=None, alias="Authorization")):
    token = _extract_token(session)
    try:
        user = service.update_password(token, data)
        return user.model_dump(mode="json")
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.delete("/account")
def delete_account(data: AccountDeletionRequest, session=Header(default=None, alias="Authorization")):
    token = _extract_token(session)
    try:
        service.delete_account(token, data)
    except ServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"status": "ok"}


@router.get("/preferences")
def get_preferences(session=Header(default=None, alias="Authorization")):
    token = _extract_token(session)
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
def update_preferences(data: UserPreferences, session=Header(default=None, alias="Authorization")):
    token = _extract_token(session)
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
