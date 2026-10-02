from dataclasses import dataclass
from datetime import datetime, timezone
import json

import redis

from core.config import settings


@dataclass(frozen=True)
class ConversationMessage:
    conversation_id: str
    user_id: str
    organization_id: str
    role: str
    content: str
    created_at: datetime


class ConversationMemoryService:
    """
    Redis-backed conversation memory.

    Memory is isolated by:
        organization_id -> user_id -> conversation_id

    Each conversation expires automatically after the configured TTL.
    """

    def __init__(self):
        self._redis = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )

    def _key(
        self,
        conversation_id: str,
        user_id: str,
        organization_id: str,
    ) -> str:
        return (
            "ai:memory:"
            f"org:{organization_id}:"
            f"user:{user_id}:"
            f"conversation:{conversation_id}"
        )

    def add_message(
        self,
        conversation_id: str,
        user_id: str,
        organization_id: str,
        role: str,
        content: str,
    ) -> ConversationMessage:

        message = ConversationMessage(
            conversation_id=conversation_id,
            user_id=user_id,
            organization_id=organization_id,
            role=role,
            content=content,
            created_at=datetime.now(timezone.utc),
        )

        key = self._key(
            conversation_id,
            user_id,
            organization_id,
        )

        self._redis.rpush(
            key,
            json.dumps(
                {
                    "conversation_id": message.conversation_id,
                    "user_id": message.user_id,
                    "organization_id": message.organization_id,
                    "role": message.role,
                    "content": message.content,
                    "created_at": message.created_at.isoformat(),
                }
            ),
        )

        self._redis.expire(
            key,
            settings.redis_memory_ttl_seconds,
        )

        return message

    def get_messages(
        self,
        conversation_id: str,
        user_id: str,
        organization_id: str,
    ) -> list[ConversationMessage]:

        key = self._key(
            conversation_id,
            user_id,
            organization_id,
        )

        stored_messages = self._redis.lrange(key, 0, -1)

        messages = []

        for item in stored_messages:
            data = json.loads(item)

            messages.append(
                ConversationMessage(
                    conversation_id=data["conversation_id"],
                    user_id=data["user_id"],
                    organization_id=data["organization_id"],
                    role=data["role"],
                    content=data["content"],
                    created_at=datetime.fromisoformat(
                        data["created_at"]
                    ),
                )
            )

        return messages

    def clear_conversation(
        self,
        conversation_id: str,
        user_id: str,
        organization_id: str,
    ) -> None:

        key = self._key(
            conversation_id,
            user_id,
            organization_id,
        )

        self._redis.delete(key)