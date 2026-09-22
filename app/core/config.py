from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings:
    # ---------------------------------------------------------
    # Application
    # ---------------------------------------------------------
    app_name: str = "GroundConnect AI"
    app_version: str = "1.0.0"
    debug: bool = True

    # ---------------------------------------------------------
    # AI Provider
    # ---------------------------------------------------------
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

    # ---------------------------------------------------------
    # BE-003: Authorization
    # ---------------------------------------------------------
    authorization_default_deny: bool = True

    # Maximum lifetime of cached authorization decisions
    authorization_cache_ttl_seconds: int = 60

    # ---------------------------------------------------------
    # BE-004: Audit / ADR
    # ---------------------------------------------------------
    audit_enabled: bool = True

    # Do not put sensitive request/message content in logs.
    audit_include_sensitive_data: bool = False

    # Maximum number of in-memory audit records retained
    audit_max_records: int = 10000

    # ---------------------------------------------------------
    # BE-005: Field-level Authorization
    # ---------------------------------------------------------
    field_auth_cache_ttl_seconds: int = 60

    # ---------------------------------------------------------
    # BE-006: Member Management
    # ---------------------------------------------------------
    member_import_max_records: int = 10000

    # ---------------------------------------------------------
    # BE-007 / BE-008: Messaging
    # ---------------------------------------------------------
    message_default_expiry_seconds: int = 86400

    # Maximum recipients allowed for a single message
    message_max_recipients: int = 200000

    # Maximum staged batch size
    message_stage_batch_size: int = 1000

    # ---------------------------------------------------------
    # BE-009: Task Engine
    # ---------------------------------------------------------
    task_default_due_hours: int = 24

    task_max_evidence_size_mb: int = 25

    # ---------------------------------------------------------
    # BE-010: Vendor Elevation
    # ---------------------------------------------------------
    vendor_elevation_max_duration_minutes: int = 60

    # ---------------------------------------------------------
    # BE-011: Two-Person Integrity
    # ---------------------------------------------------------
    tpi_enabled: bool = True

    # ---------------------------------------------------------
    # BE-012: Security / Encryption
    # ---------------------------------------------------------
    encryption_enabled: bool = True

    # Environment marker
    environment: str = "development"

    # ---------------------------------------------------------
    # BE-013: Incident Response
    # ---------------------------------------------------------
    incident_response_enabled: bool = True

    # Production release should require security checks
    pentest_release_gate: bool = False

    # ---------------------------------------------------------
    # BE-014: Notifications
    # ---------------------------------------------------------
    notifications_enabled: bool = True

    notification_retry_attempts: int = 3

    notification_retry_delay_seconds: int = 5

    # ---------------------------------------------------------
    # BE-015: Performance
    # ---------------------------------------------------------
    performance_metrics_enabled: bool = True

    # Target request timeout used by application-level checks
    request_timeout_seconds: int = 30

    # ---------------------------------------------------------
    # BE-016: HA / Backup / Recovery
    # ---------------------------------------------------------
    backup_enabled: bool = True

    # Backup retention period
    backup_retention_days: int = 30

    # Recovery Point Objective:
    # Maximum acceptable data loss = 15 minutes
    recovery_point_objective_minutes: int = 15

    # Recovery Time Objective:
    # Maximum acceptable recovery time = 60 minutes
    recovery_time_objective_minutes: int = 60

    # ---------------------------------------------------------
    # BE-017: Observability / SIEM
    # ---------------------------------------------------------
    observability_enabled: bool = True

    metrics_enabled: bool = True

    tracing_enabled: bool = True

    siem_enabled: bool = False

    # Optional future SIEM endpoint
    siem_endpoint: str | None = None

    # Correlation ID header
    correlation_id_header: str = "X-Correlation-ID"

    # ---------------------------------------------------------
    # Pydantic Settings
    # ---------------------------------------------------------
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---------------------------------------------------------
    # Helper Properties
    # ---------------------------------------------------------
    @property
    def supported_language_codes(self) -> set[str]:
        return {
            language.strip().lower()
            for language in self.supported_languages.split(",")
            if language.strip()
        }


settings = Settings()