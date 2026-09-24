from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BackupCreateRequest(BaseModel):
    backup_id: str | None = None
    backup_type: str = Field(
        default="full",
        pattern="^(full|incremental|differential)$",
    )
    source: str = Field(
        default="application",
        min_length=1,
        max_length=255,
    )
    size_bytes: int = Field(
        default=0,
        ge=0,
    )
    checksum: str | None = None
    location: str | None = None
    metadata: dict[str, Any] | None = None


class RestoreRequest(BaseModel):
    backup_id: str = Field(
        min_length=1,
    )
    requested_by: str = Field(
        min_length=1,
    )
    target: str = Field(
        default="application",
        min_length=1,
        max_length=255,
    )
    dry_run: bool = False


class BackupValidationRequest(BaseModel):
    backup_id: str = Field(
        min_length=1,
    )


class RecoveryVerificationRequest(BaseModel):
    backup_id: str = Field(
        min_length=1,
    )
    requested_by: str = Field(
        min_length=1,
    )