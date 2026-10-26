
from __future__ import annotations

import json
from typing import Any

from app.core.database import get_db_connection


class AuditRepository:
    """PostgreSQL persistence layer for authorization audit decisions."""

    def save_record(self, record: dict[str, Any]) -> None:
        """Insert or update one audit decision record."""

        required_fields = (
            "record_id",
            "timestamp",
            "subject_id",
            "action",
            "resource_type",
            "resource_id",
            "decision",
            "reason",
            "rules_evaluated",
            "failing_rule",
            "tenant_id",
            "branch_id",
            "correlation_id",
            "source",
        )

        missing_fields = [
            field for field in required_fields if field not in record
        ]
        if missing_fields:
            raise ValueError(
                f"Missing audit record fields: {', '.join(missing_fields)}"
            )

        decision = record["decision"]
        if decision not in ("ALLOW", "DENY"):
            raise ValueError("decision must be 'ALLOW' or 'DENY'")

        with get_db_connection() as connection:
            connection.execute(
                """
                INSERT INTO audit_state.authorization_decisions (
                    record_id,
                    timestamp,
                    subject_id,
                    action,
                    resource_type,
                    resource_id,
                    decision,
                    reason,
                    rules_evaluated,
                    failing_rule,
                    tenant_id,
                    branch_id,
                    correlation_id,
                    source
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s, %s, %s, %s, %s
                )
                ON CONFLICT (record_id)
                DO UPDATE SET
                    timestamp = EXCLUDED.timestamp,
                    subject_id = EXCLUDED.subject_id,
                    action = EXCLUDED.action,
                    resource_type = EXCLUDED.resource_type,
                    resource_id = EXCLUDED.resource_id,
                    decision = EXCLUDED.decision,
                    reason = EXCLUDED.reason,
                    rules_evaluated = EXCLUDED.rules_evaluated,
                    failing_rule = EXCLUDED.failing_rule,
                    tenant_id = EXCLUDED.tenant_id,
                    branch_id = EXCLUDED.branch_id,
                    correlation_id = EXCLUDED.correlation_id,
                    source = EXCLUDED.source
                """,
                (
                    record["record_id"],
                    record["timestamp"],
                    record["subject_id"],
                    record["action"],
                    record["resource_type"],
                    record["resource_id"],
                    decision,
                    record["reason"],
                    json.dumps(record["rules_evaluated"]),
                    record["failing_rule"],
                    record["tenant_id"],
                    record["branch_id"],
                    record["correlation_id"],
                    record["source"],
                ),
            )
            connection.commit()

    def get_record(self, record_id: str) -> dict[str, Any] | None:
        """Load one audit decision by its ID."""

        with get_db_connection() as connection:
            row = connection.execute(
                """
                SELECT
                    record_id,
                    timestamp,
                    subject_id,
                    action,
                    resource_type,
                    resource_id,
                    decision,
                    reason,
                    rules_evaluated,
                    failing_rule,
                    tenant_id,
                    branch_id,
                    correlation_id,
                    source
                FROM audit_state.authorization_decisions
                WHERE record_id = %s
                """,
                (record_id,),
            ).fetchone()

        return self._row_to_record(row) if row else None

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
        """List audit records using optional filters."""

        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000")

        if decision is not None and decision not in ("ALLOW", "DENY"):
            raise ValueError("decision must be 'ALLOW' or 'DENY'")

        filters = {
            "subject_id": subject_id,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "decision": decision,
            "tenant_id": tenant_id,
            "branch_id": branch_id,
        }

        conditions: list[str] = []
        parameters: list[Any] = []

        for column, value in filters.items():
            if value is not None:
                conditions.append(f"{column} = %s")
                parameters.append(value)

        where_clause = (
            "WHERE " + " AND ".join(conditions) if conditions else ""
        )

        query = f"""
            SELECT
                record_id,
                timestamp,
                subject_id,
                action,
                resource_type,
                resource_id,
                decision,
                reason,
                rules_evaluated,
                failing_rule,
                tenant_id,
                branch_id,
                correlation_id,
                source
            FROM audit_state.authorization_decisions
            {where_clause}
            ORDER BY timestamp DESC
            LIMIT %s
        """

        parameters.append(limit)

        with get_db_connection() as connection:
            rows = connection.execute(query, parameters).fetchall()

        return [self._row_to_record(row) for row in rows]

    def clear(self, *, allow_test_cleanup: bool = False) -> None:
        """
        Clear audit records only when explicitly enabled for test cleanup.

        Do not use this method against production audit data.
        """
        if not allow_test_cleanup:
            raise PermissionError(
                "Audit deletion is disabled. "
                "Use a dedicated test database for test cleanup."
            )

        with get_db_connection() as connection:
            connection.execute(
                "DELETE FROM audit_state.authorization_decisions"
            )
            connection.commit()

    @staticmethod
    def _row_to_record(row: Any) -> dict[str, Any]:
        """Convert a PostgreSQL row into an audit record."""

        rules_evaluated = row[8]
        if isinstance(rules_evaluated, str):
            rules_evaluated = json.loads(rules_evaluated)

        return {
            "record_id": row[0],
            "timestamp": float(row[1]),
            "subject_id": row[2],
            "action": row[3],
            "resource_type": row[4],
            "resource_id": row[5],
            "decision": row[6],
            "reason": row[7],
            "rules_evaluated": rules_evaluated or [],
            "failing_rule": row[9],
            "tenant_id": row[10],
            "branch_id": row[11],
            "correlation_id": row[12],
            "source": row[13],
        }
