from fastapi import APIRouter, HTTPException

from models.ai import (
    AIRequest,
    AIResponseModel,
    CopilotRequest,
    CopilotResponse,
)
from security.permissions import PermissionDeniedError
from services.ai_service import AIService
from services.copilot_service import CopilotService


router = APIRouter(
    prefix="/api/v1/ai",
    tags=["AI"],
)


ai_service = AIService()
copilot_service = CopilotService()


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