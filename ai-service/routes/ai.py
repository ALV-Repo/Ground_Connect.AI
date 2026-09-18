from fastapi import APIRouter, HTTPException

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
)

from security.permissions import PermissionDeniedError

from services.ai_service import AIService
from services.copilot_service import CopilotService
from services.leader_briefing import LeaderBriefingService
from services.summarization import SummarizationService
from services.translation import TranslationService
from services.transcription import TranscriptionService


router = APIRouter(
    prefix="/api/v1/ai",
    tags=["AI"],
)


ai_service = AIService()
copilot_service = CopilotService()
leader_briefing_service = LeaderBriefingService()
summarization_service = SummarizationService()
translation_service = TranslationService()
transcription_service = TranscriptionService()


# ============================================================
# AI-001 to AI-005
# ============================================================


@router.post(
    "/generate",
    response_model=AIResponseModel,
)
async def generate_ai_response(
    request: AIRequest,
):
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
):
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
):
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
):
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
):
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
):
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
