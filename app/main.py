from fastapi import FastAPI

from app.api.routes.ai import router as ai_router


app = FastAPI(
    title="Ground Connect API",
    version="1.0.0",
)


app.include_router(
    ai_router,
    prefix="/api/v1",
)