from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.config import settings


class MessagingService:
    """
    BE-007 + BE-008

    Responsibilities:
    - Message creation
    - Tenant isolation
    - Recipient validation
    - Message propagation
    - Blast-radius calculation
    - Staged delivery
    - Delivery halt/resume
    - Delivery event tracking
    - Message cancellation
    - Message search
    """

    def __init__(self) -> None:
        self._messages: Dict[str, Dict[str, Any]] = {}

        # message_id -> list of delivery events
        self._delivery_events: Dict[
            str,
            List[Dict[str, Any]]
        ] = {}

        self._halted_messages: Dict[
            str,
            Dict[str, Any]
        ] = {}

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _serialize(
        message: Dict[str, Any],
    ) -> Dict[str, Any]:
        return dict(message)

    def _get_message(
        self,
        message_id: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        message = self._messages.get(message_id)

        if message is None:
            raise KeyError("Message not found")

        if (
            tenant_id is not None
            and message["tenant_id"] != tenant_id
        ):
            raise PermissionError(
                "Cross-tenant message access denied"
            )

        return message

    # =========================================================
    # BE-007 — Message Creation
    # =========================================================

    def create_message(
        self,
        *,
        message_id: str,
        tenant_id: str,
        subject: str,
        body: str,
        created_by: str,
        recipients: List[Dict[str, Any]],
        priority: str = "normal",
        expires_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        if message_id in self._messages:
            raise ValueError("Message already exists")

        max_recipients = getattr(
            settings,
            "message_max_recipients",
            200000,
        )

        if len(recipients) > max_recipients:
            raise ValueError(
                f"Maximum recipients allowed: "
                f"{max_recipients}"
            )

        if not recipients:
            raise ValueError(
                "At least one recipient is required"
            )

        recipient_records: List[Dict[str, Any]] = []

        for recipient in recipients:

            if recipient.get("tenant_id") != tenant_id:
                raise PermissionError(
                    "Cross-tenant recipient is not allowed"
                )

            member_id = recipient.get("member_id")

            if not member_id:
                raise ValueError(
                    "Recipient member_id is required"
                )

            recipient_records.append(
                {
                    "member_id": member_id,
                    "tenant_id": recipient["tenant_id"],
                    "branch_id": recipient.get("branch_id"),
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

        message = {
            "message_id": message_id,
            "tenant_id": tenant_id,
            "subject": subject,
            "body": body,
            "created_by": created_by,
            "recipients": recipient_records,
            "priority": priority,
            "status": "created",
            "created_at": now,
            "updated_at": now,
            "expires_at": expires_at,
            "delivered_count": 0,
            "failed_count": 0,
            "pending_count": len(recipient_records),
            "metadata": metadata or {},
        }

        self._messages[message_id] = message

        self._delivery_events[message_id] = []

        return self._serialize(message)

    # =========================================================
    # Get Message
    # =========================================================

    def get_message(
        self,
        *,
        message_id: str,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        message = self._get_message(
            message_id,
            tenant_id,
        )

        return self._serialize(message)

    # =========================================================
    # BE-008 — Blast Radius
    # =========================================================

    def calculate_blast_radius(
        self,
        *,
        tenant_id: str,
        recipient_ids: List[str],
        max_recipients: Optional[int] = None,
    ) -> Dict[str, Any]:

        configured_limit = getattr(
            settings,
            "message_max_recipients",
            200000,
        )

        limit = min(
            max_recipients or configured_limit,
            configured_limit,
        )

        requested_count = len(recipient_ids)

        # Remove duplicate recipients while preserving order
        unique_recipient_ids = list(
            dict.fromkeys(recipient_ids)
        )

        if len(unique_recipient_ids) <= limit:

            allowed = unique_recipient_ids
            blocked: List[str] = []

        else:

            allowed = unique_recipient_ids[:limit]
            blocked = unique_recipient_ids[limit:]

        return {
            "success": len(blocked) == 0,
            "tenant_id": tenant_id,
            "requested_count": requested_count,
            "allowed_count": len(allowed),
            "blocked_count": len(blocked),
            "affected_members": allowed,
            "blocked_members": blocked,
            "reason": (
                None
                if not blocked
                else (
                    f"Recipient limit of {limit} "
                    "exceeded"
                )
            ),
        }

    # =========================================================
    # Message Propagation
    # =========================================================

    def propagate_message(
        self,
        *,
        message_id: str,
        tenant_id: str,
        requested_by: str,
        stage: str = "initial",
        batch_size: Optional[int] = None,
    ) -> Dict[str, Any]:

        message = self._get_message(
            message_id,
            tenant_id,
        )

        if message["status"] in {
            "halted",
            "cancelled",
            "expired",
            "completed",
        }:
            raise ValueError(
                f"Message cannot be propagated "
                f"in status {message['status']}"
            )

        if message_id in self._halted_messages:
            raise ValueError(
                "Message delivery has been halted"
            )

        now = self._now()

        if message["expires_at"] <= now:

            message["status"] = "expired"
            message["updated_at"] = now

            raise ValueError(
                "Message has expired"
            )

        configured_batch = getattr(
            settings,
            "message_stage_batch_size",
            1000,
        )

        batch = batch_size or configured_batch

        if batch <= 0:
            raise ValueError(
                "batch_size must be greater than zero"
            )

        recipients = message["recipients"]

        started_at = self._now()

        message["status"] = "propagating"
        message["updated_at"] = started_at

        delivered = 0
        failed = 0

        events: List[Dict[str, Any]] = []

        # Process only one batch in this propagation call.
        # Remaining batches can be processed by subsequent calls.
        start_index = message.get(
            "propagation_cursor",
            0,
        )

        end_index = min(
            start_index + batch,
            len(recipients),
        )

        for recipient in recipients[
            start_index:end_index
        ]:

            if message_id in self._halted_messages:

                message["status"] = "halted"
                break

            recipient_id = recipient["member_id"]

            event = {
                "event_id": str(uuid4()),
                "message_id": message_id,
                "recipient_id": recipient_id,
                "tenant_id": tenant_id,
                "event_type": "delivered",
                "timestamp": self._now(),
                "success": True,
                "error": None,
                "requested_by": requested_by,
                "stage": stage,
            }

            events.append(event)

            delivered += 1

        self._delivery_events.setdefault(
            message_id,
            [],
        ).extend(events)

        if message["status"] != "halted":

            message["propagation_cursor"] = (
                end_index
            )

            total_delivered = len(
                self._delivery_events.get(
                    message_id,
                    [],
                )
            )

            message["delivered_count"] = (
                total_delivered
            )

            message["failed_count"] = failed

            message["pending_count"] = max(
                len(recipients)
                - total_delivered
                - failed,
                0,
            )

            if (
                message["propagation_cursor"]
                >= len(recipients)
            ):
                message["status"] = "completed"
            else:
                message["status"] = "propagating"

        message["updated_at"] = self._now()

        completed_at = (
            self._now()
            if message["status"] == "completed"
            else None
        )

        return {
            "success": message["status"]
            in {
                "propagating",
                "completed",
            },
            "message_id": message_id,
            "stage": stage,
            "status": message["status"],
            "total_recipients": len(recipients),
            "processed": delivered + failed,
            "delivered": delivered,
            "failed": failed,
            "started_at": started_at,
            "completed_at": completed_at,
        }

    # =========================================================
    # BE-008 — Staged Delivery
    # =========================================================

    def start_staged_delivery(
        self,
        *,
        message_id: str,
        tenant_id: str,
        stage_name: str,
        batch_size: int,
        requested_by: str,
    ) -> Dict[str, Any]:

        message = self._get_message(
            message_id,
            tenant_id,
        )

        if batch_size <= 0:
            raise ValueError(
                "batch_size must be greater than zero"
            )

        recipients_count = len(
            message["recipients"]
        )

        total_batches = (
            recipients_count
            + batch_size
            - 1
        ) // batch_size

        now = self._now()

        message["status"] = "staged"
        message["updated_at"] = now

        message.setdefault(
            "stages",
            {},
        )

        message["stages"][stage_name] = {
            "batch_size": batch_size,
            "total_batches": total_batches,
            "current_batch": 0,
            "requested_by": requested_by,
            "started_at": now,
            "updated_at": now,
        }

        # Record stage creation event
        self._delivery_events.setdefault(
            message_id,
            [],
        ).append(
            {
                "event_id": str(uuid4()),
                "message_id": message_id,
                "tenant_id": tenant_id,
                "event_type": "staged",
                "timestamp": now,
                "success": True,
                "error": None,
                "requested_by": requested_by,
                "stage": stage_name,
            }
        )

        return {
            "success": True,
            "message_id": message_id,
            "stage_name": stage_name,
            "batch_size": batch_size,
            "total_batches": total_batches,
            "current_batch": 0,
            "status": "staged",
            "started_at": now,
            "updated_at": now,
        }

    # =========================================================
    # Advance Stage
    # =========================================================

    def advance_stage(
        self,
        *,
        message_id: str,
        tenant_id: str,
        stage_name: str,
    ) -> Dict[str, Any]:

        message = self._get_message(
            message_id,
            tenant_id,
        )

        stages = message.get(
            "stages",
            {},
        )

        stage = stages.get(stage_name)

        if stage is None:
            raise KeyError(
                "Delivery stage not found"
            )

        if message_id in self._halted_messages:

            message["status"] = "halted"

            raise ValueError(
                "Message delivery has been halted"
            )

        if (
            stage["current_batch"]
            >= stage["total_batches"]
        ):
            return {
                "success": True,
                "message_id": message_id,
                "stage_name": stage_name,
                "current_batch": (
                    stage["current_batch"]
                ),
                "total_batches": (
                    stage["total_batches"]
                ),
                "status": "completed",
            }

        stage["current_batch"] += 1

        now = self._now()

        stage["updated_at"] = now
        message["updated_at"] = now

        # Record stage advancement event
        self._delivery_events.setdefault(
            message_id,
            [],
        ).append(
            {
                "event_id": str(uuid4()),
                "message_id": message_id,
                "tenant_id": tenant_id,
                "event_type": "stage_advanced",
                "timestamp": now,
                "success": True,
                "error": None,
                "requested_by": stage["requested_by"],
                "stage": stage_name,
                "current_batch": stage["current_batch"],
                "total_batches": stage["total_batches"],
            }
        )

        if (
            stage["current_batch"]
            >= stage["total_batches"]
        ):
            message["status"] = "completed"

        return {
            "success": True,
            "message_id": message_id,
            "stage_name": stage_name,
            "current_batch": (
                stage["current_batch"]
            ),
            "total_batches": (
                stage["total_batches"]
            ),
            "status": message["status"],
        }

    # =========================================================
    # Emergency Halt
    # =========================================================

    def halt_delivery(
        self,
        *,
        message_id: str,
        tenant_id: str,
        reason: str,
        requested_by: str,
    ) -> Dict[str, Any]:

        message = self._get_message(
            message_id,
            tenant_id,
        )

        now = self._now()

        self._halted_messages[message_id] = {
            "reason": reason,
            "requested_by": requested_by,
            "halted_at": now,
        }

        message["status"] = "halted"
        message["updated_at"] = now

        # Record halt event
        self._delivery_events.setdefault(
            message_id,
            [],
        ).append(
            {
                "event_id": str(uuid4()),
                "message_id": message_id,
                "tenant_id": tenant_id,
                "event_type": "halted",
                "timestamp": now,
                "success": True,
                "error": None,
                "requested_by": requested_by,
                "reason": reason,
            }
        )

        return {
            "success": True,
            "message_id": message_id,
            "halted": True,
            "reason": reason,
            "halted_by": requested_by,
            "halted_at": now,
        }

    # =========================================================
    # Resume Delivery
    # =========================================================

    def resume_delivery(
        self,
        *,
        message_id: str,
        tenant_id: str,
        requested_by: str,
    ) -> Dict[str, Any]:

        message = self._get_message(
            message_id,
            tenant_id,
        )

        self._halted_messages.pop(
            message_id,
            None,
        )

        now = self._now()

        message["status"] = "propagating"
        message["updated_at"] = now

        # Record resume event
        self._delivery_events.setdefault(
            message_id,
            [],
        ).append(
            {
                "event_id": str(uuid4()),
                "message_id": message_id,
                "tenant_id": tenant_id,
                "event_type": "resumed",
                "timestamp": now,
                "success": True,
                "error": None,
                "requested_by": requested_by,
            }
        )

        return {
            "success": True,
            "message_id": message_id,
            "status": message["status"],
            "resumed_by": requested_by,
            "resumed_at": message["updated_at"],
        }

    # =========================================================
    # Delivery Events
    # =========================================================

    def delivery_events(
        self,
        *,
        message_id: str,
        tenant_id: str,
    ) -> List[Dict[str, Any]]:

        self._get_message(
            message_id,
            tenant_id,
        )

        return list(
            self._delivery_events.get(
                message_id,
                [],
            )
        )

    # =========================================================
    # Cancel
    # =========================================================

    def cancel_message(
        self,
        *,
        message_id: str,
        tenant_id: str,
        requested_by: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:

        message = self._get_message(
            message_id,
            tenant_id,
        )

        message["status"] = "cancelled"
        message["updated_at"] = self._now()

        message.setdefault(
            "metadata",
            {},
        )

        message["metadata"][
            "cancelled_by"
        ] = requested_by

        if reason:
            message["metadata"][
                "cancellation_reason"
            ] = reason

        # Record cancellation event
        self._delivery_events.setdefault(
            message_id,
            [],
        ).append(
            {
                "event_id": str(uuid4()),
                "message_id": message_id,
                "tenant_id": tenant_id,
                "event_type": "cancelled",
                "timestamp": message["updated_at"],
                "success": True,
                "error": None,
                "requested_by": requested_by,
                "reason": reason,
            }
        )

        return {
            "success": True,
            "message_id": message_id,
            "cancelled": True,
            "cancelled_by": requested_by,
            "cancelled_at": message["updated_at"],
        }

    # =========================================================
    # Search
    # =========================================================

    def search_messages(
        self,
        *,
        tenant_id: str,
        query: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:

        messages = [
            message
            for message in self._messages.values()
            if message["tenant_id"] == tenant_id
        ]

        if query:

            query_lower = query.lower()

            messages = [
                message
                for message in messages
                if (
                    query_lower
                    in str(
                        message["message_id"]
                    ).lower()
                    or query_lower
                    in str(
                        message["subject"]
                    ).lower()
                    or query_lower
                    in str(
                        message["body"]
                    ).lower()
                )
            ]

        if status:

            messages = [
                message
                for message in messages
                if message["status"] == status
            ]

        if priority:

            messages = [
                message
                for message in messages
                if message["priority"] == priority
            ]

        total = len(messages)

        start = (page - 1) * page_size
        end = start + page_size

        return {
            "items": [
                self._serialize(message)
                for message in messages[start:end]
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }


# ============================================================
# Global service instance
# ============================================================

messaging_service = MessagingService()