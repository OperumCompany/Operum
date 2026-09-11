from __future__ import annotations

import time
from dataclasses import dataclass
from threading import Lock

from fastapi import HTTPException

from app.core.config import OPERUM_ENV, OPERUM_RATE_LIMIT_ENABLED, REDIS_URL


@dataclass(frozen=True)
class RateLimitRule:
    limit: int
    window_seconds: int


class RateLimiter:
    def __init__(self) -> None:
        self.enabled = OPERUM_RATE_LIMIT_ENABLED
        self._memory: dict[str, tuple[int, float]] = {}
        self._lock = Lock()
        self._redis = None

        if not self.enabled:
            return
        if REDIS_URL:
            try:
                from redis import Redis

                self._redis = Redis.from_url(REDIS_URL, decode_responses=True)
                self._redis.ping()
            except Exception as exc:
                if OPERUM_ENV == "production":
                    raise RuntimeError("REDIS_URL invalido ou indisponivel para rate limit em producao") from exc
                self._redis = None
        elif OPERUM_ENV == "production":
            raise RuntimeError("REDIS_URL e obrigatorio quando rate limit esta ativo em producao")

    def check(self, key: str, rule: RateLimitRule) -> None:
        if not self.enabled:
            return
        if self._redis is not None:
            self._check_redis(key, rule)
            return
        self._check_memory(key, rule)

    def _reject(self, retry_after: int) -> None:
        raise HTTPException(
            status_code=429,
            detail="Muitas tentativas. Tente novamente em instantes.",
            headers={"Retry-After": str(max(1, retry_after))},
        )

    def _check_redis(self, key: str, rule: RateLimitRule) -> None:
        assert self._redis is not None
        count = int(self._redis.incr(key))
        if count == 1:
            self._redis.expire(key, rule.window_seconds)
        if count > rule.limit:
            ttl = int(self._redis.ttl(key))
            self._reject(ttl if ttl > 0 else rule.window_seconds)

    def _check_memory(self, key: str, rule: RateLimitRule) -> None:
        now = time.monotonic()
        with self._lock:
            count, reset_at = self._memory.get(key, (0, now + rule.window_seconds))
            if now >= reset_at:
                count = 0
                reset_at = now + rule.window_seconds
            count += 1
            self._memory[key] = (count, reset_at)
            if count > rule.limit:
                self._reject(int(reset_at - now))


rate_limiter = RateLimiter()


LOGIN_IP_RULE = RateLimitRule(limit=5, window_seconds=60)
LOGIN_EMAIL_RULE = RateLimitRule(limit=10, window_seconds=15 * 60)
REGISTER_IP_RULE = RateLimitRule(limit=3, window_seconds=60 * 60)
CHAT_MINUTE_RULE = RateLimitRule(limit=20, window_seconds=60)
CHAT_HOUR_RULE = RateLimitRule(limit=60, window_seconds=60 * 60)
ADMIN_NEWS_RULE = RateLimitRule(limit=5, window_seconds=60)
