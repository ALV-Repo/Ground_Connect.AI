from pydantic import BaseModel, Field


# =========================================================
# AI-011 SUMMARISATION
# =========================================================


class SummarizeRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        description="Text that needs to be summarized.",
    )

    content_type: str = Field(
        default="general",
        min_length=1,
        description=(
            "Content type: general, message_thread, "
            "field_report, or meeting."
        ),
    )


class SummarizeResponse(BaseModel):
    summary: str
    content_type: str


class BatchSummarizeRequest(BaseModel):
    texts: list[str] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Multiple texts to summarize.",
    )

    content_type: str = Field(
        default="field_report",
        min_length=1,
    )


class BatchSummarizeResponse(BaseModel):
    summaries: list[str]
    content_type: str


# =========================================================
# AI-012 TRANSLATION
# =========================================================


class TranslateRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        description="Text that needs to be translated.",
    )

    target_language: str = Field(
        ...,
        min_length=1,
        description=(
            "Target language: English, Hindi or Kannada."
        ),
    )


class TranslateResponse(BaseModel):
    original_text: str
    translated_text: str
    target_language: str
    quality_label: str


# =========================================================
# AI-013 TRANSCRIPTION
# =========================================================


class ConfirmTranscriptionRequest(BaseModel):
    transcript: str = Field(
        ...,
        min_length=1,
        description="Generated transcription.",
    )

    language: str = Field(
        ...,
        min_length=1,
        description="Speech language.",
    )

    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description=(
            "Transcription confidence between 0 and 1."
        ),
    )

    speaker_confirmed: bool


class ConfirmTranscriptionResponse(BaseModel):
    transcript: str
    language: str
    confidence: float
    speaker_confirmed: bool
    committed: bool
    requires_confirmation: bool
    quality_label: str
    message: str


class TranscribeResponse(BaseModel):
    transcript: str
    language: str
    confidence: float
    speaker_confirmed: bool
    committed: bool
    requires_confirmation: bool
    quality_label: str
    message: str


# =========================================================
# AI-013 TEXT TO SPEECH / READ BACK
# =========================================================


class TextToSpeechRequest(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        description="Text to read back.",
    )

    language: str = Field(
        ...,
        min_length=1,
        description="Language for read-back.",
    )


class TextToSpeechResponse(BaseModel):
    text: str
    language: str
    audio_available: bool
    provider: str
    message: str