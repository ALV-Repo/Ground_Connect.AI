from fastapi import APIRouter, HTTPException

from models.ai import AIRequest, AIResponseModel
from services.ai_service import AIService


router = APIRouter(
    prefix="/api/v1/ai",
    tags=["AI"],
)

ai_service = AIService()


@router.post(
    "/generate",
    response_model=AIResponseModel,
)
async def generate_ai_response(
    request: AIRequest,
):
    try:
        return await ai_service.generate(request)

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