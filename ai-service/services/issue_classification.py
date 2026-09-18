from datetime import datetime, timezone

from gateway.gateway import AIGateway
from models.ai import (
    IssueClassificationCorrectionRequest,
    IssueClassificationCorrectionResponse,
    IssueClassificationRequest,
    IssueClassificationResponse,
)
from security.permissions import (
    PermissionDeniedError,
    PermissionService,
    UserContext,
)


class IssueClassificationService:

    SUPPORTED_CATEGORIES = {
        "roads",
        "water",
        "electricity",
        "sanitation",
        "health",
        "education",
        "public_safety",
        "other",
    }

    SUPPORTED_PRIORITIES = {
        "low",
        "medium",
        "high",
        "critical",
    }

    def __init__(self):
        self.gateway = AIGateway()
        self.permission_service = PermissionService()
        self._corrections: list[
            IssueClassificationCorrectionResponse
        ] = []

    async def classify(
        self,
        request: IssueClassificationRequest,
    ) -> IssueClassificationResponse:

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

        classification_prompt = (
            "You are the GroundConnect citizen issue "
            "classification assistant.\n"
            "Classify the supplied citizen issue.\n\n"
            "Choose one category from:\n"
            + ", ".join(sorted(self.SUPPORTED_CATEGORIES))
            + "\n\n"
            "Choose one priority from:\n"
            + ", ".join(sorted(self.SUPPORTED_PRIORITIES))
            + "\n\n"
            "Requirements:\n"
            "- Do not invent information.\n"
            "- Return a category and priority.\n"
            "- Provide a confidence value between 0 and 1.\n"
            "- Mark needs_human_review as true when confidence "
            "is low or classification is uncertain.\n\n"
            "Citizen issue:\n"
            + request.issue_text
        )

        response = await self.gateway.generate(
            prompt=classification_prompt,
            provider=request.provider,
            model=request.model,
        )

        if response.prompt_injection_detected:
            return IssueClassificationResponse(
                category="other",
                priority="medium",
                confidence=0.0,
                needs_human_review=True,
                coverage=(
                    "Classification was blocked because the "
                    "request contained a detected prompt injection."
                ),
                freshness=(
                    "Classification processed at "
                    + datetime.now(timezone.utc).isoformat()
                    + " UTC."
                ),
                provider=response.provider,
                model=response.model,
                pii_masked=response.pii_masked,
                prompt_injection_detected=True,
            )

        # The current mock gateway does not return structured
        # classification data. Therefore the safe default is
        # "other" with human review required.
        return IssueClassificationResponse(
            category="other",
            priority="medium",
            confidence=0.0,
            needs_human_review=True,
            coverage=(
                "Classification is based only on the citizen "
                "issue supplied in the current request."
            ),
            freshness=(
                "Classification processed at "
                + datetime.now(timezone.utc).isoformat()
                + " UTC."
            ),
            provider=response.provider,
            model=response.model,
            pii_masked=response.pii_masked,
            prompt_injection_detected=False,
        )

    def record_correction(
        self,
        request: IssueClassificationCorrectionRequest,
    ) -> IssueClassificationCorrectionResponse:

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

        correction = IssueClassificationCorrectionResponse(
            issue_id=request.issue_id,
            original_category=request.original_category,
            corrected_category=request.corrected_category,
            feedback_recorded=True,
        )

        self._corrections.append(correction)

        return correction

    def get_corrections(
        self,
    ) -> list[IssueClassificationCorrectionResponse]:

        return list(self._corrections)
