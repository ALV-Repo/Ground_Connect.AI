from datetime import datetime, timezone

from gateway.gateway import AIGateway
from models.ai import (
    DarkUnitRadarRequest,
    DarkUnitRadarResponse,
)
from security.permissions import (
    PermissionDeniedError,
    PermissionService,
    UserContext,
)


class DarkUnitRadarService:

    def __init__(self):
        self.gateway = AIGateway()
        self.permission_service = PermissionService()

    async def analyze(
        self,
        request: DarkUnitRadarRequest,
    ) -> DarkUnitRadarResponse:

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

        radar_prompt = (
            "You are the GroundConnect Dark Unit Radar assistant.\n"
            "Identify units or reporting areas where unusual silence "
            "may indicate a reporting gap.\n\n"
            "Analyze only the supplied reporting data.\n"
            "Do not treat silence as proof of a problem.\n"
            "Possible explanations include:\n"
            "- no incidents occurred\n"
            "- reporting was delayed\n"
            "- data is missing\n"
            "- reporting coverage is incomplete\n\n"
            "For every potential dark unit, provide a reviewable "
            "reason and clearly identify uncertainty.\n\n"
            "Reporting data:\n"
            + request.data
        )

        response = await self.gateway.generate(
            prompt=radar_prompt,
            provider=request.provider,
            model=request.model,
        )

        processed_at = datetime.now(timezone.utc).isoformat()

        # AI-003: Prompt injection protection
        if response.prompt_injection_detected:
            return DarkUnitRadarResponse(
                dark_units=[],
                coverage=(
                    "Dark Unit Radar was blocked because the supplied "
                    "content contained a detected prompt injection."
                ),
                freshness=(
                    "Radar analysis processed at "
                    + processed_at
                    + " UTC."
                ),
                provider=response.provider,
                model=response.model,
                pii_masked=response.pii_masked,
                prompt_injection_detected=True,
            )

        # The current mock provider does not return structured
        # radar results. Use a safe review-required empty result.
        return DarkUnitRadarResponse(
            dark_units=[],
            coverage=(
                "Dark Unit Radar is based only on the reporting data "
                "supplied in the current request. Silence is treated "
                "as a signal for review, not proof of an issue."
            ),
            freshness=(
                "Radar analysis processed at "
                + processed_at
                + " UTC."
            ),
            provider=response.provider,
            model=response.model,
            pii_masked=response.pii_masked,
            prompt_injection_detected=False,
        )