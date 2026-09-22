from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Any


# ============================================================
# BE-017: Observability
# ============================================================

DEFAULT_CORRELATION_ID_HEADER = "X-Correlation-ID"

# These values must never appear in logs.
SENSITIVE_FIELD_NAMES = {
    "password",
    "passwd",
    "otp",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "secret",
    "authorization",
    "cookie",
    "phone_number",
    "phone",
    "email",
    "address",
    "citizen_id",
    "identity_number",
    "government_id",
    "message_content",
    "message",
    "audio",
    "transcript",
}


# ============================================================
# Correlation ID
# ============================================================


def generate_correlation_id() -> str:
    """
    Generate a unique correlation ID for one request/operation.
    """

    return str(uuid.uuid4())


def normalize_correlation_id(
    correlation_id: str | None,
) -> str:
    """
    Return the supplied correlation ID when safe,
    otherwise generate a new one.
    """

    if not correlation_id:
        return generate_correlation_id()

    value = correlation_id.strip()

    if not value:
        return generate_correlation_id()

    # Prevent excessively large header values.
    if len(value) > 128:
        return generate_correlation_id()

    return value


# ============================================================
# Structured Event
# ============================================================


@dataclass
class StructuredLogEvent:
    """
    Structured application log event.

    The event intentionally contains metadata rather than
    request/message contents.
    """

    timestamp: float
    level: str
    event: str
    correlation_id: str

    service: str = "ground-connect"
    environment: str = "development"

    subject_id: str | None = None
    tenant_id: str | None = None

    request_id: str | None = None
    trace_id: str | None = None

    duration_ms: float | None = None

    status_code: int | None = None

    metadata: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ============================================================
# Sensitive Data Sanitization
# ============================================================


def sanitize_for_logging(
    value: Any,
    *,
    key: str | None = None,
) -> Any:
    """
    Recursively remove sensitive values before logging.

    This is deliberately conservative.

    If a field name looks sensitive, its value becomes
    [REDACTED].
    """

    if key is not None:
        normalized_key = key.lower().strip()

        if normalized_key in SENSITIVE_FIELD_NAMES:
            return "[REDACTED]"

        # Also catch common variants such as:
        # user_password, refresh_token_value, etc.
        for sensitive_name in SENSITIVE_FIELD_NAMES:
            if sensitive_name in normalized_key:
                return "[REDACTED]"

    if isinstance(value, dict):
        return {
            str(item_key): sanitize_for_logging(
                item_value,
                key=str(item_key),
            )
            for item_key, item_value in value.items()
        }

    if isinstance(value, list):
        return [
            sanitize_for_logging(item)
            for item in value
        ]

    if isinstance(value, tuple):
        return [
            sanitize_for_logging(item)
            for item in value
        ]

    if isinstance(value, bytes):
        return "[BINARY_DATA_REDACTED]"

    if isinstance(value, str):
        # Do not log excessively large arbitrary text.
        if len(value) > 1000:
            return value[:1000] + "...[TRUNCATED]"

    return value


# ============================================================
# JSON Formatter
# ============================================================


class StructuredJSONFormatter(
    logging.Formatter
):
    """
    Convert Python logging records into JSON.

    Example:
    {
        "timestamp": 1234567890,
        "level": "INFO",
        "event": "request.completed",
        "correlation_id": "...",
        "service": "ground-connect"
    }
    """

    def format(
        self,
        record: logging.LogRecord,
    ) -> str:

        event_data = getattr(
            record,
            "structured_event",
            None,
        )

        if isinstance(
            event_data,
            StructuredLogEvent,
        ):
            data = event_data.to_dict()

        elif isinstance(
            event_data,
            dict,
        ):
            data = dict(event_data)

        else:
            data = {
                "timestamp": time.time(),
                "level": record.levelname,
                "event": record.getMessage(),
                "correlation_id": generate_correlation_id(),
                "service": "ground-connect",
                "environment": "development",
            }

        data = sanitize_for_logging(data)

        return json.dumps(
            data,
            ensure_ascii=False,
            separators=(",", ":"),
        )


# ============================================================
# Observability Service
# ============================================================


class ObservabilityService:
    """
    Central observability service.

    Responsibilities:
    - structured logging
    - correlation IDs
    - request timing
    - application metrics
    - tracing metadata
    - SIEM forwarding readiness
    """

    def __init__(
        self,
        *,
        service_name: str = "ground-connect",
        environment: str = "development",
        siem_enabled: bool = False,
        siem_endpoint: str | None = None,
    ):
        self.service_name = service_name
        self.environment = environment

        self.siem_enabled = siem_enabled
        self.siem_endpoint = siem_endpoint

        self.logger = logging.getLogger(
            self.service_name
        )

        self._configure_logger()

        # In-memory metrics.
        self._counters: dict[str, int] = {}

        self._timers: dict[str, list[float]] = {}

        # Recent structured events.
        self._events: list[dict[str, Any]] = []

        self._max_events = 10000

    # ========================================================
    # Logger Configuration
    # ========================================================

    def _configure_logger(self) -> None:
        """
        Configure JSON logging once.

        Does not add duplicate handlers when the application
        reloads.
        """

        self.logger.setLevel(logging.INFO)

        already_configured = any(
            isinstance(
                handler.formatter,
                StructuredJSONFormatter,
            )
            for handler in self.logger.handlers
            if handler.formatter is not None
        )

        if already_configured:
            return

        handler = logging.StreamHandler()

        handler.setFormatter(
            StructuredJSONFormatter()
        )

        self.logger.addHandler(handler)

        self.logger.propagate = False

    # ========================================================
    # Event Logging
    # ========================================================

    def log_event(
        self,
        *,
        event: str,
        level: str = "INFO",
        correlation_id: str | None = None,
        subject_id: str | None = None,
        tenant_id: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        duration_ms: float | None = None,
        status_code: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Create a structured event and send it to the application
        logger.

        Sensitive fields are sanitized before persistence/output.
        """

        normalized_correlation_id = (
            normalize_correlation_id(
                correlation_id
            )
        )

        safe_metadata = sanitize_for_logging(
            metadata or {}
        )

        event_record = StructuredLogEvent(
            timestamp=time.time(),
            level=level.upper(),
            event=event,
            correlation_id=normalized_correlation_id,
            service=self.service_name,
            environment=self.environment,
            subject_id=subject_id,
            tenant_id=tenant_id,
            request_id=request_id,
            trace_id=trace_id,
            duration_ms=duration_ms,
            status_code=status_code,
            metadata=safe_metadata,
        )

        event_dict = event_record.to_dict()

        event_dict = sanitize_for_logging(
            event_dict
        )

        self._events.append(event_dict)

        if len(self._events) > self._max_events:
            self._events = self._events[
                -self._max_events:
            ]

        record = logging.LogRecord(
            name=self.service_name,
            level=self._logging_level(level),
            pathname=__file__,
            lineno=0,
            msg=event,
            args=(),
            exc_info=None,
        )

        record.structured_event = event_record

        self.logger.handle(record)

        self._forward_to_siem(event_dict)

        return event_dict

    # ========================================================
    # Convenience Logging Methods
    # ========================================================

    def info(
        self,
        event: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.log_event(
            event=event,
            level="INFO",
            **kwargs,
        )

    def warning(
        self,
        event: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.log_event(
            event=event,
            level="WARNING",
            **kwargs,
        )

    def error(
        self,
        event: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.log_event(
            event=event,
            level="ERROR",
            **kwargs,
        )

    def critical(
        self,
        event: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return self.log_event(
            event=event,
            level="CRITICAL",
            **kwargs,
        )

    # ========================================================
    # Request Tracking
    # ========================================================

    def request_started(
        self,
        *,
        correlation_id: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        method: str | None = None,
        path: str | None = None,
    ) -> dict[str, Any]:

        return self.info(
            "request.started",
            correlation_id=correlation_id,
            request_id=request_id,
            trace_id=trace_id,
            metadata={
                "method": method,
                "path": path,
            },
        )

    def request_completed(
        self,
        *,
        correlation_id: str | None = None,
        request_id: str | None = None,
        trace_id: str | None = None,
        method: str | None = None,
        path: str | None = None,
        status_code: int | None = None,
        duration_ms: float | None = None,
    ) -> dict[str, Any]:

        return self.info(
            "request.completed",
            correlation_id=correlation_id,
            request_id=request_id,
            trace_id=trace_id,
            status_code=status_code,
            duration_ms=duration_ms,
            metadata={
                "method": method,
                "path": path,
            },
        )

    # ========================================================
    # Metrics
    # ========================================================

    def increment_counter(
        self,
        name: str,
        value: int = 1,
    ) -> int:

        if value < 0:
            raise ValueError(
                "Counter increment cannot be negative."
            )

        self._counters[name] = (
            self._counters.get(name, 0)
            + value
        )

        return self._counters[name]

    def get_counter(
        self,
        name: str,
    ) -> int:

        return self._counters.get(
            name,
            0,
        )

    def record_timing(
        self,
        name: str,
        duration_ms: float,
    ) -> float:

        if duration_ms < 0:
            raise ValueError(
                "Duration cannot be negative."
            )

        self._timers.setdefault(
            name,
            [],
        ).append(duration_ms)

        # Prevent unbounded memory growth.
        if len(self._timers[name]) > 1000:
            self._timers[name] = self._timers[
                name
            ][-1000:]

        return duration_ms

    def get_timing(
        self,
        name: str,
    ) -> dict[str, float | int | None]:

        values = self._timers.get(
            name,
            [],
        )

        if not values:
            return {
                "count": 0,
                "average_ms": None,
                "minimum_ms": None,
                "maximum_ms": None,
            }

        return {
            "count": len(values),
            "average_ms": (
                sum(values) / len(values)
            ),
            "minimum_ms": min(values),
            "maximum_ms": max(values),
        }

    # ========================================================
    # Metrics Snapshot
    # ========================================================

    def metrics_snapshot(
        self,
    ) -> dict[str, Any]:

        return {
            "counters": dict(
                self._counters
            ),
            "timings": {
                name: self.get_timing(name)
                for name in self._timers
            },
            "events_in_memory": len(
                self._events
            ),
            "service": self.service_name,
            "environment": self.environment,
        }

    # ========================================================
    # Trace Metadata
    # ========================================================

    def create_trace_context(
        self,
        correlation_id: str | None = None,
    ) -> dict[str, str]:

        return {
            "correlation_id": (
                normalize_correlation_id(
                    correlation_id
                )
            ),
            "trace_id": str(uuid.uuid4()),
            "span_id": str(uuid.uuid4()),
        }

    # ========================================================
    # Event Retrieval
    # ========================================================

    def recent_events(
        self,
        limit: int = 100,
    ) -> list[dict[str, Any]]:

        limit = max(
            1,
            min(limit, self._max_events),
        )

        return list(
            reversed(
                self._events[-limit:]
            )
        )

    # ========================================================
    # SIEM
    # ========================================================

    def _forward_to_siem(
        self,
        event: dict[str, Any],
    ) -> None:
        """
        SIEM integration readiness.

        Actual network delivery should be implemented using
        the organization's approved SIEM transport/agent.

        This method intentionally does not send arbitrary
        event data to an external endpoint.
        """

        if not self.siem_enabled:
            return

        if not self.siem_endpoint:
            return

        # Application-side readiness marker.
        #
        # In production this should be replaced with the approved
        # SIEM client/agent integration.
        #
        # We deliberately do not make an outbound HTTP request here.
        return

    # ========================================================
    # Reset
    # ========================================================

    def reset_metrics(self) -> None:
        self._counters.clear()
        self._timers.clear()

    def clear_events(self) -> None:
        self._events.clear()

    # ========================================================
    # Helpers
    # ========================================================

    @staticmethod
    def _logging_level(
        level: str,
    ) -> int:

        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        return levels.get(
            level.upper(),
            logging.INFO,
        )


# ============================================================
# Global Observability Service
# ============================================================

observability_service = ObservabilityService()