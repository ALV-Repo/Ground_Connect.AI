from fastapi import FastAPI, HTTPException, status

from core.config import settings
from gateway.providers import ProviderRegistry
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


@app.get("/health/ready")
async def readiness_check():
    registry = ProviderRegistry(settings.approved_providers)

    provider = settings.ai_provider

    try:
        registry.get_provider(provider)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "status": "not_ready",
                "provider": provider,
                "reason": str(exc),
            },
        ) from exc

    return {
        "status": "ready",
        "provider": provider,
    }