from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.closure import (
    ClosureConfirmationRequest,
    ClosureOutcome,
    ResolutionProposalRequest,
)
from app.services.closure import ClosureService


@pytest.fixture
def service():
    return ClosureService()


def setup_issue(service):
    service.register_unit(
        tenant_id="tenant-1",
        unit_id="unit-1",
        unit_size=100,
        intake_volume=1000,
    )

    service.register_issue(
        issue_id="issue-001",
        tenant_id="tenant-1",
        unit_id="unit-1",
        severity=0.8,
        corroboration_count=3,
        sla_breached=True,
    )


def create_proposal(service):
    return service.propose_resolution(
        ResolutionProposalRequest(
            issue_id="issue-001",
            tenant_id="tenant-1",
            worker_id="worker-1",
            evidence=["photo:evidence-001"],
            resolution_summary="Pothole repaired",
        )
    )


def test_register_issue(service):
    setup_issue(service)

    result = service._issues["issue-001"]

    assert result["tenant_id"] == "tenant-1"
    assert result["unit_id"] == "unit-1"
    assert result["corroboration_count"] == 3


def test_resolution_proposal_requires_evidence():
    with pytest.raises(ValueError):
        ResolutionProposalRequest(
            issue_id="issue-001",
            tenant_id="tenant-1",
            worker_id="worker-1",
            evidence=[],
            resolution_summary="Completed",
        )


def test_resolution_proposal(service):
    setup_issue(service)

    result = create_proposal(service)

    assert result.issue_id == "issue-001"
    assert result.status == "claimed"
    assert result.evidence == ["photo:evidence-001"]


def test_confirmation_request(service):
    setup_issue(service)

    proposal = create_proposal(service)

    result = service.create_confirmation_request(
        proposal_id=proposal.proposal_id,
        citizen_id="citizen-001",
        language="hi",
        wait_minutes=60,
    )

    assert result.issue_id == "issue-001"
    assert result.citizen_id == "citizen-001"
    assert result.language == "hi"
    assert result.responded is False


def test_confirmed_resolution(service):
    setup_issue(service)

    proposal = create_proposal(service)

    confirmation = service.create_confirmation_request(
        proposal_id=proposal.proposal_id,
        citizen_id="citizen-001",
        language="hi",
    )

    result = service.respond_to_confirmation(
        ClosureConfirmationRequest(
            request_id=confirmation.request_id,
            tenant_id="tenant-1",
            citizen_id="citizen-001",
            confirmed=True,
            response_language="hi",
        )
    )

    assert result.confirmed is True
    assert result.outcome == ClosureOutcome.CONFIRMED
    assert (
        service._issues["issue-001"]["resolution_confirmed"]
        is True
    )


def test_dispute_reopens_issue(service):
    setup_issue(service)

    proposal = create_proposal(service)

    confirmation = service.create_confirmation_request(
        proposal_id=proposal.proposal_id,
        citizen_id="citizen-001",
        language="hi",
    )

    result = service.respond_to_confirmation(
        ClosureConfirmationRequest(
            request_id=confirmation.request_id,
            tenant_id="tenant-1",
            citizen_id="citizen-001",
            confirmed=False,
            response_language="hi",
        )
    )

    assert result.outcome == ClosureOutcome.DISPUTED_REOPENED
    assert service._issues["issue-001"]["disputed"] is True


def test_expired_confirmation_becomes_unconfirmed(service):
    setup_issue(service)

    proposal = create_proposal(service)

    confirmation = service.create_confirmation_request(
        proposal_id=proposal.proposal_id,
        citizen_id="citizen-001",
        language="hi",
        wait_minutes=1,
    )

    future_time = datetime.now(timezone.utc) + timedelta(minutes=2)

    results = service.finalize_expired_confirmations(
        tenant_id="tenant-1",
        now=future_time,
    )

    assert len(results) == 1
    assert results[0].outcome == ClosureOutcome.UNCONFIRMED
    assert (
        service._issues["issue-001"]["status"].value
        == "Resolved-Unconfirmed"
    )


def test_confirmation_cannot_be_answered_by_another_citizen(service):
    setup_issue(service)

    proposal = create_proposal(service)

    confirmation = service.create_confirmation_request(
        proposal_id=proposal.proposal_id,
        citizen_id="citizen-001",
        language="hi",
    )

    with pytest.raises(PermissionError):
        service.respond_to_confirmation(
            ClosureConfirmationRequest(
                request_id=confirmation.request_id,
                tenant_id="tenant-1",
                citizen_id="citizen-999",
                confirmed=True,
                response_language="hi",
            )
        )


def test_closure_metrics_separate_claimed_and_confirmed(service):
    setup_issue(service)

    proposal = create_proposal(service)

    confirmation = service.create_confirmation_request(
        proposal_id=proposal.proposal_id,
        citizen_id="citizen-001",
        language="hi",
    )

    service.respond_to_confirmation(
        ClosureConfirmationRequest(
            request_id=confirmation.request_id,
            tenant_id="tenant-1",
            citizen_id="citizen-001",
            confirmed=True,
            response_language="hi",
        )
    )

    metrics = service.closure_metrics(
        tenant_id="tenant-1",
    )

    assert metrics.claimed_resolutions == 1
    assert metrics.confirmed_resolutions == 1
    assert metrics.confirmation_rate == 1.0


def test_service_debt_index_has_component_breakdown(service):
    setup_issue(service)

    result = service.calculate_service_debt_index(
        tenant_id="tenant-1",
        unit_id="unit-1",
    )

    assert result.tenant_id == "tenant-1"
    assert result.unit_id == "unit-1"
    assert result.index >= 0

    assert result.components.unresolved_volume_weight >= 0
    assert result.components.age_weight >= 0
    assert result.components.severity_weight >= 0
    assert result.components.corroboration_weight >= 0
    assert result.components.sla_breach_frequency >= 0

    assert "issue-001" in result.unresolved_issue_ids
    assert result.drill_through["unresolved_count"] == 1


def test_cross_tenant_confirmation_is_denied(service):
    setup_issue(service)

    proposal = create_proposal(service)

    confirmation = service.create_confirmation_request(
        proposal_id=proposal.proposal_id,
        citizen_id="citizen-001",
        language="hi",
    )

    with pytest.raises(PermissionError):
        service.respond_to_confirmation(
            ClosureConfirmationRequest(
                request_id=confirmation.request_id,
                tenant_id="tenant-2",
                citizen_id="citizen-001",
                confirmed=True,
                response_language="hi",
            )
        )