from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from app.services.auth import auth_service
from app.services.notifications import notification_service


class TwoPersonIntegrityService:
    """
    BE-011 — Two-Person Integrity

    Features:
    - Two-person approval
    - Different requester/approver
    - MFA verification
    - Configurable approval window (default 4 hours)
    - Expiry handling
    - Cancellation/rejection
    - Break-glass emergency path
    - Break-glass event/audit records
    - Compliance + Security Admin notifications
    """

    DEFAULT_APPROVAL_WINDOW_SECONDS = 4 * 60 * 60

    def __init__(self) -> None:
        self._operations: Dict[str, Dict[str, Any]] = {}

        # Break-glass audit/event records.
        self._break_glass_events: List[Dict[str, Any]] = []

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _expire_if_needed(
        self,
        operation: Dict[str, Any],
    ) -> None:

        if operation["status"] != "pending":
            return

        expires_at = operation.get("expires_at")

        if expires_at is None:
            return

        if self._now() >= expires_at:
            operation["status"] = "expired"

    # =========================================================
    # Create Operation
    # =========================================================

    def create_operation(
        self,
        *,
        operation_id: str,
        tenant_id: str,
        requested_by: str,
        operation_type: str,
        payload: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        approval_window_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:

        if operation_id in self._operations:
            raise ValueError("TPI operation already exists")

        if not operation_id:
            raise ValueError("operation_id is required")

        if not tenant_id:
            raise ValueError("tenant_id is required")

        if not requested_by:
            raise ValueError("requested_by is required")

        if not operation_type:
            raise ValueError("operation_type is required")

        window = (
            approval_window_seconds
            if approval_window_seconds is not None
            else self.DEFAULT_APPROVAL_WINDOW_SECONDS
        )

        if window <= 0:
            raise ValueError(
                "approval_window_seconds must be greater than zero"
            )

        now = self._now()
        expires_at = now + timedelta(seconds=window)

        operation = {
            "operation_id": operation_id,
            "tenant_id": tenant_id,
            "requested_by": requested_by,
            "operation_type": operation_type,
            "payload": payload or {},
            "reason": reason,
            "status": "pending",
            "created_at": now,
            "expires_at": expires_at,
            "approval_window_seconds": window,
            "approved_by": None,
            "approved_at": None,
            "mfa_verified": False,
        }

        self._operations[operation_id] = operation

        return dict(operation)

    # =========================================================
    # Get Operation
    # =========================================================

    def get_operation(
        self,
        *,
        operation_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:

        operation = self._operations.get(operation_id)

        if operation is None:
            return None

        if (
            tenant_id is not None
            and operation["tenant_id"] != tenant_id
        ):
            return None

        self._expire_if_needed(operation)

        return dict(operation)

    # =========================================================
    # Approve / Reject
    # =========================================================

    def approve_operation(
        self,
        *,
        operation_id: str,
        tenant_id: str,
        approved_by: str,
        approve: bool,
        reason: Optional[str] = None,
        approver_role: Optional[str] = None,
        mfa_otp: Optional[str] = None,
        mfa_source: str = "tpi",
    ) -> Dict[str, Any]:

        operation = self._operations.get(operation_id)

        if operation is None:
            raise KeyError("TPI operation not found")

        if operation["tenant_id"] != tenant_id:
            raise PermissionError(
                "Cross-tenant TPI access denied"
            )

        self._expire_if_needed(operation)

        if operation["status"] == "expired":
            raise ValueError(
                "TPI approval window has expired"
            )

        if operation["status"] != "pending":
            raise ValueError(
                "TPI operation is no longer pending"
            )

        if not approved_by:
            raise ValueError("approved_by is required")

        if operation["requested_by"] == approved_by:
            raise PermissionError(
                "Two-person integrity violation: "
                "requester cannot approve their own operation"
            )

        # -----------------------------------------------------
        # Reject
        # -----------------------------------------------------

        if not approve:
            now = self._now()

            operation["status"] = "rejected"
            operation["approved_by"] = approved_by
            operation["approved_at"] = now

            if reason:
                operation["reason"] = reason

            return dict(operation)

        # -----------------------------------------------------
        # Approval requires MFA
        # -----------------------------------------------------

        if not approver_role:
            raise PermissionError(
                "Approver role is required for TPI approval"
            )

        if not mfa_otp:
            raise PermissionError(
                "MFA verification is required for TPI approval"
            )

        mfa_result = auth_service.verify_mfa(
            approved_by,
            approver_role,
            mfa_otp,
            mfa_source,
        )

        if not mfa_result.get("verified", False):
            raise PermissionError(
                mfa_result.get(
                    "message",
                    "MFA verification failed",
                )
            )

        # Re-check expiry after MFA verification.
        if self._now() >= operation["expires_at"]:
            operation["status"] = "expired"

            raise ValueError(
                "TPI approval window has expired"
            )

        now = self._now()

        operation["status"] = "approved"
        operation["approved_by"] = approved_by
        operation["approved_at"] = now
        operation["mfa_verified"] = True

        if reason:
            operation["reason"] = reason

        return dict(operation)

    # =========================================================
    # Check Operation
    # =========================================================

    def check_operation(
        self,
        *,
        operation_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:

        operation = self._operations.get(operation_id)

        if operation is None:
            raise KeyError("TPI operation not found")

        if operation["tenant_id"] != tenant_id:
            raise PermissionError(
                "Cross-tenant TPI access denied"
            )

        self._expire_if_needed(operation)

        approved = (
            operation["status"] == "approved"
            and operation["approved_by"] is not None
            and operation["approved_by"]
            != operation["requested_by"]
            and operation.get("mfa_verified", False)
        )

        return {
            "operation_id": operation_id,
            "requires_two_person_integrity": True,
            "first_actor": operation["requested_by"],
            "second_actor": operation["approved_by"],
            "approved": approved,
            "mfa_verified": operation.get(
                "mfa_verified",
                False,
            ),
            "expires_at": operation.get(
                "expires_at"
            ),
            "status": operation["status"],
        }

    # =========================================================
    # Require Approval
    # =========================================================

    def require_approval(
        self,
        *,
        operation_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:

        result = self.check_operation(
            operation_id=operation_id,
            tenant_id=tenant_id,
        )

        if not result["approved"]:
            raise PermissionError(
                "TPI approval required before "
                "executing this operation"
            )

        return result

    # =========================================================
    # Cancel Operation
    # =========================================================

    def cancel_operation(
        self,
        *,
        operation_id: str,
        tenant_id: str,
        cancelled_by: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:

        operation = self._operations.get(operation_id)

        if operation is None:
            raise KeyError("TPI operation not found")

        if operation["tenant_id"] != tenant_id:
            raise PermissionError(
                "Cross-tenant TPI access denied"
            )

        self._expire_if_needed(operation)

        if operation["status"] != "pending":
            raise ValueError(
                "Only pending TPI operations can be cancelled"
            )

        now = self._now()

        operation["status"] = "cancelled"

        operation.setdefault(
            "metadata",
            {},
        )

        operation["metadata"]["cancelled_by"] = cancelled_by
        operation["metadata"]["cancelled_at"] = now

        if reason:
            operation["metadata"][
                "cancellation_reason"
            ] = reason

        return dict(operation)

    # =========================================================
    # BREAK-GLASS
    # =========================================================

    def break_glass_operation(
        self,
        *,
        operation_id: str,
        tenant_id: str,
        break_glass_by: str,
        reason: str,
        operation_type: Optional[str] = None,
    ) -> Dict[str, Any]:

        if not operation_id:
            raise ValueError("operation_id is required")

        if not tenant_id:
            raise ValueError("tenant_id is required")

        if not break_glass_by:
            raise ValueError(
                "break_glass_by is required"
            )

        if not reason or not reason.strip():
            raise ValueError(
                "Break-glass reason is required"
            )

        existing = self._operations.get(operation_id)

        if existing is not None:
            if existing["tenant_id"] != tenant_id:
                raise PermissionError(
                    "Cross-tenant TPI access denied"
                )

            if existing["status"] == "approved":
                raise ValueError(
                    "Operation is already approved"
                )

            existing["status"] = "break_glass"

            operation = existing

        else:
            now = self._now()

            operation = {
                "operation_id": operation_id,
                "tenant_id": tenant_id,
                "requested_by": break_glass_by,
                "operation_type": (
                    operation_type or "emergency"
                ),
                "payload": {},
                "reason": reason,
                "status": "break_glass",
                "created_at": now,
                "expires_at": None,
                "approval_window_seconds": None,
                "approved_by": None,
                "approved_at": None,
                "mfa_verified": False,
            }

            self._operations[operation_id] = operation

        now = self._now()

        # -----------------------------------------------------
        # Break-glass audit/event record
        # -----------------------------------------------------

        event = {
            "event_type": "tpi_break_glass",
            "operation_id": operation_id,
            "tenant_id": tenant_id,
            "actor": break_glass_by,
            "reason": reason.strip(),
            "timestamp": now,
            "status": "executed",
            "compliance_notified": False,
            "security_admin_notified": False,
        }

        # -----------------------------------------------------
        # Notify Compliance Officer
        # -----------------------------------------------------

        compliance_notification_id = (
            f"tpi-break-glass-compliance-{operation_id}"
        )

        try:
            notification_service.create_notification(
                notification_id=(
                    compliance_notification_id
                ),
                tenant_id=tenant_id,
                title="TPI Break-Glass Alert",
                body=(
                    f"Emergency TPI break-glass operation "
                    f"{operation_id} was executed by "
                    f"{break_glass_by}. "
                    f"Reason: {reason.strip()}"
                ),
                created_by=break_glass_by,
                recipients=[
                    {
                        "recipient_id": "compliance-officer",
                        "tenant_id": tenant_id,
                        "channel": "in_app",
                    }
                ],
                priority="critical",
                metadata={
                    "event_type": "tpi_break_glass",
                    "operation_id": operation_id,
                    "actor": break_glass_by,
                },
            )

            event["compliance_notified"] = True

        except Exception as exc:
            event["compliance_notification_error"] = str(
                exc
            )

        # -----------------------------------------------------
        # Notify Security Administrator
        # -----------------------------------------------------

        security_notification_id = (
            f"tpi-break-glass-security-{operation_id}"
        )

        try:
            notification_service.create_notification(
                notification_id=(
                    security_notification_id
                ),
                tenant_id=tenant_id,
                title="TPI Break-Glass Security Alert",
                body=(
                    f"Emergency TPI break-glass operation "
                    f"{operation_id} was executed by "
                    f"{break_glass_by}. "
                    f"Reason: {reason.strip()}"
                ),
                created_by=break_glass_by,
                recipients=[
                    {
                        "recipient_id": "security-admin",
                        "tenant_id": tenant_id,
                        "channel": "in_app",
                    }
                ],
                priority="critical",
                metadata={
                    "event_type": "tpi_break_glass",
                    "operation_id": operation_id,
                    "actor": break_glass_by,
                },
            )

            event["security_admin_notified"] = True

        except Exception as exc:
            event["security_notification_error"] = str(
                exc
            )

        self._break_glass_events.append(event)

        operation.setdefault(
            "metadata",
            {},
        )

        operation["metadata"][
            "break_glass"
        ] = True

        operation["metadata"][
            "break_glass_by"
        ] = break_glass_by

        operation["metadata"][
            "break_glass_at"
        ] = now

        operation["metadata"][
            "break_glass_reason"
        ] = reason.strip()

        operation["metadata"][
            "compliance_notified"
        ] = event["compliance_notified"]

        operation["metadata"][
            "security_admin_notified"
        ] = event["security_admin_notified"]

        return {
            "success": True,
            "operation": dict(operation),
            "break_glass_event": dict(event),
        }

    # =========================================================
    # Break-Glass Event History
    # =========================================================

    def list_break_glass_events(
        self,
        *,
        tenant_id: str,
    ) -> List[Dict[str, Any]]:

        return [
            dict(event)
            for event in self._break_glass_events
            if event["tenant_id"] == tenant_id
        ]

    # =========================================================
    # List Operations
    # =========================================================

    def list_operations(
        self,
        *,
        tenant_id: str,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:

        operations = []

        for operation in self._operations.values():

            if operation["tenant_id"] != tenant_id:
                continue

            self._expire_if_needed(operation)

            if status is not None:
                if operation["status"] != status:
                    continue

            operations.append(dict(operation))

        return operations

    # =========================================================
    # Statistics
    # =========================================================

    def statistics(
        self,
        *,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, int]:

        operations = list(
            self._operations.values()
        )

        if tenant_id is not None:
            operations = [
                operation
                for operation in operations
                if operation["tenant_id"] == tenant_id
            ]

        for operation in operations:
            self._expire_if_needed(operation)

        result = {
            "total": len(operations),
            "pending": 0,
            "approved": 0,
            "rejected": 0,
            "cancelled": 0,
            "expired": 0,
            "break_glass": 0,
        }

        for operation in operations:

            status = operation.get(
                "status",
                "pending",
            )

            if status in result:
                result[status] += 1

        return result


# ============================================================
# Global service instance
# ============================================================

tpi_service = TwoPersonIntegrityService()