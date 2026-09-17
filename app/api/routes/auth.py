from fastapi import APIRouter, Request

from app.schemas.auth import (
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
)
from app.services.auth import auth_service


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


# =========================================================
# OTP
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
# MFA
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
# Account Recovery
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
# Device Security
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