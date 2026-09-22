from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List
from uuid import uuid4

from app.schemas.closure import (
    ClosureConfirmationRequest,
    ClosureConfirmationResponse,
    ClosureMetricsResponse,
    ClosureOutcome,
    ClosureConfirmationRequestView,
    ResolutionProposalRequest,
    ResolutionProposalResponse,
    ServiceDebtComponents,
    ServiceDebtIndexResponse,
)
from app.schemas.workflow import IssueStatus


class ClosureService:
    """
    BE-020:
    Citizen-verified closure and Service Debt Index.

    The service keeps closure state separate from the resolving worker.
    A worker can propose a resolution, but confirmation is performed
    independently by citizen confirmation requests.
    """

    def __init__(self) -> None:
        self._proposals: Dict[str, Dict[str, Any]] = {}
        self._confirmation_requests: Dict[str, Dict[str, Any]] = {}
        self._responses: Dict[str, Dict[str, Any]] = {}
        self._issues: Dict[str, Dict[str, Any]] = {}
        self._units: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _new_id(prefix: str) -> str:
        return f"{prefix}_{uuid4().hex[:12]}"

    def register_issue(
        self,
        *,
        issue_id: str,
        tenant_id: str,
        unit_id: str,
        severity: float = 1.0,
        corroboration_count: int = 0,
        created_at: datetime | None = None,
        sla_breached: bool = False,
    ) -> Dict[str, Any]:
        created_at = created_at or self._now()

        self._issues[issue_id] = {
            "issue_id": issue_id,
            "tenant_id": tenant_id,
            "unit_id": unit_id,
            "severity": max(0.0, min(1.0, severity)),
            "corroboration_count": max(0, corroboration_count),
            "created_at": created_at,
            "sla_breached": sla_breached,
            "status": IssueStatus.NEW,
            "resolution_claimed": False,
            "resolution_confirmed": False,
            "disputed": False,
        }

        return dict(self._issues[issue_id])

    def register_unit(
        self,
        *,
        tenant_id: str,
        unit_id: str,
        unit_size: float,
        intake_volume: float,
    ) -> Dict[str, Any]:
        if unit_size <= 0:
            raise ValueError("unit_size must be greater than zero")

        if intake_volume <= 0:
            raise ValueError("intake_volume must be greater than zero")

        key = (tenant_id, unit_id)

        self._units[key] = {
            "tenant_id": tenant_id,
            "unit_id": unit_id,
            "unit_size": unit_size,
            "intake_volume": intake_volume,
        }

        return dict(self._units[key])

    def propose_resolution(
        self,
        request: ResolutionProposalRequest,
    ) -> ResolutionProposalResponse:
        issue = self._get_issue(
            request.issue_id,
            request.tenant_id,
        )

        proposal_id = self._new_id("proposal")
        now = self._now()

        proposal = {
            "proposal_id": proposal_id,
            "issue_id": request.issue_id,
            "tenant_id": request.tenant_id,
            "worker_id": request.worker_id,
            "evidence": list(request.evidence),
            "resolution_summary": request.resolution_summary,
            "proposed_at": now,
            "status": "claimed",
        }

        self._proposals[proposal_id] = proposal

        issue["resolution_claimed"] = True
        issue["status"] = IssueStatus.RESOLUTION_PROPOSED

        return ResolutionProposalResponse(
            proposal_id=proposal_id,
            issue_id=request.issue_id,
            tenant_id=request.tenant_id,
            evidence=list(request.evidence),
            resolution_summary=request.resolution_summary,
            proposed_at=now,
            status="claimed",
        )

    def create_confirmation_request(
        self,
        *,
        proposal_id: str,
        citizen_id: str,
        language: str,
        wait_minutes: int = 1440,
    ) -> ClosureConfirmationRequestView:
        proposal = self._proposals.get(proposal_id)

        if proposal is None:
            raise KeyError("Resolution proposal not found")

        if wait_minutes <= 0:
            raise ValueError("wait_minutes must be greater than zero")

        request_id = self._new_id("confirm")
        created_at = self._now()
        expires_at = created_at + timedelta(minutes=wait_minutes)

        record = {
            "request_id": request_id,
            "proposal_id": proposal_id,
            "issue_id": proposal["issue_id"],
            "tenant_id": proposal["tenant_id"],
            "citizen_id": citizen_id,
            "language": language,
            "created_at": created_at,
            "expires_at": expires_at,
            "responded": False,
        }

        self._confirmation_requests[request_id] = record

        return ClosureConfirmationRequestView(**{
            key: record[key]
            for key in ClosureConfirmationRequestView.model_fields
        })

    def respond_to_confirmation(
        self,
        request: ClosureConfirmationRequest,
    ) -> ClosureConfirmationResponse:
        record = self._confirmation_requests.get(request.request_id)

        if record is None:
            raise KeyError("Confirmation request not found")

        if record["tenant_id"] != request.tenant_id:
            raise PermissionError("Cross-tenant confirmation denied")

        if record["citizen_id"] != request.citizen_id:
            raise PermissionError(
                "Confirmation request belongs to another citizen"
            )

        if record["responded"]:
            raise ValueError("Confirmation request already answered")

        now = self._now()

        if now > record["expires_at"]:
            raise ValueError("Confirmation request has expired")

        issue = self._get_issue(
            record["issue_id"],
            record["tenant_id"],
        )

        record["responded"] = True

        if request.confirmed:
            outcome = ClosureOutcome.CONFIRMED
            issue["resolution_confirmed"] = True
            issue["status"] = IssueStatus.RESOLVED_CONFIRMED
        else:
            outcome = ClosureOutcome.DISPUTED_REOPENED
            issue["disputed"] = True
            issue["status"] = IssueStatus.DISPUTED_REOPENED

        response = {
            "request_id": request.request_id,
            "issue_id": record["issue_id"],
            "citizen_id": request.citizen_id,
            "confirmed": request.confirmed,
            "outcome": outcome,
            "responded_at": now,
        }

        self._responses[request.request_id] = response

        return ClosureConfirmationResponse(**response)

    def finalize_expired_confirmations(
        self,
        *,
        tenant_id: str,
        now: datetime | None = None,
    ) -> List[ClosureConfirmationResponse]:
        now = now or self._now()
        results = []

        for request_id, record in self._confirmation_requests.items():
            if record["tenant_id"] != tenant_id:
                continue

            if record["responded"]:
                continue

            if now <= record["expires_at"]:
                continue

            issue = self._get_issue(
                record["issue_id"],
                tenant_id,
            )

            record["responded"] = True
            issue["status"] = IssueStatus.RESOLVED_UNCONFIRMED

            response = {
                "request_id": request_id,
                "issue_id": record["issue_id"],
                "citizen_id": record["citizen_id"],
                "confirmed": False,
                "outcome": ClosureOutcome.UNCONFIRMED,
                "responded_at": now,
            }

            self._responses[request_id] = response
            results.append(
                ClosureConfirmationResponse(**response)
            )

        return results

    def closure_metrics(
        self,
        *,
        tenant_id: str,
    ) -> ClosureMetricsResponse:
        issues = [
            issue
            for issue in self._issues.values()
            if issue["tenant_id"] == tenant_id
        ]

        claimed = sum(
            1 for issue in issues
            if issue["resolution_claimed"]
        )

        confirmed = sum(
            1 for issue in issues
            if issue["resolution_confirmed"]
        )

        unconfirmed = sum(
            1
            for issue in issues
            if issue["status"] == IssueStatus.RESOLVED_UNCONFIRMED
        )

        disputed = sum(
            1
            for issue in issues
            if issue["disputed"]
        )

        rate = (
            confirmed / claimed
            if claimed
            else 0.0
        )

        return ClosureMetricsResponse(
            tenant_id=tenant_id,
            claimed_resolutions=claimed,
            confirmed_resolutions=confirmed,
            unconfirmed_resolutions=unconfirmed,
            disputed_reopened=disputed,
            confirmation_rate=round(rate, 4),
        )

    def calculate_service_debt_index(
        self,
        *,
        tenant_id: str,
        unit_id: str,
    ) -> ServiceDebtIndexResponse:
        unit = self._units.get((tenant_id, unit_id))

        if unit is None:
            raise KeyError("Service unit not found")

        issues = [
            issue
            for issue in self._issues.values()
            if issue["tenant_id"] == tenant_id
            and issue["unit_id"] == unit_id
        ]

        unresolved = [
            issue
            for issue in issues
            if issue["status"]
            not in {
                IssueStatus.RESOLVED_CONFIRMED,
                IssueStatus.CLOSED,
                IssueStatus.REJECTED,
            }
        ]

        now = self._now()

        unresolved_volume_weight = float(len(unresolved))

        age_weight = sum(
            min(
                (now - issue["created_at"]).total_seconds()
                / 86400.0,
                30.0,
            )
            for issue in unresolved
        )

        severity_weight = sum(
            issue["severity"]
            for issue in unresolved
        )

        confirmed_rate = (
            sum(
                1
                for issue in issues
                if issue["resolution_confirmed"]
            )
            / len(issues)
            if issues
            else 0.0
        )

        confirmed_resolution_rate = 1.0 - confirmed_rate

        corroboration_weight = sum(
            issue["corroboration_count"]
            * max(issue["severity"], 0.1)
            for issue in unresolved
        )

        sla_breach_frequency = (
            sum(
                1
                for issue in issues
                if issue["sla_breached"]
            )
            / len(issues)
            if issues
            else 0.0
        )

        unit_size_normalization = 1.0 / unit["unit_size"]
        intake_normalization = 1.0 / unit["intake_volume"]

        raw_index = (
            unresolved_volume_weight
            + age_weight
            + severity_weight
            + confirmed_resolution_rate * 10.0
            + corroboration_weight
            + sla_breach_frequency * 10.0
        )

        normalized_index = (
            raw_index
            * unit_size_normalization
            * intake_normalization
        )

        components = ServiceDebtComponents(
            unresolved_volume_weight=round(
                unresolved_volume_weight,
                4,
            ),
            age_weight=round(age_weight, 4),
            severity_weight=round(severity_weight, 4),
            confirmed_resolution_rate=round(
                confirmed_resolution_rate,
                4,
            ),
            corroboration_weight=round(
                corroboration_weight,
                4,
            ),
            sla_breach_frequency=round(
                sla_breach_frequency,
                4,
            ),
            unit_size_normalization=round(
                unit_size_normalization,
                4,
            ),
            intake_normalization=round(
                intake_normalization,
                4,
            ),
        )

        return ServiceDebtIndexResponse(
            tenant_id=tenant_id,
            unit_id=unit_id,
            index=round(normalized_index, 4),
            components=components,
            unresolved_issue_ids=[
                issue["issue_id"]
                for issue in unresolved
            ],
            drill_through={
                "issue_count": len(issues),
                "unresolved_count": len(unresolved),
                "confirmed_count": sum(
                    1
                    for issue in issues
                    if issue["resolution_confirmed"]
                ),
                "sla_breached_count": sum(
                    1
                    for issue in issues
                    if issue["sla_breached"]
                ),
            },
        )

    def get_confirmation_request(
        self,
        *,
        request_id: str,
        tenant_id: str,
    ) -> ClosureConfirmationRequestView:
        record = self._confirmation_requests.get(request_id)

        if record is None:
            raise KeyError("Confirmation request not found")

        if record["tenant_id"] != tenant_id:
            raise PermissionError(
                "Cross-tenant confirmation access denied"
            )

        return ClosureConfirmationRequestView(**{
            key: record[key]
            for key in ClosureConfirmationRequestView.model_fields
        })

    def _get_issue(
        self,
        issue_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:
        issue = self._issues.get(issue_id)

        if issue is None:
            raise KeyError("Citizen issue not found")

        if issue["tenant_id"] != tenant_id:
            raise PermissionError(
                "Cross-tenant citizen issue access denied"
            )

        return issue


closure_service = ClosureService()