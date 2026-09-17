from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GroundConnect AI Service"
    app_version: str = "1.0.0"
    environment: str = "development"

    ai_provider: str = "mock"
    ai_model: str = "mock-model"
    approved_ai_providers: str = "mock"

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