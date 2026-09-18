from dataclasses import dataclass
from threading import Lock


@dataclass(frozen=True)
class AIUsageRecord:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float


class AICostMeter:
    """
    AI-020 prototype cost meter.
    Records usage in memory.
    """

    def __init__(self):
        self._records: list[AIUsageRecord] = []
        self._lock = Lock()

    def record(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        estimated_cost: float,
    ) -> AIUsageRecord:

        record = AIUsageRecord(
            provider=provider,
            model=model,
            input_tokens=max(0, input_tokens),
            output_tokens=max(0, output_tokens),
            estimated_cost=max(0.0, estimated_cost),
        )

        with self._lock:
            self._records.append(record)

        return record

    def records(self) -> list[AIUsageRecord]:
        with self._lock:
            return list(self._records)

    def total_cost(self) -> float:
        with self._lock:
            return sum(
                record.estimated_cost
                for record in self._records
            )

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


class AIProviderRouter:
    """
    AI-020 provider routing boundary.
    Only approved providers can be selected.
    """

    def __init__(self, provider_registry):
        self.provider_registry = provider_registry

    def route(
        self,
        provider: str | None = None,
        model: str | None = None,
    ):
        selected_provider = provider or "mock"

        config = self.provider_registry.get_provider(
            selected_provider
        )

        selected_model = model or config.model

        return config, selected_model
