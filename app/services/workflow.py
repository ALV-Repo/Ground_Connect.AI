from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.schemas.workflow import (
    DisputeReopenRequest,
    EscalationEvent,
    IssueStatus,
    IssueStatusResponse,
    IssueStatusUpdateRequest,
    RejectionRequest,
    SLAConfigCreate,
    SLAConfigResponse,
    SLAStatusResponse,
    WorkflowIssueResponse,
)


class WorkflowService:
    def __init__(self):
        self._sla_configs = {}
        self._issues = {}
        self._escalations = {}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def configure_sla(self, request: SLAConfigCreate) -> SLAConfigResponse:
        config_id = f"sla_{uuid4().hex[:12]}"
        created_at = self._now()

        config = {
            "config_id": config_id,
            "tenant_id": request.tenant_id,
            "category": request.category,
            "priority": request.priority,
            "response_target_minutes": request.response_target_minutes,
            "resolution_target_minutes": request.resolution_target_minutes,
            "escalation_chain": list(request.escalation_chain),
            "created_at": created_at,
        }

        self._sla_configs[config_id] = config
        return SLAConfigResponse(**config)

    def register_issue(
        self,
        issue_id: str,
        tenant_id: str,
        category: str,
        priority: str,
        created_at: datetime | None = None,
    ) -> WorkflowIssueResponse:
        created_at = created_at or self._now()

        config = self._find_sla_config(
            tenant_id,
            category,
            priority,
        )

        response_due_at = None
        resolution_due_at = None

        if config:
            response_due_at = created_at + timedelta(
                minutes=config["response_target_minutes"]
            )
            resolution_due_at = created_at + timedelta(
                minutes=config["resolution_target_minutes"]
            )

        initial = IssueStatusResponse(
            issue_id=issue_id,
            tenant_id=tenant_id,
            status=IssueStatus.NEW,
            changed_at=created_at,
            actor_id="system",
            reason=None,
        )

        self._issues[issue_id] = {
            "issue_id": issue_id,
            "tenant_id": tenant_id,
            "category": category,
            "priority": priority,
            "created_at": created_at,
            "status": IssueStatus.NEW,
            "status_history": [initial],
            "response_due_at": response_due_at,
            "resolution_due_at": resolution_due_at,
            "response_breached": False,
            "resolution_breached": False,
        }

        self._escalations[issue_id] = []

        return self.get_issue(issue_id, tenant_id)

    def _find_sla_config(
        self,
        tenant_id: str,
        category: str,
        priority: str,
    ):
        matches = [
            config
            for config in self._sla_configs.values()
            if config["tenant_id"] == tenant_id
            and config["category"] == category
            and config["priority"] == priority
        ]

        return matches[-1] if matches else None

    def update_status(
        self,
        request: IssueStatusUpdateRequest,
    ) -> WorkflowIssueResponse:
        issue = self._get_issue(
            request.issue_id,
            request.tenant_id,
        )

        self._validate_transition(
            issue["status"],
            request.status,
        )

        changed_at = self._now()

        record = IssueStatusResponse(
            issue_id=request.issue_id,
            tenant_id=request.tenant_id,
            status=request.status,
            changed_at=changed_at,
            actor_id=request.actor_id,
            reason=request.reason,
        )

        issue["status"] = request.status
        issue["status_history"].append(record)

        return self.get_issue(
            request.issue_id,
            request.tenant_id,
        )

    @staticmethod
    def _validate_transition(
        current: IssueStatus,
        target: IssueStatus,
    ):
        allowed = {
            IssueStatus.NEW: {
                IssueStatus.ASSIGNED,
                IssueStatus.REJECTED,
            },
            IssueStatus.ASSIGNED: {
                IssueStatus.ACCEPTED,
                IssueStatus.ESCALATED,
                IssueStatus.REJECTED,
            },
            IssueStatus.ACCEPTED: {
                IssueStatus.IN_PROGRESS,
                IssueStatus.ESCALATED,
            },
            IssueStatus.IN_PROGRESS: {
                IssueStatus.WAITING,
                IssueStatus.RESOLUTION_PROPOSED,
                IssueStatus.ESCALATED,
            },
            IssueStatus.WAITING: {
                IssueStatus.IN_PROGRESS,
                IssueStatus.ESCALATED,
            },
            IssueStatus.ESCALATED: {
                IssueStatus.IN_PROGRESS,
                IssueStatus.RESOLUTION_PROPOSED,
            },
            IssueStatus.RESOLUTION_PROPOSED: {
                IssueStatus.RESOLVED_CONFIRMED,
                IssueStatus.RESOLVED_UNCONFIRMED,
                IssueStatus.DISPUTED_REOPENED,
            },
            IssueStatus.RESOLVED_CONFIRMED: {
                IssueStatus.CLOSED,
                IssueStatus.DISPUTED_REOPENED,
            },
            IssueStatus.RESOLVED_UNCONFIRMED: {
                IssueStatus.CLOSED,
                IssueStatus.DISPUTED_REOPENED,
            },
            IssueStatus.DISPUTED_REOPENED: {
                IssueStatus.IN_PROGRESS,
                IssueStatus.ESCALATED,
            },
            IssueStatus.CLOSED: set(),
            IssueStatus.REJECTED: set(),
        }

        if target not in allowed.get(current, set()):
            raise ValueError(
                f"Invalid workflow transition: "
                f"{current.value} -> {target.value}"
            )

    def reject_issue(
        self,
        request: RejectionRequest,
    ) -> WorkflowIssueResponse:
        return self.update_status(
            IssueStatusUpdateRequest(
                issue_id=request.issue_id,
                tenant_id=request.tenant_id,
                status=IssueStatus.REJECTED,
                actor_id=request.actor_id,
                reason=request.reason,
            )
        )

    def dispute_reopen(
        self,
        request: DisputeReopenRequest,
    ) -> WorkflowIssueResponse:
        issue = self._get_issue(
            request.issue_id,
            request.tenant_id,
        )

        if issue["status"] not in {
            IssueStatus.RESOLVED_CONFIRMED,
            IssueStatus.RESOLVED_UNCONFIRMED,
            IssueStatus.CLOSED,
        }:
            raise ValueError(
                "Only resolved or closed issues can be disputed and reopened"
            )

        return self.update_status(
            IssueStatusUpdateRequest(
                issue_id=request.issue_id,
                tenant_id=request.tenant_id,
                status=IssueStatus.DISPUTED_REOPENED,
                actor_id=request.actor_id,
                reason=request.reason,
            )
        )

    def check_sla(
        self,
        issue_id: str,
        tenant_id: str,
        now: datetime | None = None,
    ) -> SLAStatusResponse:
        issue = self._get_issue(issue_id, tenant_id)
        now = now or self._now()

        response_breached = (
            issue["response_due_at"] is not None
            and issue["status"] == IssueStatus.NEW
            and now >= issue["response_due_at"]
        )

        resolution_breached = (
            issue["resolution_due_at"] is not None
            and issue["status"]
            not in {
                IssueStatus.RESOLVED_CONFIRMED,
                IssueStatus.RESOLVED_UNCONFIRMED,
                IssueStatus.CLOSED,
                IssueStatus.REJECTED,
            }
            and now >= issue["resolution_due_at"]
        )

        issue["response_breached"] |= response_breached
        issue["resolution_breached"] |= resolution_breached

        if response_breached or resolution_breached:
            reason = (
                "response_sla_breach"
                if response_breached
                else "resolution_sla_breach"
            )

            self._trigger_escalation(issue, reason, now)

        escalations = self._escalations.get(issue_id, [])

        return SLAStatusResponse(
            issue_id=issue_id,
            tenant_id=tenant_id,
            response_due_at=issue["response_due_at"],
            resolution_due_at=issue["resolution_due_at"],
            response_breached=issue["response_breached"],
            resolution_breached=issue["resolution_breached"],
            escalation_triggered=bool(escalations),
            current_escalation_level=len(escalations),
        )

    def _trigger_escalation(
        self,
        issue: dict,
        reason: str,
        now: datetime,
    ):
        existing = self._escalations.setdefault(
            issue["issue_id"],
            [],
        )

        config = self._find_sla_config(
            issue["tenant_id"],
            issue["category"],
            issue["priority"],
        )

        if not config:
            return

        next_level = len(existing) + 1

        if next_level > len(config["escalation_chain"]):
            return

        target = config["escalation_chain"][next_level - 1]

        event = EscalationEvent(
            event_id=f"esc_{uuid4().hex[:12]}",
            issue_id=issue["issue_id"],
            tenant_id=issue["tenant_id"],
            level=next_level,
            target=target,
            reason=reason,
            triggered_at=now,
            deterministic_policy=True,
        )

        existing.append(event)

        if issue["status"] != IssueStatus.ESCALATED:
            issue["status"] = IssueStatus.ESCALATED

            issue["status_history"].append(
                IssueStatusResponse(
                    issue_id=issue["issue_id"],
                    tenant_id=issue["tenant_id"],
                    status=IssueStatus.ESCALATED,
                    changed_at=now,
                    actor_id="sla-policy-engine",
                    reason=reason,
                )
            )

    def get_issue(
        self,
        issue_id: str,
        tenant_id: str,
    ) -> WorkflowIssueResponse:
        issue = self._get_issue(issue_id, tenant_id)

        return WorkflowIssueResponse(
            issue_id=issue["issue_id"],
            tenant_id=issue["tenant_id"],
            status=issue["status"],
            created_at=issue["created_at"],
            status_history=list(issue["status_history"]),
            escalations=list(
                self._escalations.get(issue_id, [])
            ),
        )

    def get_escalations(
        self,
        issue_id: str,
        tenant_id: str,
    ):
        self._get_issue(issue_id, tenant_id)
        return list(
            self._escalations.get(issue_id, [])
        )

    def _get_issue(
        self,
        issue_id: str,
        tenant_id: str,
    ):
        issue = self._issues.get(issue_id)

        if not issue:
            raise KeyError(
                f"Issue not found: {issue_id}"
            )

        if issue["tenant_id"] != tenant_id:
            raise PermissionError(
                "Cross-tenant issue access denied"
            )

        return issue


workflow_service = WorkflowService()
