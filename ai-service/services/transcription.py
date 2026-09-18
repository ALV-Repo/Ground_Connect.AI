from datetime import datetime, timezone

from gateway.gateway import AIGateway
from models.ai import (
    TranscriptionRequest,
    TranscriptionResponse,
)
from security.permissions import (
    PermissionDeniedError,
    PermissionService,
    UserContext,
)


class TranscriptionService:

    SUPPORTED_LANGUAGES = {
        "english",
        "hindi",
        "telugu",
        "tamil",
        "kannada",
        "malayalam",
        "marathi",
        "bengali",
        "gujarati",
        "punjabi",
        "urdu",
        "odia",
    }

    LANGUAGE_ALIASES = {
        "en": "english",
        "hi": "hindi",
        "te": "telugu",
        "ta": "tamil",
        "kn": "kannada",
        "ml": "malayalam",
        "mr": "marathi",
        "bn": "bengali",
        "gu": "gujarati",
        "pa": "punjabi",
        "ur": "urdu",
        "or": "odia",
    }

    def __init__(self):
        self.gateway = AIGateway()
        self.permission_service = PermissionService()

    def _normalize_language(self, language: str) -> str:
        normalized = language.strip().lower()

        return self.LANGUAGE_ALIASES.get(
            normalized,
            normalized,
        )

    async def transcribe(
        self,
        request: TranscriptionRequest,
    ) -> TranscriptionResponse:

        user = UserContext(
            user_id=request.user_id,
            role=request.user_role,
            organization_id=request.organization_id,
        )

        try:
            self.permission_service.enforce_access(
                user=user,
                resource_organization_id=(
                    request.resource_organization_id
                ),
            )
        except PermissionDeniedError:
            raise

        language = self._normalize_language(
            request.language
        )

        if language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported transcription language: "
                f"{request.language}"
            )

        transcription_prompt = (
            "You are the GroundConnect voice transcription "
            "assistant.\n"
            "Transcribe the supplied audio reference accurately.\n\n"
            "Requirements:\n"
            "- Preserve the spoken meaning.\n"
            "- Do not invent words or information.\n"
            "- Preserve names, numbers, dates, and important "
            "technical terms where possible.\n"
            "- Produce the transcript in the requested language.\n"
            "- Do not provide a summary.\n"
            "- Return only the transcription text.\n\n"
            "Language:\n"
            + language
            + "\n\n"
            "Audio reference:\n"
            + request.audio_reference
        )

        response = await self.gateway.generate(
            prompt=transcription_prompt,
            provider=request.provider,
            model=request.model,
        )

        coverage = (
            "Transcription is based only on the audio reference "
            "supplied in the current request."
        )

        freshness = (
            "Transcription processed at "
            + datetime.now(timezone.utc).isoformat()
            + " UTC."
        )

        return TranscriptionResponse(
            transcript=response.content,
            language=language,
            speaker_confirmation_required=(
                request.speaker_confirmation_required
            ),
            speaker_confirmed=False,
            coverage=coverage,
            freshness=freshness,
            provider=response.provider,
            model=response.model,
            pii_masked=response.pii_masked,
            prompt_injection_detected=(
                response.prompt_injection_detected
            ),
        )