from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.workflow import (
    DisputeReopenRequest,
    IssueStatus,
    IssueStatusUpdateRequest,
    RejectionRequest,
    SLAConfigCreate,
)
from app.services.workflow import WorkflowService


@pytest.fixture
def service():
    return WorkflowService()


def configure_sla(service):
    return service.configure_sla(
        SLAConfigCreate(
            tenant_id="tenant-1",
            category="road",
            priority="high",
            response_target_minutes=30,
            resolution_target_minutes=60,
            escalation_chain=[
                "supervisor",
                "department-head",
            ],
        )
    )


def register_issue(service):
    created_at = datetime.now(timezone.utc)

    service.register_issue(
        issue_id="issue-001",
        tenant_id="tenant-1",
        category="road",
        priority="high",
        created_at=created_at,
    )

    return created_at


def test_configure_sla(service):
    result = configure_sla(service)

    assert result.tenant_id == "tenant-1"
    assert result.category == "road"
    assert result.priority == "high"
    assert result.response_target_minutes == 30
    assert result.resolution_target_minutes == 60
    assert result.escalation_chain == [
        "supervisor",
        "department-head",
    ]


def test_register_issue_creates_new_state(service):
    configure_sla(service)

    result = service.register_issue(
        issue_id="issue-001",
        tenant_id="tenant-1",
        category="road",
        priority="high",
    )

    assert result.issue_id == "issue-001"
    assert result.status == IssueStatus.NEW
    assert len(result.status_history) == 1


def test_valid_workflow_transition(service):
    register_issue(service)

    result = service.update_status(
        IssueStatusUpdateRequest(
            issue_id="issue-001",
            tenant_id="tenant-1",
            status=IssueStatus.ASSIGNED,
            actor_id="operator-1",
        )
    )

    assert result.status == IssueStatus.ASSIGNED
    assert len(result.status_history) == 2


def test_invalid_workflow_transition_rejected(service):
    register_issue(service)

    with pytest.raises(ValueError):
        service.update_status(
            IssueStatusUpdateRequest(
                issue_id="issue-001",
                tenant_id="tenant-1",
                status=IssueStatus.CLOSED,
                actor_id="operator-1",
            )
        )


def test_rejection_requires_reason(service):
    register_issue(service)

    with pytest.raises(ValueError):
        RejectionRequest(
            issue_id="issue-001",
            tenant_id="tenant-1",
            actor_id="operator-1",
            reason="",
        )


def test_issue_can_be_rejected_with_reason(service):
    register_issue(service)

    result = service.reject_issue(
        RejectionRequest(
            issue_id="issue-001",
            tenant_id="tenant-1",
            actor_id="operator-1",
            reason="Insufficient information",
        )
    )

    assert result.status == IssueStatus.REJECTED
    assert result.status_history[-1].reason == (
        "Insufficient information"
    )


def test_response_sla_breach_triggers_deterministic_escalation(service):
    configure_sla(service)

    created_at = datetime.now(timezone.utc) - timedelta(minutes=31)

    service.register_issue(
        issue_id="issue-001",
        tenant_id="tenant-1",
        category="road",
        priority="high",
        created_at=created_at,
    )

    result = service.check_sla(
        issue_id="issue-001",
        tenant_id="tenant-1",
        now=datetime.now(timezone.utc),
    )

    assert result.response_breached is True
    assert result.escalation_triggered is True
    assert result.current_escalation_level == 1

    escalations = service.get_escalations(
        "issue-001",
        "tenant-1",
    )

    assert len(escalations) == 1
    assert escalations[0].target == "supervisor"
    assert escalations[0].deterministic_policy is True


def test_resolution_sla_breach_escalates(service):
    configure_sla(service)

    created_at = datetime.now(timezone.utc) - timedelta(minutes=61)

    service.register_issue(
        issue_id="issue-001",
        tenant_id="tenant-1",
        category="road",
        priority="high",
        created_at=created_at,
    )

    service.update_status(
        IssueStatusUpdateRequest(
            issue_id="issue-001",
            tenant_id="tenant-1",
            status=IssueStatus.ASSIGNED,
            actor_id="operator-1",
        )
    )

    result = service.check_sla(
        issue_id="issue-001",
        tenant_id="tenant-1",
        now=datetime.now(timezone.utc),
    )

    assert result.resolution_breached is True
    assert result.escalation_triggered is True


def test_cross_tenant_access_denied(service):
    register_issue(service)

    with pytest.raises(PermissionError):
        service.get_issue(
            "issue-001",
            "another-tenant",
        )


def test_dispute_reopen_from_resolved_state(service):
    register_issue(service)

    service.update_status(
        IssueStatusUpdateRequest(
            issue_id="issue-001",
            tenant_id="tenant-1",
            status=IssueStatus.ASSIGNED,
            actor_id="operator-1",
        )
    )

    service.update_status(
        IssueStatusUpdateRequest(
            issue_id="issue-001",
            tenant_id="tenant-1",
            status=IssueStatus.ACCEPTED,
            actor_id="operator-1",
        )
    )

    service.update_status(
        IssueStatusUpdateRequest(
            issue_id="issue-001",
            tenant_id="tenant-1",
            status=IssueStatus.IN_PROGRESS,
            actor_id="operator-1",
        )
    )

    service.update_status(
        IssueStatusUpdateRequest(
            issue_id="issue-001",
            tenant_id="tenant-1",
            status=IssueStatus.RESOLUTION_PROPOSED,
            actor_id="operator-1",
        )
    )

    service.update_status(
        IssueStatusUpdateRequest(
            issue_id="issue-001",
            tenant_id="tenant-1",
            status=IssueStatus.RESOLVED_UNCONFIRMED,
            actor_id="operator-1",
        )
    )

    result = service.dispute_reopen(
        DisputeReopenRequest(
            issue_id="issue-001",
            tenant_id="tenant-1",
            actor_id="citizen-1",
            reason="Issue is still unresolved",
        )
    )

    assert result.status == IssueStatus.DISPUTED_REOPENED