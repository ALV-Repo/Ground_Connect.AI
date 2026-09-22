from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.core.audit import (
    AuditService,
    audit_service,
)


class AuditServiceLayer:
    """
    Service layer for BE-004 Authorization Decision Records.

    Keeps API/business logic separate from the underlying
    audit persistence implementation.
    """

    def __init__(
        self,
        service: Optional[AuditService] = None,
    ) -> None:
        self.service = service or audit_service

    # =========================================================
    # Record Authorization Decision
    # =========================================================

    def record_authorization_decision(
        self,
        *,
        subject_id: str,
        tenant_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        allowed: bool,
        reason: str,
        rules_evaluated: Optional[List[str]] = None,
        failing_rule: Optional[str] = None,
        branch_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Store an authorization decision in the audit log.
        """

        return self.service.record_decision(
            subject_id=subject_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            allowed=allowed,
            reason=reason,
            rules_evaluated=rules_evaluated or [],
            failing_rule=failing_rule,
            tenant_id=tenant_id,
            branch_id=branch_id,
            correlation_id=correlation_id,
            source=source,
        )

    # =========================================================
    # Query Records
    # =========================================================

    def query(
        self,
        *,
        subject_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        branch_id: Optional[str] = None,
        decision: Optional[bool] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Query authorization decision records.

        API boolean decision:
            True  -> ALLOW
            False -> DENY
        """

        decision_value: Optional[str] = None

        if decision is True:
            decision_value = "ALLOW"
        elif decision is False:
            decision_value = "DENY"

        return self.service.list_records(
            subject_id=subject_id,
            tenant_id=tenant_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            branch_id=branch_id,
            decision=decision_value,
            limit=limit,
        )

    # =========================================================
    # Who Can Access
    # =========================================================

    def who_can_access(
        self,
        *,
        resource_type: str,
        resource_id: str,
        action: str,
        tenant_id: str,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Return subjects that have an observed ALLOW decision
        for a specific resource/action.
        """

        subjects = self.service.who_can_access(
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            tenant_id=tenant_id,
            limit=limit,
        )

        return {
            "records": [
                {
                    "subject_id": subject_id
                }
                for subject_id in subjects
            ],
            "count": len(subjects),
        }

    # =========================================================
    # What Can Access
    # =========================================================

    def what_can_access(
        self,
        *,
        subject_id: str,
        decision: Optional[bool] = None,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Return resources/actions associated with a subject.
        """

        decision_value = "ALLOW"

        if decision is False:
            decision_value = "DENY"

        records = self.service.what_can_access(
            subject_id=subject_id,
            decision=decision_value,
            limit=limit,
        )

        return {
            "records": records,
            "count": len(records),
        }

    # =========================================================
    # Denials
    # =========================================================

    def list_denials(
        self,
        *,
        subject_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Return denied authorization decisions.
        """

        return self.service.list_denials(
            subject_id=subject_id,
            tenant_id=tenant_id,
            limit=limit,
        )

    # =========================================================
    # Export
    # =========================================================

    def export_records(
        self,
        *,
        tenant_id: Optional[str] = None,
        limit: int = 10_000,
    ) -> List[Dict[str, Any]]:
        """
        Export authorization decision records.
        """

        return self.query(
            tenant_id=tenant_id,
            limit=limit,
        )


# =============================================================
# Global service instance
# =============================================================

audit_service_layer = AuditServiceLayer()