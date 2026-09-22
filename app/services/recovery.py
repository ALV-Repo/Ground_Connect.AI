from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.config import settings


class RecoveryService:
    """
    BE-016 — HA, Backup & Recovery

    Provides:
    - Backup creation and metadata
    - Backup retention handling
    - Restore workflow
    - Recovery validation
    - RPO/RTO tracking
    - Recovery status reporting

    Note:
    This is an application-level recovery service.
    Actual production HA, object storage replication,
    database replication, and disaster recovery require
    infrastructure-level implementation.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._backups: Dict[str, Dict[str, Any]] = {}
        self._restore_events: List[Dict[str, Any]] = []
        self._last_successful_backup: Optional[datetime] = None

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def create_backup(
        self,
        *,
        backup_id: Optional[str] = None,
        backup_type: str = "full",
        source: str = "application",
        size_bytes: int = 0,
        checksum: Optional[str] = None,
        location: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Register a completed backup.

        The actual copying of database/files to durable storage
        should be performed by the production backup system.
        """
        if size_bytes < 0:
            raise ValueError("size_bytes cannot be negative")

        if backup_type not in {
            "full",
            "incremental",
            "differential",
        }:
            raise ValueError("Invalid backup_type")

        backup_id = backup_id or str(uuid4())

        with self._lock:
            if backup_id in self._backups:
                raise ValueError("Backup already exists")

            now = self._now()

            retention_days = getattr(
                settings,
                "backup_retention_days",
                30,
            )

            expires_at = now + timedelta(
                days=retention_days
            )

            backup = {
                "backup_id": backup_id,
                "backup_type": backup_type,
                "source": source,
                "size_bytes": size_bytes,
                "checksum": checksum,
                "location": location,
                "status": "completed",
                "created_at": now,
                "expires_at": expires_at,
                "metadata": metadata or {},
            }

            self._backups[backup_id] = backup
            self._last_successful_backup = now

            return dict(backup)

    def get_backup(
        self,
        *,
        backup_id: str,
    ) -> Dict[str, Any]:
        with self._lock:
            backup = self._backups.get(backup_id)

        if backup is None:
            raise KeyError("Backup not found")

        return dict(backup)

    def list_backups(
        self,
        *,
        status: Optional[str] = None,
        backup_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        with self._lock:
            backups = list(self._backups.values())

        if status:
            backups = [
                backup
                for backup in backups
                if backup["status"] == status
            ]

        if backup_type:
            backups = [
                backup
                for backup in backups
                if backup["backup_type"] == backup_type
            ]

        backups.sort(
            key=lambda backup: backup["created_at"],
            reverse=True,
        )

        return [
            dict(backup)
            for backup in backups[:limit]
        ]

    def validate_backup(
        self,
        *,
        backup_id: str,
    ) -> Dict[str, Any]:
        """
        Validate backup metadata and expiration status.
        """
        backup = self.get_backup(
            backup_id=backup_id
        )

        now = self._now()

        if backup["expires_at"] <= now:
            backup["status"] = "expired"

            with self._lock:
                self._backups[backup_id] = backup

            return {
                "valid": False,
                "backup_id": backup_id,
                "status": "expired",
                "reason": "Backup retention period has expired",
            }

        if backup["status"] != "completed":
            return {
                "valid": False,
                "backup_id": backup_id,
                "status": backup["status"],
                "reason": "Backup is not in completed state",
            }

        return {
            "valid": True,
            "backup_id": backup_id,
            "status": "completed",
            "checksum_present": bool(
                backup.get("checksum")
            ),
            "location_present": bool(
                backup.get("location")
            ),
        }

    def restore(
        self,
        *,
        backup_id: str,
        requested_by: str,
        target: str = "application",
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute or simulate a restore workflow.

        In production, this method should trigger the actual
        database/object-storage restore mechanism.
        """
        backup = self.get_backup(
            backup_id=backup_id
        )

        validation = self.validate_backup(
            backup_id=backup_id
        )

        if not validation["valid"]:
            raise ValueError(
                f"Backup cannot be restored: "
                f"{validation['reason']}"
            )

        now = self._now()

        restore_event = {
            "restore_id": str(uuid4()),
            "backup_id": backup_id,
            "requested_by": requested_by,
            "target": target,
            "dry_run": dry_run,
            "status": (
                "validated"
                if dry_run
                else "completed"
            ),
            "started_at": now,
            "completed_at": self._now(),
        }

        with self._lock:
            self._restore_events.append(
                restore_event
            )

            if not dry_run:
                backup["last_restored_at"] = (
                    restore_event["completed_at"]
                )
                backup["last_restored_by"] = requested_by
                self._backups[backup_id] = backup

        return dict(restore_event)

    def verify_recovery(
        self,
        *,
        backup_id: str,
        requested_by: str,
    ) -> Dict[str, Any]:
        """
        Perform a recovery-readiness verification.

        This checks whether the backup can pass the
        application-level validation workflow.
        """
        validation = self.validate_backup(
            backup_id=backup_id
        )

        verification = {
            "verification_id": str(uuid4()),
            "backup_id": backup_id,
            "requested_by": requested_by,
            "verified_at": self._now(),
            "valid": validation["valid"],
            "validation": validation,
        }

        return verification

    def apply_retention_policy(self) -> Dict[str, Any]:
        """
        Mark backups past their retention period as expired.
        """
        now = self._now()
        expired_count = 0

        with self._lock:
            for backup in self._backups.values():
                if (
                    backup["status"] == "completed"
                    and backup["expires_at"] <= now
                ):
                    backup["status"] = "expired"
                    expired_count += 1

        return {
            "success": True,
            "expired_count": expired_count,
            "checked_at": now,
        }

    def get_restore_events(
        self,
        *,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        with self._lock:
            events = list(self._restore_events)

        events.reverse()

        return [
            dict(event)
            for event in events[:limit]
        ]

    def get_recovery_status(self) -> Dict[str, Any]:
        with self._lock:
            backups = list(self._backups.values())
            restore_events = list(
                self._restore_events
            )
            last_backup = (
                self._last_successful_backup
            )

        now = self._now()

        completed_backups = [
            backup
            for backup in backups
            if backup["status"] == "completed"
        ]

        expired_backups = [
            backup
            for backup in backups
            if backup["status"] == "expired"
        ]

        retention_days = getattr(
            settings,
            "backup_retention_days",
            30,
        )

        rpo_minutes = getattr(
            settings,
            "backup_rpo_minutes",
            15,
        )

        rto_minutes = getattr(
            settings,
            "backup_rto_minutes",
            60,
        )

        if last_backup is None:
            backup_age_minutes = None
            rpo_within_target = False
        else:
            backup_age_minutes = round(
                (
                    now - last_backup
                ).total_seconds() / 60,
                3,
            )
            rpo_within_target = (
                backup_age_minutes
                <= rpo_minutes
            )

        return {
            "status": (
                "ready"
                if completed_backups
                else "backup_required"
            ),
            "total_backups": len(backups),
            "completed_backups": len(
                completed_backups
            ),
            "expired_backups": len(
                expired_backups
            ),
            "total_restore_events": len(
                restore_events
            ),
            "last_successful_backup": last_backup,
            "backup_age_minutes": backup_age_minutes,
            "rpo_minutes": rpo_minutes,
            "rto_minutes": rto_minutes,
            "rpo_within_target": rpo_within_target,
            "retention_days": retention_days,
        }

    def check_rpo(
        self,
        *,
        current_time: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Check whether the most recent backup is within
        the configured Recovery Point Objective.
        """
        now = current_time or self._now()

        rpo_minutes = getattr(
            settings,
            "backup_rpo_minutes",
            15,
        )

        with self._lock:
            last_backup = (
                self._last_successful_backup
            )

        if last_backup is None:
            return {
                "within_rpo": False,
                "rpo_minutes": rpo_minutes,
                "last_backup": None,
                "backup_age_minutes": None,
            }

        age_minutes = (
            now - last_backup
        ).total_seconds() / 60

        return {
            "within_rpo": age_minutes <= rpo_minutes,
            "rpo_minutes": rpo_minutes,
            "last_backup": last_backup,
            "backup_age_minutes": round(
                age_minutes,
                3,
            ),
        }

    def get_rto_target(self) -> Dict[str, Any]:
        rto_minutes = getattr(
            settings,
            "backup_rto_minutes",
            60,
        )

        return {
            "rto_minutes": rto_minutes,
            "target_recovery_time_seconds": (
                rto_minutes * 60
            ),
        }

    def clear_test_data(self) -> Dict[str, Any]:
        """
        Clear in-memory recovery state.

        Intended for development/testing only.
        """
        with self._lock:
            self._backups.clear()
            self._restore_events.clear()
            self._last_successful_backup = None

        return {
            "success": True,
            "message": "Recovery test data cleared",
        }


recovery_service = RecoveryService()