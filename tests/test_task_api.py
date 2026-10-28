
from fastapi.testclient import TestClient

from app.main import app
from app.api.routes import tasks as tasks_route
from app.core.config import settings


client = TestClient(app)


def authenticate():
    user_id = "task_api_test_user"
    device_id = "task_api_test_device"

    register = client.post(
        "/api/v1/auth/device/register",
        json={"user_id": user_id, "device_id": device_id},
    )
    assert register.status_code == 200

    session = client.post(
        "/api/v1/auth/session/create",
        json={"user_id": user_id, "device_id": device_id},
    )
    assert session.status_code == 200

    return {
        "Authorization": (
            f"Bearer {session.json()['access_token']}"
        )
    }


def test_create_task_requires_authentication():
    response = client.post(
        "/api/v1/tasks",
        json={},
    )

    assert response.status_code == 401


def test_create_task_returns_created_task(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", False)
    headers = authenticate()

    def fake_create_task(**kwargs):
        return {
            "task_id": kwargs["task_id"],
            "tenant_id": kwargs["tenant_id"],
            "title": kwargs["title"],
            "description": kwargs["description"],
            "created_by": kwargs["created_by"],
            "assignee_id": kwargs["assignee_id"],
            "priority": kwargs["priority"],
            "status": "pending",
            "due_at": kwargs["due_at"],
            "created_at": "2026-10-27T10:00:00Z",
            "updated_at": "2026-10-27T10:00:00Z",
            "metadata": kwargs["metadata"],
        }

    monkeypatch.setattr(
        tasks_route.task_service,
        "create_task",
        fake_create_task,
    )

    response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "task_id": "task-api-test-001",
            "tenant_id": "tenant-api-test",
            "title": "Test task",
            "created_by": "api-test-user",
            "priority": "normal",
            "metadata": {},
        },
    )

    assert response.status_code == 200
    assert response.json()["task_id"] == "task-api-test-001"
    assert response.json()["status"] == "pending"


def test_create_task_rejects_invalid_priority():
    headers = authenticate()

    response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "task_id": "task-api-invalid-001",
            "tenant_id": "tenant-api-test",
            "title": "Test task",
            "created_by": "api-test-user",
            "priority": "critical",
        },
    )

    assert response.status_code == 422
from uuid import UUID
from datetime import datetime, timezone

from app.api.routes import tasks as tasks_route


def test_postgres_create_task_maps_fields(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)

    task_id = "11111111-1111-4111-8111-111111111111"
    creator_id = "22222222-2222-4222-8222-222222222222"
    assignment_id = "33333333-3333-4333-8333-333333333333"
    assignee_id = "44444444-4444-4444-8444-444444444444"
    node_id = "55555555-5555-4555-8555-555555555555"

    now = datetime.now(timezone.utc)
    captured = {}

    def fake_repository_create_task(**kwargs):
        captured.update(kwargs)
        return {
            "id": UUID(task_id),
            "title": "Postgres test task",
            "description": None,
            "creator_id": UUID(creator_id),
            "assignee_id": UUID(assignee_id),
            "priority": "Medium",
            "deadline": None,
            "created_at": now,
            "updated_at": now,
        }

    monkeypatch.setattr(
        tasks_route.task_repository,
        "create_task",
        fake_repository_create_task,
    )

    headers = authenticate()
    response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "task_id": task_id,
            "tenant_id": "citizen-manual-test",
            "title": "Postgres test task",
            "created_by": creator_id,
            "assignee_id": assignee_id,
            "creator_assignment_id": assignment_id,
            "assignee_node_id": node_id,
            "priority": "normal",
            "metadata": {},
        },
    )

    assert response.status_code == 200, response.text
    assert response.json()["task_id"] == task_id
    assert response.json()["priority"] == "normal"
    assert captured["priority"] == "Medium"
    assert captured["task_id"] == UUID(task_id)
    assert captured["creator_assignment_id"] == UUID(assignment_id)
    assert captured["assignee_node_id"] == UUID(node_id)


