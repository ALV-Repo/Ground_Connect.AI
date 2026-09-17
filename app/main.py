from fastapi import FastAPI

from app.api.routes.ai import router as ai_router
from app.api.routes.auth import router as auth_router


app = FastAPI(
    title="Ground Connect API",
    version="1.0.0",
)


app.include_router(
    ai_router,
    prefix="/api/v1",
)

app.include_router(
    auth_router,
    prefix="/api/v1",
)