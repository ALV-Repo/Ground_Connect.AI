from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "GroundConnect AI"
    app_version: str = "1.0.0"
    debug: bool = True

    # AI provider
    ai_provider: str = "mock"

    # Supported launch languages
    supported_languages: str = "en,hi,kn"

    # Default language for transcription
    default_language: str = "hi-IN"

    # Transcriptions below this confidence
    # require human confirmation
    transcription_confidence_threshold: float = 0.80

    # Optional future provider key.
    # Current implementation does not require it.
    openai_api_key: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def supported_language_codes(self) -> set[str]:
        return {
            language.strip().lower()
            for language in self.supported_languages.split(",")
            if language.strip()
        }


settings = Settings()