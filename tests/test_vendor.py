import time

import pytest

from app.services.vendor import VendorElevationService


@pytest.fixture
def service():
    return VendorElevationService()


@pytest.fixture
def pending_elevation(service):
    return service.request_elevation(
        vendor_id="vendor-001",
        tenant_id="tenant-001",
        requested_by="admin-001",
        reason="Temporary production support",
        duration_minutes=30,
        scopes=["read", "support"],
    )


# ============================================================
# Request
# ============================================================


def test_request_elevation(service):
    result = service.request_elevation(
        vendor_id="vendor-001",
        tenant_id="tenant-001",
        requested_by="admin-001",
        reason="Support request",
        duration_minutes=30,
        scopes=["read"],
    )

    assert result["vendor_id"] == "vendor-001"
    assert result["tenant_id"] == "tenant-001"
    assert result["requested_by"] == "admin-001"
    assert result["status"] == "pending"
    assert result["scopes"] == ["read"]
    assert result["duration_minutes"] == 30
    assert result["expires_at"] is not None


def test_request_requires_vendor_id(service):
    with pytest.raises(ValueError):
        service.request_elevation(
            vendor_id="",
            tenant_id="tenant-001",
            requested_by="admin-001",
            reason="Support",
        )


def test_request_requires_reason(service):
    with pytest.raises(ValueError):
        service.request_elevation(
            vendor_id="vendor-001",
            tenant_id="tenant-001",
            requested_by="admin-001",
            reason="",
        )


def test_duration_cannot_exceed_limit(service):
    with pytest.raises(ValueError):
        service.request_elevation(
            vendor_id="vendor-001",
            tenant_id="tenant-001",
            requested_by="admin-001",
            reason="Support",
            duration_minutes=61,
        )


def test_duration_must_be_positive(service):
    with pytest.raises(ValueError):
        service.request_elevation(
            vendor_id="vendor-001",
            tenant_id="tenant-001",
            requested_by="admin-001",
            reason="Support",
            duration_minutes=0,
        )


# ============================================================
# Approval
# ============================================================


def test_approve_elevation(service, pending_elevation):
    result = service.approve_elevation(
        elevation_id=pending_elevation["elevation_id"],
        tenant_id="tenant-001",
        approved_by="admin-002",
    )

    assert result["status"] == "active"
    assert result["approved_by"] == "admin-002"
    assert result["approved_at"] is not None


def test_requester_cannot_approve_own_request(
    service,
    pending_elevation,
):
    with pytest.raises(PermissionError):
        service.approve_elevation(
            elevation_id=pending_elevation["elevation_id"],
            tenant_id="tenant-001",
            approved_by="admin-001",
        )


def test_cannot_approve_twice(service, pending_elevation):
    elevation_id = pending_elevation["elevation_id"]

    service.approve_elevation(
        elevation_id=elevation_id,
        tenant_id="tenant-001",
        approved_by="admin-002",
    )

    with pytest.raises(ValueError):
        service.approve_elevation(
            elevation_id=elevation_id,
            tenant_id="tenant-001",
            approved_by="admin-003",
        )


# ============================================================
# Rejection
# ============================================================


def test_reject_elevation(service, pending_elevation):
    result = service.reject_elevation(
        elevation_id=pending_elevation["elevation_id"],
        tenant_id="tenant-001",
        rejected_by="admin-002",
        reason="Insufficient justification",
    )

    assert result["status"] == "rejected"
    assert result["revoked_by"] == "admin-002"
    assert result["rejection_reason"] == "Insufficient justification"


def test_cannot_reject_active_elevation(
    service,
    pending_elevation,
):
    elevation_id = pending_elevation["elevation_id"]

    service.approve_elevation(
        elevation_id=elevation_id,
        tenant_id="tenant-001",
        approved_by="admin-002",
    )

    with pytest.raises(ValueError):
        service.reject_elevation(
            elevation_id=elevation_id,
            tenant_id="tenant-001",
            rejected_by="admin-003",
        )


# ============================================================
# Tenant Isolation
# ============================================================


def test_cross_tenant_access_denied(
    service,
    pending_elevation,
):
    with pytest.raises(PermissionError):
        service.get_elevation(
            elevation_id=pending_elevation["elevation_id"],
            tenant_id="tenant-002",
        )


def test_cross_tenant_approval_denied(
    service,
    pending_elevation,
):
    with pytest.raises(PermissionError):
        service.approve_elevation(
            elevation_id=pending_elevation["elevation_id"],
            tenant_id="tenant-002",
            approved_by="admin-002",
        )


