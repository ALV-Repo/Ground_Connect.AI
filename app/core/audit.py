from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


AUDIT_DATA_DIR = Path(".audit_data")
AUDIT_FILE = AUDIT_DATA_DIR / "authorization_decisions.jsonl"

# Never store these fields in audit records.
SENSITIVE_FIELDS = {
    "password",
    "otp",
    "token",
    "access_token",
    "refresh_token",
    "secret",
    "api_key",
    "message_content",
    "phone_number",
    "email",
    "citizen_data",
}


@dataclass
class AuthorizationDecisionRecord:
    """
    ADR - Authorization Decision Record.

    Stores the decision metadata required for auditing without
    storing sensitive request/message content.
    """

    record_id: str
    timestamp: float

    subject_id: str
    action: str
    resource_type: str
    resource_id: str

    decision: str
    reason: str

    rules_evaluated: list[str]
    failing_rule: str | None

    tenant_id: str | None = None
    branch_id: str | None = None

    correlation_id: str | None = None

    source: str | None = None


class AuditService:
    """
    BE-004 Authorization Decision Record service.

    Responsibilities:
    - Record allow/deny authorization decisions.
    - Keep records structured.
    - Avoid sensitive information.
    - Provide admin query methods.
    - Support basic persistent JSONL storage.
    """

    def __init__(
        self,
        audit_file: Path = AUDIT_FILE,
        max_records: int = 10000,
    ):
        self.audit_file = audit_file
        self.max_records = max_records

        self._records: list[AuthorizationDecisionRecord] = []

        self.audit_file.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._load_records()

    # =========================================================
    # Record Authorization Decision
    # =========================================================

    def record_decision(
        self,
        *,
        subject_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        allowed: bool,
        reason: str,
        rules_evaluated: list[str] | None = None,
        failing_rule: str | None = None,
        tenant_id: str | None = None,
        branch_id: str | None = None,
        correlation_id: str | None = None,
        source: str | None = None,
    ) -> dict[str, Any]:
        """
        Create and persist an ADR record.
        """

        record = AuthorizationDecisionRecord(
            record_id=str(uuid.uuid4()),
            timestamp=time.time(),
            subject_id=self._safe_string(subject_id),
            action=self._safe_string(action).upper(),
            resource_type=self._safe_string(resource_type),
            resource_id=self._safe_string(resource_id),
            decision="ALLOW" if allowed else "DENY",
            reason=self._safe_string(reason),
            rules_evaluated=[
                self._safe_string(rule)
                for rule in (rules_evaluated or [])
            ],
            failing_rule=(
                self._safe_string(failing_rule)
                if failing_rule
                else None
            ),
            tenant_id=(
                self._safe_string(tenant_id)
                if tenant_id
                else None
            ),
            branch_id=(
                self._safe_string(branch_id)
                if branch_id
                else None
            ),
            correlation_id=(
                self._safe_string(correlation_id)
                if correlation_id
                else None
            ),
            source=(
                self._safe_string(source)
                if source
                else None
            ),
        )

        self._records.append(record)

        # Keep memory bounded.
        if len(self._records) > self.max_records:
            self._records = self._records[-self.max_records :]

        self._append_to_file(record)

        return self._record_to_dict(record)

    # =========================================================
    # Persistence
    # =========================================================

    def _append_to_file(
        self,
        record: AuthorizationDecisionRecord,
    ) -> None:
        """
        Append one structured ADR record as JSON Lines.
        """

        data = self._record_to_dict(record)

        with self.audit_file.open(
            "a",
            encoding="utf-8",
        ) as file:
            file.write(
                json.dumps(
                    data,
                    ensure_ascii=False,
                )
                + "\n"
            )

    def _load_records(self) -> None:
        """
        Load existing ADR records from disk.

        Invalid lines are ignored rather than preventing the
        application from starting.
        """

        if not self.audit_file.exists():
            return

        try:
            with self.audit_file.open(
                "r",
                encoding="utf-8",
            ) as file:

                for line in file:
                    line = line.strip()

                    if not line:
                        continue

                    try:
                        data = json.loads(line)

                        record = AuthorizationDecisionRecord(
                            record_id=str(data["record_id"]),
                            timestamp=float(data["timestamp"]),
                            subject_id=str(data["subject_id"]),
                            action=str(data["action"]),
                            resource_type=str(data["resource_type"]),
                            resource_id=str(data["resource_id"]),
                            decision=str(data["decision"]),
                            reason=str(data["reason"]),
                            rules_evaluated=list(
                                data.get("rules_evaluated", [])
                            ),
                            failing_rule=data.get("failing_rule"),
                            tenant_id=data.get("tenant_id"),
                            branch_id=data.get("branch_id"),
                            correlation_id=data.get(
                                "correlation_id"
                            ),
                            source=data.get("source"),
                        )

                        self._records.append(record)

                    except (
                        KeyError,
                        TypeError,
                        ValueError,
                        json.JSONDecodeError,
                    ):
                        continue

        except OSError:
            # Application should still start if audit storage
            # temporarily cannot be read.
            return

        if len(self._records) > self.max_records:
            self._records = self._records[-self.max_records :]

    # =========================================================
    # Query APIs
    # =========================================================

    def get_record(
        self,
        record_id: str,
    ) -> dict[str, Any] | None:
        """
        Get a single ADR record.
        """

        for record in self._records:
            if record.record_id == record_id:
                return self._record_to_dict(record)

        return None

    def list_records(
        self,
        *,
        subject_id: str | None = None,
        action: str | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        decision: str | None = None,
        tenant_id: str | None = None,
        branch_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Query ADR records.

        All supplied filters are combined using AND logic.
        """

        limit = max(1, min(limit, self.max_records))

        normalized_action = (
            action.upper()
            if action
            else None
        )

        normalized_decision = (
            decision.upper()
            if decision
            else None
        )

        results: list[dict[str, Any]] = []

        # Newest records first.
        for record in reversed(self._records):

            if (
                subject_id is not None
                and record.subject_id != subject_id
            ):
                continue

            if (
                normalized_action is not None
                and record.action != normalized_action
            ):
                continue

            if (
                resource_type is not None
                and record.resource_type != resource_type
            ):
                continue

            if (
                resource_id is not None
                and record.resource_id != resource_id
            ):
                continue

            if (
                normalized_decision is not None
                and record.decision != normalized_decision
            ):
                continue

            if (
                tenant_id is not None
                and record.tenant_id != tenant_id
            ):
                continue

            if (
                branch_id is not None
                and record.branch_id != branch_id
            ):
                continue

            results.append(
                self._record_to_dict(record)
            )

            if len(results) >= limit:
                break

        return results

    # =========================================================
    # Admin Query Helpers
    # =========================================================

    def who_can_access(
        self,
        *,
        resource_type: str,
        resource_id: str,
        action: str = "READ",
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> list[str]:
        """
        Return subjects that have an observed ALLOW decision
        for a particular resource/action.

        This is an audit-based query; it is not a replacement
        for the live authorization engine.
        """

        records = self.list_records(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            decision="ALLOW",
            tenant_id=tenant_id,
            limit=limit,
        )

        subjects: list[str] = []

        for record in records:
            subject_id = record["subject_id"]

            if subject_id not in subjects:
                subjects.append(subject_id)

        return subjects

    def what_can_access(
        self,
        *,
        subject_id: str,
        decision: str = "ALLOW",
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Return resources for which a subject has an observed
        authorization decision.
        """

        return self.list_records(
            subject_id=subject_id,
            decision=decision,
            limit=limit,
        )

    # =========================================================
    # Security Event Query
    # =========================================================

    def list_denials(
        self,
        *,
        subject_id: str | None = None,
        tenant_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Convenience method for security/admin review of
        authorization denials.
        """

        return self.list_records(
            subject_id=subject_id,
            tenant_id=tenant_id,
            decision="DENY",
            limit=limit,
        )

    # =========================================================
    # Utility
    # =========================================================

    def count(self) -> int:
        return len(self._records)

    def clear_memory(self) -> None:
        """
        Clear in-memory records.

        Does not delete the persistent audit file.
        """

        self._records.clear()

    def clear_storage(self) -> None:
        """
        Clear both in-memory and persistent audit records.

        Intended for tests/development only.
        """

        self._records.clear()

        try:
            if self.audit_file.exists():
                self.audit_file.unlink()
        except OSError:
            pass

    # =========================================================
    # Internal Helpers
    # =========================================================

    @staticmethod
    def _safe_string(value: Any) -> str:
        """
        Convert a value to a safe string.

        Prevents accidental object serialization.
        """

        text = str(value)

        lowered = text.lower()

        for field_name in SENSITIVE_FIELDS:
            if field_name in lowered:
                return "[REDACTED]"

        return text

    @staticmethod
    def _record_to_dict(
        record: AuthorizationDecisionRecord,
    ) -> dict[str, Any]:
        return asdict(record)


# Global audit service instance.
audit_service = AuditService()