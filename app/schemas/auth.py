from pydantic import BaseModel, Field


# =========================================================
# OTP
# =========================================================

class OTPRequest(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=15)


class OTPResponse(BaseModel):
    message: str
    expires_in_seconds: int
    attempts_remaining: int
    development_otp: str | None = None


class OTPVerifyRequest(BaseModel):
    phone_number: str = Field(..., min_length=10, max_length=15)
    otp: str = Field(..., min_length=6, max_length=6)


class OTPVerifyResponse(BaseModel):
    verified: bool
    message: str
    attempts_remaining: int
    locked: bool


# =========================================================
# MFA
# =========================================================

class MFARequest(BaseModel):
    user_id: str
    role: str


class MFAVerifyRequest(BaseModel):
    user_id: str
    role: str
    otp: str = Field(..., min_length=6, max_length=6)


class MFAResponse(BaseModel):
    verified: bool
    mfa_required: bool
    message: str


# =========================================================
# Account Recovery
# =========================================================

class RecoveryRequest(BaseModel):
    user_id: str
    phone_number: str = Field(..., min_length=10, max_length=15)
    role: str


class RecoveryVerifyRequest(BaseModel):
    user_id: str
    phone_number: str = Field(..., min_length=10, max_length=15)
    role: str
    otp: str = Field(..., min_length=6, max_length=6)


class RecoveryResponse(BaseModel):
    verified: bool
    recovery_allowed: bool
    mfa_required: bool
    message: str
    development_otp: str | None = None
    expires_in_seconds: int = 0


# =========================================================
# Device Security
# =========================================================

class DeviceSecurityRequest(BaseModel):
    user_id: str
    is_rooted: bool = False
    is_jailbroken: bool = False


class DeviceSecurityResponse(BaseModel):
    allowed: bool
    message: str

# =========================================================
# SESSION & DEVICE BINDING - BE-002
# =========================================================

class DeviceRegisterRequest(BaseModel):
    user_id: str
    device_id: str = Field(..., min_length=3, max_length=200)


class DeviceRegisterResponse(BaseModel):
    registered: bool
    user_id: str
    device_id: str
    message: str


class SessionCreateRequest(BaseModel):
    user_id: str
    device_id: str


class SessionCreateResponse(BaseModel):
    session_created: bool
    session_id: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    device_id: str
    idle_expires_in_seconds: int = 0
    absolute_expires_in_seconds: int = 0
    step_up_required: bool = False
    message: str


class SessionRefreshRequest(BaseModel):
    refresh_token: str


class SessionRefreshResponse(BaseModel):
    refreshed: bool
    session_id: str | None = None
    access_token: str | None = None
    refresh_token: str | None = None
    idle_expires_in_seconds: int = 0
    absolute_expires_in_seconds: int = 0
    family_invalidated: bool = False
    security_event: bool = False
    message: str


class SessionStatusRequest(BaseModel):
    session_id: str


class SessionStatusResponse(BaseModel):
    active: bool
    session_id: str
    user_id: str | None = None
    device_id: str | None = None
    idle_expired: bool = False
    absolute_expired: bool = False
    revoked: bool = False
    purge_offline_data: bool = False
    message: str


class SessionLogoutRequest(BaseModel):
    session_id: str


class SessionLogoutResponse(BaseModel):
    logged_out: bool
    session_id: str
    purge_offline_data: bool
    message: str


class DeviceRevokeRequest(BaseModel):
    user_id: str
    device_id: str


class DeviceRevokeResponse(BaseModel):
    revoked: bool
    user_id: str
    device_id: str
    affected_sessions: int
    purge_offline_data: bool
    message: str