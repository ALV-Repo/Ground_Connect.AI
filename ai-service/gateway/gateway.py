from dataclasses import dataclass

from core.config import settings
from gateway.pii_masker import PIIMasker
from gateway.providers import (
    AIProviderError,
    ProviderRegistry,
)
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
    evaluation_eligible: bool = False


class AIGateway:

    FALLBACK_PROVIDER = "deterministic"
    FALLBACK_MODEL = "rule-based-fallback"

    # AI-021: supported language coverage.
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

    def __init__(
        self,
        provider_registry: ProviderRegistry | None = None,
        pii_masker: PIIMasker | None = None,
        prompt_security: PromptSecurityService | None = None,
        cost_meter: AICostMeter | None = None,
    ):

        self.provider_registry = (
            provider_registry
            or ProviderRegistry(
                settings.approved_providers
            )
        )

        self.pii_masker = (
            pii_masker
            or PIIMasker()
        )

        self.prompt_security = (
            prompt_security
            or PromptSecurityService()
        )

        # AI-020: provider routing and cost metering.
        self.cost_meter = (
            cost_meter
            or AICostMeter()
        )

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

        # AI-003: block detected prompt injection.
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

        # AI-001: mask PII before sending data to a provider.
        masked_prompt = self.pii_masker.mask(
            sanitized_prompt
        )

        pii_masked = (
            masked_prompt != sanitized_prompt
        )

        try:
            # AI-020: route through the approved provider registry.
            provider_config, selected_model = (
                self.provider_router.route(
                    provider=selected_provider,
                    model=model,
                )
            )

            # Execute the selected provider.
            content, input_tokens, output_tokens = (
                await self.provider_registry.generate(
                    provider=provider_config.name,
                    prompt=masked_prompt,
                    model=selected_model,
                )
            )

            # AI-020: calculate provider-specific cost.
            estimated_cost = self._estimate_cost(
                provider=provider_config.name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

            # AI-020: record provider usage.
            self.cost_meter.record(
                provider=provider_config.name,
                model=selected_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost=estimated_cost,
            )

            normalized_language = language.lower()

            return AIResponse(
                provider=provider_config.name,
                model=selected_model,
                content=content,
                pii_masked=pii_masked,
                prompt_injection_detected=False,
                fallback_used=False,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost=estimated_cost,
                language=language,
                evaluation_eligible=(
                    normalized_language
                    in self.SUPPORTED_LANGUAGES
                ),
            )

        except AIProviderError:
            # AI-014: provider-specific failures use the
            # deterministic fallback.
            return self._deterministic_fallback(
                prompt=masked_prompt,
                pii_masked=pii_masked,
                language=language,
            )

    def _estimate_cost(
        self,
        provider: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:

        if provider.lower() != "anthropic":
            return 0.0

        input_cost = (
            input_tokens
            / 1000
            * settings.anthropic_input_cost_per_1k_tokens
        )

        output_cost = (
            output_tokens
            / 1000
            * settings.anthropic_output_cost_per_1k_tokens
        )

        return round(
            input_cost + output_cost,
            8,
        )

    def _deterministic_fallback(
        self,
        prompt: str,
        pii_masked: bool,
        language: str = "unknown",
    ) -> AIResponse:

        # AI-020: meter fallback usage separately.
        input_tokens = len(prompt.split())

        fallback_content = (
            "AI provider is currently unavailable. "
            "A deterministic fallback response was used. "
            "Please retry the request later."
        )

        output_tokens = len(
            fallback_content.split()
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
            content=fallback_content,
            pii_masked=pii_masked,
            prompt_injection_detected=False,
            fallback_used=True,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=0.0,
            language=language,
            evaluation_eligible=False,
        )