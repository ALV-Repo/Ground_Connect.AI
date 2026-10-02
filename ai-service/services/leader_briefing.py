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

    def __init__(
        self,
        gateway: AIGateway | None = None,
        permission_service: PermissionService | None = None,
    ):
        self.gateway = gateway or AIGateway()
        self.permission_service = (
            permission_service or PermissionService()
        )

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
        # Enforce role-based access for Leader Briefing.
        self.permission_service.enforce_feature_access(
            user=user,
            feature="leader_briefing",
        )

        # AI-002:
        # Enforce organization-level access before
        # processing leadership data.
        self.permission_service.enforce_access(
            user=user,
            resource_organization_id=(
                request.resource_organization_id
            ),
        )

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

        now = datetime.now(timezone.utc)

        return LeaderBriefingResponse(
            briefing_date=request.briefing_date,
            summary=response.content,
            facts=[],
            inferences=[],
            recommendations=[],
            coverage=(
                "Coverage is based on the context supplied "
                "for this briefing."
            ),
            freshness=(
                "Information reflects the context available at "
                f"{now.isoformat()} UTC."
            ),
            provider=response.provider,
            model=response.model,
            pii_masked=response.pii_masked,
            prompt_injection_detected=(
                response.prompt_injection_detected
            ),
        )