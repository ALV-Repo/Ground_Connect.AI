from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.config import settings


class MemberService:
    """
    BE-006 — Member Lifecycle & Bulk Import

    Provides:
    - Member creation
    - Member retrieval/search
    - Member updates
    - Lifecycle actions
    - Bulk import
    - Tenant isolation
    """

    def __init__(self) -> None:
        self._members: Dict[str, Dict[str, Any]] = {}

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_member(member: Dict[str, Any]) -> Dict[str, Any]:
        return {
            **member,
            "metadata": dict(member.get("metadata") or {}),
        }

    # =========================================================
    # Create
    # =========================================================

    def create_member(
        self,
        *,
        member_id: str,
        tenant_id: str,
        name: str,
        role: str = "member",
        branch_id: Optional[str] = None,
        mobile: Optional[str] = None,
        email: Optional[str] = None,
        status: str = "active",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Create a new member.

        Duplicate member IDs are rejected.
        """

        if member_id in self._members:
            raise ValueError("Member already exists")

        now = self._now()

        member = {
            "member_id": member_id,
            "tenant_id": tenant_id,
            "branch_id": branch_id,
            "name": name,
            "mobile": mobile,
            "email": email,
            "role": role,
            "status": status,
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
        }

        self._members[member_id] = member

        return self._normalize_member(member)

    # =========================================================
    # Get
    # =========================================================

    def get_member(
        self,
        *,
        member_id: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve a member.

        If tenant_id is supplied, cross-tenant access is denied.
        """

        member = self._members.get(member_id)

        if member is None:
            return None

        if tenant_id is not None and member["tenant_id"] != tenant_id:
            return None

        return self._normalize_member(member)

    # =========================================================
    # Update
    # =========================================================

    def update_member(
        self,
        *,
        member_id: str,
        tenant_id: str,
        name: Optional[str] = None,
        mobile: Optional[str] = None,
        email: Optional[str] = None,
        role: Optional[str] = None,
        status: Optional[str] = None,
        branch_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Update an existing member within its tenant.
        """

        member = self._members.get(member_id)

        if member is None:
            raise KeyError("Member not found")

        if member["tenant_id"] != tenant_id:
            raise PermissionError("Cross-tenant member access denied")

        if name is not None:
            member["name"] = name

        if mobile is not None:
            member["mobile"] = mobile

        if email is not None:
            member["email"] = email

        if role is not None:
            member["role"] = role

        if status is not None:
            member["status"] = status

        if branch_id is not None:
            member["branch_id"] = branch_id

        if metadata is not None:
            member["metadata"] = dict(metadata)

        member["updated_at"] = self._now()

        return self._normalize_member(member)

    # =========================================================
    # Lifecycle
    # =========================================================

    def lifecycle_action(
        self,
        *,
        member_id: str,
        tenant_id: str,
        action: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Apply a lifecycle state transition.
        """

        member = self._members.get(member_id)

        if member is None:
            raise KeyError("Member not found")

        if member["tenant_id"] != tenant_id:
            raise PermissionError("Cross-tenant member access denied")

        transitions = {
            "activate": "active",
            "deactivate": "inactive",
            "suspend": "suspended",
            "restore": "active",
        }

        if action not in transitions:
            raise ValueError("Unsupported lifecycle action")

        member["status"] = transitions[action]

        if reason:
            member.setdefault("metadata", {})["lifecycle_reason"] = reason

        member["updated_at"] = self._now()

        return self._normalize_member(member)

    # =========================================================
    # Delete
    # =========================================================

    def delete_member(
        self,
        *,
        member_id: str,
        tenant_id: str,
        reason: Optional[str] = None,
    ) -> bool:
        """
        Delete a member from the service store.

        In production this should normally be replaced by
        a soft-delete/audited database operation.
        """

        member = self._members.get(member_id)

        if member is None:
            return False

        if member["tenant_id"] != tenant_id:
            raise PermissionError("Cross-tenant member access denied")

        if reason:
            member.setdefault("metadata", {})["deletion_reason"] = reason

        del self._members[member_id]

        return True

    # =========================================================
    # Search
    # =========================================================

    def search_members(
        self,
        *,
        tenant_id: str,
        query: Optional[str] = None,
        branch_id: Optional[str] = None,
        status: Optional[str] = None,
        role: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Search members within one tenant.
        """

        members = [
            member
            for member in self._members.values()
            if member["tenant_id"] == tenant_id
        ]

        if branch_id is not None:
            members = [
                member
                for member in members
                if member.get("branch_id") == branch_id
            ]

        if status is not None:
            members = [
                member
                for member in members
                if member.get("status") == status
            ]

        if role is not None:
            members = [
                member
                for member in members
                if member.get("role") == role
            ]

        if query:
            query_lower = query.lower()

            members = [
                member
                for member in members
                if (
                    query_lower in str(member.get("member_id", "")).lower()
                    or query_lower in str(member.get("name", "")).lower()
                    or query_lower in str(member.get("mobile", "")).lower()
                    or query_lower in str(member.get("email", "")).lower()
                )
            ]

        total = len(members)

        start = (page - 1) * page_size
        end = start + page_size

        paginated = members[start:end]

        return {
            "items": [
                self._normalize_member(member)
                for member in paginated
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    # =========================================================
    # Bulk Import
    # =========================================================

    def bulk_import(
        self,
        *,
        tenant_id: str,
        records: List[Dict[str, Any]],
        source: str = "api",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Bulk create/update members.

        Existing member IDs are updated.
        New member IDs are created.

        The configured maximum import size is enforced.
        """

        max_records = getattr(
            settings,
            "member_import_max_records",
            10000,
        )

        if len(records) > max_records:
            raise ValueError(
                f"Maximum bulk import size is {max_records}"
            )

        imported = 0
        updated = 0
        skipped = 0
        failed = 0

        errors: List[str] = []

        for index, record in enumerate(records):
            try:
                record_tenant = record.get("tenant_id")

                if record_tenant != tenant_id:
                    failed += 1
                    errors.append(
                        f"Record {index}: tenant mismatch"
                    )
                    continue

                member_id = record.get("member_id")

                if not member_id:
                    failed += 1
                    errors.append(
                        f"Record {index}: member_id is required"
                    )
                    continue

                if dry_run:
                    if member_id in self._members:
                        updated += 1
                    else:
                        imported += 1

                    continue

                existing = self._members.get(member_id)

                if existing:
                    if existing["tenant_id"] != tenant_id:
                        failed += 1
                        errors.append(
                            f"Record {index}: cross-tenant update denied"
                        )
                        continue

                    now = self._now()

                    existing.update(
                        {
                            "branch_id": record.get(
                                "branch_id",
                                existing.get("branch_id"),
                            ),
                            "name": record.get(
                                "name",
                                existing.get("name"),
                            ),
                            "mobile": record.get(
                                "mobile",
                                existing.get("mobile"),
                            ),
                            "email": record.get(
                                "email",
                                existing.get("email"),
                            ),
                            "role": record.get(
                                "role",
                                existing.get("role", "member"),
                            ),
                            "status": record.get(
                                "status",
                                existing.get("status", "active"),
                            ),
                            "metadata": record.get(
                                "metadata",
                                existing.get("metadata", {}),
                            ),
                            "updated_at": now,
                        }
                    )

                    updated += 1

                else:
                    now = self._now()

                    self._members[member_id] = {
                        "member_id": member_id,
                        "tenant_id": tenant_id,
                        "branch_id": record.get("branch_id"),
                        "name": record.get("name", ""),
                        "mobile": record.get("mobile"),
                        "email": record.get("email"),
                        "role": record.get("role", "member"),
                        "status": record.get("status", "active"),
                        "metadata": record.get("metadata", {}),
                        "created_at": now,
                        "updated_at": now,
                    }

                    imported += 1

            except Exception as exc:
                failed += 1
                errors.append(
                    f"Record {index}: {str(exc)}"
                )

        return {
            "imported": imported,
            "updated": updated,
            "skipped": skipped,
            "failed": failed,
            "errors": errors,
            "source": source,
            "dry_run": dry_run,
        }

    # =========================================================
    # Statistics
    # =========================================================

    def statistics(
        self,
        *,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Return member statistics.
        """

        members = list(self._members.values())

        if tenant_id is not None:
            members = [
                member
                for member in members
                if member["tenant_id"] == tenant_id
            ]

        statistics: Dict[str, int] = {
            "total": len(members),
            "active": 0,
            "inactive": 0,
            "suspended": 0,
            "pending": 0,
        }

        for member in members:
            status = member.get("status", "active")

            if status in statistics:
                statistics[status] += 1

        return statistics


# Global service instance
member_service = MemberService()