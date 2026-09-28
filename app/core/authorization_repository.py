from __future__ import annotations

from typing import Any

from app.core.database import get_db_connection


class AuthorizationRepository:
    """PostgreSQL persistence layer for authorization identities and grants."""

    def load_identities(self) -> dict[str, dict[str, Any]]:
        """Load all persisted identities from PostgreSQL."""
        with get_db_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    subject_id,
                    tenant_id,
                    branch_id,
                    role,
                    active,
                    parent_id
                FROM authorization_state.identities
                """
            ).fetchall()

        return {
            row[0]: {
                "subject_id": row[0],
                "tenant_id": row[1],
                "branch_id": row[2],
                "role": row[3],
                "active": row[4],
                "parent_id": row[5],
            }
            for row in rows
        }

    def save_identity(self, identity: dict[str, Any]) -> None:
        """Create or update one authorization identity."""
        with get_db_connection() as connection:
            connection.execute(
                """
                INSERT INTO authorization_state.identities
                (
                    subject_id,
                    tenant_id,
                    branch_id,
                    role,
                    active,
                    parent_id
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (subject_id)
                DO UPDATE SET
                    tenant_id = EXCLUDED.tenant_id,
                    branch_id = EXCLUDED.branch_id,
                    role = EXCLUDED.role,
                    active = EXCLUDED.active,
                    parent_id = EXCLUDED.parent_id,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    identity["subject_id"],
                    identity["tenant_id"],
                    identity["branch_id"],
                    identity["role"],
                    identity["active"],
                    identity["parent_id"],
                ),
            )
            connection.commit()

    def delete_identity(self, subject_id: str) -> None:
        """Delete one persisted authorization identity."""
        with get_db_connection() as connection:
            connection.execute(
                """
                DELETE FROM authorization_state.identities
                WHERE subject_id = %s
                """,
                (subject_id,),
            )
            connection.commit()

    def load_grants(self) -> dict[tuple[str, str, str, str, str, str | None], dict[str, Any]]:
        """Load all persisted authorization grants."""
        with get_db_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    subject_id,
                    tenant_id,
                    resource_type,
                    resource_id,
                    action,
                    branch_id
                FROM authorization_state.grants
                """
            ).fetchall()

        return {
            (
                row[0],
                row[1],
                row[2],
                row[3],
                row[4],
                row[5],
            ): {
                "subject_id": row[0],
                "tenant_id": row[1],
                "resource_type": row[2],
                "resource_id": row[3],
                "action": row[4],
                "branch_id": row[5],
            }
            for row in rows
        }

    def save_grant(self, grant: dict[str, Any]) -> None:
        """Persist one authorization grant."""
        with get_db_connection() as connection:
            connection.execute(
                """
                INSERT INTO authorization_state.grants
                (
                    subject_id,
                    tenant_id,
                    resource_type,
                    resource_id,
                    action,
                    branch_id
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    grant["subject_id"],
                    grant["tenant_id"],
                    grant["resource_type"],
                    grant["resource_id"],
                    grant["action"],
                    grant["branch_id"],
                ),
            )
            connection.commit()

    def delete_grant(
        self,
        subject_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        branch_id: str | None,
    ) -> None:
        """Delete one persisted authorization grant."""
        with get_db_connection() as connection:
            connection.execute(
                """
                DELETE FROM authorization_state.grants
                WHERE subject_id = %s
                  AND tenant_id = %s
                  AND resource_type = %s
                  AND resource_id = %s
                  AND action = %s
                  AND branch_id IS NOT DISTINCT FROM %s
                """,
                (
                    subject_id,
                    tenant_id,
                    resource_type,
                    resource_id,
                    action,
                    branch_id,
                ),
            )
            connection.commit()

    def clear(self) -> None:
        """Remove all persisted authorization state."""
        with get_db_connection() as connection:
            connection.execute("DELETE FROM authorization_state.grants")
            connection.execute("DELETE FROM authorization_state.identities")
            connection.commit()