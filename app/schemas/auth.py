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