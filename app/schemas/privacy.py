from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class LawfulBasis(str, Enum):
    CONSENT = "consent"
    LEGAL_OBLIGATION = "legal_obligation"
    VITAL_INTEREST = "vital_interest"
    PUBLIC_FUNCTION = "public_function"


class PrivacyInteractionCreate(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    principal_id: str = Field(..., min_length=1, max_length=128)
    purpose: str = Field(..., min_length=1, max_length=256)
    notice_version: str = Field(..., min_length=1, max_length=128)
    language: str = Field(..., min_length=1, max_length=64)
    mechanism: str = Field(..., min_length=1, max_length=128)
    lawful_basis: LawfulBasis
    timestamp: Optional[datetime] = None


class PrivacyInteractionResponse(BaseModel):
    receipt_id: str
    tenant_id: str
    principal_id: str
    purpose: str
    notice_version: str
    language: str
    mechanism: str
    lawful_basis: LawfulBasis
    timestamp: datetime


class DataAccessRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    principal_id: str = Field(..., min_length=1, max_length=128)


class DataAccessResponse(BaseModel):
    tenant_id: str
    principal_id: str
    records: List[Dict[str, Any]]


class DataCorrectionRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    principal_id: str = Field(..., min_length=1, max_length=128)
    field: str = Field(..., min_length=1, max_length=128)
    value: Any


class DataCorrectionResponse(BaseModel):
    tenant_id: str
    principal_id: str
    field: str
    corrected: bool
    corrected_at: datetime


class ErasureRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    principal_id: str = Field(..., min_length=1, max_length=128)
    verification_reference: str = Field(
        ...,
        min_length=1,
        max_length=256,
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
    )


class ErasureCertificate(BaseModel):
    certificate_id: str
    request_id: str
    tenant_id: str
    principal_id: str
    removed: List[str]
    retained: List[str]
    retention_reasons: Dict[str, str]
    completed_at: datetime


class RetentionPolicyCreate(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    data_class: str = Field(..., min_length=1, max_length=128)
    retention_days: int = Field(..., ge=1)
    legal_hold_allowed: bool = True


class RetentionPolicyResponse(BaseModel):
    policy_id: str
    tenant_id: str
    data_class: str
    retention_days: int
    legal_hold_allowed: bool


class LegalHoldRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    data_class: str = Field(..., min_length=1, max_length=128)
    reason: str = Field(..., min_length=1, max_length=500)
    active: bool = True


class LegalHoldResponse(BaseModel):
    hold_id: str
    tenant_id: str
    data_class: str
    reason: str
    active: bool
    created_at: datetime