# ============================================================
# Active / Revoke
# ============================================================


def test_is_active_after_approval(
    service,
    pending_elevation,
):
    elevation_id = pending_elevation["elevation_id"]

    service.approve_elevation(
        elevation_id=elevation_id,
        tenant_id="tenant-001",
        approved_by="admin-002",
    )

    assert (
        service.is_active(
            elevation_id=elevation_id,
            tenant_id="tenant-001",
        )
        is True
    )


def test_revoke_active_elevation(
    service,
    pending_elevation,
):
    elevation_id = pending_elevation["elevation_id"]

    service.approve_elevation(
        elevation_id=elevation_id,
        tenant_id="tenant-001",
        approved_by="admin-002",
    )

    result = service.revoke_elevation(
        elevation_id=elevation_id,
        tenant_id="tenant-001",
        revoked_by="admin-003",
        reason="Support completed",
    )

    assert result["status"] == "revoked"
    assert result["revoked_by"] == "admin-003"
    assert result["revocation_reason"] == "Support completed"

    assert (
        service.is_active(
            elevation_id=elevation_id,
            tenant_id="tenant-001",
        )
        is False
    )


# ============================================================
# Listing
# ============================================================


def test_list_elevations(service):
    service.request_elevation(
        vendor_id="vendor-001",
        tenant_id="tenant-001",
        requested_by="admin-001",
        reason="Support 1",
    )

    service.request_elevation(
        vendor_id="vendor-002",
        tenant_id="tenant-001",
        requested_by="admin-001",
        reason="Support 2",
    )

    result = service.list_elevations(
        tenant_id="tenant-001",
    )

    assert len(result) == 2


def test_list_by_vendor(service):
    service.request_elevation(
        vendor_id="vendor-001",
        tenant_id="tenant-001",
        requested_by="admin-001",
        reason="Support 1",
    )

    service.request_elevation(
        vendor_id="vendor-002",
        tenant_id="tenant-001",
        requested_by="admin-001",
        reason="Support 2",
    )

    result = service.list_elevations(
        tenant_id="tenant-001",
        vendor_id="vendor-001",
    )

    assert len(result) == 1
    assert result[0]["vendor_id"] == "vendor-001"


def test_list_by_status(service, pending_elevation):
    result = service.list_elevations(
        tenant_id="tenant-001",
        status="pending",
    )

    assert len(result) == 1
    assert result[0]["status"] == "pending"


# ============================================================
# Statistics
# ============================================================


def test_statistics(service):
    service.request_elevation(
        vendor_id="vendor-001",
        tenant_id="tenant-001",
        requested_by="admin-001",
        reason="Support",
    )

    result = service.statistics(
        tenant_id="tenant-001",
    )

    assert result["tenant_id"] == "tenant-001"
    assert result["total"] == 1
    assert result["by_status"]["pending"] == 1


# ============================================================
# Missing Elevation
# ============================================================


def test_get_missing_elevation(service):
    with pytest.raises(KeyError):
        service.get_elevation(
            elevation_id="does-not-exist",
            tenant_id="tenant-001",
        )


# ============================================================
# Expiry
# ============================================================


def test_expired_elevation_is_not_active(service):
    result = service.request_elevation(
        vendor_id="vendor-001",
        tenant_id="tenant-001",
        requested_by="admin-001",
        reason="Short support",
        duration_minutes=1,
    )

    elevation_id = result["elevation_id"]

    service.approve_elevation(
        elevation_id=elevation_id,
        tenant_id="tenant-001",
        approved_by="admin-002",
    )

    record = service._elevations[elevation_id]

    # Force expiry for deterministic testing.
    from datetime import datetime, timedelta, timezone

    record["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    )

    assert (
        service.is_active(
            elevation_id=elevation_id,
            tenant_id="tenant-001",
        )
        is False
    )

    updated = service.get_elevation(
        elevation_id=elevation_id,
        tenant_id="tenant-001",
    )

    assert updated["status"] == "expired"


# ============================================================
# Cleanup
# ============================================================


def test_cleanup_expired(service):
    result = service.request_elevation(
        vendor_id="vendor-001",
        tenant_id="tenant-001",
        requested_by="admin-001",
        reason="Short support",
    )

    elevation_id = result["elevation_id"]

    service.approve_elevation(
        elevation_id=elevation_id,
        tenant_id="tenant-001",
        approved_by="admin-002",
    )

    from datetime import datetime, timedelta, timezone

    service._elevations[elevation_id]["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    )

    result = service.cleanup_expired()

    assert result["success"] is True
    assert result["expired_count"] == 1