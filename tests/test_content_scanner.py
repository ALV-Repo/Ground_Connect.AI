import pytest

from app.schemas.content_scanner import ContentScanRequest, ScanSeverity
from app.services.content_scanner import ContentScannerService


def make_request(
    tenant_id="tenant-1",
    content="Normal service issue reported.",
    source="api",
):
    return ContentScanRequest(
        tenant_id=tenant_id,
        content=content,
        source=source,
    )


def test_safe_content():
    service = ContentScannerService()

    result = service.scan(
        make_request(
            content="Water supply is unavailable in ward 12."
        )
    )

    assert result.safe is True
    assert result.matches == []
    assert result.alert_created is False


def test_religion_attribute_is_detected():
    service = ContentScannerService()

    result = service.scan(
        make_request(
            content="The report contains religious information."
        )
    )

    assert result.safe is False
    assert result.alert_created is True
    assert len(result.matches) == 1
    assert result.matches[0].attribute == "religion"
    assert result.matches[0].severity == ScanSeverity.HIGH


def test_caste_attribute_is_detected():
    service = ContentScannerService()

    result = service.scan(
        make_request(
            content="The citizen's caste was mentioned."
        )
    )

    assert result.safe is False
    assert result.matches[0].attribute == "caste"


def test_political_affiliation_is_detected():
    service = ContentScannerService()

    result = service.scan(
        make_request(
            content="The citizen has political party affiliation."
        )
    )

    assert result.safe is False
    assert result.matches[0].attribute == "political_affiliation"


def test_sexual_orientation_is_detected():
    service = ContentScannerService()

    result = service.scan(
        make_request(
            content="The report contains sexual orientation information."
        )
    )

    assert result.safe is False
    assert result.matches[0].attribute == "sexual_orientation"


def test_health_attribute_is_detected():
    service = ContentScannerService()

    result = service.scan(
        make_request(
            content="The report contains a medical condition."
        )
    )

    assert result.safe is False
    assert result.matches[0].attribute == "health_condition"
    assert result.matches[0].severity == ScanSeverity.HIGH


def test_biometric_attribute_is_critical():
    service = ContentScannerService()

    result = service.scan(
        make_request(
            content="Fingerprint information was included."
        )
    )

    assert result.safe is False
    assert result.matches[0].attribute == "biometric"
    assert result.matches[0].severity == ScanSeverity.CRITICAL


def test_multiple_prohibited_attributes_are_detected():
    service = ContentScannerService()

    result = service.scan(
        make_request(
            content=(
                "The report contains religion, caste and "
                "biometric information."
            )
        )
    )

    attributes = {
        match.attribute
        for match in result.matches
    }

    assert result.safe is False
    assert result.alert_created is True
    assert "religion" in attributes
    assert "caste" in attributes
    assert "biometric" in attributes


def test_alert_is_created_for_match():
    service = ContentScannerService()

    result = service.scan(
        make_request(
            content="The citizen is Hindu."
        )
    )

    alerts = service.list_alerts(
        tenant_id="tenant-1"
    )

    assert result.alert_created is True
    assert len(alerts) == 1
    assert alerts[0]["scan_id"] == result.scan_id


def test_alerts_are_tenant_scoped():
    service = ContentScannerService()

    result = service.scan(
        make_request(
            tenant_id="tenant-1",
            content="The citizen has a disability."
        )
    )

    tenant1_alerts = service.list_alerts("tenant-1")
    tenant2_alerts = service.list_alerts("tenant-2")

    assert len(tenant1_alerts) == 1
    assert tenant1_alerts[0]["scan_id"] == result.scan_id
    assert tenant2_alerts == []


def test_cross_tenant_alert_access_is_blocked():
    service = ContentScannerService()

    result = service.scan(
        make_request(
            tenant_id="tenant-1",
            content="Fingerprint information detected."
        )
    )

    with pytest.raises(PermissionError):
        service.get_alert(
            tenant_id="tenant-2",
            scan_id=result.scan_id,
        )


def test_unknown_alert_returns_not_found():
    service = ContentScannerService()

    with pytest.raises(KeyError):
        service.get_alert(
            tenant_id="tenant-1",
            scan_id="scan-does-not-exist",
        )


def test_scan_preserves_source_independently():
    service = ContentScannerService()

    result = service.scan(
        make_request(
            source="citizen-report",
            content="Normal issue without prohibited data.",
        )
    )

    assert result.safe is True
    assert result.tenant_id == "tenant-1"