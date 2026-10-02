from fastapi import APIRouter, Depends, HTTPException

from core.security import verify_token

from models.ai import (
    AIRequest,
    AIResponseModel,
    CopilotRequest,
    CopilotResponse,
    LeaderBriefingRequest,
    LeaderBriefingResponse,
    SummarizationRequest,
    SummarizationResponse,
    TranslationRequest,
    TranslationResponse,
    TranscriptionRequest,
    TranscriptionResponse,
    IssueClassificationRequest,
    IssueClassificationResponse,
    IssueClassificationCorrectionRequest,
    IssueClassificationCorrectionResponse,
    ClusteringSuggestionRequest,
    ClusteringSuggestionResponse,
    GroundAnalyticsRequest,
    GroundAnalyticsResponse,
    DarkUnitRadarRequest,
    DarkUnitRadarResponse,
)

from security.permissions import (
    PermissionDeniedError,
    UserContext,
)

from services.ai_service import AIService
from services.copilot_service import CopilotService
from services.leader_briefing import LeaderBriefingService
from services.summarization import SummarizationService
from services.translation import TranslationService
from services.transcription import TranscriptionService
from services.issue_classification import IssueClassificationService
from services.clustering import ClusteringSuggestionService
from services.ground_analytics import GroundAnalyticsService
from services.dark_unit_radar import DarkUnitRadarService


router = APIRouter(
    prefix="/api/v1/ai",
    tags=["AI"],
)


def apply_authenticated_identity(
    request,
    current_user: UserContext,
):
    """
    Replace identity fields supplied by the request body
    with the authenticated identity from the JWT.
    """
    return request.model_copy(
        update={
            "user_id": current_user.user_id,
            "user_role": current_user.role,
            "organization_id": current_user.organization_id,
        }
    )


def get_ai_service() -> AIService:
    return AIService()


def get_copilot_service() -> CopilotService:
    return CopilotService()


def get_leader_briefing_service() -> LeaderBriefingService:
    return LeaderBriefingService()


def get_summarization_service() -> SummarizationService:
    return SummarizationService()


def get_translation_service() -> TranslationService:
    return TranslationService()


def get_transcription_service() -> TranscriptionService:
    return TranscriptionService()


def get_issue_classification_service() -> IssueClassificationService:
    return IssueClassificationService()


def get_clustering_service() -> ClusteringSuggestionService:
    return ClusteringSuggestionService()


def get_ground_analytics_service() -> GroundAnalyticsService:
    return GroundAnalyticsService()


def get_dark_unit_radar_service() -> DarkUnitRadarService:
    return DarkUnitRadarService()


# ============================================================
# AI-001 to AI-005
# ============================================================


@router.post(
    "/generate",
    response_model=AIResponseModel,
)
async def generate_ai_response(
    request: AIRequest,
    current_user: UserContext = Depends(verify_token),
    ai_service: AIService = Depends(get_ai_service),
):
    request = apply_authenticated_identity(
        request,
        current_user,
    )

    try:
        return await ai_service.generate(request)

    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="AI_ACCESS_DENIED",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="AI gateway request failed",
        ) from exc


# ============================================================
# AI-006 to AI-008
# ============================================================


@router.post(
    "/copilot/ask",
    response_model=CopilotResponse,
)
async def ask_copilot(
    request: CopilotRequest,
    current_user: UserContext = Depends(verify_token),
    copilot_service: CopilotService = Depends(get_copilot_service),
):
    request = apply_authenticated_identity(
        request,
        current_user,
    )

    try:
        return await copilot_service.ask(request)

    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="AI_ACCESS_DENIED",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="AI Copilot request failed",
        ) from exc


# ============================================================
# AI-010
# ============================================================


@router.post(
    "/leader-briefing",
    response_model=LeaderBriefingResponse,
)
async def generate_leader_briefing(
    request: LeaderBriefingRequest,
    current_user: UserContext = Depends(verify_token),
    leader_briefing_service: LeaderBriefingService = Depends(
        get_leader_briefing_service
    ),
):
    request = apply_authenticated_identity(
        request,
        current_user,
    )

    try:
        return await leader_briefing_service.generate(request)

    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="AI_ACCESS_DENIED",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="AI leader briefing request failed",
        ) from exc


# ============================================================
# AI-011
# ============================================================


