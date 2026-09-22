import pytest

from app.schemas.compliance import (
    ComplianceMode,
    ComplianceProfileActivateRequest,
    ComplianceProfileCreate,
)
from app.services.compliance import ComplianceService


def make_profile(
    tenant_id="tenant-1",
    name="Standard Profile",
    mode=ComplianceMode.STANDARD,
):
    return ComplianceProfileCreate(
        tenant_id=tenant_id,
        profile_name=name,
        mode=mode,
        description="Test compliance profile",
        controls={
            "audit_required": True,
            "consent_required": True,
        },
    )


def test_create_compliance_profile():
    service = ComplianceService()

    result = service.create_profile(
        make_profile()
    )

    assert result.profile_id.startswith("profile_")
    assert result.tenant_id == "tenant-1"
    assert result.profile_name == "Standard Profile"
    assert result.mode == ComplianceMode.STANDARD
    assert result.active is False


def test_profile_is_created_with_controls():
    service = ComplianceService()

    result = service.create_profile(
        make_profile()
    )

    assert result.controls["audit_required"] is True
    assert result.controls["consent_required"] is True


def test_activate_compliance_profile():
    service = ComplianceService()

    profile = service.create_profile(
        make_profile()
    )

    result = service.activate_profile(
        ComplianceProfileActivateRequest(
            tenant_id="tenant-1",
            profile_id=profile.profile_id,
            actor_id="admin-1",
        )
    )

    assert result.active is True

    status = service.get_status("tenant-1")

    assert status.active_profile_id == profile.profile_id
    assert status.mode == ComplianceMode.STANDARD


def test_only_one_profile_is_active():
    service = ComplianceService()

    first = service.create_profile(
        make_profile(
            name="Profile A",
        )
    )

    second = service.create_profile(
        make_profile(
            name="Profile B",
        )
    )

    service.activate_profile(
        ComplianceProfileActivateRequest(
            tenant_id="tenant-1",
            profile_id=first.profile_id,
            actor_id="admin-1",
        )
    )

    service.activate_profile(
        ComplianceProfileActivateRequest(
            tenant_id="tenant-1",
            profile_id=second.profile_id,
            actor_id="admin-1",
        )
    )

    first_result = service.get_profile(
        tenant_id="tenant-1",
        profile_id=first.profile_id,
    )

    second_result = service.get_profile(
        tenant_id="tenant-1",
        profile_id=second.profile_id,
    )

    assert first_result.active is False
    assert second_result.active is True


def test_get_profile():
    service = ComplianceService()

    profile = service.create_profile(
        make_profile()
    )

    result = service.get_profile(
        tenant_id="tenant-1",
        profile_id=profile.profile_id,
    )

    assert result.profile_id == profile.profile_id
    assert result.tenant_id == "tenant-1"


def test_cross_tenant_profile_access_is_blocked():
    service = ComplianceService()

    profile = service.create_profile(
        make_profile(
            tenant_id="tenant-1",
        )
    )

    with pytest.raises(PermissionError):
        service.get_profile(
            tenant_id="tenant-2",
            profile_id=profile.profile_id,
        )


def test_cross_tenant_activation_is_blocked():
    service = ComplianceService()

    profile = service.create_profile(
        make_profile(
            tenant_id="tenant-1",
        )
    )

    with pytest.raises(PermissionError):
        service.activate_profile(
            ComplianceProfileActivateRequest(
                tenant_id="tenant-2",
                profile_id=profile.profile_id,
                actor_id="admin-2",
            )
        )


def test_unknown_profile_activation_fails():
    service = ComplianceService()

    with pytest.raises(KeyError):
        service.activate_profile(
            ComplianceProfileActivateRequest(
                tenant_id="tenant-1",
                profile_id="profile-unknown",
                actor_id="admin-1",
            )
        )


def test_status_without_active_profile():
    service = ComplianceService()

    result = service.get_status("tenant-1")

    assert result.active_profile_id is None
    assert result.mode is None
    assert result.controls == {}


def test_high_risk_default_controls():
    controls = ComplianceService.default_controls(
        ComplianceMode.HIGH_RISK
    )

    assert controls["audit_required"] is True
    assert controls["consent_required"] is True
    assert controls["strict_erasure"] is True
    assert controls["enhanced_review"] is True
    assert controls["second_approval_required"] is True


def test_strict_default_controls():
    controls = ComplianceService.default_controls(
        ComplianceMode.STRICT
    )

    assert controls["audit_required"] is True
    assert controls["consent_required"] is True
    assert controls["strict_erasure"] is True
    assert controls["enhanced_review"] is True


def test_standard_default_controls():
    controls = ComplianceService.default_controls(
        ComplianceMode.STANDARD
    )

    assert controls["audit_required"] is True
    assert controls["consent_required"] is True
    assert controls["strict_erasure"] is False
    assert controls["enhanced_review"] is False


def test_profiles_are_tenant_scoped():
    service = ComplianceService()

    tenant1 = service.create_profile(
        make_profile(
            tenant_id="tenant-1",
            name="Tenant 1",
        )
    )

    tenant2 = service.create_profile(
        make_profile(
            tenant_id="tenant-2",
            name="Tenant 2",
        )
    )

    service.activate_profile(
        ComplianceProfileActivateRequest(
            tenant_id="tenant-1",
            profile_id=tenant1.profile_id,
            actor_id="admin-1",
        )
    )

    service.activate_profile(
        ComplianceProfileActivateRequest(
            tenant_id="tenant-2",
            profile_id=tenant2.profile_id,
            actor_id="admin-2",
        )
    )

    status1 = service.get_status("tenant-1")
    status2 = service.get_status("tenant-2")

    assert status1.active_profile_id == tenant1.profile_id
    assert status2.active_profile_id == tenant2.profile_id