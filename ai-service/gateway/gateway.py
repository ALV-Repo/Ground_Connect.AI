from dataclasses import dataclass

from core.config import settings
from gateway.pii_masker import PIIMasker
from gateway.providers import ProviderRegistry


@dataclass
class AIResponse:
    provider: str
    model: str
    content: str
    pii_masked: bool


class AIGateway:

    def __init__(self):

        self.provider_registry = ProviderRegistry(
            settings.approved_providers
        )

        self.pii_masker = PIIMasker()

    async def generate(
        self,
        prompt: str,
        provider: str | None = None,
        model: str | None = None,
    ) -> AIResponse:

        selected_provider = (
            provider or settings.ai_provider
        ).lower()

        provider_config = (
            self.provider_registry.get_provider(
                selected_provider
            )
        )

        masked_prompt = self.pii_masker.mask(prompt)

        selected_model = (
            model or provider_config.model
        )

        # Mock provider for initial testing.
        content = (
            "Mock AI response generated successfully."
        )

        return AIResponse(
            provider=provider_config.name,
            model=selected_model,
            content=content,
            pii_masked=masked_prompt != prompt,
        )