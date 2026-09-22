from __future__ import annotations

from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field


class ComplianceMode(str, Enum):
    STANDARD = "standard"
    STRICT = "strict"
    HIGH_RISK = "high_risk"


class ComplianceProfileCreate(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    profile_name: str = Field(..., min_length=1, max_length=128)
    mode: ComplianceMode
    description: str = Field(default="", max_length=500)
    controls: Dict[str, bool] = Field(default_factory=dict)


class ComplianceProfileResponse(BaseModel):
    profile_id: str
    tenant_id: str
    profile_name: str
    mode: ComplianceMode
    description: str
    controls: Dict[str, bool]
    active: bool


class ComplianceProfileActivateRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    profile_id: str = Field(..., min_length=1, max_length=128)
    actor_id: str = Field(..., min_length=1, max_length=128)


class ComplianceProfileStatusResponse(BaseModel):
    tenant_id: str
    active_profile_id: str | None
    mode: ComplianceMode | None
    controls: Dict[str, bool]