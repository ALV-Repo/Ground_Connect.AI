from datetime import datetime, timezone

from gateway.gateway import AIGateway
from models.ai import CopilotRequest, CopilotResponse
from security.permissions import (
    PermissionDeniedError,
    PermissionService,
    UserContext,
)
from services.memory import ConversationMemoryService


class CopilotService:

    def __init__(self):
        self.gateway = AIGateway()
        self.permission_service = PermissionService()
        self.memory_service = ConversationMemoryService()

    async def ask(
        self,
        request: CopilotRequest,
    ) -> CopilotResponse:

        user = UserContext(
            user_id=request.user_id,
            role=request.user_role,
            organization_id=request.organization_id,
        )

        # AI-002:
        # Enforce organization-level access.
        try:
            self.permission_service.enforce_access(
                user=user,
                resource_organization_id=(
                    request.resource_organization_id
                ),
            )
        except PermissionDeniedError:
            raise

        # AI-004:
        # Retrieve conversation context only for:
        # - same conversation
        # - same user
        # - same organization
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

        # Build the Copilot prompt.
        if context_parts:
            full_prompt = (
                "You are the GroundConnect Leadership Copilot.\n"
                "Answer the leadership user's question clearly "
                "and concisely using the available context.\n\n"
                "Separate your response into three categories:\n"
                "FACTS: information directly supported by the "
                "available context.\n"
                "INFERENCES: conclusions derived from the facts.\n"
                "RECOMMENDATIONS: suggested actions based on "
                "the available information.\n\n"
                "Do not present an inference or recommendation "
                "as a fact.\n\n"
                "Previous conversation context:\n"
                + "\n".join(context_parts)
                + "\n\nCurrent leadership question:\n"
                + request.question
            )
        else:
            full_prompt = (
                "You are the GroundConnect Leadership Copilot.\n"
                "Answer the leadership user's question clearly "
                "and concisely.\n\n"
                "Separate your response into three categories:\n"
                "FACTS: information directly supported by the "
                "available context.\n"
                "INFERENCES: conclusions derived from the facts.\n"
                "RECOMMENDATIONS: suggested actions based on "
                "the available information.\n\n"
                "Do not present an inference or recommendation "
                "as a fact.\n\n"
                "Current leadership question:\n"
                + request.question
            )

        # AI-001 + AI-003:
        # Route through the central AI Gateway.
        response = await self.gateway.generate(
            prompt=full_prompt,
            provider=request.provider,
            model=request.model,
        )

        # Store the user's question.
        self.memory_service.add_message(
            conversation_id=request.conversation_id,
            user_id=request.user_id,
            organization_id=request.organization_id,
            role="user",
            content=request.question,
        )

        # Store the assistant response when it was not
        # blocked by prompt-injection security.
        if not response.prompt_injection_detected:
            self.memory_service.add_message(
                conversation_id=request.conversation_id,
                user_id=request.user_id,
                organization_id=request.organization_id,
                role="assistant",
                content=response.content,
            )

        # AI-007:
        # Coverage disclosure.
        if previous_messages:
            coverage = (
                "Conversation context available for the current "
                "user, organization, and conversation."
            )
        else:
            coverage = (
                "No previous conversation context was available; "
                "answer is based on the current request."
            )

        # AI-007:
        # Freshness disclosure.
        freshness = (
            "Information reflects the context available at "
            + datetime.now(timezone.utc).isoformat()
            + " UTC."
        )

        # AI-008:
        # Separate facts, inferences, and recommendations.
        #
        # The current mock gateway does not return structured
        # classifications, so the service exposes the available
        # AI answer as a fact-supported response and keeps the
        # other categories explicit rather than inventing data.
        facts = [
            response.content,
        ]

        inferences = []

        recommendations = []

        return CopilotResponse(
            answer=response.content,
            provider=response.provider,
            model=response.model,
            pii_masked=response.pii_masked,
            prompt_injection_detected=(
                response.prompt_injection_detected
            ),
            coverage=coverage,
            freshness=freshness,
            facts=facts,
            inferences=inferences,
            recommendations=recommendations,
        )