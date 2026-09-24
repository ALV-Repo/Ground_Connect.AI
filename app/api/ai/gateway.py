from app.api.ai.fallback import fallback_provider
from app.api.ai.providers.mock import mock_provider
from app.core.config import settings


class AIGateway:
    """
    Central gateway for AI operations.

    Business services communicate with this gateway
    instead of directly depending on an AI provider.
    """

    def __init__(self):
        self.provider_name = settings.ai_provider.strip().lower()

        providers = {
            "mock": mock_provider,
            "fallback": fallback_provider,
        }

        self.provider = providers.get(
            self.provider_name,
            fallback_provider,
        )

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