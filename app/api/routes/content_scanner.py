from fastapi import APIRouter, HTTPException, Query

from app.schemas.content_scanner import ContentScanRequest
from app.services.content_scanner import content_scanner_service


router = APIRouter(
    prefix="/content-scanner",
    tags=["BE-026 Prohibited Attribute Scanner"],
)


@router.post("/scan")
def scan_content(request: ContentScanRequest):
    return content_scanner_service.scan(
        request
    ).model_dump(mode="json")


@router.get("/alerts")
def list_alerts(
    tenant_id: str = Query(...),
):
    alerts = content_scanner_service.list_alerts(
        tenant_id=tenant_id,
    )

    return [
        {
            **alert,
            "matches": [
                match.model_dump(mode="json")
                for match in alert["matches"]
            ],
        }
        for alert in alerts
    ]


@router.get("/alerts/{scan_id}")
def get_alert(
    scan_id: str,
    tenant_id: str = Query(...),
):
    try:
        alert = content_scanner_service.get_alert(
            tenant_id=tenant_id,
            scan_id=scan_id,
        )

        return {
            **alert,
            "matches": [
                match.model_dump(mode="json")
                for match in alert["matches"]
            ],
        }

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        )
    except PermissionError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        )