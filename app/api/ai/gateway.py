from app.api.ai.fallback import fallback_provider
from app.core.config import settings


class AIGateway:
    """
    Central gateway for AI operations.

    Business services communicate with this gateway
    instead of directly depending on an AI provider.
    """

    def __init__(self):
        self.provider_name = settings.ai_provider.lower()

        # Current implementation intentionally uses
        # deterministic fallback/mock provider.
        self.provider = fallback_provider

    def summarize(
        self,
        text: str,
        content_type: str = "general",
    ) -> str:
        return self.provider.summarize(
            text,
            content_type,
        )

    def translate(
        self,
        text: str,
        target_language: str,
    ) -> str:
        return self.provider.translate(
            text,
            target_language,
        )

    def transcribe(
        self,
        filename: str,
        language: str | None = None,
    ) -> dict:
        return self.provider.transcribe(
            filename,
            language,
        )


ai_gateway = AIGateway()