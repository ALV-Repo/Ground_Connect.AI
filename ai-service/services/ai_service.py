from core.audit import AuditService
from gateway.gateway import AIGateway
from models.ai import AIRequest, AIResponseModel
from security.permissions import (
    PermissionDeniedError,
    PermissionService,
    UserContext,
)
from services.memory import ConversationMemoryService


class AIService:

    def __init__(self):
        self.gateway = AIGateway()
        self.permission_service = PermissionService()
        self.memory_service = ConversationMemoryService()
        self.audit_service = AuditService()

    async def generate(
        self,
        request: AIRequest,
    ) -> AIResponseModel:

        user = UserContext(
            user_id=request.user_id,
            role=request.user_role,
            organization_id=request.organization_id,
        )

        # AI-002 + AI-005:
        # Permission boundary + access-denied audit
        try:
            self.permission_service.enforce_access(
                user=user,
                resource_organization_id=(
                    request.resource_organization_id
                ),
            )

        except PermissionDeniedError:
            self.audit_service.record_access_denied(
                user_id=user.user_id,
                organization_id=user.organization_id,
                resource_organization_id=(
                    request.resource_organization_id
                ),
            )

            raise

        # AI-004:
        # Retrieve only the current user's
        # current organization's conversation context.
        previous_messages = (
            self.memory_service.get_messages(
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                organization_id=request.organization_id,
            )
        )

        context_parts = [
            message.content
            for message in previous_messages
        ]

        if context_parts:
            full_prompt = (
                "Previous conversation context:\n"
                + "\n".join(context_parts)
                + "\n\nCurrent user request:\n"
                + request.prompt
            )
        else:
            full_prompt = request.prompt

        # AI-001 + AI-003:
        # Send the request through the central AI gateway.
        response = await self.gateway.generate(
            prompt=full_prompt,
            provider=request.provider,
            model=request.model,
        )

        # Store the user's message.
        self.memory_service.add_message(
            conversation_id=request.conversation_id,
            user_id=request.user_id,
            organization_id=request.organization_id,
            role="user",
            content=request.prompt,
        )

        # Store the AI response only when the request
        # was not blocked by prompt-injection security.
        if not response.prompt_injection_detected:
            self.memory_service.add_message(
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                organization_id=request.organization_id,
                role="assistant",
                content=response.content,
            )

        return AIResponseModel(
            provider=response.provider,
            model=response.model,
            content=response.content,
            pii_masked=response.pii_masked,
            prompt_injection_detected=(
                response.prompt_injection_detected
            ),
        )