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
    fallback_used: bool = False


class AIGateway:

    FALLBACK_PROVIDER = "deterministic"
    FALLBACK_MODEL = "rule-based-fallback"

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

        sanitized_prompt, injection_detected = (
            self.prompt_security.sanitize(prompt)
        )

        if injection_detected:
            return AIResponse(
                provider=selected_provider,
                model=model or "unknown",
                content=(
                    "Request blocked because "
                    "prompt injection was detected."
                ),
                pii_masked=False,
                prompt_injection_detected=True,
                fallback_used=False,
            )

        masked_prompt = self.pii_masker.mask(
            sanitized_prompt
        )

        try:
            provider_config = (
                self.provider_registry.get_provider(
                    selected_provider
                )
            )

            selected_model = (
                model or provider_config.model
            )

            # Mock provider for initial testing.
            if provider_config.name == "mock":
                content = (
                    "Mock AI response generated successfully."
                )

                return AIResponse(
                    provider=provider_config.name,
                    model=selected_model,
                    content=content,
                    pii_masked=(
                        masked_prompt != sanitized_prompt
                    ),
                    prompt_injection_detected=False,
                    fallback_used=False,
                )

            raise RuntimeError(
                f"AI provider '{selected_provider}' failed"
            )

        except Exception:
            return self._deterministic_fallback(
                prompt=masked_prompt,
                pii_masked=(
                    masked_prompt != sanitized_prompt
                ),
            )

    def _deterministic_fallback(
        self,
        prompt: str,
        pii_masked: bool,
    ) -> AIResponse:

        return AIResponse(
            provider=self.FALLBACK_PROVIDER,
            model=self.FALLBACK_MODEL,
            content=(
                "AI provider is currently unavailable. "
                "A deterministic fallback response was used. "
                "Please retry the request later."
            ),
            pii_masked=pii_masked,
            prompt_injection_detected=False,
            fallback_used=True,
        )
