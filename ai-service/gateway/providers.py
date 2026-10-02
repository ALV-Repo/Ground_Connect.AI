from dataclasses import dataclass

import anthropic
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.config import settings


class AIProviderError(Exception):
    """Raised when an approved AI provider fails during execution."""


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    model: str
    enabled: bool = True


class ProviderRegistry:

    def __init__(self, approved_providers: set[str]):

        self._providers = {
            "mock": ProviderConfig(
                name="mock",
                model="mock-model",
                enabled=True,
            ),
            "anthropic": ProviderConfig(
                name="anthropic",
                model=settings.anthropic_model,
                enabled=bool(settings.anthropic_api_key),
            ),
        }

        self._approved_providers = {
            provider.lower()
            for provider in approved_providers
        }

    def is_approved(self, provider: str) -> bool:
        return provider.lower() in self._approved_providers

    def get_provider(self, provider: str) -> ProviderConfig:

        provider = provider.lower()

        if not self.is_approved(provider):
            raise ValueError(
                f"AI provider '{provider}' is not approved"
            )

        provider_config = self._providers.get(provider)

        if provider_config is None:
            raise ValueError(
                f"AI provider '{provider}' is unavailable"
            )

        if not provider_config.enabled:
            raise ValueError(
                f"AI provider '{provider}' is disabled"
            )

        return provider_config

    async def generate(
        self,
        provider: str,
        prompt: str,
        model: str | None = None,
    ) -> tuple[str, int, int]:

        provider_config = self.get_provider(provider)
        selected_model = model or provider_config.model

        if provider_config.name == "mock":
            content = (
                "Mock AI response generated successfully."
            )

            return (
                content,
                len(prompt.split()),
                len(content.split()),
            )

        if provider_config.name == "anthropic":
            return await self._generate_anthropic(
                prompt=prompt,
                model=selected_model,
            )

        raise AIProviderError(
            f"AI provider '{provider}' is not implemented"
        )

    @retry(
        retry=retry_if_exception_type(AIProviderError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(
            multiplier=1,
            min=1,
            max=2,
        ),
        reraise=True,
    )
    async def _generate_anthropic(
        self,
        prompt: str,
        model: str,
    ) -> tuple[str, int, int]:

        if not settings.anthropic_api_key:
            raise AIProviderError(
                "Anthropic API key is not configured"
            )

        try:
            client = anthropic.AsyncAnthropic(
                api_key=settings.anthropic_api_key
            )

            response = await client.messages.create(
                model=model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
            )

            content_parts = []

            for block in response.content:
                if getattr(block, "type", None) == "text":
                    content_parts.append(block.text)

            content = "\n".join(content_parts).strip()

            if not content:
                raise AIProviderError(
                    "Anthropic returned an empty response"
                )

            usage = response.usage

            input_tokens = getattr(
                usage,
                "input_tokens",
                0,
            )

            output_tokens = getattr(
                usage,
                "output_tokens",
                0,
            )

            return (
                content,
                input_tokens,
                output_tokens,
            )

        except AIProviderError:
            raise

        except Exception as exc:
            raise AIProviderError(
                f"Anthropic provider request failed: {exc}"
            ) from exc