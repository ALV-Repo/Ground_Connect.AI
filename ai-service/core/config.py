from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    app_name: str = "GroundConnect AI Service"
    app_version: str = "1.0.0"
    environment: str = "development"

    # AI Provider Configuration
    ai_provider: str = "mock"
    ai_model: str = "mock-model"
    approved_ai_providers: str = "mock"

    # Anthropic Provider
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-3-5-sonnet-latest"

    # AI Cost Configuration
    anthropic_input_cost_per_1k_tokens: float = 0.0
    anthropic_output_cost_per_1k_tokens: float = 0.0

    # Redis Conversation Memory
    redis_url: str = "redis://localhost:6379/0"
    redis_memory_ttl_seconds: int = 86400

    # JWT Security
    jwt_secret: str = "dev-only-groundconnect-jwt-secret-32"
    jwt_algorithm: str = "HS256"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def approved_providers(self) -> set[str]:
        return {
            provider.strip().lower()
            for provider in self.approved_ai_providers.split(",")
            if provider.strip()
        }


settings = Settings()