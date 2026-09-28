from __future__ import annotations

import json
from typing import Any

from app.core.database import get_db_connection


class AuditRepository:
    """PostgreSQL persistence layer for authorization audit decisions."""

    def save_record(self, record: dict[str, Any]) -> None:
        """Insert or update one audit decision record."""
        with get_db_connection() as connection:
            connection.execute(
                """
                INSERT INTO audit_state.authorization_decisions
                (
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
                    record["decision"],
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
        """Load one audit record by ID."""
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
        """Query audit records using optional filters."""
        conditions: list[str] = []
        parameters: list[Any] = []

        if subject_id is not None:
            conditions.append("subject_id = %s")
            parameters.append(subject_id)

        if action is not None:
            conditions.append("action = %s")
            parameters.append(action)

        if resource_type is not None:
            conditions.append("resource_type = %s")
            parameters.append(resource_type)

        if resource_id is not None:
            conditions.append("resource_id = %s")
            parameters.append(resource_id)

        if decision is not None:
            conditions.append("decision = %s")
            parameters.append(decision)

        if tenant_id is not None:
            conditions.append("tenant_id = %s")
            parameters.append(tenant_id)

        if branch_id is not None:
            conditions.append("branch_id = %s")
            parameters.append(branch_id)

        where_clause = ""

        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)

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

        return [
            self._row_to_record(row)
            for row in rows
        ]

    def clear(self) -> None:
        """Delete all audit records. Intended for tests/development."""
        with get_db_connection() as connection:
            connection.execute(
                "DELETE FROM audit_state.authorization_decisions"
            )
            connection.commit()

    @staticmethod
    def _row_to_record(row: Any) -> dict[str, Any]:
        """Convert a PostgreSQL row into an audit record."""
        return {
            "record_id": row[0],
            "timestamp": float(row[1]),
            "subject_id": row[2],
            "action": row[3],
            "resource_type": row[4],
            "resource_id": row[5],
            "decision": row[6],
            "reason": row[7],
            "rules_evaluated": row[8] or [],
            "failing_rule": row[9],
            "tenant_id": row[10],
            "branch_id": row[11],
            "correlation_id": row[12],
            "source": row[13],
        }