from __future__ import annotations

import hashlib
import json
from typing import Any

import redis

from app.core.config import settings


class RedisAuthorizationCache:
    """Redis-backed cache for authorization decisions."""

    def __init__(self) -> None:
        self._client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
        self._prefix = settings.redis_key_prefix

    def _key(self, cache_key: tuple[Any, ...]) -> str:
        """
        Build a Redis key with the subject ID in a dedicated segment.

        Keeping subject_id outside the JSON payload makes subject-level
        invalidation reliable with Redis SCAN patterns.
        """
        subject_id = str(cache_key[0])

        payload = json.dumps(
            cache_key,
            default=str,
            separators=(",", ":"),
        )

        digest = hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()

        return (
            f"{self._prefix}:authorization:"
            f"subject:{subject_id}:{digest}"
        )

    def get(
        self,
        cache_key: tuple[Any, ...],
    ) -> dict[str, Any] | None:
        """Return a cached authorization decision if available."""
        try:
            value = self._client.get(
                self._key(cache_key)
            )
        except redis.RedisError:
            return None

        if value is None:
            return None

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None

    def set(
        self,
        cache_key: tuple[Any, ...],
        value: dict[str, Any],
        ttl_seconds: int,
    ) -> None:
        """Store an authorization decision with a bounded TTL."""
        try:
            self._client.setex(
                self._key(cache_key),
                ttl_seconds,
                json.dumps(value),
            )
        except redis.RedisError:
            pass

    def delete(
        self,
        cache_key: tuple[Any, ...],
    ) -> None:
        """Delete one authorization decision from Redis."""
        try:
            self._client.delete(
                self._key(cache_key)
            )
        except redis.RedisError:
            pass

    def delete_subject(
        self,
        subject_id: str,
    ) -> int:
        """Delete all authorization decisions for one subject."""
        try:
            pattern = (
                f"{self._prefix}:authorization:"
                f"subject:{subject_id}:*"
            )

            keys = list(
                self._client.scan_iter(
                    match=pattern
                )
            )

            if not keys:
                return 0

            return int(
                self._client.delete(*keys)
            )

        except redis.RedisError:
            return 0

    def clear(self) -> int:
        """Delete all authorization decisions from Redis."""
        try:
            pattern = (
                f"{self._prefix}:authorization:*"
            )

            keys = list(
                self._client.scan_iter(
                    match=pattern
                )
            )

            if not keys:
                return 0

            return int(
                self._client.delete(*keys)
            )

        except redis.RedisError:
            return 0