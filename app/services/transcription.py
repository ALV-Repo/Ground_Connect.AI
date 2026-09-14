from app.api.ai.gateway import ai_gateway
from app.core.config import settings


SUPPORTED_SPEECH_LANGUAGES = {
    "en",
    "en-in",
    "english",

    "hi",
    "hi-in",
    "hindi",

    "kn",
    "kn-in",
    "kannada",
}


def normalize_speech_language(
    language: str | None,
) -> str:
    """
    Normalize speech language to Indian locale.
    """

    if not language:
        return settings.default_language

    value = language.strip().lower()

    if value not in SUPPORTED_SPEECH_LANGUAGES:
        raise ValueError(
            f"Unsupported speech language: {language}. "
            f"Supported languages: English, Hindi, Kannada."
        )

    if value in {"en", "english"}:
        return "en-IN"

    if value in {"hi", "hindi"}:
        return "hi-IN"

    if value in {"kn", "kannada"}:
        return "kn-IN"

    if value in {
        "en-in",
        "hi-in",
        "kn-in",
    }:
        return value[:2] + "-IN"

    return value


def transcription_quality(
    confidence: float,
) -> tuple[bool, str]:
    """
    Determine whether human confirmation is required.
    """

    requires_confirmation = (
        confidence
        < settings.transcription_confidence_threshold
    )

    if requires_confirmation:
        quality_label = "low-confidence"
    else:
        quality_label = "acceptable-confidence"

    return (
        requires_confirmation,
        quality_label,
    )


def transcribe_audio(
    filename: str,
    language: str | None = None,
) -> dict:
    """
    Generate transcription.
    """

    normalized_language = normalize_speech_language(
        language
    )

    result = ai_gateway.transcribe(
        filename,
        normalized_language,
    )

    requires_confirmation, quality_label = (
        transcription_quality(
            result["confidence"]
        )
    )

    # Speaker confirmation remains mandatory
    # before record commit.
    requires_confirmation = (
        requires_confirmation
        or not result.get(
            "speaker_confirmed",
            False,
        )
    )

    return {
        **result,
        "language": normalized_language,
        "requires_confirmation": requires_confirmation,
        "quality_label": quality_label,
    }


def confirm_transcription(
    transcript: str,
    language: str,
    confidence: float,
    speaker_confirmed: bool,
) -> dict:
    """
    Human confirmation / commit flow.
    """

    transcript = transcript.strip()
    language = language.strip()

    if not transcript:
        raise ValueError(
            "Transcript cannot be empty."
        )

    if not language:
        raise ValueError(
            "Language is required."
        )

    # Normalize and validate language.
    normalized_language = normalize_speech_language(
        language
    )

    requires_confirmation, quality_label = (
        transcription_quality(
            confidence
        )
    )

    # Low confidence MUST NOT be committed
    # without confirmation.
    if requires_confirmation:
        return {
            "transcript": transcript,
            "language": normalized_language,
            "confidence": confidence,
            "speaker_confirmed": speaker_confirmed,
            "committed": False,
            "requires_confirmation": True,
            "quality_label": quality_label,
            "message": (
                "Low-confidence transcription "
                "requires human confirmation."
            ),
        }

    # Speaker confirmation is mandatory.
    if not speaker_confirmed:
        return {
            "transcript": transcript,
            "language": normalized_language,
            "confidence": confidence,
            "speaker_confirmed": False,
            "committed": False,
            "requires_confirmation": True,
            "quality_label": quality_label,
            "message": (
                "Speaker confirmation is required "
                "before committing the record."
            ),
        }

    return {
        "transcript": transcript,
        "language": normalized_language,
        "confidence": confidence,
        "speaker_confirmed": True,
        "committed": True,
        "requires_confirmation": False,
        "quality_label": quality_label,
        "message": (
            "Transcription confirmed and committed."
        ),
    }


def text_to_speech(
    text: str,
    language: str,
) -> dict:
    """
    TTS/read-back interface.

    Current implementation exposes the interface
    using the mock provider. Actual audio generation
    requires a configured TTS provider.
    """

    text = text.strip()

    if not text:
        raise ValueError(
            "Text cannot be empty."
        )

    normalized_language = normalize_speech_language(
        language
    )

    return {
        "text": text,
        "language": normalized_language,
        "audio_available": False,
        "provider": "mock",
        "message": (
            "TTS read-back interface is available. "
            "Real audio generation requires a "
            "configured TTS provider."
        ),
    }