from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class MemberCreateRequest(BaseModel):
    member_id: str = Field(..., min_length=1, max_length=128)
    tenant_id: str = Field(..., min_length=1, max_length=128)
    branch_id: Optional[str] = Field(default=None, max_length=128)

    name: str = Field(..., min_length=1, max_length=200)
    mobile: Optional[str] = Field(default=None, max_length=32)
    email: Optional[str] = Field(default=None, max_length=320)

    role: str = Field(default="member", min_length=1, max_length=64)
    status: str = Field(default="active", max_length=32)

    metadata: dict = Field(default_factory=dict)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        allowed = {"active", "inactive", "suspended", "pending"}
        if value not in allowed:
            raise ValueError(
                f"status must be one of: {', '.join(sorted(allowed))}"
            )
        return value


class MemberResponse(BaseModel):
    member_id: str
    tenant_id: str
    branch_id: Optional[str] = None

    name: str
    mobile: Optional[str] = None
    email: Optional[str] = None

    role: str
    status: str

    metadata: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class MemberListResponse(BaseModel):
    items: List[MemberResponse]
    total: int
    page: int = 1
    page_size: int = 50


class MemberUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    mobile: Optional[str] = Field(default=None, max_length=32)
    email: Optional[str] = Field(default=None, max_length=320)
    role: Optional[str] = Field(default=None, max_length=64)
    status: Optional[str] = Field(default=None, max_length=32)
    branch_id: Optional[str] = Field(default=None, max_length=128)
    metadata: Optional[dict] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        allowed = {"active", "inactive", "suspended", "pending"}

        if value not in allowed:
            raise ValueError(
                f"status must be one of: {', '.join(sorted(allowed))}"
            )

        return value


class BulkMemberRecord(BaseModel):
    member_id: str = Field(..., min_length=1, max_length=128)
    tenant_id: str = Field(..., min_length=1, max_length=128)
    branch_id: Optional[str] = Field(default=None, max_length=128)

    name: str = Field(..., min_length=1, max_length=200)
    mobile: Optional[str] = Field(default=None, max_length=32)
    email: Optional[str] = Field(default=None, max_length=320)

    role: str = Field(default="member", max_length=64)
    status: str = Field(default="active", max_length=32)

    metadata: dict = Field(default_factory=dict)


class BulkMemberImportRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)
    records: List[BulkMemberRecord] = Field(
        ...,
        min_length=1,
        max_length=10000,
    )

    source: str = Field(default="api", max_length=64)
    dry_run: bool = False


class BulkMemberImportResult(BaseModel):
    imported: int
    updated: int
    skipped: int
    failed: int

    errors: List[str] = Field(default_factory=list)


class BulkMemberImportResponse(BaseModel):
    success: bool
    result: BulkMemberImportResult


class MemberSearchRequest(BaseModel):
    tenant_id: str = Field(..., min_length=1, max_length=128)

    branch_id: Optional[str] = Field(default=None, max_length=128)
    query: Optional[str] = Field(default=None, max_length=200)

    status: Optional[str] = Field(default=None, max_length=32)
    role: Optional[str] = Field(default=None, max_length=64)

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=500)


class MemberLifecycleRequest(BaseModel):
    member_id: str = Field(..., min_length=1, max_length=128)
    action: str = Field(..., min_length=1, max_length=32)
    reason: Optional[str] = Field(default=None, max_length=500)

    @field_validator("action")
    @classmethod
    def validate_action(cls, value: str) -> str:
        allowed = {
            "activate",
            "deactivate",
            "suspend",
            "restore",
        }

        if value not in allowed:
            raise ValueError(
                f"action must be one of: {', '.join(sorted(allowed))}"
            )

        return value


class MemberLifecycleResponse(BaseModel):
    success: bool
    member_id: str
    action: str
    status: str
    updated_at: datetime


class MemberDeleteRequest(BaseModel):
    member_id: str = Field(..., min_length=1, max_length=128)
    reason: Optional[str] = Field(default=None, max_length=500)


class MemberDeleteResponse(BaseModel):
    success: bool
    member_id: str
    deleted: bool