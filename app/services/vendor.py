from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.config import settings


class VendorElevationService:
    """
    BE-010 — Vendor Support Elevation

    Provides:
    - Vendor elevation requests
    - Time-limited elevation
    - Approval/status tracking
    - Active elevation checks
    - Expiry handling
    - Elevation revocation
    - Tenant isolation
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._elevations: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def request_elevation(
        self,
        *,
        vendor_id: str,
        tenant_id: str,
        requested_by: str,
        reason: str,
        duration_minutes: Optional[int] = None,
        scopes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:

        if not vendor_id.strip():
            raise ValueError("vendor_id is required")

        if not tenant_id.strip():
            raise ValueError("tenant_id is required")

        if not requested_by.strip():
            raise ValueError("requested_by is required")

        if not reason.strip():
            raise ValueError("reason is required")

        max_duration = getattr(
            settings,
            "vendor_elevation_max_minutes",
            60,
        )

        duration = (
            duration_minutes
            if duration_minutes is not None
            else max_duration
        )

        if duration <= 0:
            raise ValueError(
                "duration_minutes must be greater than zero"
            )

        if duration > max_duration:
            raise ValueError(
                f"Maximum elevation duration is "
                f"{max_duration} minutes"
            )

        now = self._now()
        elevation_id = str(uuid4())

        record = {
            "elevation_id": elevation_id,
            "vendor_id": vendor_id,
            "tenant_id": tenant_id,
            "requested_by": requested_by,
            "reason": reason,
            "scopes": scopes or [],
            "status": "pending",
            "requested_at": now,
            "approved_at": None,
            "approved_by": None,
            "expires_at": now + timedelta(
                minutes=duration
            ),
            "revoked_at": None,
            "revoked_by": None,
            "duration_minutes": duration,
        }

        with self._lock:
            self._elevations[elevation_id] = record

        return dict(record)

    def get_elevation(
        self,
        *,
        elevation_id: str,
        tenant_id: str,
    ) -> Dict[str, Any]:

        with self._lock:
            record = self._elevations.get(elevation_id)

        if record is None:
            raise KeyError(
                "Elevation request not found"
            )

        if record["tenant_id"] != tenant_id:
            raise PermissionError(
                "Cross-tenant elevation access denied"
            )

        self._expire_if_needed(record)

        return dict(record)

    def approve_elevation(
        self,
        *,
        elevation_id: str,
        tenant_id: str,
        approved_by: str,
    ) -> Dict[str, Any]:

        record = self.get_elevation(
            elevation_id=elevation_id,
            tenant_id=tenant_id,
        )

        if record["status"] != "pending":
            raise ValueError(
                f"Elevation cannot be approved from "
                f"status {record['status']}"
            )

        if record["requested_by"] == approved_by:
            raise PermissionError(
                "Requester cannot approve their own elevation"
            )

        now = self._now()

        record["status"] = "active"
        record["approved_at"] = now
        record["approved_by"] = approved_by

        with self._lock:
            self._elevations[elevation_id] = record

        return dict(record)

    def reject_elevation(
        self,
        *,
        elevation_id: str,
        tenant_id: str,
        rejected_by: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:

        record = self.get_elevation(
            elevation_id=elevation_id,
            tenant_id=tenant_id,
        )

        if record["status"] != "pending":
            raise ValueError(
                f"Elevation cannot be rejected from "
                f"status {record['status']}"
            )

        now = self._now()

        record["status"] = "rejected"
        record["revoked_at"] = now
        record["revoked_by"] = rejected_by

        if reason:
            record["rejection_reason"] = reason

        with self._lock:
            self._elevations[elevation_id] = record

        return dict(record)

    def _expire_if_needed(
        self,
        record: Dict[str, Any],
    ) -> None:

        if (
            record["status"] == "active"
            and record["expires_at"] <= self._now()
        ):
            record["status"] = "expired"

            with self._lock:
                self._elevations[
                    record["elevation_id"]
                ] = record

    def is_active(
        self,
        *,
        elevation_id: str,
        tenant_id: str,
    ) -> bool:

        record = self.get_elevation(
            elevation_id=elevation_id,
            tenant_id=tenant_id,
        )

        return record["status"] == "active"

    def revoke_elevation(
        self,
        *,
        elevation_id: str,
        tenant_id: str,
        revoked_by: str,
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:

        record = self.get_elevation(
            elevation_id=elevation_id,
            tenant_id=tenant_id,
        )

        if record["status"] not in {
            "active",
            "pending",
        }:
            raise ValueError(
                f"Elevation cannot be revoked from "
                f"status {record['status']}"
            )

        now = self._now()

        record["status"] = "revoked"
        record["revoked_at"] = now
        record["revoked_by"] = revoked_by

        if reason:
            record["revocation_reason"] = reason

        with self._lock:
            self._elevations[elevation_id] = record

        return dict(record)

    def list_elevations(
        self,
        *,
        tenant_id: str,
        vendor_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:

        if limit <= 0:
            raise ValueError(
                "limit must be greater than zero"
            )

        with self._lock:
            records = [
                dict(record)
                for record in self._elevations.values()
                if record["tenant_id"] == tenant_id
            ]

        for record in records:
            self._expire_if_needed(record)

        if vendor_id:
            records = [
                record
                for record in records
                if record["vendor_id"] == vendor_id
            ]

        if status:
            records = [
                record
                for record in records
                if record["status"] == status
            ]

        records.sort(
            key=lambda item: item["requested_at"],
            reverse=True,
        )

        return records[:limit]

    def cleanup_expired(self) -> Dict[str, Any]:
        """
        Mark active elevations that have passed their
        expiry time as expired.
        """

        now = self._now()
        expired_count = 0

        with self._lock:
            for record in self._elevations.values():
                if (
                    record["status"] == "active"
                    and record["expires_at"] <= now
                ):
                    record["status"] = "expired"
                    expired_count += 1

        return {
            "success": True,
            "expired_count": expired_count,
            "checked_at": now,
        }

    def statistics(
        self,
        *,
        tenant_id: str,
    ) -> Dict[str, Any]:

        records = self.list_elevations(
            tenant_id=tenant_id,
            limit=100000,
        )

        counts: Dict[str, int] = {}

        for record in records:
            status = record["status"]
            counts[status] = (
                counts.get(status, 0) + 1
            )

        return {
            "tenant_id": tenant_id,
            "total": len(records),
            "by_status": counts,
        }


vendor_elevation_service = VendorElevationService()