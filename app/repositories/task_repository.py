from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4
from contextlib import nullcontext

from psycopg.types.json import Jsonb

from app.core.database import get_db_connection


class TaskRepository:
    """PostgreSQL persistence for tasks."""

    @staticmethod
    def _resolve_organization(connection, tenant_id: str) -> UUID:
        row = connection.execute(
            """
            SELECT id
            FROM tenant_and_configuration.tenants
            WHERE id::text = %(tenant_id)s OR slug = %(tenant_id)s
            LIMIT 1
            """,
            {"tenant_id": tenant_id},
        ).fetchone()

        if row is None:
            raise ValueError(
                f"Tenant '{tenant_id}' does not exist in the database."
            )

        return row[0]

    def create_task(
        self,
        *,
        tenant_id: str,
        title: str,
        creator_id: UUID,
        creator_assignment_id: UUID,
        task_id: UUID | None = None,
        assignee_id: UUID,
        assignee_node_id: UUID,
        description: str | None = None,
        priority: str = "Medium",
        status: str = "Assigned",
        deadline=None,
        parent_task_id: UUID | None = None,
        escalation_rule: dict[str, Any] | None = None,
        response_requirement: str | None = None,
        connection=None,
    ) -> dict[str, Any]:
        if not title.strip():
            raise ValueError("Task title is required.")

        if priority not in {"High", "Medium", "Low"}:
            raise ValueError("Priority must be High, Medium or Low.")

        if status not in {
            "Assigned",
            "Accepted",
            "In_Progress",
            "Blocked",
            "Completed",
            "Rejected",
            "Overdue",
        }:
            raise ValueError("Unsupported database task status.")

        owns_connection = connection is None
        connection_context = (
            get_db_connection() if owns_connection
            else nullcontext(connection)
        )
        with connection_context as connection:
            transaction_context = (
                connection.transaction()
                if owns_connection
                else nullcontext()
            )
            with transaction_context:
                organization_id = self._resolve_organization(
                    connection, tenant_id
                )

                cursor = connection.execute(
                    """
                    INSERT INTO tasks_field_reports.tasks (
                        id,
                        organization_id,
                        title,
                        description,
                        creator_id,
                        creator_assignment_id,
                        assignee_id,
                        assignee_node_id,
                        parent_task_id,
                        priority,
                        status,
                        deadline,
                        escalation_rule,
                        response_requirement
                    )
                    VALUES (
                        COALESCE(%(task_id)s, gen_random_uuid()),
                        %(organization_id)s,
                        %(title)s,
                        %(description)s,
                        %(creator_id)s,
                        %(creator_assignment_id)s,
                        %(assignee_id)s,
                        %(assignee_node_id)s,
                        %(parent_task_id)s,
                        %(priority)s,
                        %(status)s,
                        %(deadline)s,
                        %(escalation_rule)s,
                        %(response_requirement)s
                    )
                    RETURNING *
                    """,
                    {
                        "task_id": task_id,
                        "organization_id": organization_id,
                        "title": title.strip(),
                        "description": description,
                        "creator_id": creator_id,
                        "creator_assignment_id": creator_assignment_id,
                        "assignee_id": assignee_id,
                        "assignee_node_id": assignee_node_id,
                        "parent_task_id": parent_task_id,
                        "priority": priority,
                        "status": status,
                        "deadline": deadline,
                        "escalation_rule": (
                            Jsonb(escalation_rule)
                            if escalation_rule is not None
                            else None
                        ),
                        "response_requirement": response_requirement,
                    },
                )

                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError("Task creation failed.")

                columns = [item.name for item in cursor.description]
                return dict(zip(columns, row))

    def get_task(
        self,
        *,
        task_id: UUID,
        tenant_id: str,
        connection=None,
    ) -> dict[str, Any] | None:
        connection_context = (
            nullcontext(connection)
            if connection is not None
            else get_db_connection()
        )
        with connection_context as connection:
            organization_id = self._resolve_organization(
                connection, tenant_id
            )

            cursor = connection.execute(
                """
                SELECT *
                FROM tasks_field_reports.tasks
                WHERE id = %s AND organization_id = %s
                """,
                (task_id, organization_id),
            )

            row = cursor.fetchone()
            if row is None:
                return None

            columns = [item.name for item in cursor.description]
            return dict(zip(columns, row))


    def update_task(
        self,
        *,
        task_id: UUID,
        tenant_id: str,
        title: str | None = None,
        description: str | None = None,
        priority: str | None = None,
        status: str | None = None,
        deadline=None,
        update_deadline: bool = False,
        connection=None,
    ) -> dict[str, Any] | None:
        """Update supported fields on a tenant-scoped task."""
        if title is not None and not title.strip():
            raise ValueError("Task title cannot be empty.")

        if priority is not None and priority not in {"High", "Medium", "Low"}:
            raise ValueError("Priority must be High, Medium or Low.")

        allowed_statuses = {
            "Assigned", "Accepted", "In_Progress", "Blocked",
            "Completed", "Rejected", "Overdue",
        }
        if status is not None and status not in allowed_statuses:
            raise ValueError("Unsupported database task status.")

        values: dict[str, Any] = {}
        if title is not None:
            values["title"] = title.strip()
        if description is not None:
            values["description"] = description
        if priority is not None:
            values["priority"] = priority
        if status is not None:
            values["status"] = status
        if update_deadline:
            values["deadline"] = deadline

        if connection is None:
            with get_db_connection() as db_connection:
                with db_connection.transaction():
                    return self.update_task(
                        task_id=task_id,
                        tenant_id=tenant_id,
                        title=title,
                        description=description,
                        priority=priority,
                        status=status,
                        deadline=deadline,
                        update_deadline=update_deadline,
                        connection=db_connection,
                    )

        organization_id = self._resolve_organization(connection, tenant_id)

        if not values:
            return self.get_task(
                task_id=task_id,
                tenant_id=tenant_id,
                connection=connection,
            )

        assignments = [
            f"{column} = %({column})s"
            for column in values
        ]
        assignments.append("updated_at = NOW()")
        values["task_id"] = task_id
        values["organization_id"] = organization_id

        cursor = connection.execute(
            f"""
            UPDATE tasks_field_reports.tasks
            SET {", ".join(assignments)}
            WHERE id = %(task_id)s
              AND organization_id = %(organization_id)s
            RETURNING *
            """,
            values,
        )

        row = cursor.fetchone()
        if row is None:
            return None

        columns = [item.name for item in cursor.description]
        return dict(zip(columns, row))


    def search_tasks(
        self,
        *,
        tenant_id: str,
        query: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        assignee_id: UUID | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Search tasks within a tenant with filtering and pagination."""
        if page < 1:
            raise ValueError("page must be at least 1.")
        if not 1 <= page_size <= 500:
            raise ValueError("page_size must be between 1 and 500.")

        status_map = {
            "pending": ["Assigned", "Accepted"],
            "in_progress": ["In_Progress", "Blocked"],
            "completed": ["Completed"],
            "cancelled": ["Rejected"],
            "overdue": ["Overdue"],
        }
        priority_map = {
            "low": "Low",
            "normal": "Medium",
            "high": "High",
        }

        if status is not None and status not in status_map:
            raise ValueError("Unsupported task status filter.")
        if priority is not None and priority not in priority_map:
            raise ValueError("Unsupported task priority filter.")

        with get_db_connection() as connection:
            organization_id = self._resolve_organization(
                connection, tenant_id
            )

            where = ["organization_id = %(organization_id)s"]
            params: dict[str, Any] = {
                "organization_id": organization_id,
                "limit": page_size,
                "offset": (page - 1) * page_size,
            }

            if query:
                where.append(
                    "(title ILIKE %(query)s OR description ILIKE %(query)s)"
                )
                params["query"] = f"%{query}%"

            if status is not None:
                where.append("status = ANY(%(statuses)s)")
                params["statuses"] = status_map[status]

            if priority is not None:
                where.append("priority = %(priority)s")
                params["priority"] = priority_map[priority]

            if assignee_id is not None:
                where.append("assignee_id = %(assignee_id)s")
                params["assignee_id"] = assignee_id

            where_sql = " AND ".join(where)

            total = connection.execute(
                f"""
                SELECT COUNT(*)
                FROM tasks_field_reports.tasks
                WHERE {where_sql}
                """,
                params,
            ).fetchone()[0]

            cursor = connection.execute(
                f"""
                SELECT *
                FROM tasks_field_reports.tasks
                WHERE {where_sql}
                ORDER BY created_at DESC, id
                LIMIT %(limit)s OFFSET %(offset)s
                """,
                params,
            )

            columns = [item.name for item in cursor.description]
            rows = [
                dict(zip(columns, row))
                for row in cursor.fetchall()
            ]

            return {
                "items": rows,
                "total": total,
                "page": page,
                "page_size": page_size,
            }


    def task_action(
        self,
        *,
        task_id: UUID,
        tenant_id: str,
        action: str,
        requested_by: UUID,
        reason: str | None = None,
        connection=None,
    ) -> dict[str, Any]:
        """Persist a supported task lifecycle action and its history."""
        action = action.strip().lower()
        transitions = {
            "start": ("In_Progress", {"Assigned", "Accepted", "In_Progress"}),
            "complete": ("Completed", {"Assigned", "Accepted", "In_Progress", "Blocked"}),
            "cancel": ("Rejected", {"Assigned", "Accepted", "In_Progress", "Blocked"}),
            "reopen": ("Assigned", {"Completed", "Rejected"}),
        }

        if action in {"assign", "unassign"}:
            raise ValueError(
                "Assign and unassign are not supported in PostgreSQL mode "
                "because tasks.assignee_id and tasks.assignee_node_id are required."
            )
        if action not in transitions:
            raise ValueError("Unsupported task action.")

        if connection is None:
            with get_db_connection() as db_connection:
                with db_connection.transaction():
                    return self.task_action(
                        task_id=task_id,
                        tenant_id=tenant_id,
                        action=action,
                        requested_by=requested_by,
                        reason=reason,
                        connection=db_connection,
                    )

        organization_id = self._resolve_organization(connection, tenant_id)
        task_cursor = connection.execute(
            """
            SELECT *
            FROM tasks_field_reports.tasks
            WHERE id = %s AND organization_id = %s
            FOR UPDATE
            """,
            (task_id, organization_id),
        )
        task_row = task_cursor.fetchone()
        if task_row is None:
            raise KeyError("Task not found.")
        task = dict(zip([c.name for c in task_cursor.description], task_row))

        actor = connection.execute(
            """
            SELECT na.id
            FROM identity_authentication_sessions.users u
            JOIN hierarchy_bitemporal_model.node_assignments na
              ON na.user_id = u.id
             AND na.organization_id = u.organization_id
            WHERE u.id = %s
              AND u.organization_id = %s
              AND u.lifecycle_status = 'Active'
              AND na.valid_from <= NOW()
              AND (na.valid_to IS NULL OR na.valid_to > NOW())
            ORDER BY na.valid_from DESC, na.id
            LIMIT 1
            """,
            (requested_by, organization_id),
        ).fetchone()
        if actor is None:
            raise PermissionError(
                "Actor must have an active assignment in this tenant."
            )
        actor_assignment_id = actor[0]

        target_status, allowed_statuses = transitions[action]
        old_status = task["status"]
        if old_status not in allowed_statuses:
            raise ValueError(
                f"Action '{action}' is not allowed from status '{old_status}'."
            )

        new_status = old_status if target_status is None else target_status
        updated = connection.execute(
            """
            UPDATE tasks_field_reports.tasks
            SET status = %s,
                completed_at = CASE
                    WHEN %s = 'Completed' THEN NOW()
                    WHEN %s <> 'Completed' THEN NULL
                    ELSE completed_at
                END,
                rejected_at = CASE
                    WHEN %s = 'Rejected' THEN NOW()
                    WHEN %s <> 'Rejected' THEN NULL
                    ELSE rejected_at
                END,
                updated_at = NOW()
            WHERE id = %s AND organization_id = %s
            RETURNING *
            """,
            (
                new_status, new_status, new_status,
                new_status, new_status, task_id, organization_id,
            ),
        )
        updated_row = updated.fetchone()
        updated_task = dict(
            zip([c.name for c in updated.description], updated_row)
        )

        history_reason = f"action={action}"
        if reason:
            history_reason += f"; {reason}"

        connection.execute(
            """
            INSERT INTO tasks_field_reports.task_history (
                organization_id, task_id, from_status, to_status,
                actor_id, actor_assignment_id, reason
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                organization_id, task_id, old_status, new_status,
                requested_by, actor_assignment_id, history_reason,
            ),
        )

        return {
            "success": True,
            "task_id": str(task_id),
            "action": action,
            "status": new_status,
            "assignee_id": str(updated_task["assignee_id"]),
            "history_persisted": True,
        }

    def statistics(
        self,
        *,
        tenant_id: str,
    ) -> dict[str, Any]:
        """Return tenant-scoped task and evidence statistics."""
        with get_db_connection() as connection:
            organization_id = self._resolve_organization(
                connection, tenant_id
            )

            task_cursor = connection.execute(
                """
                SELECT status, priority, COUNT(*) AS count
                FROM tasks_field_reports.tasks
                WHERE organization_id = %(organization_id)s
                GROUP BY status, priority
                """,
                {"organization_id": organization_id},
            )

            status_counts: dict[str, int] = {}
            priority_counts: dict[str, int] = {}
            total = 0

            for status, priority, count in task_cursor.fetchall():
                count = int(count)
                total += count
                status_counts[str(status)] = (
                    status_counts.get(str(status), 0) + count
                )
                priority_counts[str(priority)] = (
                    priority_counts.get(str(priority), 0) + count
                )

            evidence_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM tasks_field_reports.evidence_media em
                    JOIN tasks_field_reports.field_reports fr
                      ON fr.id = em.report_id
                     AND fr.organization_id = em.organization_id
                    WHERE em.organization_id = %(organization_id)s
                    """,
                    {"organization_id": organization_id},
                ).fetchone()[0]
            )

            result: dict[str, Any] = {
                "total": total,
                "total_tasks": total,
                "tenant_id": tenant_id,
                "evidence_count": evidence_count,
                "status_counts": status_counts,
                "priority_counts": priority_counts,
            }

            for status, count in status_counts.items():
                result[status] = count

            return result



    def add_evidence(
        self,
        *,
        tenant_id: str,
        task_id: UUID,
        evidence_id: UUID,
        uploaded_by: UUID,
        sha256: str,
        storage_reference: str,
        content_type: str,
        connection=None,
    ) -> dict[str, Any]:
        """Persist a field report and its evidence atomically."""
        if not sha256.strip():
            raise ValueError("sha256 is required in PostgreSQL mode.")
        if not storage_reference.strip():
            raise ValueError("storage_reference is required in PostgreSQL mode.")
        if not content_type or "/" not in content_type:
            raise ValueError("A valid content_type is required.")

        if content_type.startswith("image/"):
            media_type = "photo"
        elif content_type.startswith("video/"):
            media_type = "video"
        elif content_type.startswith("audio/"):
            media_type = "audio"
        else:
            media_type = "document"

        if connection is None:
            with get_db_connection() as db_connection:
                with db_connection.transaction():
                    return self.add_evidence(
                        tenant_id=tenant_id,
                        task_id=task_id,
                        evidence_id=evidence_id,
                        uploaded_by=uploaded_by,
                        sha256=sha256,
                        storage_reference=storage_reference,
                        content_type=content_type,
                        connection=db_connection,
                    )

        with connection.transaction():
            organization_id = self._resolve_organization(
                connection, tenant_id
            )

            task_cursor = connection.execute(
                """
                SELECT id, assignee_id, assignee_node_id
                FROM tasks_field_reports.tasks
                WHERE id = %s AND organization_id = %s
                """,
                (task_id, organization_id),
            )
            task = task_cursor.fetchone()
            if task is None:
                raise KeyError("Task not found.")

            actor = connection.execute(
                """
                SELECT na.id
                FROM identity_authentication_sessions.users u
                JOIN hierarchy_bitemporal_model.node_assignments na
                  ON na.user_id = u.id
                 AND na.organization_id = u.organization_id
                WHERE u.id = %s
                  AND u.organization_id = %s
                  AND u.lifecycle_status = 'Active'
                  AND na.valid_from <= NOW()
                  AND (na.valid_to IS NULL OR na.valid_to > NOW())
                ORDER BY na.valid_from DESC, na.id
                LIMIT 1
                """,
                (uploaded_by, organization_id),
            ).fetchone()
            if actor is None:
                raise PermissionError(
                    "Uploader must have an active assignment in this tenant."
                )

            report_id = uuid4()
            report_cursor = connection.execute(
                """
                INSERT INTO tasks_field_reports.field_reports (
                    id, organization_id, task_id, reporter_id,
                    reporter_assignment_id, text, completion_pct,
                    integrity_status, integrity_flags, attested_count,
                    unattested_count, flagged_count, submitted_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, NULL, NULL,
                    'unverified', '[]'::jsonb, 0, 1, 0, NOW()
                )
                RETURNING id, submitted_at
                """,
                (
                    report_id, organization_id, task_id,
                    uploaded_by, actor[0],
                ),
            )
            report_cursor.fetchone()

            media_cursor = connection.execute(
                """
                INSERT INTO tasks_field_reports.evidence_media (
                    id, organization_id, report_id, media_type,
                    capture_method, trust_class, object_storage_key,
                    media_hash, exif_stripped, attestation_status,
                    coherence_flags, tampered, uploaded_at
                )
                VALUES (
                    %s, %s, %s, %s, 'gallery_upload', 'unattested',
                    %s, %s, FALSE, 'unattested', '[]'::jsonb,
                    FALSE, NOW()
                )
                RETURNING id, media_type, object_storage_key,
                          media_hash, uploaded_at
                """,
                (
                    evidence_id, organization_id, report_id,
                    media_type, storage_reference, sha256,
                ),
            )
            media = media_cursor.fetchone()

            return {
                "evidence_id": str(media[0]),
                "report_id": str(report_id),
                "task_id": str(task_id),
                "uploaded_by": str(uploaded_by),
                "content_type": content_type,
                "sha256": media[3],
                "storage_reference": media[2],
                "created_at": media[4],
                "verified": False,
                "verification_persisted": False,
            }

    def list_evidence(
        self, *, tenant_id: str, task_id: UUID
    ) -> list[dict[str, Any]]:
        with get_db_connection() as connection:
            organization_id = self._resolve_organization(
                connection, tenant_id
            )
            cursor = connection.execute(
                """
                SELECT em.id AS evidence_id, fr.id AS report_id,
                       fr.task_id, fr.reporter_id AS uploaded_by,
                       em.media_type, em.media_hash AS sha256,
                       em.object_storage_key AS storage_reference,
                       em.uploaded_at AS created_at,
                       em.attestation_status, em.trust_class
                FROM tasks_field_reports.field_reports fr
                JOIN tasks_field_reports.evidence_media em
                  ON em.report_id = fr.id
                 AND em.organization_id = fr.organization_id
                WHERE fr.organization_id = %s AND fr.task_id = %s
                ORDER BY em.uploaded_at DESC, em.id
                """,
                (organization_id, task_id),
            )
            columns = [item.name for item in cursor.description]
            return [
                dict(zip(columns, row)) for row in cursor.fetchall()
            ]

    def get_evidence(
        self, *, tenant_id: str, task_id: UUID, evidence_id: UUID
    ) -> dict[str, Any] | None:
        with get_db_connection() as connection:
            organization_id = self._resolve_organization(
                connection, tenant_id
            )
            cursor = connection.execute(
                """
                SELECT em.id AS evidence_id, fr.id AS report_id,
                       fr.task_id, fr.reporter_id AS uploaded_by,
                       em.media_type, em.media_hash AS sha256,
                       em.object_storage_key AS storage_reference,
                       em.uploaded_at AS created_at,
                       em.attestation_status, em.trust_class
                FROM tasks_field_reports.field_reports fr
                JOIN tasks_field_reports.evidence_media em
                  ON em.report_id = fr.id
                 AND em.organization_id = fr.organization_id
                WHERE fr.organization_id = %s
                  AND fr.task_id = %s
                  AND em.id = %s
                LIMIT 1
                """,
                (organization_id, task_id, evidence_id),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            columns = [item.name for item in cursor.description]
            return dict(zip(columns, row))

    def verify_evidence_hash(
        self, *, tenant_id: str, task_id: UUID,
        evidence_id: UUID, expected_sha256: str,
    ) -> dict[str, Any] | None:
        evidence = self.get_evidence(
            tenant_id=tenant_id, task_id=task_id,
            evidence_id=evidence_id,
        )
        if evidence is None:
            return None

        actual = evidence.get("sha256")
        matched = bool(actual) and actual == expected_sha256
        return {
            "success": True,
            "evidence_id": str(evidence_id),
            "verified": matched,
            "actual_sha256": actual,
            "expected_sha256": expected_sha256,
            "verification_persisted": False,
            "note": "Hash comparison only; verification audit is not stored by the current schema.",
        }

task_repository = TaskRepository()
