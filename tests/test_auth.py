import json
import time

import pytest

from app.services.auth import (
    AuthService,
    DATA_DIR,
    LOCKOUT_FILE,
)


# =========================================================
# Fixtures
# =========================================================

@pytest.fixture
def auth_service(tmp_path, monkeypatch):
    """
    Create a fresh AuthService for every test.

    Lockout data is stored in a temporary directory so tests
    do not affect the real .auth_data/lockouts.json file.
    """
    data_dir = tmp_path / ".auth_data"
    lockout_file = data_dir / "lockouts.json"

    monkeypatch.setattr(
        "app.services.auth.DATA_DIR",
        data_dir,
    )

    monkeypatch.setattr(
        "app.services.auth.LOCKOUT_FILE",
        lockout_file,
    )

    return AuthService()


# =========================================================
# OTP Tests
# =========================================================

def test_otp_request(auth_service):
    response = auth_service.issue_otp(
        "919876500010"
    )

    assert response["message"] == (
        "OTP issued successfully."
    )
    assert response["expires_in_seconds"] == 300
    assert response["attempts_remaining"] == 5
    assert response["development_otp"] is not None
    assert len(response["development_otp"]) == 6


def test_otp_verify_success(auth_service):
    phone = "919876500011"

    response = auth_service.issue_otp(phone)
    otp = response["development_otp"]

    result = auth_service.verify_otp(
        phone,
        otp,
        "127.0.0.1",
    )

    assert result["verified"] is True
    assert result["locked"] is False


def test_otp_is_single_use(auth_service):
    phone = "919876500012"

    response = auth_service.issue_otp(phone)
    otp = response["development_otp"]

    first = auth_service.verify_otp(
        phone,
        otp,
        "127.0.0.1",
    )

    second = auth_service.verify_otp(
        phone,
        otp,
        "127.0.0.1",
    )

    assert first["verified"] is True
    assert second["verified"] is False
    assert second["message"] == (
        "OTP has already been used."
    )


def test_invalid_otp_attempts(auth_service):
    phone = "919876500013"

    auth_service.issue_otp(phone)

    result = auth_service.verify_otp(
        phone,
        "111111",
        "127.0.0.1",
    )

    assert result["verified"] is False
    assert result["attempts_remaining"] == 4
    assert result["locked"] is False


def test_progressive_lockout(auth_service):
    phone = "919876500014"
    source = "127.0.0.1"

    auth_service.issue_otp(phone)

    for _ in range(4):
        result = auth_service.verify_otp(
            phone,
            "111111",
            source,
        )

    assert result["attempts_remaining"] == 1
    assert result["locked"] is False

    result = auth_service.verify_otp(
        phone,
        "111111",
        source,
    )

    assert result["verified"] is False
    assert result["locked"] is True
    assert result["attempts_remaining"] == 0


# =========================================================
# Lockout Persistence
# =========================================================

def test_lockout_survives_restart(tmp_path, monkeypatch):
    data_dir = tmp_path / ".auth_data"
    lockout_file = data_dir / "lockouts.json"

    monkeypatch.setattr(
        "app.services.auth.DATA_DIR",
        data_dir,
    )

    monkeypatch.setattr(
        "app.services.auth.LOCKOUT_FILE",
        lockout_file,
    )

    phone = "919876500015"
    source = "127.0.0.1"

    service_one = AuthService()

    service_one.issue_otp(phone)

    for _ in range(5):
        result = service_one.verify_otp(
            phone,
            "111111",
            source,
        )

    assert result["locked"] is True

    # Simulate application restart.
    service_two = AuthService()

    locked_result = service_two.verify_otp(
        phone,
        "111111",
        source,
    )

    assert locked_result["verified"] is False
    assert locked_result["locked"] is True


# =========================================================
# MFA Tests
# =========================================================

def test_mfa_required_for_elevated_role(auth_service):
    user_id = "leader001"

    response = auth_service.issue_mfa(
        user_id,
        "Leader",
    )

    assert response["mfa_required"] is True
    assert response["development_otp"] is not None
    assert response["expires_in_seconds"] == 300


def test_mfa_verify_success(auth_service):
    user_id = "leader002"

    response = auth_service.issue_mfa(
        user_id,
        "Leader",
    )

    otp = response["development_otp"]

    result = auth_service.verify_mfa(
        user_id,
        "Leader",
        otp,
        "127.0.0.1",
    )

    assert result["verified"] is True
    assert result["mfa_required"] is True


def test_mfa_is_single_use(auth_service):
    user_id = "leader003"

    response = auth_service.issue_mfa(
        user_id,
        "Leader",
    )

    otp = response["development_otp"]

    first = auth_service.verify_mfa(
        user_id,
        "Leader",
        otp,
        "127.0.0.1",
    )

    second = auth_service.verify_mfa(
        user_id,
        "Leader",
        otp,
        "127.0.0.1",
    )

    assert first["verified"] is True
    assert second["verified"] is False
    assert second["message"] == (
        "MFA OTP has already been used."
    )


def test_mfa_not_required_for_normal_role(auth_service):
    response = auth_service.issue_mfa(
        "citizen001",
        "Citizen",
    )

    assert response["mfa_required"] is False
    assert response["development_otp"] is None
    assert response["expires_in_seconds"] == 0


# =========================================================
# Account Recovery Tests
# =========================================================

def test_recovery_requires_verified_identity(
    auth_service,
):
    result = auth_service.issue_recovery(
        "user001",
        "919876500020",
        "Citizen",
    )

    assert result["verified"] is False
    assert result["recovery_allowed"] is False
    assert result["mfa_required"] is False
    assert result["development_otp"] is None


def test_recovery_success(auth_service):
    phone = "919876500021"
    user_id = "user002"

    # First verify identity through normal OTP.
    otp_response = auth_service.issue_otp(phone)

    auth_service.verify_otp(
        phone,
        otp_response["development_otp"],
        "127.0.0.1",
    )

    # Request recovery OTP.
    recovery_response = auth_service.issue_recovery(
        user_id,
        phone,
        "Citizen",
    )

    assert recovery_response["development_otp"] is not None

    recovery_otp = (
        recovery_response["development_otp"]
    )

    # Verify recovery OTP.
    result = auth_service.verify_recovery(
        user_id,
        phone,
        "Citizen",
        recovery_otp,
        "127.0.0.1",
    )

    assert result["verified"] is True
    assert result["recovery_allowed"] is True
    assert result["mfa_required"] is False


def test_recovery_otp_is_single_use(auth_service):
    phone = "919876500022"
    user_id = "user003"

    otp_response = auth_service.issue_otp(phone)

    auth_service.verify_otp(
        phone,
        otp_response["development_otp"],
        "127.0.0.1",
    )

    recovery_response = auth_service.issue_recovery(
        user_id,
        phone,
        "Citizen",
    )

    recovery_otp = (
        recovery_response["development_otp"]
    )

    first = auth_service.verify_recovery(
        user_id,
        phone,
        "Citizen",
        recovery_otp,
        "127.0.0.1",
    )

    second = auth_service.verify_recovery(
        user_id,
        phone,
        "Citizen",
        recovery_otp,
        "127.0.0.1",
    )

    assert first["verified"] is True
    assert second["verified"] is False
    assert second["recovery_allowed"] is False
    assert second["message"] == (
        "Recovery OTP has already been used."
    )


def test_elevated_recovery_requires_mfa(auth_service):
    phone = "919876500023"
    user_id = "leader004"

    otp_response = auth_service.issue_otp(phone)

    auth_service.verify_otp(
        phone,
        otp_response["development_otp"],
        "127.0.0.1",
    )

    recovery_response = auth_service.issue_recovery(
        user_id,
        phone,
        "Leader",
    )

    # Recovery request currently issues the OTP,
    # but elevated recovery must not bypass MFA.
    assert recovery_response["mfa_required"] is True

    result = auth_service.verify_recovery(
        user_id,
        phone,
        "Leader",
        recovery_response["development_otp"],
        "127.0.0.1",
    )

    assert result["verified"] is False
    assert result["recovery_allowed"] is False
    assert result["mfa_required"] is True


# =========================================================
# Device Security Tests
# =========================================================

def test_device_security_normal(auth_service):
    result = auth_service.check_device_security(
        "user001",
        is_rooted=False,
        is_jailbroken=False,
    )

    assert result["allowed"] is True


def test_rooted_device_is_blocked(auth_service):
    result = auth_service.check_device_security(
        "user002",
        is_rooted=True,
        is_jailbroken=False,
    )

    assert result["allowed"] is False
    assert result["message"] == (
        "Access denied. Rooted device detected."
    )


def test_jailbroken_device_is_blocked(auth_service):
    result = auth_service.check_device_security(
        "user003",
        is_rooted=False,
        is_jailbroken=True,
    )

    assert result["allowed"] is False
    assert result["message"] == (
        "Access denied. Jailbroken device detected."
    )