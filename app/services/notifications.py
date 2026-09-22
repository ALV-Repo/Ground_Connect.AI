from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.config import settings


class NotificationService:
    """
    BE-014 — Notification Delivery

    Provides:
    - Notification creation
    - Multi-channel delivery
    - Retry handling
    - Cancellation
    - Delivery status tracking
    - Tenant isolation
    """

    def __init__(self) -> None:
        self._notifications: Dict[str, Dict[str, Any]] = {}
        self._delivery_attempts: Dict[
            str, List[Dict[str, Any]]
        ] = {}

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _get_notification(
        self,
        notification_id: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        notification = self._notifications.get(
            notification_id
        )

        if notification is None:
            raise KeyError("Notification not found")

        if (
            tenant_id is not None
            and notification["tenant_id"] != tenant_id
        ):
            raise PermissionError(
                "Cross-tenant notification access denied"
            )

        return notification

    # =========================================================
    # Create Notification
    # =========================================================

    def create_notification(
        self,
        *,
        notification_id: str,
        tenant_id: str,
        title: str,
        body: str,
        created_by: str,
        recipients: List[Dict[str, Any]],
        priority: str = "normal",
        scheduled_at: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        if notification_id in self._notifications:
            raise ValueError(
                "Notification already exists"
            )

        max_recipients = getattr(
            settings,
            "message_max_recipients",
            200000,
        )

        if not recipients:
            raise ValueError(
                "At least one recipient is required"
            )

        if len(recipients) > max_recipients:
            raise ValueError(
                f"Maximum recipients allowed: "
                f"{max_recipients}"
            )

        normalized_recipients = []

        for recipient in recipients:

            if recipient.get("tenant_id") != tenant_id:
                raise PermissionError(
                    "Cross-tenant recipient is not allowed"
                )

            if not recipient.get("recipient_id"):
                raise ValueError(
                    "recipient_id is required"
                )

            normalized_recipients.append(
                {
                    "recipient_id": recipient[
                        "recipient_id"
                    ],
                    "tenant_id": recipient[
                        "tenant_id"
                    ],
                    "channel": recipient.get(
                        "channel",
                        "in_app",
                    ),
                    "endpoint": recipient.get(
                        "endpoint"
                    ),
                }
            )

        now = self._now()

        if expires_at is None:
            expiry_seconds = getattr(
                settings,
                "message_expiry_seconds",
                86400,
            )

            expires_at = now + timedelta(
                seconds=expiry_seconds
            )

        notification = {
            "notification_id": notification_id,
            "tenant_id": tenant_id,
            "title": title,
            "body": body,
            "created_by": created_by,
            "recipients": normalized_recipients,
            "priority": priority,
            "status": "created",
            "created_at": now,
            "updated_at": now,
            "scheduled_at": scheduled_at,
            "expires_at": expires_at,
            "delivered_count": 0,
            "failed_count": 0,
            "pending_count": len(
                normalized_recipients
            ),
            "retry_count": 0,
            "metadata": metadata or {},
        }

        self._notifications[
            notification_id
        ] = notification

        self._delivery_attempts[
            notification_id
        ] = []

        return dict(notification)

    # =========================================================
    # Get Notification
    # =========================================================

    def get_notification(
        self,
        *,
        notification_id: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        return dict(
            self._get_notification(
                notification_id,
                tenant_id,
            )
        )

    # =========================================================
    # Deliver Notification
    # =========================================================

    def deliver(
        self,
        *,
        notification_id: str,
        tenant_id: str,
        recipient_id: str,
        channel: str,
        requested_by: str,
    ) -> Dict[str, Any]:

        notification = self._get_notification(
            notification_id,
            tenant_id,
        )

        if notification["status"] in {
            "cancelled",
            "expired",
        }:
            raise ValueError(
                f"Notification cannot be delivered "
                f"in status {notification['status']}"
            )

        now = self._now()

        if notification["expires_at"] <= now:

            notification["status"] = "expired"
            notification["updated_at"] = now

            raise ValueError(
                "Notification has expired"
            )

        recipient = None

        for item in notification["recipients"]:
            if (
                item["recipient_id"]
                == recipient_id
                and item["channel"]
                == channel
            ):
                recipient = item
                break

        if recipient is None:
            raise KeyError(
                "Notification recipient/channel not found"
            )

        attempt_id = str(uuid4())

        attempt = {
            "attempt_id": attempt_id,
            "notification_id": notification_id,
            "recipient_id": recipient_id,
            "channel": channel,
            "requested_by": requested_by,
            "status": "delivered",
            "attempted_at": now,
            "error": None,
        }

        self._delivery_attempts[
            notification_id
        ].append(attempt)

        notification["delivered_count"] += 1

        notification["pending_count"] = max(
            notification["pending_count"] - 1,
            0,
        )

        if notification["pending_count"] == 0:
            notification["status"] = "delivered"
        else:
            notification["status"] = "partially_delivered"

        notification["updated_at"] = now

        return {
            "success": True,
            "notification_id": notification_id,
            "recipient_id": recipient_id,
            "channel": channel,
            "status": "delivered",
            "delivered_at": now,
            "error": None,
        }

    # =========================================================
    # Retry
    # =========================================================

    def retry(
        self,
        *,
        notification_id: str,
        tenant_id: str,
        recipient_id: Optional[str],
        requested_by: str,
    ) -> Dict[str, Any]:

        notification = self._get_notification(
            notification_id,
            tenant_id,
        )

        if notification["status"] == "cancelled":
            raise ValueError(
                "Cancelled notification cannot be retried"
            )

        attempts = self._delivery_attempts.get(
            notification_id,
            [],
        )

        if recipient_id is None:
            retry_targets = [
                recipient
                for recipient in notification[
                    "recipients"
                ]
            ]
        else:
            retry_targets = [
                recipient
                for recipient in notification[
                    "recipients"
                ]
                if recipient["recipient_id"]
                == recipient_id
            ]

        if not retry_targets:
            raise KeyError(
                "No matching notification recipients"
            )

        retry_count = 0

        for recipient in retry_targets:

            attempt = {
                "attempt_id": str(uuid4()),
                "notification_id": notification_id,
                "recipient_id": recipient[
                    "recipient_id"
                ],
                "channel": recipient["channel"],
                "requested_by": requested_by,
                "status": "retry_queued",
                "attempted_at": self._now(),
                "error": None,
            }

            attempts.append(attempt)
            retry_count += 1

        notification["retry_count"] += retry_count
        notification["status"] = "retry_queued"
        notification["updated_at"] = self._now()

        return {
            "success": True,
            "notification_id": notification_id,
            "retried_count": retry_count,
            "status": "retry_queued",
        }

    # =========================================================
    # Cancel
    # =========================================================

    def cancel(
        self,
        *,
        notification_id: str,
        tenant_id: str,
        requested_by: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:

        notification = self._get_notification(
            notification_id,
            tenant_id,
        )

        now = self._now()

        notification["status"] = "cancelled"
        notification["updated_at"] = now

        notification.setdefault(
            "metadata",
            {},
        )

        notification["metadata"][
            "cancelled_by"
        ] = requested_by

        notification["metadata"][
            "cancelled_at"
        ] = now

        if reason:
            notification["metadata"][
                "cancellation_reason"
            ] = reason

        return {
            "success": True,
            "notification_id": notification_id,
            "cancelled": True,
            "cancelled_by": requested_by,
            "cancelled_at": now,
        }

    # =========================================================
    # Status
    # =========================================================

    def status(
        self,
        *,
        notification_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:

        notification = self._get_notification(
            notification_id,
            tenant_id,
        )

        return {
            "notification_id": notification[
                "notification_id"
            ],
            "status": notification["status"],
            "total_recipients": len(
                notification["recipients"]
            ),
            "delivered_count": notification[
                "delivered_count"
            ],
            "failed_count": notification[
                "failed_count"
            ],
            "pending_count": notification[
                "pending_count"
            ],
            "retry_count": notification[
                "retry_count"
            ],
            "created_at": notification[
                "created_at"
            ],
            "updated_at": notification[
                "updated_at"
            ],
        }

    # =========================================================
    # Delivery Attempts
    # =========================================================

    def delivery_attempts(
        self,
        *,
        notification_id: str,
        tenant_id: str,
    ) -> List[Dict[str, Any]]:

        self._get_notification(
            notification_id,
            tenant_id,
        )

        return list(
            self._delivery_attempts.get(
                notification_id,
                [],
            )
        )

    # =========================================================
    # Search
    # =========================================================

    def search(
        self,
        *,
        tenant_id: str,
        query: Optional[str] = None,
        status: Optional[str] = None,
        channel: Optional[str] = None,
        priority: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:

        notifications = [
            notification
            for notification
            in self._notifications.values()
            if notification["tenant_id"]
            == tenant_id
        ]

        if query:

            query_lower = query.lower()

            notifications = [
                notification
                for notification
                in notifications
                if (
                    query_lower
                    in str(
                        notification[
                            "notification_id"
                        ]
                    ).lower()
                    or query_lower
                    in str(
                        notification["title"]
                    ).lower()
                    or query_lower
                    in str(
                        notification["body"]
                    ).lower()
                )
            ]

        if status:

            notifications = [
                notification
                for notification
                in notifications
                if notification["status"]
                == status
            ]

        if channel:

            notifications = [
                notification
                for notification
                in notifications
                if any(
                    recipient["channel"]
                    == channel
                    for recipient
                    in notification[
                        "recipients"
                    ]
                )
            ]

        if priority:

            notifications = [
                notification
                for notification
                in notifications
                if notification["priority"]
                == priority
            ]

        total = len(notifications)

        start = (page - 1) * page_size
        end = start + page_size

        return {
            "items": [
                dict(notification)
                for notification
                in notifications[
                    start:end
                ]
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


# ============================================================
# Global service instance
# ============================================================

notification_service = NotificationService()