@router.post(
    "/summarize",
    response_model=SummarizationResponse,
)
async def summarize_content(
    request: SummarizationRequest,
    current_user: UserContext = Depends(verify_token),
    summarization_service: SummarizationService = Depends(
        get_summarization_service
    ),
):
    request = apply_authenticated_identity(
        request,
        current_user,
    )

    try:
        return await summarization_service.summarize(request)

    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="AI_ACCESS_DENIED",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="AI summarization request failed",
        ) from exc


# ============================================================
# AI-012
# ============================================================


@router.post(
    "/translate",
    response_model=TranslationResponse,
)
async def translate_text(
    request: TranslationRequest,
    current_user: UserContext = Depends(verify_token),
    translation_service: TranslationService = Depends(
        get_translation_service
    ),
):
    request = apply_authenticated_identity(
        request,
        current_user,
    )

    try:
        return await translation_service.translate(request)

    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="AI_ACCESS_DENIED",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="AI translation request failed",
        ) from exc


# ============================================================
# AI-013
# ============================================================


@router.post(
    "/transcribe",
    response_model=TranscriptionResponse,
)
async def transcribe_audio(
    request: TranscriptionRequest,
    current_user: UserContext = Depends(verify_token),
    transcription_service: TranscriptionService = Depends(
        get_transcription_service
    ),
):
    request = apply_authenticated_identity(
        request,
        current_user,
    )

    try:
        return await transcription_service.transcribe(request)

    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="AI_ACCESS_DENIED",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="AI transcription request failed",
        ) from exc


# ============================================================
# AI-016
# Citizen Issue Classification + Human Correction
# ============================================================


@router.post(
    "/classify-issue",
    response_model=IssueClassificationResponse,
)
async def classify_issue(
    request: IssueClassificationRequest,
    current_user: UserContext = Depends(verify_token),
    issue_classification_service: IssueClassificationService = Depends(
        get_issue_classification_service
    ),
):
    request = apply_authenticated_identity(
        request,
        current_user,
    )

    try:
        return await issue_classification_service.classify(request)

    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="AI_ACCESS_DENIED",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="AI issue classification request failed",
        ) from exc


@router.post(
    "/classify-issue/correction",
    response_model=IssueClassificationCorrectionResponse,
)
async def record_issue_classification_correction(
    request: IssueClassificationCorrectionRequest,
    current_user: UserContext = Depends(verify_token),
    issue_classification_service: IssueClassificationService = Depends(
        get_issue_classification_service
    ),
):
    request = apply_authenticated_identity(
        request,
        current_user,
    )

    try:
        return issue_classification_service.record_correction(
            request
        )

    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="AI_ACCESS_DENIED",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="AI issue classification correction failed",
        ) from exc


# ============================================================
# AI-017
# AI-Assisted Clustering Suggestions
# ============================================================


@router.post(
    "/clustering/suggest",
    response_model=ClusteringSuggestionResponse,
)
async def suggest_clusters(
    request: ClusteringSuggestionRequest,
    current_user: UserContext = Depends(verify_token),
    clustering_service: ClusteringSuggestionService = Depends(
        get_clustering_service
    ),
):
    request = apply_authenticated_identity(
        request,
        current_user,
    )

    try:
        return await clustering_service.suggest_clusters(request)

    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="AI_ACCESS_DENIED",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="AI clustering suggestion request failed",
        ) from exc


# ============================================================
# AI-018
# Ground-Intelligence Analytics
# ============================================================


@router.post(
    "/ground-analytics",
    response_model=GroundAnalyticsResponse,
)
async def analyze_ground_intelligence(
    request: GroundAnalyticsRequest,
    current_user: UserContext = Depends(verify_token),
    ground_analytics_service: GroundAnalyticsService = Depends(
        get_ground_analytics_service
    ),
):
    request = apply_authenticated_identity(
        request,
        current_user,
    )

    try:
        return await ground_analytics_service.analyze(request)

    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="AI_ACCESS_DENIED",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="AI ground analytics request failed",
        ) from exc


# ============================================================
# AI-019
# Dark Unit Radar
# ============================================================


@router.post(
    "/dark-unit-radar",
    response_model=DarkUnitRadarResponse,
)
async def analyze_dark_units(
    request: DarkUnitRadarRequest,
    current_user: UserContext = Depends(verify_token),
    dark_unit_radar_service: DarkUnitRadarService = Depends(
        get_dark_unit_radar_service
    ),
):
    request = apply_authenticated_identity(
        request,
        current_user,
    )

    try:
        return await dark_unit_radar_service.analyze(request)

    except PermissionDeniedError as exc:
        raise HTTPException(
            status_code=403,
            detail="AI_ACCESS_DENIED",
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="AI dark unit radar request failed",
        ) from exc