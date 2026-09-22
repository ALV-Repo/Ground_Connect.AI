from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field


class CredentialScope(str, Enum):
    ISSUES_READ = "issues:read"
    ISSUES_WRITE = "issues:write"
    TASKS_READ = "tasks:read"
    TASKS_WRITE = "tasks:write"
    WEBHOOKS_MANAGE = "webhooks:manage"


class PublicCredentialCreate(BaseModel):
    tenant_id: str
    name: str
    scopes: List[CredentialScope]
    rate_limit_per_minute: int = Field(default=60, ge=1)


class PublicCredentialResponse(BaseModel):
    credential_id: str
    tenant_id: str
    name: str
    scopes: List[CredentialScope]
    rate_limit_per_minute: int
    active: bool
    created_at: datetime


class WebhookCreate(BaseModel):
    tenant_id: str
    url: str
    events: List[str]
    secret: str = Field(min_length=16)


class WebhookResponse(BaseModel):
    webhook_id: str
    tenant_id: str
    url: str
    events: List[str]
    active: bool
    created_at: datetime


class WebhookDeliveryResponse(BaseModel):
    delivery_id: str
    webhook_id: str
    event_type: str
    signature: str
    attempt: int
    status: str
    delivered_at: datetime | None = None


class WebhookEventRequest(BaseModel):
    tenant_id: str
    event_type: str
    payload: Dict[str, object]
    event_id: str | None = None