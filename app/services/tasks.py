from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.authorization import AuthorizationEngine


class TaskService:
    """
    BE-009 — Task Engine & Evidence

    Responsibilities:
    - Task creation and lifecycle
    - Task assignment
    - Task delegation hierarchy
    - Due-date handling
    - Task transition history
    - Evidence registration
    - Evidence verification
    - Tenant isolation
    """

    def __init__(
        self,
        authorization_engine: Optional[AuthorizationEngine] = None,
    ) -> None:
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._evidence: Dict[str, Dict[str, Any]] = {}

        self.authorization_engine = (
            authorization_engine
            or AuthorizationEngine()
        )

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _validate_delegation(
        self,
        *,
        assigner_id: str,
        assignee_id: str,
        tenant_id: str,
    ) -> None:
        """
        TSK-02:
        Delegation is allowed only downward within the
        assigner's organizational subtree.
        """

        if not assigner_id:
            raise PermissionError(
                "Delegation actor is required."
            )

        if not assignee_id:
            raise ValueError(
                "Assignee is required."
            )

        if not self.authorization_engine.can_delegate_to(
            assigner_id=assigner_id,
            assignee_id=assignee_id,
            tenant_id=tenant_id,
        ):
            raise PermissionError(
                "Task delegation is allowed only to an "
                "active descendant within the same tenant."
            )

    # =========================================================
    # Task Creation
    # =========================================================

    def create_task(
        self,
        *,
        task_id: str,
        tenant_id: str,
        title: str,
        created_by: str,
        description: Optional[str] = None,
        assignee_id: Optional[str] = None,
        priority: str = "normal",
        due_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        if task_id in self._tasks:
            raise ValueError("Task already exists")

        if not title or not title.strip():
            raise ValueError("Task title is required")

        now = self._now()

        task = {
            "task_id": task_id,
            "tenant_id": tenant_id,
            "title": title,
            "description": description,
            "created_by": created_by,
            "assignee_id": assignee_id,
            "priority": priority,
            "status": "pending",
            "due_at": due_at,
            "created_at": now,
            "updated_at": now,
            "metadata": dict(metadata or {}),
            "history": [],
        }

        self._tasks[task_id] = task

        return dict(task)

    # =========================================================
    # Get Task
    # =========================================================

    def get_task(
        self,
        *,
        task_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:

        task = self._tasks.get(task_id)

        if task is None:
            return None

        if (
            tenant_id is not None
            and task["tenant_id"] != tenant_id
        ):
            return None

        return dict(task)

    # =========================================================
    # Update Task
    # =========================================================

    def update_task(
        self,
        *,
        task_id: str,
        tenant_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        assignee_id: Optional[str] = None,
        priority: Optional[str] = None,
        due_at: Optional[datetime] = None,
        status: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        updated_by: Optional[str] = None,
    ) -> Dict[str, Any]:

        task = self._tasks.get(task_id)

        if task is None:
            raise KeyError("Task not found")

        if task["tenant_id"] != tenant_id:
            raise PermissionError(
                "Cross-tenant task access denied"
            )

        if title is not None:
            if not title.strip():
                raise ValueError(
                    "Task title cannot be empty"
                )

            task["title"] = title

        if description is not None:
            task["description"] = description

        if assignee_id is not None:
            actor_id = (
                updated_by
                if updated_by is not None
                else task["created_by"]
            )

            self._validate_delegation(
                assigner_id=actor_id,
                assignee_id=assignee_id,
                tenant_id=tenant_id,
            )

            task["assignee_id"] = assignee_id

        if priority is not None:
            task["priority"] = priority

        if due_at is not None:
            task["due_at"] = due_at

        if status is not None:
            task["status"] = status

        if metadata is not None:
            task["metadata"] = dict(metadata)

        task["updated_at"] = self._now()

        return dict(task)

    # =========================================================
    # Task Lifecycle
    # =========================================================

    def task_action(
        self,
        *,
        task_id: str,
        tenant_id: str,
        action: str,
        requested_by: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:

        task = self._tasks.get(task_id)

        if task is None:
            raise KeyError("Task not found")

        if task["tenant_id"] != tenant_id:
            raise PermissionError(
                "Cross-tenant task access denied"
            )

        action = action.strip().lower()

        transitions = {
            "start": "in_progress",
            "complete": "completed",
            "cancel": "cancelled",
            "reopen": "pending",
            "assign": task["status"],
            "unassign": task["status"],
        }

        if action not in transitions:
            raise ValueError(
                "Unsupported task action"
            )

        # -----------------------------------------------------
        # TSK-02 delegation hierarchy
        # -----------------------------------------------------

        if action == "assign":
            assignee_id = task.get("assignee_id")

            if not assignee_id:
                raise ValueError(
                    "Task must have an assignee"
                )

            self._validate_delegation(
                assigner_id=requested_by,
                assignee_id=assignee_id,
                tenant_id=tenant_id,
            )

        # -----------------------------------------------------
        # Unassign
        # -----------------------------------------------------

        if action == "unassign":
            task["assignee_id"] = None

        # -----------------------------------------------------
        # Apply transition
        # -----------------------------------------------------

        task["status"] = transitions[action]

        task.setdefault("metadata", {})

        task["metadata"]["last_action"] = action
        task["metadata"]["last_action_by"] = requested_by

        if reason:
            task["metadata"]["last_action_reason"] = reason

        task["updated_at"] = self._now()

        # -----------------------------------------------------
        # Full transition history
        # -----------------------------------------------------

        task.setdefault("history", [])

        task["history"].append(
            {
                "action": action,
                "requested_by": requested_by,
                "status": task["status"],
                "timestamp": task["updated_at"],
                "reason": reason,
            }
        )

        return {
            "success": True,
            "task_id": task_id,
            "action": action,
            "status": task["status"],
            "assignee_id": task.get("assignee_id"),
            "history": list(task["history"]),
        }

    # =========================================================
    # Search Tasks
    # =========================================================

    def search_tasks(
        self,
        *,
        tenant_id: str,
        query: Optional[str] = None,
        assignee_id: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:

        if page < 1:
            raise ValueError(
                "Page must be greater than zero"
            )

        if page_size < 1:
            raise ValueError(
                "Page size must be greater than zero"
            )

        tasks = [
            task
            for task in self._tasks.values()
            if task["tenant_id"] == tenant_id
        ]

        if query:
            normalized_query = query.strip().lower()

            tasks = [
                task
                for task in tasks
                if (
                    normalized_query
                    in str(
                        task.get("title", "")
                    ).lower()
                    or normalized_query
                    in str(
                        task.get("description", "")
                    ).lower()
                )
            ]

        if assignee_id is not None:
            tasks = [
                task
                for task in tasks
                if task.get("assignee_id")
                == assignee_id
            ]

        if status is not None:
            tasks = [
                task
                for task in tasks
                if task.get("status") == status
            ]

        if priority is not None:
            tasks = [
                task
                for task in tasks
                if task.get("priority") == priority
            ]

        # -----------------------------------------------------
        # Overdue detection
        # -----------------------------------------------------

        now = self._now()

        for task in tasks:
            due_at = task.get("due_at")

            if (
                due_at is not None
                and due_at < now
                and task.get("status")
                not in {
                    "completed",
                    "cancelled",
                }
            ):
                task["status"] = "overdue"

        total = len(tasks)

        start = (page - 1) * page_size
        end = start + page_size

        paginated = tasks[start:end]

        return {
            "items": [
                dict(task)
                for task in paginated
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (
                (total + page_size - 1)
                // page_size
                if total
                else 0
            ),
        }

    # =========================================================
    # Evidence Registration
    # =========================================================

    def add_evidence(
        self,
        *,
        evidence_id: str,
        task_id: str,
        uploaded_by: str,
        file_name: Optional[str] = None,
        content_type: Optional[str] = None,
        size_bytes: int = 0,
        sha256: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        if evidence_id in self._evidence:
            raise ValueError(
                "Evidence already exists"
            )

        task = self._tasks.get(task_id)

        if task is None:
            raise KeyError("Task not found")

        if size_bytes < 0:
            raise ValueError(
                "Evidence size cannot be negative"
            )

        max_size = 25 * 1024 * 1024

        if size_bytes > max_size:
            raise ValueError(
                "Evidence exceeds maximum size of 25 MB"
            )

        now = self._now()

        evidence = {
            "evidence_id": evidence_id,
            "task_id": task_id,
            "tenant_id": task["tenant_id"],
            "uploaded_by": uploaded_by,
            "file_name": file_name,
            "content_type": content_type,
            "size_bytes": size_bytes,
            "sha256": sha256,
            "metadata": dict(metadata or {}),
            "created_at": now,
            "verified": False,
            "verified_by": None,
            "verified_at": None,
        }

        self._evidence[evidence_id] = evidence

        return dict(evidence)

    # =========================================================
    # Evidence Verification
    # =========================================================

    def verify_evidence(
        self,
        *,
        evidence_id: str,
        verified_by: str,
        expected_sha256: Optional[str] = None,
    ) -> Dict[str, Any]:

        evidence = self._evidence.get(evidence_id)

        if evidence is None:
            raise KeyError("Evidence not found")

        stored_hash = evidence.get("sha256")

        if expected_sha256 is not None:
            verified = (
                stored_hash is not None
                and stored_hash == expected_sha256
            )
        else:
            verified = stored_hash is not None

        now = self._now()

        evidence["verified"] = verified
        evidence["verified_by"] = verified_by
        evidence["verified_at"] = now

        return {
            "success": True,
            "evidence_id": evidence_id,
            "verified": verified,
            "verified_by": verified_by,
            "expected_sha256": expected_sha256,
            "actual_sha256": stored_hash,
            "sha256": stored_hash,
            "verified_at": now,
        }

    # =========================================================
    # Get Evidence
    # =========================================================

    def get_evidence(
        self,
        *,
        evidence_id: str,
        tenant_id: str,
    ) -> Optional[Dict[str, Any]]:

        evidence = self._evidence.get(evidence_id)

        if evidence is None:
            return None

        if evidence["tenant_id"] != tenant_id:
            return None

        return dict(evidence)

    # =========================================================
    # Task Statistics
    # =========================================================

    def statistics(
        self,
        *,
        tenant_id: str,
    ) -> Dict[str, Any]:

        tasks = [
            task
            for task in self._tasks.values()
            if task["tenant_id"] == tenant_id
        ]

        status_counts: Dict[str, int] = {}

        for task in tasks:
            status = str(
                task.get("status", "unknown")
            )

            status_counts[status] = (
                status_counts.get(status, 0) + 1
            )

        priority_counts: Dict[str, int] = {}

        for task in tasks:
            priority = str(
                task.get("priority", "unknown")
            )

            priority_counts[priority] = (
                priority_counts.get(priority, 0) + 1
            )

        evidence_count = sum(
            1
            for evidence in self._evidence.values()
            if evidence.get("tenant_id") == tenant_id
        )

        result: Dict[str, Any] = {
            "total": len(tasks),
            "total_tasks": len(tasks),
            "tenant_id": tenant_id,
            "evidence_count": evidence_count,
            "status_counts": status_counts,
            "priority_counts": priority_counts,
        }

        # Backward-compatible flat status counters.
        for status, count in status_counts.items():
            result[status] = count

        return result

    # =========================================================
    # Delegation Helpers
    # =========================================================

    def can_delegate(
        self,
        *,
        assigner_id: str,
        assignee_id: str,
        tenant_id: str,
    ) -> bool:

        return self.authorization_engine.can_delegate_to(
            assigner_id=assigner_id,
            assignee_id=assignee_id,
            tenant_id=tenant_id,
        )

    def get_delegation_targets(
        self,
        *,
        subject_id: str,
        tenant_id: str,
        active_only: bool = True,
    ) -> List[Dict[str, Any]]:

        return self.authorization_engine.get_descendants(
            subject_id=subject_id,
            tenant_id=tenant_id,
            active_only=active_only,
        )


# =============================================================
# Singleton Service
# =============================================================

task_service = TaskService()