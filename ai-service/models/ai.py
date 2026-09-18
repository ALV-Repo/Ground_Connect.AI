from pydantic import BaseModel, Field


# ============================================================
# AI-001 to AI-005: Core AI Gateway
# ============================================================

class AIRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=10000)
    conversation_id: str = Field(..., min_length=1, max_length=100)
    provider: str | None = None
    model: str | None = None
    user_id: str = Field(..., min_length=1)
    user_role: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    resource_organization_id: str = Field(..., min_length=1)

    # AI-015: Mandatory human confirmation gate
    requires_human_confirmation: bool = False
    human_confirmed: bool = False


class AIResponseModel(BaseModel):
    provider: str
    model: str
    content: str
    pii_masked: bool
    prompt_injection_detected: bool


# ============================================================
# AI-006 to AI-008: Leadership Copilot
# ============================================================

class CopilotRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=10000)
    conversation_id: str = Field(..., min_length=1, max_length=100)
    user_id: str = Field(..., min_length=1)
    user_role: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    resource_organization_id: str = Field(..., min_length=1)
    provider: str | None = None
    model: str | None = None


class CopilotResponse(BaseModel):
    answer: str
    provider: str
    model: str
    pii_masked: bool
    prompt_injection_detected: bool
    coverage: str
    freshness: str
    facts: list[str]
    inferences: list[str]
    recommendations: list[str]


# ============================================================
# AI-010: Daily Leader Briefing
# ============================================================

class LeaderBriefingRequest(BaseModel):
    briefing_date: str = Field(..., min_length=1)
    context: str = Field(..., min_length=1, max_length=30000)
    user_id: str = Field(..., min_length=1)
    user_role: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    resource_organization_id: str = Field(..., min_length=1)
    provider: str | None = None
    model: str | None = None


class LeaderBriefingResponse(BaseModel):
    briefing_date: str
    summary: str
    facts: list[str]
    inferences: list[str]
    recommendations: list[str]
    coverage: str
    freshness: str
    provider: str
    model: str
    pii_masked: bool
    prompt_injection_detected: bool


# ============================================================
# AI-011: Summarization
# ============================================================

class SummarizationRequest(BaseModel):
    source_type: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1, max_length=30000)
    user_id: str = Field(..., min_length=1)
    user_role: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    resource_organization_id: str = Field(..., min_length=1)
    provider: str | None = None
    model: str | None = None


class SummarizationResponse(BaseModel):
    source_type: str
    summary: str
    coverage: str
    freshness: str
    provider: str
    model: str
    pii_masked: bool
    prompt_injection_detected: bool


# ============================================================
# AI-012: Translation
# ============================================================

class TranslationRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=30000)
    source_language: str = Field(..., min_length=1)
    target_language: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    user_role: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    resource_organization_id: str = Field(..., min_length=1)
    provider: str | None = None
    model: str | None = None


class TranslationResponse(BaseModel):
    translated_text: str
    source_language: str
    target_language: str
    coverage: str
    freshness: str
    provider: str
    model: str
    pii_masked: bool
    prompt_injection_detected: bool


# ============================================================
# AI-013: Indian-language Voice Transcription
# ============================================================

class TranscriptionRequest(BaseModel):
    audio_reference: str = Field(..., min_length=1, max_length=10000)
    language: str = Field(..., min_length=1)
    speaker_confirmation_required: bool = True
    user_id: str = Field(..., min_length=1)
    user_role: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    resource_organization_id: str = Field(..., min_length=1)
    provider: str | None = None
    model: str | None = None


class TranscriptionResponse(BaseModel):
    transcript: str
    language: str
    speaker_confirmation_required: bool
    speaker_confirmed: bool
    coverage: str
    freshness: str
    provider: str
    model: str
    pii_masked: bool
    prompt_injection_detected: bool


# ============================================================
# AI-016: Citizen Issue Classification
# ============================================================

class IssueClassificationRequest(BaseModel):
    issue_text: str = Field(..., min_length=1, max_length=10000)
    user_id: str = Field(..., min_length=1)
    user_role: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    resource_organization_id: str = Field(..., min_length=1)
    provider: str | None = None
    model: str | None = None


class IssueClassificationResponse(BaseModel):
    category: str
    priority: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_human_review: bool
    coverage: str
    freshness: str
    provider: str
    model: str
    pii_masked: bool
    prompt_injection_detected: bool


class IssueClassificationCorrectionRequest(BaseModel):
    issue_id: str = Field(..., min_length=1)
    original_category: str = Field(..., min_length=1)
    corrected_category: str = Field(..., min_length=1)
    user_id: str = Field(..., min_length=1)
    user_role: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    resource_organization_id: str = Field(..., min_length=1)


class IssueClassificationCorrectionResponse(BaseModel):
    issue_id: str
    original_category: str
    corrected_category: str
    feedback_recorded: bool


# ============================================================
# AI-017: AI-Assisted Clustering
# ============================================================

class ClusteringSuggestionRequest(BaseModel):
    items: str = Field(..., min_length=1, max_length=30000)
    user_id: str = Field(..., min_length=1)
    user_role: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    resource_organization_id: str = Field(..., min_length=1)
    provider: str | None = None
    model: str | None = None


class ClusteringSuggestionResponse(BaseModel):
    suggestions: list[str]
    confidence: float = Field(..., ge=0.0, le=1.0)
    needs_human_review: bool
    coverage: str
    freshness: str
    provider: str
    model: str
    pii_masked: bool
    prompt_injection_detected: bool


# ============================================================
# AI-018: Ground-Intelligence Analytics
# ============================================================

class GroundAnalyticsRequest(BaseModel):
    data: str = Field(..., min_length=1, max_length=30000)
    user_id: str = Field(..., min_length=1)
    user_role: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    resource_organization_id: str = Field(..., min_length=1)
    provider: str | None = None
    model: str | None = None


class GroundAnalyticsResponse(BaseModel):
    trends: list[str]
    workload: list[str]
    reporting_gaps: list[str]
    coverage: str
    freshness: str
    provider: str
    model: str
    pii_masked: bool
    prompt_injection_detected: bool


# ============================================================
# AI-019: Dark Unit Radar
# ============================================================

class DarkUnitRadarRequest(BaseModel):
    data: str = Field(..., min_length=1, max_length=30000)
    user_id: str = Field(..., min_length=1)
    user_role: str = Field(..., min_length=1)
    organization_id: str = Field(..., min_length=1)
    resource_organization_id: str = Field(..., min_length=1)
    provider: str | None = None
    model: str | None = None


class DarkUnitRadarResponse(BaseModel):
    dark_units: list[str]
    coverage: str
    freshness: str
    provider: str
    model: str
    pii_masked: bool
    prompt_injection_detected: bool
