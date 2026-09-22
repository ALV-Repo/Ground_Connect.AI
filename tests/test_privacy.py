from datetime import datetime, timezone

import pytest

from app.schemas.privacy import (
    DataCorrectionRequest,
    DataAccessRequest,
    ErasureRequest,
    LawfulBasis,
    LegalHoldRequest,
    PrivacyInteractionCreate,
    RetentionPolicyCreate,
)
from app.services.privacy import PrivacyService


def test_record_privacy_interaction():
    service = PrivacyService()

    result = service.record_interaction(
        PrivacyInteractionCreate(
            tenant_id="tenant-1",
            principal_id="citizen-1",
            purpose="grievance_resolution",
            notice_version="v1.0",
            language="hi",
            mechanism="mobile",
            lawful_basis=LawfulBasis.CONSENT,
        )
    )

    assert result.receipt_id.startswith("receipt_")
    assert result.tenant_id == "tenant-1"
    assert result.principal_id == "citizen-1"
    assert result.notice_version == "v1.0"
    assert result.language == "hi"
    assert result.lawful_basis == LawfulBasis.CONSENT


def test_interaction_timestamp_is_preserved():
    service = PrivacyService()

    timestamp = datetime.now(timezone.utc)

    result = service.record_interaction(
        PrivacyInteractionCreate(
            tenant_id="tenant-1",
            principal_id="citizen-1",
            purpose="service_delivery",
            notice_version="v2",
            language="en",
            mechanism="web",
            lawful_basis=LawfulBasis.PUBLIC_FUNCTION,
            timestamp=timestamp,
        )
    )

    assert result.timestamp == timestamp


def test_principal_data_access():
    service = PrivacyService()

    service.register_principal_data(
        tenant_id="tenant-1",
        principal_id="citizen-1",
        data={
            "name": "Test User",
            "email": "test@example.com",
            "issue_reference": "GC-123",
        },
    )

    result = service.access_data(
        tenant_id="tenant-1",
        principal_id="citizen-1",
    )

    assert len(result.records) == 1
    assert result.records[0]["name"] == "Test User"
    assert result.records[0]["issue_reference"] == "GC-123"


def test_principal_data_correction():
    service = PrivacyService()

    service.register_principal_data(
        tenant_id="tenant-1",
        principal_id="citizen-1",
        data={
            "name": "Old Name",
        },
    )

    result = service.correct_data(
        DataCorrectionRequest(
            tenant_id="tenant-1",
            principal_id="citizen-1",
            field="name",
            value="New Name",
        )
    )

    assert result.corrected is True
    assert result.field == "name"

    data = service.access_data(
        tenant_id="tenant-1",
        principal_id="citizen-1",
    )

    assert data.records[0]["name"] == "New Name"


def test_correction_requires_existing_principal():
    service = PrivacyService()

    with pytest.raises(KeyError):
        service.correct_data(
            DataCorrectionRequest(
                tenant_id="tenant-1",
                principal_id="unknown",
                field="name",
                value="Test",
            )
        )


def test_retention_policy_creation():
    service = PrivacyService()

    result = service.create_retention_policy(
        RetentionPolicyCreate(
            tenant_id="tenant-1",
            data_class="email",
            retention_days=365,
            legal_hold_allowed=True,
        )
    )

    assert result.policy_id.startswith("ret_")
    assert result.retention_days == 365
    assert result.legal_hold_allowed is True


def test_legal_hold_creation():
    service = PrivacyService()

    result = service.create_legal_hold(
        LegalHoldRequest(
            tenant_id="tenant-1",
            data_class="email",
            reason="Active legal proceeding",
            active=True,
        )
    )

    assert result.hold_id.startswith("hold_")
    assert result.active is True
    assert result.reason == "Active legal proceeding"


def test_verified_erasure_requires_reference():
    service = PrivacyService()

    with pytest.raises(ValueError):
        service.request_erasure(
            ErasureRequest(
                tenant_id="tenant-1",
                principal_id="citizen-1",
                verification_reference="   ",
            )
        )


