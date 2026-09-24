from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ClosureOutcome(str, Enum):
    CONFIRMED = "Resolved-Confirmed"
    UNCONFIRMED = "Resolved-Unconfirmed"
    DISPUTED_REOPENED = "Disputed-Reopened"


class ClosureIssueRegistrationRequest(BaseModel):
    issue_id: str = Field(..., min_length=1, max_length=128)
    tenant_id: str = Field(..., min_length=1, max_length=128)
    unit_id: str = Field(..., min_length=1, max_length=128)
    severity: float = Field(default=1.0, ge=0.0, le=1.0)
    corroboration_count: int = Field(default=0, ge=0)
    sla_breached: bool = False


class ClosureUnitRegistrationRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    unit_id: str = Field(..., min_length=1, max_length=128)
    unit_size: float = Field(..., gt=0)
    intake_volume: float = Field(..., gt=0)

class ResolutionProposalRequest(BaseModel):
    issue_id: str = Field(..., min_length=1, max_length=128)
    tenant_id: str = Field(..., min_length=1, max_length=128)
    worker_id: str = Field(..., min_length=1, max_length=128)
    evidence: List[str] = Field(
        ...,
        min_length=1,
        max_length=20,
    )
    resolution_summary: str = Field(
        ...,
        min_length=1,
        max_length=2000,
    )


class ResolutionProposalResponse(BaseModel):
    proposal_id: str
    issue_id: str
    tenant_id: str
    evidence: List[str]
    resolution_summary: str
    proposed_at: datetime
    status: str


class ClosureConfirmationRequest(BaseModel):
    request_id: str = Field(..., min_length=1, max_length=128)
    tenant_id: str = Field(..., min_length=1, max_length=128)
    citizen_id: str = Field(..., min_length=1, max_length=128)
    confirmed: bool
    response_language: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )


class ClosureConfirmationResponse(BaseModel):
    request_id: str
    issue_id: str
    citizen_id: str
    confirmed: bool
    outcome: ClosureOutcome
    responded_at: datetime


class ClosureConfirmationRequestView(BaseModel):
    request_id: str
    issue_id: str
    tenant_id: str
    citizen_id: str
    language: str
    created_at: datetime
    expires_at: datetime
    responded: bool = False


class ClosureMetricsResponse(BaseModel):
    tenant_id: str
    claimed_resolutions: int
    confirmed_resolutions: int
    unconfirmed_resolutions: int
    disputed_reopened: int
    confirmation_rate: float


class ServiceDebtComponents(BaseModel):
    unresolved_volume_weight: float
    age_weight: float
    severity_weight: float
    confirmed_resolution_rate: float
    corroboration_weight: float
    sla_breach_frequency: float
    unit_size_normalization: float
    intake_normalization: float


class ServiceDebtIndexResponse(BaseModel):
    tenant_id: str
    unit_id: str
    index: float
    components: ServiceDebtComponents
    unresolved_issue_ids: List[str]
    drill_through: Dict[str, object]