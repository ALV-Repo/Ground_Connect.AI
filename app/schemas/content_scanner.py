from __future__ import annotations

from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class ScanSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ScanMatch(BaseModel):
    attribute: str
    matched_text: str
    severity: ScanSeverity
    reason: str


class ContentScanRequest(BaseModel):
    tenant_id: str
    content: str
    source: str = "api"


class ContentScanResponse(BaseModel):
    scan_id: str
    tenant_id: str
    safe: bool
    matches: List[ScanMatch] = Field(default_factory=list)
    alert_created: bool