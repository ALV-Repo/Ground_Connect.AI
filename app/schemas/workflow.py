from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class IssueStatus(str, Enum):
    NEW = "New"
    ASSIGNED = "Assigned"
    ACCEPTED = "Accepted"
    IN_PROGRESS = "In Progress"
    WAITING = "Waiting"
    ESCALATED = "Escalated"
    RESOLUTION_PROPOSED = "Resolution Proposed"
    RESOLVED_CONFIRMED = "Resolved-Confirmed"
    RESOLVED_UNCONFIRMED = "Resolved-Unconfirmed"
    DISPUTED_REOPENED = "Disputed-Reopened"
    CLOSED = "Closed"
    REJECTED = "Rejected"


class SLAConfigCreate(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    category: str = Field(..., min_length=1, max_length=128)
    priority: str = Field(..., min_length=1, max_length=32)
    response_target_minutes: int = Field(..., gt=0)
    resolution_target_minutes: int = Field(..., gt=0)
    escalation_chain: List[str] = Field(..., min_length=1, max_length=20)


class SLAConfigResponse(SLAConfigCreate):
    config_id: str
    created_at: datetime


class IssueStatusUpdateRequest(BaseModel):
    issue_id: str = Field(..., min_length=1, max_length=128)
    tenant_id: str = Field(..., min_length=1, max_length=128)
    status: IssueStatus
    actor_id: str = Field(..., min_length=1, max_length=128)
    reason: Optional[str] = Field(default=None, max_length=2000)


class IssueStatusResponse(BaseModel):
    issue_id: str
    tenant_id: str
    status: IssueStatus
    changed_at: datetime
    actor_id: str
    reason: Optional[str] = None


class SLAStatusResponse(BaseModel):
    issue_id: str
    tenant_id: str
    response_due_at: Optional[datetime] = None
    resolution_due_at: Optional[datetime] = None
    response_breached: bool = False
    resolution_breached: bool = False
    escalation_triggered: bool = False
    current_escalation_level: int = 0


class EscalationEvent(BaseModel):
    event_id: str
    issue_id: str
    tenant_id: str
    level: int
    target: str
    reason: str
    triggered_at: datetime
    deterministic_policy: bool = True


class RejectionRequest(BaseModel):
    issue_id: str = Field(..., min_length=1, max_length=128)
    tenant_id: str = Field(..., min_length=1, max_length=128)
    actor_id: str = Field(..., min_length=1, max_length=128)
    reason: str = Field(..., min_length=1, max_length=2000)


class DisputeReopenRequest(BaseModel):
    issue_id: str = Field(..., min_length=1, max_length=128)
    tenant_id: str = Field(..., min_length=1, max_length=128)
    actor_id: str = Field(..., min_length=1, max_length=128)
    reason: str = Field(..., min_length=1, max_length=2000)


class WorkflowIssueResponse(BaseModel):
    issue_id: str
    tenant_id: str
    status: IssueStatus
    created_at: datetime
    status_history: List[IssueStatusResponse] = Field(default_factory=list)
