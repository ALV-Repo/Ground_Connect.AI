import pytest

from app.services.auth import auth_service
from app.services.tpi import TwoPersonIntegrityService


def test_org_admin_cannot_approve_firewall_disable():
    service = TwoPersonIntegrityService()

    service.create_operation(
        operation_id="tpi-firewall-001",
        tenant_id="tenant-a",
        requested_by="org-admin-1",
        operation_type="disable_prohibited_attribute_firewall",
        reason="Attempt to disable prohibited-attribute firewall",
    )

    with pytest.raises(
        PermissionError,
        match="Compliance Officer approval is required",
    ):
        service.approve_operation(
            operation_id="tpi-firewall-001",
            tenant_id="tenant-a",
            approved_by="security-admin-1",
            approve=True,
            approver_role="security admin",
            mfa_otp="123456",
        )


def test_firewall_disable_requires_compliance_approval():
    service = TwoPersonIntegrityService()

    service.create_operation(
        operation_id="tpi-firewall-002",
        tenant_id="tenant-a",
        requested_by="org-admin-1",
        operation_type="disable_prohibited_attribute_firewall",
        reason="Firewall configuration change",
    )

    with pytest.raises(
        PermissionError,
        match="Compliance Officer approval is required",
    ):
        service.approve_operation(
            operation_id="tpi-firewall-002",
            tenant_id="tenant-a",
            approved_by="security-admin-1",
            approve=True,
            approver_role="security admin",
            mfa_otp="123456",
        )


def test_compliance_can_approve_firewall_disable_with_mfa():
    service = TwoPersonIntegrityService()

    service.create_operation(
        operation_id="tpi-firewall-003",
        tenant_id="tenant-a",
        requested_by="org-admin-1",
        operation_type="disable_prohibited_attribute_firewall",
        reason="Approved firewall configuration change",
    )

    mfa_response = auth_service.issue_mfa(
        "compliance-officer-1",
        "compliance",
    )

    otp = mfa_response["development_otp"]

    result = service.approve_operation(
        operation_id="tpi-firewall-003",
        tenant_id="tenant-a",
        approved_by="compliance-officer-1",
        approve=True,
        approver_role="compliance",
        mfa_otp=otp,
        mfa_source="127.0.0.1",
    )

    assert result["status"] == "approved"
    assert result["approved_by"] == "compliance-officer-1"
    assert result["mfa_verified"] is True