from __future__ import annotations

from uuid import uuid4

from app.core.database import get_db_connection
from app.repositories.task_repository import TaskRepository


TEST_TENANT_ID = "87af3e41-7074-4a7f-8f75-ccba26e7946f"


class _RollbackIntegrationTest(Exception):
    pass


def test_task_repository_create_and_read_in_rollback_transaction():
    repository = TaskRepository()

    with get_db_connection() as connection:
        database = connection.execute(
            "SELECT current_database()"
        ).fetchone()[0]
        assert database == "groundconnect_test"

        try:
            with connection.transaction():
                tenant_id = repository._resolve_organization(
                    connection, TEST_TENANT_ID
                )

                level_id = connection.execute(
                    """
                    INSERT INTO tenant_and_configuration.hierarchy_levels
                        (organization_id, level_index, name)
                    VALUES (%s, 0, %s)
                    RETURNING id
                    """,
                    (tenant_id, f"Integration Level {uuid4()}"),
                ).fetchone()[0]

                user_id = connection.execute(
                    """
                    INSERT INTO identity_authentication_sessions.users (
                        organization_id, mobile_encrypted, mobile_hash,
                        name_encrypted, preferred_language,
                        lifecycle_status, mfa_required
                    )
                    VALUES (%s, %s, %s, %s, 'en', 'Active', FALSE)
                    RETURNING id
                    """,
                    (
                        tenant_id,
                        uuid4().bytes,
                        f"test-{uuid4()}",
                        uuid4().bytes,
                    ),
                ).fetchone()[0]

                node_id = connection.execute(
                    """
                    INSERT INTO hierarchy_bitemporal_model.nodes (
                        organization_id, level_id, name, status
                    )
                    VALUES (%s, %s, %s, 'active')
                    RETURNING id
                    """,
                    (tenant_id, level_id, f"Integration Node {uuid4()}"),
                ).fetchone()[0]

                assignment_id = connection.execute(
                    """
                    INSERT INTO hierarchy_bitemporal_model.node_assignments (
                        organization_id, user_id, node_id, role,
                        valid_from, recorded_by
                    )
                    VALUES (%s, %s, %s, 'field_worker', NOW(), %s)
                    RETURNING id
                    """,
                    (tenant_id, user_id, node_id, user_id),
                ).fetchone()[0]

                task = repository.create_task(
                    tenant_id=TEST_TENANT_ID,
                    title="Integration test task",
                    creator_id=user_id,
                    creator_assignment_id=assignment_id,
                    assignee_id=user_id,
                    assignee_node_id=node_id,
                    priority="Medium",
                    status="Assigned",
                    connection=connection,
                )

                assert task["title"] == "Integration test task"
                assert task["organization_id"] == tenant_id

                fetched = repository.get_task(
                    task_id=task["id"],
                    tenant_id=TEST_TENANT_ID,
                    connection=connection,
                )
                assert fetched is not None
                assert fetched["id"] == task["id"]
                assert fetched["title"] == task["title"]

                raise _RollbackIntegrationTest()

        except _RollbackIntegrationTest:
            pass

def test_task_repository_update_in_rollback_transaction():
    repository = TaskRepository()

    with get_db_connection() as connection:
        database = connection.execute(
            "SELECT current_database()"
        ).fetchone()[0]
        assert database == "groundconnect_test"

        try:
            with connection.transaction():
                tenant_id = repository._resolve_organization(
                    connection, TEST_TENANT_ID
                )

                level_id = connection.execute(
                    """
                    INSERT INTO tenant_and_configuration.hierarchy_levels
                        (organization_id, level_index, name)
                    VALUES (%s, 0, %s)
                    RETURNING id
                    """,
                    (tenant_id, f"Update Integration Level {uuid4()}"),
                ).fetchone()[0]

                user_id = connection.execute(
                    """
                    INSERT INTO identity_authentication_sessions.users (
                        organization_id, mobile_encrypted, mobile_hash,
                        name_encrypted, preferred_language,
                        lifecycle_status, mfa_required
                    )
                    VALUES (%s, %s, %s, %s, 'en', 'Active', FALSE)
                    RETURNING id
                    """,
                    (
                        tenant_id,
                        uuid4().bytes,
                        f"update-test-{uuid4()}",
                        uuid4().bytes,
                    ),
                ).fetchone()[0]

                node_id = connection.execute(
                    """
                    INSERT INTO hierarchy_bitemporal_model.nodes (
                        organization_id, level_id, name, status
                    )
                    VALUES (%s, %s, %s, 'active')
                    RETURNING id
                    """,
                    (tenant_id, level_id, f"Update Integration Node {uuid4()}"),
                ).fetchone()[0]

                assignment_id = connection.execute(
                    """
                    INSERT INTO hierarchy_bitemporal_model.node_assignments (
                        organization_id, user_id, node_id, role,
                        valid_from, recorded_by
                    )
                    VALUES (%s, %s, %s, 'field_worker', NOW(), %s)
                    RETURNING id
                    """,
                    (tenant_id, user_id, node_id, user_id),
                ).fetchone()[0]

                task = repository.create_task(
                    tenant_id=TEST_TENANT_ID,
                    title="Task before update",
                    creator_id=user_id,
                    creator_assignment_id=assignment_id,
                    assignee_id=user_id,
                    assignee_node_id=node_id,
                    priority="Medium",
                    status="Assigned",
                    connection=connection,
                )

                updated = repository.update_task(
                    task_id=task["id"],
                    tenant_id=TEST_TENANT_ID,
                    title="Task after update",
                    description="Integration update verified",
                    priority="High",
                    status="In_Progress",
                    connection=connection,
                )

                assert updated is not None
                assert updated["id"] == task["id"]
                assert updated["title"] == "Task after update"
                assert updated["description"] == "Integration update verified"
                assert updated["priority"] == "High"
                assert updated["status"] == "In_Progress"

                fetched = repository.get_task(
                    task_id=task["id"],
                    tenant_id=TEST_TENANT_ID,
                    connection=connection,
                )
                assert fetched is not None
                assert fetched["title"] == "Task after update"
                assert fetched["priority"] == "High"
                assert fetched["status"] == "In_Progress"

                raise _RollbackIntegrationTest()

        except _RollbackIntegrationTest:
            pass