def test_verified_erasure_removes_personal_data():
    service = PrivacyService()

    service.register_principal_data(
        tenant_id="tenant-1",
        principal_id="citizen-1",
        data={
            "name": "Test User",
            "email": "test@example.com",
            "phone": "9999999999",
            "issue_status": "Closed",
        },
    )

    service.record_interaction(
        PrivacyInteractionCreate(
            tenant_id="tenant-1",
            principal_id="citizen-1",
            purpose="grievance_resolution",
            notice_version="v1",
            language="hi",
            mechanism="mobile",
            lawful_basis=LawfulBasis.CONSENT,
        )
    )

    certificate = service.request_erasure(
        ErasureRequest(
            tenant_id="tenant-1",
            principal_id="citizen-1",
            verification_reference="VERIFIED-123",
        )
    )

    assert certificate.certificate_id.startswith("cert_")
    assert certificate.request_id.startswith("erase_")

    assert "name" in certificate.removed
    assert "email" in certificate.removed
    assert "phone" in certificate.removed

    assert "privacy_interaction_receipts" in certificate.removed
    assert "retrieval_indices" in certificate.removed
    assert "ai_caches" in certificate.removed


def test_erasure_anonymises_remaining_service_record():
    service = PrivacyService()

    service.register_principal_data(
        tenant_id="tenant-1",
        principal_id="citizen-1",
        data={
            "name": "Test User",
            "email": "test@example.com",
            "issue_status": "Resolved",
        },
    )

    service.request_erasure(
        ErasureRequest(
            tenant_id="tenant-1",
            principal_id="citizen-1",
            verification_reference="VERIFIED-456",
        )
    )

    result = service.access_data(
        tenant_id="tenant-1",
        principal_id="citizen-1",
    )

    assert result.records
    assert result.records[0]["anonymised"] is True
    assert "name" not in result.records[0]
    assert "email" not in result.records[0]
    assert result.records[0]["issue_status"] == "Resolved"


def test_legal_hold_retains_held_data():
    service = PrivacyService()

    service.register_principal_data(
        tenant_id="tenant-1",
        principal_id="citizen-1",
        data={
            "name": "Test User",
            "email": "test@example.com",
            "issue_status": "Disputed",
        },
    )

    service.create_legal_hold(
        LegalHoldRequest(
            tenant_id="tenant-1",
            data_class="email",
            reason="Legal case",
            active=True,
        )
    )

    certificate = service.request_erasure(
        ErasureRequest(
            tenant_id="tenant-1",
            principal_id="citizen-1",
            verification_reference="VERIFIED-HOLD",
        )
    )

    assert "email" in certificate.retained
    assert (
        certificate.retention_reasons["email"]
        == "active_legal_hold"
    )


def test_erasure_certificate_can_be_retrieved():
    service = PrivacyService()

    service.register_principal_data(
        tenant_id="tenant-1",
        principal_id="citizen-1",
        data={
            "name": "Test User",
        },
    )

    certificate = service.request_erasure(
        ErasureRequest(
            tenant_id="tenant-1",
            principal_id="citizen-1",
            verification_reference="VERIFIED-CERT",
        )
    )

    result = service.get_certificate(
        certificate_id=certificate.certificate_id,
        tenant_id="tenant-1",
    )

    assert result.certificate_id == certificate.certificate_id
    assert result.request_id == certificate.request_id


def test_cross_tenant_certificate_access_is_blocked():
    service = PrivacyService()

    certificate = service.request_erasure(
        ErasureRequest(
            tenant_id="tenant-1",
            principal_id="citizen-1",
            verification_reference="VERIFIED-TENANT",
        )
    )

    with pytest.raises(PermissionError):
        service.get_certificate(
            certificate_id=certificate.certificate_id,
            tenant_id="tenant-2",
        )


def test_unknown_certificate_returns_error():
    service = PrivacyService()

    with pytest.raises(KeyError):
        service.get_certificate(
            certificate_id="cert-does-not-exist",
            tenant_id="tenant-1",
        )