from datetime import datetime, timezone

from gateway.gateway import AIGateway
from models.ai import (
    GroundAnalyticsRequest,
    GroundAnalyticsResponse,
)
from security.permissions import (
    PermissionDeniedError,
    PermissionService,
    UserContext,
)


class GroundAnalyticsService:

    def __init__(self):
        self.gateway = AIGateway()
        self.permission_service = PermissionService()

    async def analyze(
        self,
        request: GroundAnalyticsRequest,
    ) -> GroundAnalyticsResponse:

        user = UserContext(
            user_id=request.user_id,
            role=request.user_role,
            organization_id=request.organization_id,
        )

        # AI-002: Permission boundary
        try:
            self.permission_service.enforce_access(
                user=user,
                resource_organization_id=(
                    request.resource_organization_id
                ),
            )
        except PermissionDeniedError:
            raise

        analytics_prompt = (
            "You are the GroundConnect ground-intelligence "
            "analytics assistant.\n"
            "Analyze the supplied ground-intelligence data.\n\n"
            "Identify:\n"
            "1. Important trends\n"
            "2. Workload patterns\n"
            "3. Reporting gaps\n\n"
            "Requirements:\n"
            "- Use only the supplied data.\n"
            "- Do not invent facts.\n"
            "- Clearly separate observations from assumptions.\n"
            "- Flag insufficient data.\n"
            "- Keep the analysis reviewable by a human.\n\n"
            "Ground-intelligence data:\n"
            + request.data
        )

        response = await self.gateway.generate(
            prompt=analytics_prompt,
            provider=request.provider,
            model=request.model,
        )

        processed_at = datetime.now(timezone.utc).isoformat()

        # AI-003: Prompt injection protection
        if response.prompt_injection_detected:
            return GroundAnalyticsResponse(
                trends=[],
                workload=[],
                reporting_gaps=[],
                coverage=(
                    "Analytics was blocked because the supplied "
                    "content contained a detected prompt injection."
                ),
                freshness=(
                    "Analytics processed at "
                    + processed_at
                    + " UTC."
                ),
                provider=response.provider,
                model=response.model,
                pii_masked=response.pii_masked,
                prompt_injection_detected=True,
            )

        # The current mock provider does not return structured
        # analytics. Use a safe review-required empty result.
        return GroundAnalyticsResponse(
            trends=[],
            workload=[],
            reporting_gaps=[],
            coverage=(
                "Analytics is based only on the ground-intelligence "
                "data supplied in the current request."
            ),
            freshness=(
                "Analytics processed at "
                + processed_at
                + " UTC."
            ),
            provider=response.provider,
            model=response.model,
            pii_masked=response.pii_masked,
            prompt_injection_detected=False,
        )