from __future__ import annotations

from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field


class NotificationChannel(str, Enum):
    SMS = "sms"
    EMAIL = "email"


class ProviderStatus(str, Enum):
    ACTIVE = "active"
    FAILED = "failed"
    DISABLED = "disabled"


class ProviderCreate(BaseModel):
    tenant_id: str
    provider_name: str
    channel: NotificationChannel
    priority: int = Field(default=1, ge=1)
    enabled: bool = True


class ProviderResponse(BaseModel):
    provider_id: str
    tenant_id: str
    provider_name: str
    channel: NotificationChannel
    priority: int
    status: ProviderStatus
    enabled: bool


class NotificationSendRequest(BaseModel):
    tenant_id: str
    channel: NotificationChannel
    recipient: str
    message: str
    metadata: Dict[str, str] = Field(default_factory=dict)


class NotificationSendResponse(BaseModel):
    notification_id: str
    tenant_id: str
    channel: NotificationChannel
    status: str
    provider_id: str
    attempts: int
    failed_providers: List[str] = Field(default_factory=list)
    