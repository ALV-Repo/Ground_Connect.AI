from datetime import datetime, timezone

from gateway.gateway import AIGateway
from models.ai import (
    TranslationRequest,
    TranslationResponse,
)
from security.permissions import (
    PermissionDeniedError,
    PermissionService,
    UserContext,
)


class TranslationService:

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

    async def translate(
        self,
        request: TranslationRequest,
    ) -> TranslationResponse:

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

        source_language = self._normalize_language(
            request.source_language
        )

        target_language = self._normalize_language(
            request.target_language
        )

        if source_language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported source language: "
                f"{request.source_language}"
            )

        if target_language not in self.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported target language: "
                f"{request.target_language}"
            )

        if source_language == target_language:
            translated_text = request.text
        else:
            translation_prompt = (
                "You are the GroundConnect multilingual "
                "translation assistant.\n"
                "Translate the supplied text accurately from "
                "the source language to the target language.\n\n"
                "Requirements:\n"
                "- Preserve the original meaning.\n"
                "- Do not add information.\n"
                "- Do not remove important information.\n"
                "- Preserve names, numbers, dates, and "
                "technical terms where appropriate.\n"
                "- Return only the translated text.\n\n"
                "Source language:\n"
                + source_language
                + "\n\n"
                "Target language:\n"
                + target_language
                + "\n\n"
                "Text to translate:\n"
                + request.text
            )

            response = await self.gateway.generate(
                prompt=translation_prompt,
                provider=request.provider,
                model=request.model,
            )

            translated_text = response.content

        if source_language == target_language:
            pii_masked = False
            prompt_injection_detected = False
            provider = request.provider or "mock"
            model = request.model or "mock-model"
        else:
            pii_masked = response.pii_masked
            prompt_injection_detected = (
                response.prompt_injection_detected
            )
            provider = response.provider
            model = response.model

        coverage = (
            "Translation is based only on the text supplied "
            "in the current request."
        )

        freshness = (
            "Translation processed at "
            + datetime.now(timezone.utc).isoformat()
            + " UTC."
        )

        return TranslationResponse(
            translated_text=translated_text,
            source_language=source_language,
            target_language=target_language,
            coverage=coverage,
            freshness=freshness,
            provider=provider,
            model=model,
            pii_masked=pii_masked,
            prompt_injection_detected=(
                prompt_injection_detected
            ),
        )