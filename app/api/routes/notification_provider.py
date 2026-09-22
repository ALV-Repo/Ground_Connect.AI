from fastapi import APIRouter, HTTPException, Query

from app.schemas.notification_provider import (
    NotificationChannel,
    NotificationSendRequest,
    ProviderCreate,
    ProviderStatus,
)
from app.services.notification_provider import notification_provider_service


router = APIRouter(
    prefix="/notification-providers",
    tags=["BE-025 Notification Providers"],
)


@router.post("/providers")
def register_provider(request: ProviderCreate):
    return notification_provider_service.register_provider(
        request
    ).model_dump(mode="json")


@router.get("/providers")
def list_providers(
    tenant_id: str = Query(...),
    channel: NotificationChannel = Query(...),
):
    return [
        provider.model_dump(mode="json")
        for provider in notification_provider_service.list_providers(
            tenant_id=tenant_id,
            channel=channel,
        )
    ]


@router.get("/providers/{provider_id}")
def get_provider(
    provider_id: str,
    tenant_id: str = Query(...),
):
    try:
        return notification_provider_service.get_provider(
            tenant_id=tenant_id,
            provider_id=provider_id,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/providers/{provider_id}/status")
def set_provider_status(
    provider_id: str,
    status: ProviderStatus,
    tenant_id: str = Query(...),
):
    try:
        return notification_provider_service.set_provider_status(
            tenant_id=tenant_id,
            provider_id=provider_id,
            status=status,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/send")
def send_notification(request: NotificationSendRequest):
    try:
        return notification_provider_service.send(
            request
        ).model_dump(mode="json")
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc))