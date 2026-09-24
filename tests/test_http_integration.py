from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_auth_endpoint_is_public():
    response = client.post(
        "/api/v1/auth/otp/request",
        json={
            "phone_number": "+919999999999",
        },
    )

    assert response.status_code != 401


def test_protected_endpoint_requires_authentication():
    response = client.get("/api/v1/security/status")

    assert response.status_code == 401


def test_authenticated_request_can_access_protected_endpoint():
    user_id = "http_integration_user"
    device_id = "http_integration_device"

    register_response = client.post(
        "/api/v1/auth/device/register",
        json={
            "user_id": user_id,
            "device_id": device_id,
        },
    )

    assert register_response.status_code == 200

    session_response = client.post(
        "/api/v1/auth/session/create",
        json={
            "user_id": user_id,
            "device_id": device_id,
        },
    )

    assert session_response.status_code == 200

    session_data = session_response.json()
    access_token = session_data["access_token"]

    protected_response = client.get(
        "/api/v1/security/status",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert protected_response.status_code == 200

def test_cache_clear_does_not_expose_internal_error(monkeypatch):
    from app.api.routes import authorization as authorization_route

    def failing_clear_cache():
        raise RuntimeError("SECRET_INTERNAL_ERROR")

    monkeypatch.setattr(
        authorization_route.authorization_service,
        "clear_cache",
        failing_clear_cache,
    )

    user_id = "cache_clear_test_user"
    device_id = "cache_clear_test_device"

    register_response = client.post(
        "/api/v1/auth/device/register",
        json={
            "user_id": user_id,
            "device_id": device_id,
        },
    )

    assert register_response.status_code == 200

    session_response = client.post(
        "/api/v1/auth/session/create",
        json={
            "user_id": user_id,
            "device_id": device_id,
        },
    )

    assert session_response.status_code == 200

    access_token = session_response.json()["access_token"]

    response = client.post(
        "/api/v1/authorization/cache/clear",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to clear authorization cache"
    assert "SECRET_INTERNAL_ERROR" not in response.text


def test_evidence_preservation_uses_request_body():
    user_id = "evidence_http_test_user"
    device_id = "evidence_http_test_device"

    register_response = client.post(
        "/api/v1/auth/device/register",
        json={
            "user_id": user_id,
            "device_id": device_id,
        },
    )

    assert register_response.status_code == 200

    session_response = client.post(
        "/api/v1/auth/session/create",
        json={
            "user_id": user_id,
            "device_id": device_id,
        },
    )

    assert session_response.status_code == 200

    access_token = session_response.json()["access_token"]

    headers = {
        "Authorization": f"Bearer {access_token}",
    }

    incident_response = client.post(
        "/api/v1/incident-response/incidents",
        headers=headers,
        json={
            "incident_type": "security_test",
            "title": "Evidence API test",
            "description": "Testing evidence request payload",
            "severity": "medium",
        },
    )

    assert incident_response.status_code == 200

    incident_id = incident_response.json()["incident_id"]

    response = client.post(
        f"/api/v1/incident-response/incidents/{incident_id}/evidence",
        headers=headers,
        json={
            "evidence_type": "text",
            "captured_by": "test_user",
            "evidence": "test evidence content",
            "location_reference": "test-location",
        },
    )

    assert response.status_code == 200
    assert response.json()["incident_id"] == incident_id

def test_tpi_operation_creation_uses_request_body():
    user_id = "tpi_http_test_user"
    device_id = "tpi_http_test_device"

    register_response = client.post(
        "/api/v1/auth/device/register",
        json={"user_id": user_id, "device_id": device_id},
    )
    assert register_response.status_code == 200

    session_response = client.post(
        "/api/v1/auth/session/create",
        json={"user_id": user_id, "device_id": device_id},
    )
    assert session_response.status_code == 200

    access_token = session_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    response = client.post(
        "/api/v1/tpi/operations",
        headers=headers,
        json={
            "operation_id": "tpi-http-001",
            "tenant_id": "tenant-a",
            "requested_by": user_id,
            "operation_type": "disable_prohibited_attribute_firewall",
            "reason": "HTTP request body test",
        },
    )

    assert response.status_code == 200
    assert response.json()["operation_id"] == "tpi-http-001"

def test_vendor_elevation_uses_request_body_for_scopes():
    user_id = "vendor_http_test_user"
    device_id = "vendor_http_test_device"

    register_response = client.post(
        "/api/v1/auth/device/register",
        json={"user_id": user_id, "device_id": device_id},
    )
    assert register_response.status_code == 200

    session_response = client.post(
        "/api/v1/auth/session/create",
        json={"user_id": user_id, "device_id": device_id},
    )
    assert session_response.status_code == 200

    access_token = session_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {access_token}"}

    response = client.post(
        "/api/v1/vendor/elevation",
        headers=headers,
        json={
            "vendor_id": "vendor-http-001",
            "tenant_id": "tenant-a",
            "requested_by": user_id,
            "reason": "HTTP vendor support test",
            "duration_minutes": 30,
            "scopes": ["read", "support"],
        },
    )

    assert response.status_code == 200
    assert response.json()["vendor_id"] == "vendor-http-001"
    assert response.json()["tenant_id"] == "tenant-a"
    assert response.json()["scopes"] == ["read", "support"]