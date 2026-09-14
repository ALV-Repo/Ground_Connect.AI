from fastapi import (
    APIRouter,
    File,
    HTTPException,
    UploadFile,
)

from app.schemas.ai import (
    BatchSummarizeRequest,
    BatchSummarizeResponse,
    ConfirmTranscriptionRequest,
    ConfirmTranscriptionResponse,
    SummarizeRequest,
    SummarizeResponse,
    TextToSpeechRequest,
    TextToSpeechResponse,
    TranscribeResponse,
    TranslateRequest,
    TranslateResponse,
)

from app.services.summarization import (
    SUPPORTED_CONTENT_TYPES,
    summarize_batch,
    summarize_text,
)

from app.services.translation import (
    translate_text,
    translation_quality_label,
)

from app.services.transcription import (
    confirm_transcription,
    text_to_speech,
    transcribe_audio,
)


router = APIRouter(
    prefix="/ai",
    tags=["AI"],
)


# =========================================================
# AUDIO CONFIGURATION
# =========================================================


ALLOWED_AUDIO_TYPES = {
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp3",
    "audio/mp4",
    "audio/x-m4a",
    "audio/ogg",
    "audio/webm",
}

MAX_AUDIO_SIZE = 10 * 1024 * 1024


# =========================================================
# AI-011 SUMMARISATION
# =========================================================


@router.post(
    "/summarize",
    response_model=SummarizeResponse,
)
def summarize(
    payload: SummarizeRequest,
):
    text = payload.text.strip()

    if not text:
        raise HTTPException(
            status_code=422,
            detail="Text cannot be empty.",
        )

    content_type = (
        payload.content_type
        .strip()
        .lower()
    )

    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported content_type: "
                f"{payload.content_type}"
            ),
        )

    try:
        summary = summarize_text(
            text,
            content_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "summary": summary,
        "content_type": content_type,
    }


@router.post(
    "/summarize/batch",
    response_model=BatchSummarizeResponse,
)
def summarize_batch_api(
    payload: BatchSummarizeRequest,
):
    content_type = (
        payload.content_type
        .strip()
        .lower()
    )

    if content_type not in SUPPORTED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported content_type: "
                f"{payload.content_type}"
            ),
        )

    texts = [
        text.strip()
        for text in payload.texts
    ]

    if any(not text for text in texts):
        raise HTTPException(
            status_code=422,
            detail=(
                "Batch text items cannot be empty."
            ),
        )

    try:
        summaries = summarize_batch(
            texts,
            content_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "summaries": summaries,
        "content_type": content_type,
    }


# =========================================================
# AI-012 TRANSLATION
# =========================================================


@router.post(
    "/translate",
    response_model=TranslateResponse,
)
def translate(
    payload: TranslateRequest,
):
    text = payload.text.strip()
    target_language = (
        payload.target_language.strip()
    )

    if not text:
        raise HTTPException(
            status_code=422,
            detail="Text cannot be empty.",
        )

    if not target_language:
        raise HTTPException(
            status_code=422,
            detail="Target language is required.",
        )

    try:
        translated_text = translate_text(
            text,
            target_language,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        "original_text": text,
        "translated_text": translated_text,
        "target_language": target_language,
        "quality_label": translation_quality_label(),
    }


# =========================================================
# AI-013 VOICE TRANSCRIPTION
# =========================================================


@router.post(
    "/transcribe",
    response_model=TranscribeResponse,
)
async def transcribe(
    file: UploadFile = File(...),
    language: str | None = None,
):
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail="Audio file name is required.",
        )

    if file.content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                f"Unsupported audio format: "
                f"{file.content_type}"
            ),
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=400,
            detail="Audio file is empty.",
        )

    if len(content) > MAX_AUDIO_SIZE:
        raise HTTPException(
            status_code=413,
            detail=(
                "Audio file size must not exceed 10 MB."
            ),
        )

    try:
        result = transcribe_audio(
            file.filename,
            language,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return {
        **result,
        "message": (
            "Transcription generated. "
            "Speaker confirmation is required "
            "before record commit."
        ),
    }


# =========================================================
# AI-013 SPEAKER CONFIRMATION
# =========================================================


@router.post(
    "/transcribe/confirm",
    response_model=ConfirmTranscriptionResponse,
)
def confirm_transcription_api(
    payload: ConfirmTranscriptionRequest,
):
    try:
        return confirm_transcription(
            transcript=payload.transcript.strip(),
            language=payload.language.strip(),
            confidence=payload.confidence,
            speaker_confirmed=payload.speaker_confirmed,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc


# =========================================================
# AI-013 READ-BACK / TTS
# =========================================================


@router.post(
    "/transcribe/read-back",
    response_model=TextToSpeechResponse,
)
def transcription_read_back(
    payload: TextToSpeechRequest,
):
    try:
        return text_to_speech(
            payload.text.strip(),
            payload.language.strip(),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc