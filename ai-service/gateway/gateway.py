from dataclasses import dataclass

from core.config import settings
from gateway.pii_masker import PIIMasker
from gateway.providers import ProviderRegistry
from security.prompt_security import PromptSecurityService
from services.cost_metering import (
    AICostMeter,
    AIProviderRouter,
)


@dataclass
class AIResponse:
    provider: str
    model: str
    content: str
    pii_masked: bool
    prompt_injection_detected: bool
    fallback_used: bool = False

    # AI-020: usage and cost metering
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0

    # AI-021: evaluation/language coverage metadata
    language: str = "unknown"
    evaluation_eligible: bool = True


class AIGateway:

    FALLBACK_PROVIDER = "deterministic"
    FALLBACK_MODEL = "rule-based-fallback"

    # AI-021: initial language coverage registry.
    # Provider-specific language support can be expanded later.
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
        "odia",
        "urdu",
    }

    def __init__(self):

        self.provider_registry = ProviderRegistry(
            settings.approved_providers
        )

        self.pii_masker = PIIMasker()
        self.prompt_security = PromptSecurityService()

        # AI-020: provider routing and cost metering
        self.cost_meter = AICostMeter()
        self.provider_router = AIProviderRouter(
            self.provider_registry
        )

    async def generate(
        self,
        prompt: str,
        provider: str | None = None,
        model: str | None = None,
        language: str = "unknown",
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
                language=language,
                evaluation_eligible=False,
            )

        masked_prompt = self.pii_masker.mask(
            sanitized_prompt
        )

        try:
            # AI-020: route only through the approved provider registry.
            provider_config, selected_model = (
                self.provider_router.route(
                    provider=selected_provider,
                    model=model,
                )
            )

            # Mock provider for initial testing.
            if provider_config.name == "mock":
                content = (
                    "Mock AI response generated successfully."
                )

                input_tokens = len(masked_prompt.split())
                output_tokens = len(content.split())
                estimated_cost = 0.0

                # AI-020: record usage/cost.
                self.cost_meter.record(
                    provider=provider_config.name,
                    model=selected_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=estimated_cost,
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
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=estimated_cost,
                    language=language,
                    evaluation_eligible=(
                        language.lower() == "unknown"
                        or language.lower()
                        in self.SUPPORTED_LANGUAGES
                    ),
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
                language=language,
            )

    def _deterministic_fallback(
        self,
        prompt: str,
        pii_masked: bool,
        language: str = "unknown",
    ) -> AIResponse:

        # AI-020: fallback usage is metered separately.
        input_tokens = len(prompt.split())
        output_tokens = len(
            (
                "AI provider is currently unavailable. "
                "A deterministic fallback response was used. "
                "Please retry the request later."
            ).split()
        )

        self.cost_meter.record(
            provider=self.FALLBACK_PROVIDER,
            model=self.FALLBACK_MODEL,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=0.0,
        )

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
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=0.0,
            language=language,
            evaluation_eligible=False,
        )
