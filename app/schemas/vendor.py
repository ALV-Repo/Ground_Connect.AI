from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class VendorElevationRequest(BaseModel):
    vendor_id: str = Field(..., min_length=1, max_length=128)
    tenant_id: str = Field(..., min_length=1, max_length=128)
    requested_by: str = Field(..., min_length=1, max_length=128)
    reason: str = Field(..., min_length=1, max_length=2000)
    duration_minutes: Optional[int] = Field(
        default=None,
        ge=1,
    )
    scopes: Optional[List[str]] = Field(
        default=None,
        max_length=50,
    )