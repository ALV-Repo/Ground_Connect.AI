from datetime import datetime, timedelta, timezone

import pytest

from app.services.tasks import TaskService


@pytest.fixture
def service():
    return TaskService()


@pytest.fixture
def task(service):
    return service.create_task(
        task_id="task-001",
        tenant_id="tenant-001",
        title="Test Task",
        description="BE-009 test task",
        created_by="leader-001",
        assignee_id="member-001",
        priority="high",
        due_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )


# ============================================================
# Task Creation
# ============================================================


def test_create_task(service):
    result = service.create_task(
        task_id="task-001",
        tenant_id="tenant-001",
        title="Test Task",
        created_by="leader-001",
        assignee_id="member-001",
    )

    assert result["task_id"] == "task-001"
    assert result["tenant_id"] == "tenant-001"
    assert result["title"] == "Test Task"


def test_duplicate_task_rejected(service):
    service.create_task(
        task_id="task-001",
        tenant_id="tenant-001",
        title="Test Task",
        created_by="leader-001",
    )

    with pytest.raises(ValueError):
        service.create_task(
            task_id="task-001",
            tenant_id="tenant-001",
            title="Duplicate Task",
            created_by="leader-001",
        )


# ============================================================
# Tenant Isolation
# ============================================================


def test_task_tenant_isolation(service, task):
    result = service.get_task(
        task_id="task-001",
        tenant_id="tenant-002",
    )

    assert result is None


# ============================================================
# Task Lifecycle
# ============================================================


def test_task_start(service, task):
    result = service.task_action(
        task_id="task-001",
        tenant_id="tenant-001",
        action="start",
        requested_by="member-001",
    )

    assert result["success"] is True
    assert result["status"] == "in_progress"


def test_task_complete(service, task):
    service.task_action(
        task_id="task-001",
        tenant_id="tenant-001",
        action="start",
        requested_by="member-001",
    )

    result = service.task_action(
        task_id="task-001",
        tenant_id="tenant-001",
        action="complete",
        requested_by="member-001",
    )

    assert result["success"] is True
    assert result["status"] == "completed"


def test_task_cancel(service, task):
    result = service.task_action(
        task_id="task-001",
        tenant_id="tenant-001",
        action="cancel",
        requested_by="leader-001",
        reason="No longer required",
    )

    assert result["success"] is True
    assert result["status"] == "cancelled"


def test_task_reopen(service, task):
    service.task_action(
        task_id="task-001",
        tenant_id="tenant-001",
        action="complete",
        requested_by="member-001",
    )

    result = service.task_action(
        task_id="task-001",
        tenant_id="tenant-001",
        action="reopen",
        requested_by="leader-001",
        reason="Additional work required",
    )

    assert result["success"] is True
    assert result["status"] == "pending"


# ============================================================
# Assignment
# ============================================================


def test_task_assignment_required(service):
    service.create_task(
        task_id="task-002",
        tenant_id="tenant-001",
        title="Unassigned Task",
        created_by="leader-001",
    )

    with pytest.raises(ValueError):
        service.task_action(
            task_id="task-002",
            tenant_id="tenant-001",
            action="assign",
            requested_by="leader-001",
        )


def test_task_unassign(service, task):
    result = service.task_action(
        task_id="task-001",
        tenant_id="tenant-001",
        action="unassign",
        requested_by="leader-001",
    )

    assert result["success"] is True

    updated = service.get_task(
        task_id="task-001",
        tenant_id="tenant-001",
    )

    assert updated["assignee_id"] is None


# ============================================================
# Evidence
# ============================================================


def test_add_evidence(service, task):
    result = service.add_evidence(
        evidence_id="evidence-001",
        task_id="task-001",
        uploaded_by="member-001",
        file_name="report.jpg",
        content_type="image/jpeg",
        size_bytes=1024,
        sha256="abc123",
    )

    assert result["evidence_id"] == "evidence-001"
    assert result["task_id"] == "task-001"
    assert result["verified"] is False