def test_postgres_create_task_rejects_missing_assignment_ids(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)

    headers = authenticate()
    response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "task_id": "11111111-1111-4111-8111-111111111111",
            "tenant_id": "citizen-manual-test",
            "title": "Missing assignments",
            "created_by": "22222222-2222-4222-8222-222222222222",
            "priority": "normal",
            "metadata": {},
        },
    )

    assert response.status_code == 400
    assert "creator_assignment_id" in response.json()["detail"]


def test_postgres_create_task_rejects_metadata(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)

    headers = authenticate()
    response = client.post(
        "/api/v1/tasks",
        headers=headers,
        json={
            "task_id": "11111111-1111-4111-8111-111111111111",
            "tenant_id": "citizen-manual-test",
            "title": "Metadata test",
            "created_by": "22222222-2222-4222-8222-222222222222",
            "assignee_id": "44444444-4444-4444-8444-444444444444",
            "creator_assignment_id": "33333333-3333-4333-8333-333333333333",
            "assignee_node_id": "55555555-5555-4555-8555-555555555555",
            "priority": "normal",
            "metadata": {"source": "test"},
        },
    )

    assert response.status_code == 400
    assert "metadata" in response.json()["detail"].lower()
def test_postgres_get_task_returns_mapped_task(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)

    task_id = "11111111-1111-4111-8111-111111111111"
    creator_id = "22222222-2222-4222-8222-222222222222"
    assignee_id = "44444444-4444-4444-8444-444444444444"
    now = datetime.now(timezone.utc)
    captured = {}

    def fake_get_task(**kwargs):
        captured.update(kwargs)
        return {
            "id": UUID(task_id),
            "title": "Retrieved task",
            "description": "Test description",
            "creator_id": UUID(creator_id),
            "assignee_id": UUID(assignee_id),
            "priority": "High",
            "status": "In_Progress",
            "deadline": None,
            "created_at": now,
            "updated_at": now,
        }

    monkeypatch.setattr(
        tasks_route.task_repository,
        "get_task",
        fake_get_task,
    )

    response = client.get(
        f"/api/v1/tasks/{task_id}",
        headers=authenticate(),
        params={"tenant_id": "citizen-manual-test"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["task_id"] == task_id
    assert body["priority"] == "high"
    assert body["status"] == "in_progress"
    assert body["created_by"] == creator_id
    assert captured["task_id"] == UUID(task_id)


def test_postgres_get_task_returns_404_when_missing(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)
    monkeypatch.setattr(
        tasks_route.task_repository,
        "get_task",
        lambda **kwargs: None,
    )

    response = client.get(
        "/api/v1/tasks/11111111-1111-4111-8111-111111111111",
        headers=authenticate(),
        params={"tenant_id": "citizen-manual-test"},
    )

    assert response.status_code == 404


def test_postgres_get_task_rejects_invalid_uuid(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)

    response = client.get(
        "/api/v1/tasks/not-a-uuid",
        headers=authenticate(),
        params={"tenant_id": "citizen-manual-test"},
    )

    assert response.status_code == 400

def test_postgres_search_tasks_maps_results_and_filters(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)

    task_id = UUID("11111111-1111-4111-8111-111111111111")
    creator_id = UUID("22222222-2222-4222-8222-222222222222")
    assignee_id = UUID("44444444-4444-4444-8444-444444444444")
    now = datetime.now(timezone.utc)
    captured = {}

    def fake_search_tasks(**kwargs):
        captured.update(kwargs)
        return {
            "items": [{
                "id": task_id,
                "title": "Search result",
                "description": "Task description",
                "creator_id": creator_id,
                "assignee_id": assignee_id,
                "priority": "High",
                "status": "In_Progress",
                "deadline": None,
                "created_at": now,
                "updated_at": now,
            }],
            "total": 1,
            "page": 2,
            "page_size": 10,
        }

    monkeypatch.setattr(
        tasks_route.task_repository,
        "search_tasks",
        fake_search_tasks,
    )

    response = client.get(
        "/api/v1/tasks/search",
        headers=authenticate(),
        params={
            "tenant_id": "citizen-manual-test",
            "query": "Search",
            "status": "in_progress",
            "priority": "high",
            "assignee_id": str(assignee_id),
            "page": 2,
            "page_size": 10,
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()

    assert body["total"] == 1
    assert body["page"] == 2
    assert body["page_size"] == 10
    assert len(body["items"]) == 1
    assert body["items"][0]["task_id"] == str(task_id)
    assert body["items"][0]["priority"] == "high"
    assert body["items"][0]["status"] == "in_progress"
    assert body["items"][0]["created_by"] == str(creator_id)
    assert body["items"][0]["assignee_id"] == str(assignee_id)

    assert captured["tenant_id"] == "citizen-manual-test"
    assert captured["query"] == "Search"
    assert captured["status"] == "in_progress"
    assert captured["priority"] == "high"
    assert captured["assignee_id"] == assignee_id
    assert captured["page"] == 2
    assert captured["page_size"] == 10


def test_postgres_search_tasks_rejects_invalid_assignee_uuid(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)

    response = client.get(
        "/api/v1/tasks/search",
        headers=authenticate(),
        params={
            "tenant_id": "citizen-manual-test",
            "assignee_id": "not-a-uuid",
        },
    )

    assert response.status_code == 400
    assert "valid UUID" in response.json()["detail"]


def test_postgres_search_tasks_returns_400_for_repository_value_error(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)

    def fake_search_tasks(**kwargs):
        raise ValueError("Unsupported task status filter.")

    monkeypatch.setattr(
        tasks_route.task_repository,
        "search_tasks",
        fake_search_tasks,
    )

    response = client.get(
        "/api/v1/tasks/search",
        headers=authenticate(),
        params={
            "tenant_id": "citizen-manual-test",
            "status": "unknown",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported task status filter."


def test_postgres_search_tasks_returns_empty_results(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)
    monkeypatch.setattr(
        tasks_route.task_repository,
        "search_tasks",
        lambda **kwargs: {
            "items": [],
            "total": 0,
            "page": 1,
            "page_size": 50,
        },
    )

    response = client.get(
        "/api/v1/tasks/search",
        headers=authenticate(),
        params={"tenant_id": "citizen-manual-test"},
    )

    assert response.status_code == 200, response.text
    assert response.json() == {
        "items": [],
        "total": 0,
        "page": 1,
        "page_size": 50,
    }


def test_task_statistics_uses_postgres_repository(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)
    expected = {
        "total": 3,
        "total_tasks": 3,
        "tenant_id": "citizen-manual-test",
        "evidence_count": 2,
        "status_counts": {"Assigned": 2, "Completed": 1},
        "priority_counts": {"Medium": 2, "High": 1},
        "Assigned": 2,
        "Completed": 1,
    }
    calls = []

    def fake_statistics(*, tenant_id):
        calls.append(tenant_id)
        return expected

    monkeypatch.setattr(
        tasks_route.task_repository,
        "statistics",
        fake_statistics,
    )

    response = client.get(
        "/api/v1/tasks/statistics/summary",
        params={"tenant_id": "citizen-manual-test"},
        headers=authenticate(),
    )

    assert response.status_code == 200
    assert response.json() == expected
    assert calls == ["citizen-manual-test"]


def test_task_statistics_maps_repository_value_error_to_400(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)

    def fake_statistics(*, tenant_id):
        raise ValueError("Unknown tenant")

    monkeypatch.setattr(
        tasks_route.task_repository,
        "statistics",
        fake_statistics,
    )

    response = client.get(
        "/api/v1/tasks/statistics/summary",
        params={"tenant_id": "unknown-tenant"},
        headers=authenticate(),
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown tenant"


def test_task_statistics_maps_repository_permission_error_to_403(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)

    def fake_statistics(*, tenant_id):
        raise PermissionError("Access denied")

    monkeypatch.setattr(
        tasks_route.task_repository,
        "statistics",
        fake_statistics,
    )

    response = client.get(
        "/api/v1/tasks/statistics/summary",
        params={"tenant_id": "citizen-manual-test"},
        headers=authenticate(),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Access denied"


def test_task_statistics_uses_in_memory_service(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", False)
    expected = {
        "total": 1,
        "tenant_id": "memory-test",
        "status_counts": {"pending": 1},
    }
    calls = []

    def fake_statistics(*, tenant_id):
        calls.append(tenant_id)
        return expected

    monkeypatch.setattr(
        tasks_route.task_service,
        "statistics",
        fake_statistics,
    )

    response = client.get(
        "/api/v1/tasks/statistics/summary",
        params={"tenant_id": "memory-test"},
        headers=authenticate(),
    )

    assert response.status_code == 200
    assert response.json() == expected
    assert calls == ["memory-test"]


def test_postgres_patch_task_updates_fields(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)

    task_id = "11111111-1111-4111-8111-111111111111"
    now = datetime.now(timezone.utc)
    captured = {}

    def fake_update_task(**kwargs):
        captured.update(kwargs)
        return {
            "id": UUID(task_id),
            "creator_id": UUID("22222222-2222-4222-8222-222222222222"),
            "assignee_id": UUID("44444444-4444-4444-8444-444444444444"),
            "title": kwargs["title"],
            "description": kwargs["description"],
            "priority": kwargs["priority"],
            "status": kwargs["status"],
            "deadline": kwargs["deadline"],
            "created_at": now,
            "updated_at": now,
        }

    monkeypatch.setattr(
        tasks_route.task_repository,
        "update_task",
        fake_update_task,
    )

    response = client.patch(
        f"/api/v1/tasks/{task_id}",
        headers=authenticate(),
        params={"tenant_id": "citizen-manual-test"},
        json={
            "title": "Updated task",
            "description": "Updated description",
            "priority": "high",
            "status": "completed",
            "due_at": "2026-11-01T10:00:00Z",
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["title"] == "Updated task"
    assert data["priority"] == "high"
    assert data["status"] == "completed"
    assert captured["task_id"] == UUID(task_id)
    assert captured["tenant_id"] == "citizen-manual-test"
    assert captured["priority"] == "High"
    assert captured["status"] == "Completed"
    assert captured["update_deadline"] is True


def test_postgres_patch_task_rejects_invalid_uuid(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)

    response = client.patch(
        "/api/v1/tasks/not-a-uuid",
        headers=authenticate(),
        params={"tenant_id": "citizen-manual-test"},
        json={"title": "Updated task"},
    )

    assert response.status_code == 400
    assert "UUID" in response.json()["detail"]


def test_postgres_patch_task_returns_404_when_missing(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)
    monkeypatch.setattr(
        tasks_route.task_repository,
        "update_task",
        lambda **kwargs: None,
    )

    response = client.patch(
        "/api/v1/tasks/11111111-1111-4111-8111-111111111111",
        headers=authenticate(),
        params={"tenant_id": "citizen-manual-test"},
        json={"title": "Updated task"},
    )

    assert response.status_code == 404


def test_postgres_patch_task_rejects_assignee_change(monkeypatch):
    monkeypatch.setattr(settings, "database_enabled", True)

    response = client.patch(
        "/api/v1/tasks/11111111-1111-4111-8111-111111111111",
        headers=authenticate(),
        params={"tenant_id": "citizen-manual-test"},
        json={"assignee_id": "44444444-4444-4444-8444-444444444444"},
    )

    assert response.status_code == 400
    assert "assignee" in response.json()["detail"].lower()
