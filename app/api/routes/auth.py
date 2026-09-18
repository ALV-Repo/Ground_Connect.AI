from fastapi import APIRouter, Request

from app.schemas.auth import (
    # BE-001
    DeviceSecurityRequest,
    DeviceSecurityResponse,
    MFARequest,
    MFAResponse,
    MFAVerifyRequest,
    OTPRequest,
    OTPResponse,
    OTPVerifyRequest,
    OTPVerifyResponse,
    RecoveryRequest,
    RecoveryResponse,
    RecoveryVerifyRequest,

    # BE-002
    DeviceRegisterRequest,
    DeviceRegisterResponse,
    DeviceRevokeRequest,
    DeviceRevokeResponse,
    SessionCreateRequest,
    SessionCreateResponse,
    SessionLogoutRequest,
    SessionLogoutResponse,
    SessionRefreshRequest,
    SessionRefreshResponse,
    SessionStatusRequest,
    SessionStatusResponse,
)

from app.services.auth import auth_service


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# =========================================================
# BE-001 - OTP
# =========================================================

@router.post(
    "/otp/request",
    response_model=OTPResponse,
)
def request_otp(
    request: OTPRequest,
):
    return auth_service.issue_otp(
        request.phone_number
    )


@router.post(
    "/otp/verify",
    response_model=OTPVerifyResponse,
)
def verify_otp(
    request: OTPVerifyRequest,
    http_request: Request,
):
    source = (
        http_request.client.host
        if http_request.client
        else "unknown"
    )

    return auth_service.verify_otp(
        request.phone_number,
        request.otp,
        source,
    )


# =========================================================
# BE-001 - MFA
# =========================================================

@router.post(
    "/mfa/request",
)
def request_mfa(
    request: MFARequest,
):
    return auth_service.issue_mfa(
        request.user_id,
        request.role,
    )


@router.post(
    "/mfa/verify",
    response_model=MFAResponse,
)
def verify_mfa(
    request: MFAVerifyRequest,
    http_request: Request,
):
    source = (
        http_request.client.host
        if http_request.client
        else "unknown"
    )

    return auth_service.verify_mfa(
        request.user_id,
        request.role,
        request.otp,
        source,
    )


# =========================================================
# BE-001 - ACCOUNT RECOVERY
# =========================================================

@router.post(
    "/recovery/request",
    response_model=RecoveryResponse,
)
def request_recovery(
    request: RecoveryRequest,
):
    return auth_service.issue_recovery(
        request.user_id,
        request.phone_number,
        request.role,
    )


@router.post(
    "/recovery/verify",
    response_model=RecoveryResponse,
)
def verify_recovery(
    request: RecoveryVerifyRequest,
    http_request: Request,
):
    source = (
        http_request.client.host
        if http_request.client
        else "unknown"
    )

    return auth_service.verify_recovery(
        request.user_id,
        request.phone_number,
        request.role,
        request.otp,
        source,
    )


# =========================================================
# BE-001 - DEVICE SECURITY
# =========================================================

@router.post(
    "/device/security",
    response_model=DeviceSecurityResponse,
)
def check_device_security(
    request: DeviceSecurityRequest,
):
    return auth_service.check_device_security(
        request.user_id,
        request.is_rooted,
        request.is_jailbroken,
    )


# =========================================================
# BE-002 - DEVICE REGISTRATION
# =========================================================

@router.post(
    "/device/register",
    response_model=DeviceRegisterResponse,
)
def register_device(
    request: DeviceRegisterRequest,
):
    return auth_service.register_device(
        request.user_id,
        request.device_id,
    )


# =========================================================
# BE-002 - SESSION CREATION
# =========================================================

@router.post(
    "/session/create",
    response_model=SessionCreateResponse,
)
def create_session(
    request: SessionCreateRequest,
):
    return auth_service.create_session(
        request.user_id,
        request.device_id,
    )


# =========================================================
# BE-002 - SESSION REFRESH
# =========================================================

@router.post(
    "/session/refresh",
    response_model=SessionRefreshResponse,
)
def refresh_session(
    request: SessionRefreshRequest,
):
    return auth_service.refresh_session(
        request.refresh_token,
    )


# =========================================================
# BE-002 - SESSION STATUS
# =========================================================

@router.post(
    "/session/status",
    response_model=SessionStatusResponse,
)
def session_status(
    request: SessionStatusRequest,
):
    return auth_service.session_status(
        request.session_id,
    )


# =========================================================
# BE-002 - REMOTE LOGOUT
# =========================================================

@router.post(
    "/session/logout",
    response_model=SessionLogoutResponse,
)
def logout_session(
    request: SessionLogoutRequest,
):
    return auth_service.logout_session(
        request.session_id,
    )


# =========================================================
# BE-002 - DEVICE REVOCATION
# =========================================================

@router.post(
    "/device/revoke",
    response_model=DeviceRevokeResponse,
)
def revoke_device(
    request: DeviceRevokeRequest,
):
    return auth_service.revoke_device(
        request.user_id,
        request.device_id,
    )