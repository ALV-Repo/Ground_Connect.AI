from fastapi import APIRouter, HTTPException, Query

from app.schemas.public_api import (
    CredentialScope,
    PublicCredentialCreate,
    WebhookCreate,
    WebhookEventRequest,
)
from app.services.public_api import public_api_service


router = APIRouter(
    prefix="/public",
    tags=["BE-024 Public API & Webhooks"],
)


@router.post("/credentials")
def create_credential(request: PublicCredentialCreate):
    return public_api_service.create_credential(request).model_dump(mode="json")


@router.get("/credentials/{credential_id}")
def get_credential(
    credential_id: str,
    tenant_id: str = Query(...),
):
    try:
        return public_api_service.get_credential(
            tenant_id=tenant_id,
            credential_id=credential_id,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/webhooks")
def create_webhook(request: WebhookCreate):
    try:
        return public_api_service.create_webhook(request).model_dump(
            mode="json"
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/webhooks/{webhook_id}")
def get_webhook(
    webhook_id: str,
    tenant_id: str = Query(...),
):
    try:
        return public_api_service.get_webhook(
            tenant_id=tenant_id,
            webhook_id=webhook_id,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/webhooks/events")
def deliver_webhook_event(request: WebhookEventRequest):
    try:
        deliveries = public_api_service.deliver_event(request)

        return [
            delivery.model_dump(mode="json")
            for delivery in deliveries
        ]
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/webhooks/deliveries/{delivery_id}/retry")
def retry_webhook_delivery(
    delivery_id: str,
    tenant_id: str = Query(...),
):
    try:
        return public_api_service.retry_delivery(
            tenant_id=tenant_id,
            delivery_id=delivery_id,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.get("/webhooks/deliveries/{delivery_id}")
def get_webhook_delivery(
    delivery_id: str,
    tenant_id: str = Query(...),
):
    try:
        return public_api_service.get_delivery(
            tenant_id=tenant_id,
            delivery_id=delivery_id,
        ).model_dump(mode="json")
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/rate-limit/check")
def check_rate_limit(
    tenant_id: str = Query(...),
    credential_id: str = Query(...),
    scope: CredentialScope = Query(...),
):
    try:
        public_api_service.check_rate_limit(
            tenant_id=tenant_id,
            credential_id=credential_id,
            scope=scope,
        )

        return {
            "allowed": True,
            "tenant_id": tenant_id,
            "credential_id": credential_id,
            "scope": scope.value,
        }

    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=429, detail=str(exc))