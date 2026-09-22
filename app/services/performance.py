from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.core.config import settings


class PerformanceService:
    """
    BE-015 — Performance & Scalability

    Provides:
    - Operation performance tracking
    - Request/response latency tracking
    - Throughput metrics
    - Slow-operation detection
    - Performance summaries
    - Basic load-control helpers
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._operations: List[Dict[str, Any]] = []
        self._counters: Dict[str, int] = defaultdict(int)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _normalize_duration(duration_ms: float) -> float:
        if duration_ms < 0:
            raise ValueError("duration_ms cannot be negative")
        return round(float(duration_ms), 3)

    def record_operation(
        self,
        *,
        operation: str,
        duration_ms: float,
        success: bool = True,
        endpoint: Optional[str] = None,
        tenant_id: Optional[str] = None,
        status_code: Optional[int] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Record one completed operation.

        Sensitive business data should not be placed in metadata.
        """
        if not operation.strip():
            raise ValueError("operation is required")

        duration_ms = self._normalize_duration(duration_ms)

        event = {
            "event_id": str(uuid4()),
            "operation": operation,
            "duration_ms": duration_ms,
            "success": bool(success),
            "endpoint": endpoint,
            "tenant_id": tenant_id,
            "status_code": status_code,
            "correlation_id": correlation_id,
            "recorded_at": self._now(),
            "metadata": metadata or {},
        }

        with self._lock:
            self._operations.append(event)
            self._counters["operations_total"] += 1

            if success:
                self._counters["operations_success"] += 1
            else:
                self._counters["operations_failed"] += 1

            if self.is_slow_operation(duration_ms):
                self._counters["slow_operations"] += 1

        return dict(event)

    @staticmethod
    def is_slow_operation(duration_ms: float) -> bool:
        """
        Determine whether an operation exceeds the configured
        request timeout threshold.
        """
        timeout_seconds = getattr(
            settings,
            "request_timeout_seconds",
            30,
        )
        return duration_ms >= timeout_seconds * 1000

    def get_operation_metrics(
        self,
        *,
        operation: Optional[str] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            records = list(self._operations)

        if operation:
            records = [
                record
                for record in records
                if record["operation"] == operation
            ]

        if not records:
            return {
                "operation": operation,
                "count": 0,
                "success_count": 0,
                "failure_count": 0,
                "average_duration_ms": 0.0,
                "min_duration_ms": 0.0,
                "max_duration_ms": 0.0,
                "slow_operation_count": 0,
            }

        durations = [
            record["duration_ms"]
            for record in records
        ]

        success_count = sum(
            1
            for record in records
            if record["success"]
        )

        failure_count = len(records) - success_count

        slow_count = sum(
            1
            for duration in durations
            if self.is_slow_operation(duration)
        )

        return {
            "operation": operation,
            "count": len(records),
            "success_count": success_count,
            "failure_count": failure_count,
            "average_duration_ms": round(
                sum(durations) / len(durations),
                3,
            ),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "slow_operation_count": slow_count,
        }

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            records = list(self._operations)
            counters = dict(self._counters)

        if not records:
            return {
                "total_operations": 0,
                "successful_operations": 0,
                "failed_operations": 0,
                "slow_operations": 0,
                "average_duration_ms": 0.0,
                "throughput_per_second": 0.0,
                "operations_by_name": {},
            }

        durations = [
            record["duration_ms"]
            for record in records
        ]

        operation_counts: Dict[str, int] = defaultdict(int)

        for record in records:
            operation_counts[record["operation"]] += 1

        first_time = min(
            record["recorded_at"]
            for record in records
        )
        last_time = max(
            record["recorded_at"]
            for record in records
        )

        elapsed_seconds = (
            last_time - first_time
        ).total_seconds()

        if elapsed_seconds <= 0:
            throughput = float(len(records))
        else:
            throughput = len(records) / elapsed_seconds

        return {
            "total_operations": counters.get(
                "operations_total",
                len(records),
            ),
            "successful_operations": counters.get(
                "operations_success",
                0,
            ),
            "failed_operations": counters.get(
                "operations_failed",
                0,
            ),
            "slow_operations": counters.get(
                "slow_operations",
                0,
            ),
            "average_duration_ms": round(
                sum(durations) / len(durations),
                3,
            ),
            "throughput_per_second": round(
                throughput,
                3,
            ),
            "operations_by_name": dict(
                operation_counts
            ),
        }

    def list_slow_operations(
        self,
        *,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        with self._lock:
            records = [
                dict(record)
                for record in self._operations
                if self.is_slow_operation(
                    record["duration_ms"]
                )
            ]

        records.sort(
            key=lambda item: item["duration_ms"],
            reverse=True,
        )

        return records[:limit]

    def get_recent_operations(
        self,
        *,
        limit: int = 100,
        operation: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if limit <= 0:
            raise ValueError("limit must be greater than zero")

        with self._lock:
            records = list(self._operations)

        if operation:
            records = [
                record
                for record in records
                if record["operation"] == operation
            ]

        records.reverse()

        return [
            dict(record)
            for record in records[:limit]
        ]

    def check_request_timeout(
        self,
        *,
        duration_ms: float,
    ) -> Dict[str, Any]:
        duration_ms = self._normalize_duration(duration_ms)

        timeout_seconds = getattr(
            settings,
            "request_timeout_seconds",
            30,
        )

        timeout_ms = timeout_seconds * 1000

        return {
            "timed_out": duration_ms >= timeout_ms,
            "duration_ms": duration_ms,
            "timeout_ms": timeout_ms,
        }

    def load_control(
        self,
        *,
        active_requests: int,
        max_concurrent_requests: int = 100,
    ) -> Dict[str, Any]:
        """
        Basic application-level load-control decision.

        This is a readiness helper; actual distributed rate limiting
        should be handled by the production gateway/load balancer.
        """
        if active_requests < 0:
            raise ValueError(
                "active_requests cannot be negative"
            )

        if max_concurrent_requests <= 0:
            raise ValueError(
                "max_concurrent_requests must be greater than zero"
            )

        overloaded = (
            active_requests >= max_concurrent_requests
        )

        utilization = (
            active_requests / max_concurrent_requests
        )

        return {
            "allowed": not overloaded,
            "active_requests": active_requests,
            "max_concurrent_requests": max_concurrent_requests,
            "utilization": round(utilization, 3),
            "overloaded": overloaded,
        }

    def reset_metrics(self) -> Dict[str, Any]:
        """
        Reset in-memory performance metrics.

        Intended for development/testing.
        """
        with self._lock:
            self._operations.clear()
            self._counters.clear()

        return {
            "success": True,
            "message": "Performance metrics reset",
        }


performance_service = PerformanceService()