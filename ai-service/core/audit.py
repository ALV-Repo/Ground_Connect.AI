from dataclasses import dataclass
from datetime import datetime, timezone
import json

import redis

from core.config import settings


@dataclass(frozen=True)
class AuditEvent:
    event_type: str
    user_id: str
    organization_id: str
    resource_organization_id: str
    timestamp: datetime
    details: str


class AuditService:
    """
    Redis-backed AI audit service.

    Audit events are persisted in Redis so they can be retrieved
    across service instances.
    """

    REDIS_KEY = "ai:audit:access-denied"

    def __init__(self):
        self._redis = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )

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

        self._redis.rpush(
            self.REDIS_KEY,
            json.dumps(
                {
                    "event_type": event.event_type,
                    "user_id": event.user_id,
                    "organization_id": event.organization_id,
                    "resource_organization_id": (
                        event.resource_organization_id
                    ),
                    "timestamp": event.timestamp.isoformat(),
                    "details": event.details,
                }
            ),
        )

        return event

    def get_events(self) -> list[AuditEvent]:
        raw_events = self._redis.lrange(
            self.REDIS_KEY,
            0,
            -1,
        )

        events: list[AuditEvent] = []

        for raw_event in raw_events:
            data = json.loads(raw_event)

            events.append(
                AuditEvent(
                    event_type=data["event_type"],
                    user_id=data["user_id"],
                    organization_id=data["organization_id"],
                    resource_organization_id=(
                        data["resource_organization_id"]
                    ),
                    timestamp=datetime.fromisoformat(
                        data["timestamp"]
                    ),
                    details=data["details"],
                )
            )

        return events