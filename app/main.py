from fastapi import Depends, FastAPI, Request
from fastapi.responses import Response

from app.core.security import get_current_user

from app.api.routes.ai import router as ai_router
from app.api.routes.auth import router as auth_router
from app.api.routes.authorization import router as authorization_router
from app.api.routes.audit import router as audit_router
from app.api.routes.field_authorization import (
    router as field_authorization_router,
)
from app.api.routes.members import router as members_router
from app.api.routes.messaging import router as messaging_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.vendor import router as vendor_router
from app.api.routes.tpi import router as tpi_router
from app.api.routes.security import router as security_router
from app.api.routes.incident_response import (
    router as incident_response_router,
)
from app.api.routes.notifications import router as notifications_router
from app.api.routes.performance import router as performance_router
from app.api.routes.recovery import router as recovery_router
from app.api.routes.observability import router as observability_router
from app.api.routes.citizen import router as citizen_router
from app.api.routes.workflow import router as workflow_router
from app.api.routes.closure import router as closure_router
from app.api.routes.offline import router as offline_router
from app.api.routes.privacy import router as privacy_router
from app.api.routes.compliance import router as compliance_router
from app.api.routes.public_api import router as public_api_router
from app.api.routes.notification_provider import (
    router as notification_provider_router,
)
from app.api.routes.content_scanner import (
    router as content_scanner_router,
)

app = FastAPI(
    title="Ground Connect API",
    version="1.0.0",
)


# ============================================================
# Request / Correlation ID Middleware
# ============================================================

@app.middleware("http")
async def correlation_id_middleware(
    request: Request,
    call_next,
) -> Response:
    correlation_id = request.headers.get(
        "X-Correlation-ID"
    )

    if not correlation_id:
        from app.core.observability import (
            generate_correlation_id,
        )

        correlation_id = generate_correlation_id()

    request.state.correlation_id = correlation_id

    response = await call_next(request)

    response.headers["X-Correlation-ID"] = correlation_id

    return response


# ============================================================
# Authentication
# ============================================================

# Auth endpoints remain public because they establish
# authentication/session credentials.
app.include_router(
    auth_router,
    prefix="/api/v1",
)


# ============================================================
# BE-001 / AI
# ============================================================

app.include_router(
    ai_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-003: Central Authorization
# BE-004: ADR Logging & Admin Query
# BE-005: Field-level Authorization
# ============================================================

app.include_router(
    authorization_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)

app.include_router(
    audit_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)

app.include_router(
    field_authorization_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-006: Member Lifecycle & Bulk Import
# ============================================================

app.include_router(
    members_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-007 / BE-008: Messaging
# ============================================================

app.include_router(
    messaging_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-009: Task Engine & Evidence
# ============================================================

app.include_router(
    tasks_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-010: Vendor Support Elevation
# ============================================================

app.include_router(
    vendor_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-011: Two-Person Integrity
# ============================================================

app.include_router(
    tpi_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-012: Transport & At-rest Encryption
# ============================================================

app.include_router(
    security_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-013: Incident Response & Pentest
# ============================================================

app.include_router(
    incident_response_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-014: Notification Delivery
# ============================================================

app.include_router(
    notifications_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-015: Performance & Scalability
# ============================================================

app.include_router(
    performance_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-016: HA / Backup / Recovery
# ============================================================

app.include_router(
    recovery_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-017: Observability & SIEM
# ============================================================

app.include_router(
    observability_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-018: Citizen Issue Intake & Clustering
# ============================================================

app.include_router(
    citizen_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-019: Citizen Workflow, SLA & Escalation
# ============================================================

app.include_router(
    workflow_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-020: Citizen-Verified Closure & Service Debt Index
# ============================================================

app.include_router(
    closure_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-021: Offline Sync Engine
# ============================================================

app.include_router(
    offline_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-022: DPDP Privacy Controls & Erasure
# ============================================================

app.include_router(
    privacy_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-023: Compliance Mode Profiles
# ============================================================

app.include_router(
    compliance_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-024: Public REST API & Webhooks
# ============================================================

app.include_router(
    public_api_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-025: SMS/Email Provider Abstraction & Failover
# ============================================================

app.include_router(
    notification_provider_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)


# ============================================================
# BE-026: Prohibited Attribute Content Scanner
# ============================================================

app.include_router(
    content_scanner_router,
    prefix="/api/v1",
    dependencies=[Depends(get_current_user)],
)
