from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class TPICreateOperationRequest(BaseModel):
    operation_id: str = Field(..., min_length=1, max_length=128)
    tenant_id: str = Field(..., min_length=1, max_length=128)
    requested_by: str = Field(..., min_length=1, max_length=128)
    operation_type: str = Field(..., min_length=1, max_length=128)
    payload: Optional[Dict[str, Any]] = None
    reason: Optional[str] = Field(default=None, max_length=2000)
    approval_window_seconds: Optional[int] = Field(
        default=None,
        gt=0,
    )