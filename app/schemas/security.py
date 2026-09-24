from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================
# BE-012 — Transport & At-rest Encryption
# ============================================================

class EncryptionRequest(BaseModel):
    plaintext: str = Field(
        ...,
        min_length=1,
        max_length=10_000_000,
    )

    context: Optional[str] = Field(
        default=None,
        max_length=200,
    )


class EncryptionResponse(BaseModel):
    success: bool

    ciphertext: str

    algorithm: str
    key_version: str

    created_at: datetime


class DecryptionRequest(BaseModel):
    ciphertext: str = Field(
        ...,
        min_length=1,
        max_length=20_000_000,
    )

    context: Optional[str] = Field(
        default=None,
        max_length=200,
    )


class DecryptionResponse(BaseModel):
    success: bool

    plaintext: str

    algorithm: str
    key_version: str


class SensitiveFieldEncryptRequest(BaseModel):
    entity_type: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    entity_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    fields: Dict[str, str] = Field(
        ...,
        min_length=1,
    )


class SensitiveFieldEncryptResponse(BaseModel):
    success: bool

    entity_type: str
    entity_id: str

    encrypted_fields: Dict[str, str]

    algorithm: str
    key_version: str


class TLSStatusResponse(BaseModel):
    valid: bool

    minimum_tls_version: str
    preferred_tls_version: str

    hsts_enabled: bool
    certificate_pinning_required: bool


# ============================================================
# BE-013 — Incident Response
# ============================================================

class IncidentCreateRequest(BaseModel):
    incident_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    incident_type: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    severity: str = Field(
        default="medium",
        max_length=32,
    )

    description: str = Field(
        ...,
        min_length=1,
        max_length=10_000,
    )

    detected_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    affected_tenant_id: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    affected_resources: List[str] = Field(
        default_factory=list,
        max_length=1000,
    )

    metadata: dict = Field(
        default_factory=dict,
    )

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, value: str) -> str:
        allowed = {
            "low",
            "medium",
            "high",
            "critical",
        }

        if value not in allowed:
            raise ValueError(
                f"severity must be one of: {', '.join(sorted(allowed))}"
            )

        return value


class IncidentResponse(BaseModel):
    incident_id: str

    incident_type: str
    severity: str

    description: str

    status: str

    detected_by: str

    assigned_to: Optional[str] = None

    affected_tenant_id: Optional[str] = None

    affected_resources: List[str] = Field(
        default_factory=list,
    )

    created_at: datetime
    updated_at: datetime

    resolved_at: Optional[datetime] = None

    metadata: dict = Field(
        default_factory=dict,
    )


class IncidentUpdateRequest(BaseModel):
    status: Optional[str] = Field(
        default=None,
        max_length=32,
    )

    severity: Optional[str] = Field(
        default=None,
        max_length=32,
    )

    assigned_to: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    resolution_notes: Optional[str] = Field(
        default=None,
        max_length=10_000,
    )

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        allowed = {
            "open",
            "investigating",
            "contained",
            "resolved",
            "closed",
        }

        if value not in allowed:
            raise ValueError(
                f"status must be one of: {', '.join(sorted(allowed))}"
            )

        return value

    @field_validator("severity")
    @classmethod
    def validate_severity(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        allowed = {
            "low",
            "medium",
            "high",
            "critical",
        }

        if value not in allowed:
            raise ValueError(
                f"severity must be one of: {', '.join(sorted(allowed))}"
            )

        return value


class IncidentActionRequest(BaseModel):
    incident_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    action: str = Field(
        ...,
        min_length=1,
        max_length=64,
    )

    performed_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    reason: Optional[str] = Field(
        default=None,
        max_length=2000,
    )

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        allowed = {
            "acknowledge",
            "investigate",
            "contain",
            "resolve",
            "close",
            "escalate",
        }

        if value not in allowed:
            raise ValueError(
                f"action must be one of: {', '.join(sorted(allowed))}"
            )

        return value


class IncidentActionResponse(BaseModel):
    success: bool

    incident_id: str

    action: str

    status: str

    performed_by: str
    performed_at: datetime


class IncidentListResponse(BaseModel):
    items: List[IncidentResponse]

    total: int

    page: int = 1
    page_size: int = 50


class IncidentSearchRequest(BaseModel):
    severity: Optional[str] = Field(
        default=None,
        max_length=32,
    )

    status: Optional[str] = Field(
        default=None,
        max_length=32,
    )

    incident_type: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    tenant_id: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    page: int = Field(
        default=1,
        ge=1,
    )

    page_size: int = Field(
        default=50,
        ge=1,
        le=500,
    )


# ============================================================
# Pentest Gate
# ============================================================

class PentestGateRequest(BaseModel):
    environment: str = Field(
        default="development",
        max_length=32,
    )

    requested_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    acknowledgement: bool

    notes: Optional[str] = Field(
        default=None,
        max_length=5000,
    )


class PentestGateResponse(BaseModel):
    allowed: bool

    environment: str

    pentest_required: bool
    pentest_completed: bool

    message: str


# ============================================================
# Security Health / Status
# ============================================================

class SecurityHealthResponse(BaseModel):
    encryption_enabled: bool
    transport_security_enabled: bool
    incident_response_enabled: bool

    pentest_gate_enabled: bool

    minimum_tls_version: str
    preferred_tls_version: str

    hsts_enabled: bool
    certificate_pinning_required: bool

    active_incidents: int


class SecurityEventResponse(BaseModel):
    event_id: str

    event_type: str
    severity: str

    actor_id: Optional[str] = None
    tenant_id: Optional[str] = None

    timestamp: datetime

    details: dict = Field(
        default_factory=dict,
    )


class SecuritySuccessResponse(BaseModel):
    success: bool = True

    message: str = "Security operation completed successfully."


class SecurityErrorResponse(BaseModel):
    success: bool = False

    error: str

# ============================================================
# BE-013 — Incident Response Route Requests
# ============================================================

class IncidentRouteCreateRequest(BaseModel):
    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=256,
    )

    incident_type: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=128,
    )

    description: str = Field(
        ...,
        min_length=1,
        max_length=10_000,
    )

    severity: str = Field(
        ...,
        min_length=1,
        max_length=32,
    )

    assigned_to: Optional[str] = Field(
        default=None,
        max_length=128,
    )


class IncidentEvidenceRequest(BaseModel):
    evidence_type: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    captured_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    evidence: str = Field(
        ...,
        min_length=1,
        max_length=20_000_000,
    )

    location_reference: Optional[str] = Field(
        default=None,
        max_length=1000,
    )

class SecurityEncryptPayload(BaseModel):
    plaintext: str = Field(
        ...,
        min_length=1,
        max_length=10_000_000,
    )


class SecurityDecryptPayload(BaseModel):
    encrypted: Dict[str, object]


class SecurityFieldsPayload(BaseModel):
    fields: Dict[str, object]