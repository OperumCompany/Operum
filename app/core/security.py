from __future__ import annotations

import json
from urllib.parse import urlparse

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import CORS_ORIGINS, OPERUM_COOKIE_SECURE, OPERUM_SESSION_COOKIE
from app.core.rate_limit import (
    ADMIN_NEWS_RULE,
    CHAT_HOUR_RULE,
    CHAT_MINUTE_RULE,
    LOGIN_EMAIL_RULE,
    LOGIN_IP_RULE,
    REGISTER_IP_RULE,
    rate_limiter,
)

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
ALLOWED_ORIGINS = {origin.strip().rstrip("/") for origin in CORS_ORIGINS if origin.strip()}


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        OPERUM_SESSION_COOKIE,
        token,
        httponly=True,
        secure=OPERUM_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        OPERUM_SESSION_COOKIE,
        httponly=True,
        secure=OPERUM_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def _path_key(path: str) -> str:
    return path.strip("/").replace("/", ":") or "root"


def _origin_allowed(origin: str) -> bool:
    return origin.rstrip("/") in ALLOWED_ORIGINS


def validate_mutating_origin(request: Request) -> None:
    if request.method not in MUTATING_METHODS:
        return
    origin = request.headers.get("origin")
    if origin and not _origin_allowed(origin):
        raise HTTPException(status_code=403, detail="Origem nao permitida")


def apply_security_headers(response: Response) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "connect-src 'self' http://localhost:* http://127.0.0.1:*; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'",
    )
    if OPERUM_COOKIE_SECURE:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")


def _session_or_ip_key(request: Request) -> str:
    token = request.cookies.get(OPERUM_SESSION_COOKIE)
    return f"user:{token}" if token else f"ip:{client_ip(request)}"


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            validate_mutating_origin(request)
            await self._check_rate_limits(request)
        except HTTPException as exc:
            response = Response(
                content=json.dumps({"detail": exc.detail}),
                status_code=exc.status_code,
                media_type="application/json",
                headers=exc.headers,
            )
            apply_security_headers(response)
            return response

        response = await call_next(request)
        apply_security_headers(response)
        return response

    async def _check_rate_limits(self, request: Request) -> None:
        path = request.url.path
        ip = client_ip(request)

        if request.method == "POST" and path == "/api/auth/login":
            body = await request.body()
            email = ""
            try:
                email = (json.loads(body.decode("utf-8") or "{}").get("email") or "").strip().lower()
            except json.JSONDecodeError:
                email = ""
            rate_limiter.check(f"rl:login:ip:{ip}", LOGIN_IP_RULE)
            if email:
                rate_limiter.check(f"rl:login:email:{email}", LOGIN_EMAIL_RULE)
            return

        if request.method == "POST" and path == "/api/auth/register":
            rate_limiter.check(f"rl:register:ip:{ip}", REGISTER_IP_RULE)
            return

        if request.method == "POST" and (path == "/api/chat" or path.endswith("/messages")):
            key = _session_or_ip_key(request)
            rate_limiter.check(f"rl:chat:min:{key}", CHAT_MINUTE_RULE)
            rate_limiter.check(f"rl:chat:hour:{key}", CHAT_HOUR_RULE)
            return

        if request.method == "POST" and path in {"/api/news/reindex", "/api/news/backfill"}:
            rate_limiter.check(f"rl:admin-news:{ip}:{_path_key(path)}", ADMIN_NEWS_RULE)

