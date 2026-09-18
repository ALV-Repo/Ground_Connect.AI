from pydantic import BaseModel, Field


# ============================================================
# AI-001 to AI-005
# ============================================================


class AIRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=10000,
    )

    conversation_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    provider: str | None = None
    model: str | None = None

    # AI-015: Mandatory human confirmation
    requires_human_confirmation: bool = False
    human_confirmed: bool = False

    user_id: str = Field(
        ...,
        min_length=1,
    )

    user_role: str = Field(
        ...,
        min_length=1,
    )

    organization_id: str = Field(
        ...,
        min_length=1,
    )

    resource_organization_id: str = Field(
        ...,
        min_length=1,
    )


class AIResponseModel(BaseModel):
    provider: str
    model: str
    content: str
    pii_masked: bool
    prompt_injection_detected: bool


# ============================================================
# AI-006 to AI-008
# ============================================================


class CopilotRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=10000,
    )

    conversation_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
    )

    user_id: str = Field(
        ...,
        min_length=1,
    )

    user_role: str = Field(
        ...,
        min_length=1,
    )

    organization_id: str = Field(
        ...,
        min_length=1,
    )

    resource_organization_id: str = Field(
        ...,
        min_length=1,
    )

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
# AI-010
# ============================================================


class LeaderBriefingRequest(BaseModel):
    briefing_date: str = Field(
        ...,
        min_length=1,
        max_length=20,
    )

    context: str = Field(
        ...,
        min_length=1,
        max_length=20000,
    )

    user_id: str = Field(
        ...,
        min_length=1,
    )

    user_role: str = Field(
        ...,
        min_length=1,
    )

    organization_id: str = Field(
        ...,
        min_length=1,
    )

    resource_organization_id: str = Field(
        ...,
        min_length=1,
    )

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
# AI-011
# ============================================================


class SummarizationRequest(BaseModel):
    source_type: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    content: str = Field(
        ...,
        min_length=1,
        max_length=30000,
    )

    user_id: str = Field(
        ...,
        min_length=1,
    )

    user_role: str = Field(
        ...,
        min_length=1,
    )

    organization_id: str = Field(
        ...,
        min_length=1,
    )

    resource_organization_id: str = Field(
        ...,
        min_length=1,
    )

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
# AI-012: Multilingual Translation
# ============================================================


class TranslationRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=20000,
    )

    source_language: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    target_language: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    user_id: str = Field(
        ...,
        min_length=1,
    )

    user_role: str = Field(
        ...,
        min_length=1,
    )

    organization_id: str = Field(
        ...,
        min_length=1,
    )

    resource_organization_id: str = Field(
        ...,
        min_length=1,
    )

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
    audio_reference: str = Field(
        ...,
        min_length=1,
        max_length=500,
    )

    language: str = Field(
        ...,
        min_length=1,
        max_length=50,
    )

    speaker_confirmation_required: bool = True

    user_id: str = Field(
        ...,
        min_length=1,
    )

    user_role: str = Field(
        ...,
        min_length=1,
    )

    organization_id: str = Field(
        ...,
        min_length=1,
    )

    resource_organization_id: str = Field(
        ...,
        min_length=1,
    )

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