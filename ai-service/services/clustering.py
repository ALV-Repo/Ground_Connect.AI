from datetime import datetime, timezone

from gateway.gateway import AIGateway
from models.ai import (
    ClusteringSuggestionRequest,
    ClusteringSuggestionResponse,
)
from security.permissions import (
    PermissionDeniedError,
    PermissionService,
    UserContext,
)


class ClusteringSuggestionService:

    def __init__(self):
        self.gateway = AIGateway()
        self.permission_service = PermissionService()

    async def suggest_clusters(
        self,
        request: ClusteringSuggestionRequest,
    ) -> ClusteringSuggestionResponse:

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

        clustering_prompt = (
            "You are the GroundConnect clustering assistant.\n"
            "Suggest meaningful clusters for the supplied "
            "ground-intelligence items.\n\n"
            "Requirements:\n"
            "- Group similar items conceptually.\n"
            "- Do not invent information.\n"
            "- Suggestions must remain reviewable by a human.\n"
            "- Provide confidence between 0 and 1.\n"
            "- Flag uncertain suggestions for human review.\n\n"
            "Items:\n"
            + request.items
        )

        response = await self.gateway.generate(
            prompt=clustering_prompt,
            provider=request.provider,
            model=request.model,
        )

        processed_at = datetime.now(timezone.utc).isoformat()

        # AI-003: Prompt injection protection
        if response.prompt_injection_detected:
            return ClusteringSuggestionResponse(
                suggestions=[],
                confidence=0.0,
                needs_human_review=True,
                coverage=(
                    "Clustering was blocked because the supplied "
                    "content contained a detected prompt injection."
                ),
                freshness=(
                    "Clustering processed at "
                    + processed_at
                    + " UTC."
                ),
                provider=response.provider,
                model=response.model,
                pii_masked=response.pii_masked,
                prompt_injection_detected=True,
            )

        # The current mock provider does not return structured
        # clustering results. Use a safe review-required response.
        return ClusteringSuggestionResponse(
            suggestions=[],
            confidence=0.0,
            needs_human_review=True,
            coverage=(
                "Clustering suggestions are based only on the "
                "items supplied in the current request."
            ),
            freshness=(
                "Clustering processed at "
                + processed_at
                + " UTC."
            ),
            provider=response.provider,
            model=response.model,
            pii_masked=response.pii_masked,
            prompt_injection_detected=False,
        )
