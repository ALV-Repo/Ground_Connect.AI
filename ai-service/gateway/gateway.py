from dataclasses import dataclass

from core.config import settings
from gateway.pii_masker import PIIMasker
from gateway.providers import ProviderRegistry
from security.prompt_security import PromptSecurityService


@dataclass
class AIResponse:
    provider: str
    model: str
    content: str
    pii_masked: bool
    prompt_injection_detected: bool


class AIGateway:

    def __init__(self):

        self.provider_registry = ProviderRegistry(
            settings.approved_providers
        )

        self.pii_masker = PIIMasker()
        self.prompt_security = PromptSecurityService()

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

        sanitized_prompt, injection_detected = (
            self.prompt_security.sanitize(prompt)
        )

        if injection_detected:
            return AIResponse(
                provider=provider_config.name,
                model=model or provider_config.model,
                content=(
                    "Request blocked because "
                    "prompt injection was detected."
                ),
                pii_masked=False,
                prompt_injection_detected=True,
            )

        masked_prompt = self.pii_masker.mask(
            sanitized_prompt
        )

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
            pii_masked=masked_prompt != sanitized_prompt,
            prompt_injection_detected=False,
        )