def test_duplicate_evidence_rejected(service, task):
    service.add_evidence(
        evidence_id="evidence-001",
        task_id="task-001",
        uploaded_by="member-001",
        file_name="report.jpg",
        content_type="image/jpeg",
        size_bytes=1024,
        sha256="abc123",
    )

    with pytest.raises(ValueError):
        service.add_evidence(
            evidence_id="evidence-001",
            task_id="task-001",
            uploaded_by="member-001",
            file_name="report2.jpg",
            content_type="image/jpeg",
            size_bytes=1024,
            sha256="xyz789",
        )


def test_evidence_verification_success(service, task):
    service.add_evidence(
        evidence_id="evidence-001",
        task_id="task-001",
        uploaded_by="member-001",
        file_name="report.jpg",
        content_type="image/jpeg",
        size_bytes=1024,
        sha256="abc123",
    )

    result = service.verify_evidence(
        evidence_id="evidence-001",
        verified_by="leader-001",
        expected_sha256="abc123",
    )

    assert result["success"] is True
    assert result["verified"] is True
    assert result["actual_sha256"] == "abc123"


def test_evidence_verification_failure(service, task):
    service.add_evidence(
        evidence_id="evidence-001",
        task_id="task-001",
        uploaded_by="member-001",
        file_name="report.jpg",
        content_type="image/jpeg",
        size_bytes=1024,
        sha256="abc123",
    )

    result = service.verify_evidence(
        evidence_id="evidence-001",
        verified_by="leader-001",
        expected_sha256="wrong-hash",
    )

    assert result["success"] is True
    assert result["verified"] is False


# ============================================================
# Search
# ============================================================


def test_task_search(service):
    service.create_task(
        task_id="task-001",
        tenant_id="tenant-001",
        title="Fire Inspection",
        description="Inspect fire equipment",
        created_by="leader-001",
        assignee_id="member-001",
    )

    service.create_task(
        task_id="task-002",
        tenant_id="tenant-001",
        title="Road Inspection",
        description="Inspect road",
        created_by="leader-001",
        assignee_id="member-002",
    )

    result = service.search_tasks(
        tenant_id="tenant-001",
        query="Fire",
    )

    assert result["total"] == 1
    assert result["items"][0]["task_id"] == "task-001"


# ============================================================
# Overdue
# ============================================================


def test_overdue_task(service):
    service.create_task(
        task_id="task-overdue",
        tenant_id="tenant-001",
        title="Overdue Task",
        created_by="leader-001",
        due_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    result = service.search_tasks(
        tenant_id="tenant-001",
    )

    assert result["total"] == 1
    assert result["items"][0]["status"] == "overdue"


# ============================================================
# Statistics
# ============================================================


def test_task_statistics(service):
    service.create_task(
        task_id="task-001",
        tenant_id="tenant-001",
        title="Pending Task",
        created_by="leader-001",
    )

    service.create_task(
        task_id="task-002",
        tenant_id="tenant-001",
        title="Completed Task",
        created_by="leader-001",
    )

    service.task_action(
        task_id="task-002",
        tenant_id="tenant-001",
        action="complete",
        requested_by="leader-001",
    )

    result = service.statistics(
        tenant_id="tenant-001",
    )

    assert result["total"] == 2
    assert result["pending"] == 1
    assert result["completed"] == 1
def test_task_transition_history_is_recorded(service, task):
    service.task_action(
        task_id="task-001",
        tenant_id="tenant-001",
        action="start",
        requested_by="member-001",
    )

    service.task_action(
        task_id="task-001",
        tenant_id="tenant-001",
        action="complete",
        requested_by="member-001",
    )

    result = service.get_task(
        task_id="task-001",
        tenant_id="tenant-001",
    )

    history = result["history"]

    assert len(history) == 2

    assert history[0]["action"] == "start"
    assert history[0]["requested_by"] == "member-001"
    assert history[0]["status"] == "in_progress"
    assert history[0]["timestamp"] is not None

    assert history[1]["action"] == "complete"
    assert history[1]["requested_by"] == "member-001"
    assert history[1]["status"] == "completed"
    assert history[1]["timestamp"] is not None
