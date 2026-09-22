from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Literal

from pydantic import BaseModel, Field, field_validator


# ============================================================
# BE-018 — Citizen Issue Intake & Clustering
# ============================================================


class Location(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class ConsentReceipt(BaseModel):
    purpose: str = Field(..., min_length=1, max_length=500)
    privacy_notice_version: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )
    language: str = Field(..., min_length=1, max_length=50)
    timestamp: datetime
    mechanism: str = Field(..., min_length=1, max_length=100)


class MediaAttachment(BaseModel):
    media_id: str = Field(..., min_length=1, max_length=128)

    media_type: Literal[
        "voice",
        "photo",
        "video",
    ]

    content_reference: str = Field(
        ...,
        min_length=1,
        max_length=1000,
    )


class AIClassificationProposal(BaseModel):
    category: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    location: Optional[Location] = None

    priority: Optional[str] = Field(
        default=None,
        max_length=32,
    )

    proposed_at: datetime

    model_version: Optional[str] = Field(
        default=None,
        max_length=100,
    )

    human_confirmed: bool = False


class CitizenIssueCreateRequest(BaseModel):
    tenant_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    citizen_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    text: Optional[str] = Field(
        default=None,
        max_length=10000,
    )

    media: List[MediaAttachment] = Field(
        default_factory=list,
        max_length=10,
    )

    location: Optional[Location] = None

    consent: ConsentReceipt

    @field_validator("media")
    @classmethod
    def validate_media(
        cls,
        value: List[MediaAttachment],
    ) -> List[MediaAttachment]:
        if len(value) > 10:
            raise ValueError(
                "maximum 10 media attachments are allowed"
            )

        return value

    def validate_submission_content(self) -> None:
        if not self.text and not self.media:
            raise ValueError(
                "at least text or one media attachment is required"
            )


class CitizenIssueResponse(BaseModel):
    issue_id: str

    reference_number: str

    tenant_id: str

    citizen_id: str

    text: Optional[str] = None

    media: List[MediaAttachment] = Field(
        default_factory=list
    )

    location: Optional[Location] = None

    consent: ConsentReceipt

    ai_proposal: Optional[AIClassificationProposal] = None

    category: Optional[str] = None

    priority: Optional[str] = None

    classification_status: str

    cluster_id: Optional[str] = None

    created_at: datetime

    updated_at: datetime


class CitizenIssueClassificationRequest(BaseModel):
    issue_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    category: Optional[str] = Field(
        default=None,
        max_length=128,
    )

    location: Optional[Location] = None

    priority: Optional[str] = Field(
        default=None,
        max_length=32,
    )

    corrected_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
    )


class CorroboratingCitizen(BaseModel):
    citizen_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    issue_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    status: str = "reported"

    notifications_enabled: bool = True

    closure_confirmation: Optional[bool] = None

    added_at: datetime


class CitizenClusterResponse(BaseModel):
    cluster_id: str

    tenant_id: str

    canonical_issue_id: str

    category: Optional[str] = None

    location: Optional[Location] = None

    corroboration_count: int = 0

    distinct_citizen_count: int = 0

    issue_ids: List[str] = Field(
        default_factory=list
    )

    corroborators: List[CorroboratingCitizen] = Field(
        default_factory=list
    )

    clustering_status: str

    history_preserved: bool = True

    created_at: datetime

    updated_at: datetime


class ClusterSuggestionRequest(BaseModel):
    issue_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )


class ClusterConfirmRequest(BaseModel):
    cluster_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    confirmed_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )


class ClusterSplitRequest(BaseModel):
    cluster_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    issue_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=500,
    )

    requested_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
    )


class ClusterMergeRequest(BaseModel):
    cluster_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    target_cluster_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    requested_by: str = Field(
        ...,
        min_length=1,
        max_length=128,
    )

    reason: Optional[str] = Field(
        default=None,
        max_length=1000,
    )


class ClusterActionResponse(BaseModel):
    success: bool

    cluster_id: str

    action: str

    canonical_issue_id: Optional[str] = None

    issue_ids: List[str] = Field(
        default_factory=list
    )

    history_preserved: bool = True

    updated_at: datetime

class ClusterCorroborationRequest(BaseModel):
    issue_id: str = Field(..., min_length=1, max_length=128)
    citizen_id: str = Field(..., min_length=1, max_length=128)