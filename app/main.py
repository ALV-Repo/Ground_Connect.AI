from fastapi import FastAPI

from app.api.routes.ai import router as ai_router
from app.api.routes.auth import router as auth_router
from app.api.routes.authorization import router as authorization_router
from app.api.routes.audit import router as audit_router
from app.api.routes.field_authorization import router as field_authorization_router
from app.api.routes.members import router as members_router
from app.api.routes.messaging import router as messaging_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.vendor import router as vendor_router
from app.api.routes.tpi import router as tpi_router
from app.api.routes.security import router as security_router
from app.api.routes.incident_response import router as incident_response_router
from app.api.routes.notifications import router as notifications_router
from app.api.routes.performance import router as performance_router
from app.api.routes.recovery import router as recovery_router
from app.api.routes.observability import router as observability_router
from app.api.routes.citizen import router as citizen_router


app = FastAPI(
    title="Ground Connect API",
    version="1.0.0",
)


# ============================================================
# Existing AI & Authentication
# ============================================================

app.include_router(ai_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")


# ============================================================
# BE-003: Central Authorization
# BE-004: ADR Logging & Admin Query
# BE-005: Field-level Authorization
# ============================================================

app.include_router(
    authorization_router,
    prefix="/api/v1",
)

app.include_router(
    audit_router,
    prefix="/api/v1",
)

app.include_router(
    field_authorization_router,
    prefix="/api/v1",
)


# ============================================================
# BE-006: Member Lifecycle & Bulk Import
# ============================================================

app.include_router(
    members_router,
    prefix="/api/v1",
)


# ============================================================
# BE-007 / BE-008: Messaging
# ============================================================

app.include_router(
    messaging_router,
    prefix="/api/v1",
)


# ============================================================
# BE-009: Task Engine & Evidence
# ============================================================

app.include_router(
    tasks_router,
    prefix="/api/v1",
)


# ============================================================
# BE-010: Vendor Support Elevation
# ============================================================

app.include_router(
    vendor_router,
    prefix="/api/v1",
)


# ============================================================
# BE-011: Two-Person Integrity
# ============================================================

app.include_router(
    tpi_router,
    prefix="/api/v1",
)


# ============================================================
# BE-012: Transport & At-rest Encryption
# ============================================================

app.include_router(
    security_router,
    prefix="/api/v1",
)


# ============================================================
# BE-013: Incident Response & Pentest
# ============================================================

app.include_router(
    incident_response_router,
    prefix="/api/v1",
)


# ============================================================
# BE-014: Notification Delivery
# ============================================================

app.include_router(
    notifications_router,
    prefix="/api/v1",
)


# ============================================================
# BE-015: Performance & Scalability
# ============================================================

app.include_router(
    performance_router,
    prefix="/api/v1",
)


# ============================================================
# BE-016: HA / Backup / Recovery
# ============================================================

app.include_router(
    recovery_router,
    prefix="/api/v1",
)


# ============================================================
# BE-017: Observability & SIEM
# ============================================================

app.include_router(
    observability_router,
    prefix="/api/v1",
)


# ============================================================
# BE-018: Citizen Issue Intake & Clustering
# ============================================================

app.include_router(
    citizen_router,
    prefix="/api/v1",
)