from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class ConversationMessage:
    conversation_id: str
    user_id: str
    organization_id: str
    role: str
    content: str
    created_at: datetime


class ConversationMemoryService:

    def __init__(self):
        self._messages: list[ConversationMessage] = []

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

        self._messages.append(message)

        return message

    def get_messages(
        self,
        conversation_id: str,
        user_id: str,
        organization_id: str,
    ) -> list[ConversationMessage]:

        return [
            message
            for message in self._messages
            if (
                message.conversation_id == conversation_id
                and message.user_id == user_id
                and message.organization_id == organization_id
            )
        ]

    def clear_conversation(
        self,
        conversation_id: str,
        user_id: str,
        organization_id: str,
    ) -> None:

        self._messages = [
            message
            for message in self._messages
            if not (
                message.conversation_id == conversation_id
                and message.user_id == user_id
                and message.organization_id == organization_id
            )
        ]