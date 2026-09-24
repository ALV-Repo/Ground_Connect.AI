from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.schemas.notifications import NotificationCreateRequest
from app.services.notifications import notification_service


router = APIRouter(
    prefix="/notifications",
    tags=["Notifications"],
)


# ---------------------------------------------------------------------------
# Create Notification
# ---------------------------------------------------------------------------

@router.post("")
def create_notification(
    payload: NotificationCreateRequest,
):
    try:
        return notification_service.create_notification(
            notification_id=payload.notification_id,
            tenant_id=payload.tenant_id,
            title=payload.title,
            body=payload.body,
            created_by=payload.created_by,
            recipients=[
                recipient.model_dump()
                for recipient in payload.recipients
            ],
            priority=payload.priority,
            scheduled_at=payload.scheduled_at,
            expires_at=payload.expires_at,
            metadata=payload.metadata,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Search Notifications
# NOTE: This route must come before /{notification_id}
# ---------------------------------------------------------------------------

@router.get("/search")
def search_notifications(
    tenant_id: str = Query(...),
    query: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    channel: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    try:
        return notification_service.search(
            tenant_id=tenant_id,
            query=query,
            status=status,
            channel=channel,
            priority=priority,
            page=page,
            page_size=page_size,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Get Notification
# ---------------------------------------------------------------------------

@router.get("/{notification_id}")
def get_notification(
    notification_id: str,
    tenant_id: str = Query(...),
):
    notification = notification_service.get_notification(
        notification_id=notification_id,
        tenant_id=tenant_id,
    )

    if notification is None:
        raise HTTPException(
            status_code=404,
            detail=f"Notification '{notification_id}' not found.",
        )

    return notification


# ---------------------------------------------------------------------------
# Deliver Notification
# ---------------------------------------------------------------------------

@router.post("/{notification_id}/deliver")
def deliver_notification(
    notification_id: str,
    tenant_id: str = Query(...),
    recipient_id: str = Query(...),
    channel: str = Query(...),
    requested_by: str = Query(...),
):
    try:
        return notification_service.deliver(
            notification_id=notification_id,
            tenant_id=tenant_id,
            recipient_id=recipient_id,
            channel=channel,
            requested_by=requested_by,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Retry Notification
# ---------------------------------------------------------------------------

@router.post("/{notification_id}/retry")
def retry_notification(
    notification_id: str,
    tenant_id: str = Query(...),
    recipient_id: Optional[str] = Query(None),
    requested_by: str = Query(...),
):
    try:
        return notification_service.retry(
            notification_id=notification_id,
            tenant_id=tenant_id,
            recipient_id=recipient_id,
            requested_by=requested_by,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Cancel Notification
# ---------------------------------------------------------------------------

@router.post("/{notification_id}/cancel")
def cancel_notification(
    notification_id: str,
    tenant_id: str = Query(...),
    requested_by: str = Query(...),
    reason: Optional[str] = Query(None),
):
    try:
        return notification_service.cancel(
            notification_id=notification_id,
            tenant_id=tenant_id,
            requested_by=requested_by,
            reason=reason,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Notification Status
# ---------------------------------------------------------------------------

@router.get("/{notification_id}/status")
def notification_status(
    notification_id: str,
    tenant_id: str = Query(...),
):
    try:
        return notification_service.status(
            notification_id=notification_id,
            tenant_id=tenant_id,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc


# ---------------------------------------------------------------------------
# Delivery Attempts
# ---------------------------------------------------------------------------

@router.get("/{notification_id}/attempts")
def notification_attempts(
    notification_id: str,
    tenant_id: str = Query(...),
):
    try:
        return {
            "items": notification_service.delivery_attempts(
                notification_id=notification_id,
                tenant_id=tenant_id,
            )
        }

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc