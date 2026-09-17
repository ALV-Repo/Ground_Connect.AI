from dataclasses import dataclass


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
            )
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