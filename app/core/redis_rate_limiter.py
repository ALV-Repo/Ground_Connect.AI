from __future__ import annotations

import hashlib
import math
import time
import uuid

import redis

from app.core.config import settings


class RedisRateLimiter:
    """Distributed sliding-window rate limiter backed by Redis."""

    _SCRIPT = """
    local key = KEYS[1]
    local now_ms = tonumber(ARGV[1])
    local cutoff_ms = tonumber(ARGV[2])
    local limit = tonumber(ARGV[3])
    local window_seconds = tonumber(ARGV[4])
    local member = ARGV[5]

    redis.call("ZREMRANGEBYSCORE", key, "-inf", cutoff_ms)

    local count = redis.call("ZCARD", key)

    if count >= limit then
        return 0
    end

    redis.call("ZADD", key, now_ms, member)
    redis.call("EXPIRE", key, window_seconds + 1)

    return 1
    """

    def __init__(self) -> None:
        self._client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        self._prefix = settings.redis_key_prefix

    @staticmethod
    def _hash_identity(identity: str) -> str:
        """Hash rate-limit identity before storing it in Redis."""
        return hashlib.sha256(
            identity.encode("utf-8")
        ).hexdigest()

    def _key(self, namespace: str, identity: str) -> str:
        identity_hash = self._hash_identity(identity)

        return (
            f"{self._prefix}:rate_limit:"
            f"{namespace}:{identity_hash}"
        )

    def allow(
        self,
        namespace: str,
        identity: str,
        limit: int,
        window_seconds: int,
    ) -> bool:
        """Return True when the request is within the configured limit."""
        now_ms = int(time.time() * 1000)
        cutoff_ms = now_ms - (window_seconds * 1000)

        key = self._key(namespace, identity)

        try:
            result = self._client.eval(
                self._SCRIPT,
                1,
                key,
                now_ms,
                cutoff_ms,
                limit,
                window_seconds,
                uuid.uuid4().hex,
            )

            return bool(result)

        except redis.RedisError:
            # Redis failure should not disable the existing
            # application-level fallback rate limiter.
            return True

    def clear(self, namespace: str, identity: str) -> None:
        """Clear the Redis rate-limit window for one identity."""
        key = self._key(namespace, identity)

        try:
            self._client.delete(key)
        except redis.RedisError:
            return