from app.api.ai.providers.base import AIProvider
from app.api.ai.providers.mock import mock_provider


class FallbackAIProvider(AIProvider):
    """
    Deterministic fallback provider.

    Used when no real AI provider is configured.
    """

    def summarize(
        self,
        text: str,
        content_type: str = "general",
    ) -> str:
        return mock_provider.summarize(
            text,
            content_type,
        )

    def translate(
        self,
        text: str,
        target_language: str,
    ) -> str:
        return mock_provider.translate(
            text,
            target_language,
        )

    def transcribe(
        self,
        filename: str,
        language: str | None = None,
    ) -> dict:
        return mock_provider.transcribe(
            filename,
            language,
        )


fallback_provider = FallbackAIProvider()