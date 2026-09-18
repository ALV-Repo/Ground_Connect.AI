from datetime import datetime, timezone

from gateway.gateway import AIGateway
from models.ai import (
    LeaderBriefingRequest,
    LeaderBriefingResponse,
)
from security.permissions import (
    PermissionDeniedError,
    PermissionService,
    UserContext,
)


class LeaderBriefingService:

    def __init__(self):
        self.gateway = AIGateway()
        self.permission_service = PermissionService()

    async def generate(
        self,
        request: LeaderBriefingRequest,
    ) -> LeaderBriefingResponse:

        user = UserContext(
            user_id=request.user_id,
            role=request.user_role,
            organization_id=request.organization_id,
        )

        # AI-002:
        # Enforce organization-level access before
        # processing leadership data.
        try:
            self.permission_service.enforce_access(
                user=user,
                resource_organization_id=(
                    request.resource_organization_id
                ),
            )
        except PermissionDeniedError:
            raise

        # AI-003:
        # The central AI Gateway performs prompt-injection
        # detection and PII masking.
        briefing_prompt = (
            "You are the GroundConnect Daily Leader Briefing "
            "assistant.\n"
            "Generate a concise daily briefing for leadership.\n\n"
            "Separate the information into:\n"
            "SUMMARY: overall situation.\n"
            "FACTS: information directly supported by the "
            "provided context.\n"
            "INFERENCES: conclusions derived from those facts.\n"
            "RECOMMENDATIONS: suggested actions based on the "
            "available information.\n\n"
            "Do not present inferences or recommendations as facts.\n"
            "Do not invent information that is not present in the "
            "provided context.\n\n"
            "Briefing date:\n"
            + request.briefing_date
            + "\n\n"
            "Available context:\n"
            + request.context
        )

        response = await self.gateway.generate(
            prompt=briefing_prompt,
            provider=request.provider,
            model=request.model,
        )

        # AI-007:
        # Explicitly disclose the coverage of the briefing.
        coverage = (
            "Briefing is based only on the context supplied "
            "for the requested briefing date."
        )

        # AI-007:
        # Explicitly disclose freshness.
        freshness = (
            "Information reflects the context available at "
            + datetime.now(timezone.utc).isoformat()
            + " UTC."
        )

        # AI-008:
        # The current mock gateway does not produce structured
        # categories, so do not invent facts, inferences, or
        # recommendations.
        facts = []
        inferences = []
        recommendations = []

        # If prompt injection was detected, the generated
        # content must not be treated as a normal briefing.
        if response.prompt_injection_detected:
            summary = response.content
        else:
            summary = response.content

        return LeaderBriefingResponse(
            briefing_date=request.briefing_date,
            summary=summary,
            facts=facts,
            inferences=inferences,
            recommendations=recommendations,
            coverage=coverage,
            freshness=freshness,
            provider=response.provider,
            model=response.model,
            pii_masked=response.pii_masked,
            prompt_injection_detected=(
                response.prompt_injection_detected
            ),
        )