from datetime import datetime, timezone

from gateway.gateway import AIGateway
from models.ai import (
    SummarizationRequest,
    SummarizationResponse,
)
from security.permissions import (
    PermissionDeniedError,
    PermissionService,
    UserContext,
)


class SummarizationService:

    SUPPORTED_SOURCE_TYPES = {
        "message_thread",
        "field_report_batch",
        "meeting",
    }

    def __init__(self):
        self.gateway = AIGateway()
        self.permission_service = PermissionService()

    async def summarize(
        self,
        request: SummarizationRequest,
    ) -> SummarizationResponse:

        user = UserContext(
            user_id=request.user_id,
            role=request.user_role,
            organization_id=request.organization_id,
        )

        try:
            self.permission_service.enforce_access(
                user=user,
                resource_organization_id=(
                    request.resource_organization_id
                ),
            )
        except PermissionDeniedError:
            raise

        source_type = request.source_type.lower().strip()

        if source_type not in self.SUPPORTED_SOURCE_TYPES:
            raise ValueError(
                "Unsupported summarization source type"
            )

        if source_type == "message_thread":
            source_instruction = (
                "Summarize the message thread, highlighting "
                "important decisions, issues, and action items."
            )

        elif source_type == "field_report_batch":
            source_instruction = (
                "Summarize the field reports, highlighting "
                "important events, recurring issues, and "
                "operational observations."
            )

        else:
            source_instruction = (
                "Summarize the meeting, highlighting key "
                "discussion points, decisions, and action items."
            )

        summarization_prompt = (
            "You are the GroundConnect summarization assistant.\n"
            + source_instruction
            + "\n\n"
            "Do not invent information that is not present "
            "in the supplied content.\n\n"
            "Source type:\n"
            + source_type
            + "\n\n"
            "Content to summarize:\n"
            + request.content
        )

        response = await self.gateway.generate(
            prompt=summarization_prompt,
            provider=request.provider,
            model=request.model,
        )

        coverage = (
            "Summary is based only on the supplied "
            + source_type
            + " content."
        )

        freshness = (
            "Information reflects the content available at "
            + datetime.now(timezone.utc).isoformat()
            + " UTC."
        )

        return SummarizationResponse(
            source_type=source_type,
            summary=response.content,
            coverage=coverage,
            freshness=freshness,
            provider=response.provider,
            model=response.model,
            pii_masked=response.pii_masked,
            prompt_injection_detected=(
                response.prompt_injection_detected
            ),
        )