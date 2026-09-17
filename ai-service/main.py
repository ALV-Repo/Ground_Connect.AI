from fastapi import FastAPI

from core.config import settings
from routes.ai import router as ai_router


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="GroundConnect internal AI service",
)


app.include_router(ai_router)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }