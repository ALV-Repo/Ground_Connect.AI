from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    user_id: str
    organization_id: str
    resource_organization_id: str
    timestamp: datetime
    details: str


class AuditService:

    def __init__(self):
        self._events: list[AuditEvent] = []

    def record_access_denied(
        self,
        user_id: str,
        organization_id: str,
        resource_organization_id: str,
        details: str = "AI access denied",
    ) -> AuditEvent:

        event = AuditEvent(
            event_type="AI_ACCESS_DENIED",
            user_id=user_id,
            organization_id=organization_id,
            resource_organization_id=resource_organization_id,
            timestamp=datetime.now(timezone.utc),
            details=details,
        )

        self._events.append(event)

        return event

    def get_events(self) -> list[AuditEvent]:
        return list(self._events)
