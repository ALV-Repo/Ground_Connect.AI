import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


# =========================================================
# CONFIGURATION
# =========================================================

OTP_EXPIRY_SECONDS = 300

MAX_OTP_ATTEMPTS = 5

LOCKOUT_DURATIONS = [
    30,
    60,
    120,
    300,
]

OTP_RATE_LIMIT_WINDOW_SECONDS = 60
OTP_REQUEST_LIMIT = 5
OTP_VERIFY_LIMIT = 10

DATA_DIR = Path(".auth_data")
LOCKOUT_FILE = DATA_DIR / "lockouts.json"


# =========================================================
# BE-002 SESSION CONFIGURATION
# =========================================================

SESSION_IDLE_TIMEOUT_SECONDS = 1800       # 30 minutes
SESSION_ABSOLUTE_TIMEOUT_SECONDS = 86400  # 24 hours


# =========================================================
# OTP RECORD
# =========================================================

@dataclass
class OTPRecord:
    otp_hash: str
    expires_at: float
    attempts: int = 0
    used: bool = False


# =========================================================
# LOCKOUT RECORD
# =========================================================

@dataclass
class LockoutRecord:
    failures: int = 0
    locked_until: float = 0.0


# =========================================================
# BE-002 DEVICE RECORD
# =========================================================

@dataclass
class DeviceRecord:
    user_id: str
    device_id: str
    registered_at: float
    revoked_at: float | None = None


# =========================================================
# BE-002 SESSION RECORD
# =========================================================

@dataclass
class SessionRecord:
    session_id: str
    user_id: str
    device_id: str
    family_id: str

    access_token_hash: str
    refresh_token_hash: str

    created_at: float
    last_activity_at: float
    absolute_expires_at: float

    revoked_at: float | None = None
    purge_offline_data: bool = False


# =========================================================
# AUTH SERVICE
# =========================================================

class AuthService:

    def __init__(self):

        # -------------------------------------------------
        # BE-001 OTP stores
        # -------------------------------------------------

        self._otp_store: dict[str, OTPRecord] = {}

        self._mfa_store: dict[str, OTPRecord] = {}

        self._recovery_store: dict[str, OTPRecord] = {}

        self._otp_request_windows: dict[str, list[float]] = {}
        self._otp_verify_windows: dict[str, list[float]] = {}

        self._verified_identities: set[str] = set()

        # -------------------------------------------------
        # Persistent lockout state
        # -------------------------------------------------

        self._lockouts: dict[
            str,
            LockoutRecord
        ] = {}

        DATA_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._load_lockouts()

        # -------------------------------------------------
        # BE-002 device/session stores
        # -------------------------------------------------

        self._devices: dict[
            tuple[str, str],
            DeviceRecord
        ] = {}

        self._sessions: dict[
            str,
            SessionRecord
        ] = {}

        # -------------------------------------------------
        # Old rotated refresh tokens
        #
        # old_refresh_token_hash -> family_id
        # -------------------------------------------------

        self._rotated_refresh_tokens: dict[
            str,
            str
        ] = {}

        # -------------------------------------------------
        # Security events
        # -------------------------------------------------

        self._security_events: list[
            dict
        ] = []


    # =====================================================
    # BE-001 OTP HELPERS
    # =====================================================

    @staticmethod
    def _hash_otp(
        otp: str,
    ) -> str:

        return hashlib.sha256(
            otp.encode("utf-8")
        ).hexdigest()


    @staticmethod
    def _generate_otp() -> str:

        return f"{secrets.randbelow(1_000_000):06d}"


    @staticmethod
    def _lockout_key(
        identity: str,
        source: str,
    ) -> str:

        return f"{identity}:{source}"


    @staticmethod
    def _check_otp_rate_limit(
        key: str,
        limit: int,
        now: float,
        windows: dict[str, list[float]],
    ) -> None:
        window = windows.setdefault(key, [])

        cutoff = now - OTP_RATE_LIMIT_WINDOW_SECONDS
        windows[key] = [
            timestamp
            for timestamp in window
            if timestamp > cutoff
        ]

        if len(windows[key]) >= limit:
            raise PermissionError("OTP rate limit exceeded")

        windows[key].append(now)


    @staticmethod
    def is_elevated_role(
        role: str,
    ) -> bool:

        elevated_roles = {
            item.strip().lower()
            for item in settings.authorization_elevated_roles.split(",")
            if item.strip()
        }

        return role.strip().lower() in elevated_roles


    # =====================================================
    # BE-001 LOCKOUT PERSISTENCE
    # =====================================================

    def _load_lockouts(self):

        if not LOCKOUT_FILE.exists():
            return

        try:

            with LOCKOUT_FILE.open(
                "r",
                encoding="utf-8",
            ) as file:

                data = json.load(file)

            for key, value in data.items():

                self._lockouts[key] = LockoutRecord(
                    failures=int(
                        value.get(
                            "failures",
                            0,
                        )
                    ),
                    locked_until=float(
                        value.get(
                            "locked_until",
                            0.0,
                        )
                    ),
                )

        except (
            json.JSONDecodeError,
            OSError,
            TypeError,
            ValueError,
        ):

            self._lockouts = {}


    def _save_lockouts(self):

        payload = {
            key: {
                "failures": record.failures,
                "locked_until": record.locked_until,
            }
            for key, record
            in self._lockouts.items()
        }

        temp_file = LOCKOUT_FILE.with_suffix(
            ".tmp"
        )

        with temp_file.open(
            "w",
            encoding="utf-8",
        ) as file:

            json.dump(
                payload,
                file,
            )

        temp_file.replace(
            LOCKOUT_FILE
        )


    # =====================================================
    # BE-001 OTP ISSUANCE
    # =====================================================

    def issue_otp(
        self,
        phone_number: str,
    ):
        now = time.time()

        self._check_otp_rate_limit(
            key=phone_number,
            limit=OTP_REQUEST_LIMIT,
            now=now,
            windows=self._otp_request_windows,
        )

        otp = self._generate_otp()

        self._otp_store[
            phone_number
        ] = OTPRecord(
            otp_hash=self._hash_otp(
                otp
            ),
            expires_at=(
                now
                + OTP_EXPIRY_SECONDS
            ),
        )

        return {
            "message":
                "OTP issued successfully.",
            "expires_in_seconds":
                OTP_EXPIRY_SECONDS,
            "attempts_remaining":
                MAX_OTP_ATTEMPTS,
            "development_otp":
                otp,
        }


    # =====================================================
    # BE-001 OTP VERIFICATION
    # =====================================================

    def verify_otp(
        self,
        phone_number: str,
        otp: str,
        source: str,
    ):

        now = time.time()

        self._check_otp_rate_limit(
            key=f"{phone_number}:{source}",
            limit=OTP_VERIFY_LIMIT,
            now=now,
            windows=self._otp_verify_windows,
        )

        key = self._lockout_key(
            phone_number,
            source,
        )

        lockout = self._lockouts.get(
            key,
            LockoutRecord(),
        )

        # -------------------------------------------------
        # Check active lock
        # -------------------------------------------------

        if now < lockout.locked_until:

            return {
                "verified": False,
                "message":
                    "Too many failed attempts. Account is temporarily locked.",
                "attempts_remaining": 0,
                "locked": True,
            }

        # -------------------------------------------------
        # Lock expired
        # -------------------------------------------------

        if (
            lockout.locked_until > 0
            and now >= lockout.locked_until
        ):

            lockout.locked_until = 0.0

        record = self._otp_store.get(
            phone_number
        )

        # -------------------------------------------------
        # OTP missing
        # -------------------------------------------------

        if record is None:

            return {
                "verified": False,
                "message":
                    "OTP not found. Please request a new OTP.",
                "attempts_remaining": 0,
                "locked": False,
            }

        # -------------------------------------------------
        # OTP expired
        # -------------------------------------------------

        if now > record.expires_at:

            del self._otp_store[
                phone_number
            ]

            return {
                "verified": False,
                "message":
                    "OTP has expired. Please request a new OTP.",
                "attempts_remaining": 0,
                "locked": False,
            }

        # -------------------------------------------------
        # OTP already used
        # -------------------------------------------------

        if record.used:

            return {
                "verified": False,
                "message":
                    "OTP has already been used.",
                "attempts_remaining": 0,
                "locked": False,
            }

        # -------------------------------------------------
        # Compare OTP
        # -------------------------------------------------

        expected_hash = record.otp_hash

        supplied_hash = self._hash_otp(
            otp
        )

        if not hmac.compare_digest(
            expected_hash,
            supplied_hash,
        ):

            record.attempts += 1

            lockout.failures += 1

            # -------------------------------------------------
            # IMPORTANT:
            # First 4 wrong attempts should NOT lock.
            # 5th wrong attempt causes lock.
            # -------------------------------------------------

            if (
                record.attempts
                >= MAX_OTP_ATTEMPTS
            ):

                index = min(
                    lockout.failures - 1,
                    len(
                        LOCKOUT_DURATIONS
                    ) - 1,
                )

                lockout.locked_until = (
                    now
                    + LOCKOUT_DURATIONS[index]
                )

            else:

                lockout.locked_until = 0.0

            self._lockouts[key] = lockout

            self._save_lockouts()

            return {
                "verified": False,
                "message":
                    "Invalid OTP.",
                "attempts_remaining": max(
                    0,
                    MAX_OTP_ATTEMPTS
                    - record.attempts,
                ),
                "locked":
                    record.attempts
                    >= MAX_OTP_ATTEMPTS,
            }

        # -------------------------------------------------
        # Successful verification
        # -------------------------------------------------

        record.used = True

        self._verified_identities.add(
            phone_number
        )

        self._lockouts.pop(
            key,
            None,
        )

        self._save_lockouts()

        return {
            "verified": True,
            "message":
                "OTP verified successfully.",
            "attempts_remaining": max(
                0,
                MAX_OTP_ATTEMPTS
                - record.attempts,
            ),
            "locked": False,
        }


    # =====================================================
    # BE-001 MFA
    # =====================================================

    def issue_mfa(
        self,
        user_id: str,
        role: str,
    ):

        # Normal role
        if not self.is_elevated_role(
            role
        ):

            return {
                "mfa_required": False,
                "message":
                    "MFA is not required for this role.",
                "development_otp": None,
                "expires_in_seconds": 0,
            }

        otp = self._generate_otp()

        self._mfa_store[
            user_id
        ] = OTPRecord(
            otp_hash=self._hash_otp(
                otp
            ),
            expires_at=(
                time.time()
                + OTP_EXPIRY_SECONDS
            ),
        )

        return {
            "mfa_required": True,
            "message":
                "MFA OTP issued successfully.",
            "expires_in_seconds":
                OTP_EXPIRY_SECONDS,
            "development_otp":
                otp,
        }


    def verify_mfa(
        self,
        user_id: str,
        role: str,
        otp: str,
        source: str,
    ):

        # Normal role
        if not self.is_elevated_role(
            role
        ):

            return {
                "verified": True,
                "mfa_required": False,
                "message":
                    "MFA is not required for this role.",
            }

        now = time.time()

        key = self._lockout_key(
            f"mfa:{user_id}",
            source,
        )

        lockout = self._lockouts.get(
            key,
            LockoutRecord(),
        )

        if now < lockout.locked_until:

            return {
                "verified": False,
                "mfa_required": True,
                "message":
                    "MFA temporarily locked.",
            }

        record = self._mfa_store.get(
            user_id
        )

        if record is None:

            return {
                "verified": False,
                "mfa_required": True,
                "message":
                    "MFA OTP not found.",
            }

        if now > record.expires_at:

            del self._mfa_store[
                user_id
            ]

            return {
                "verified": False,
                "mfa_required": True,
                "message":
                    "MFA OTP has expired.",
            }

        if record.used:

            return {
                "verified": False,
                "mfa_required": True,
                "message":
                    "MFA OTP has already been used.",
            }

        if not hmac.compare_digest(
            record.otp_hash,
            self._hash_otp(otp),
        ):

            record.attempts += 1

            lockout.failures += 1

            if (
                record.attempts
                >= MAX_OTP_ATTEMPTS
            ):

                index = min(
                    lockout.failures - 1,
                    len(
                        LOCKOUT_DURATIONS
                    ) - 1,
                )

                lockout.locked_until = (
                    now
                    + LOCKOUT_DURATIONS[index]
                )

            else:

                lockout.locked_until = 0.0

            self._lockouts[key] = lockout

            self._save_lockouts()

            return {
                "verified": False,
                "mfa_required": True,
                "message":
                    "Invalid MFA OTP.",
            }

        record.used = True

        self._lockouts.pop(
            key,
            None,
        )

        self._save_lockouts()

        return {
            "verified": True,
            "mfa_required": True,
            "message":
                "MFA verified successfully.",
        }


    # =====================================================
    # BE-001 ACCOUNT RECOVERY
    # =====================================================

    def issue_recovery(
        self,
        user_id: str,
        phone_number: str,
        role: str,
    ):

        if (
            phone_number
            not in self._verified_identities
        ):

            return {
                "verified": False,
                "recovery_allowed": False,
                "mfa_required": False,
                "message":
                    "Identity verification is required before account recovery.",
                "development_otp": None,
                "expires_in_seconds": 0,
            }

        otp = self._generate_otp()

        self._recovery_store[
            user_id
        ] = OTPRecord(
            otp_hash=self._hash_otp(
                otp
            ),
            expires_at=(
                time.time()
                + OTP_EXPIRY_SECONDS
            ),
        )

        return {
            "verified": False,
            "recovery_allowed": False,
            "mfa_required":
                self.is_elevated_role(
                    role
                ),
            "message":
                "Recovery OTP issued successfully.",
            "development_otp":
                otp,
            "expires_in_seconds":
                OTP_EXPIRY_SECONDS,
        }


    def verify_recovery(
        self,
        user_id: str,
        phone_number: str,
        role: str,
        otp: str,
        source: str,
    ):

        if (
            phone_number
            not in self._verified_identities
        ):

            return {
                "verified": False,
                "recovery_allowed": False,
                "mfa_required": False,
                "message":
                    "Verified identity is required.",
                "development_otp": None,
                "expires_in_seconds": 0,
            }

        # Elevated role cannot bypass MFA.
        if self.is_elevated_role(
            role
        ):

            return {
                "verified": False,
                "recovery_allowed": False,
                "mfa_required": True,
                "message":
                    "MFA verification is required for elevated-role recovery.",
                "development_otp": None,
                "expires_in_seconds": 0,
            }

        record = self._recovery_store.get(
            user_id
        )

        if record is None:

            return {
                "verified": False,
                "recovery_allowed": False,
                "mfa_required": False,
                "message":
                    "Recovery OTP not found.",
                "development_otp": None,
                "expires_in_seconds": 0,
            }

        now = time.time()

        if now > record.expires_at:

            del self._recovery_store[
                user_id
            ]

            return {
                "verified": False,
                "recovery_allowed": False,
                "mfa_required": False,
                "message":
                    "Recovery OTP has expired.",
                "development_otp": None,
                "expires_in_seconds": 0,
            }

        if record.used:

            return {
                "verified": False,
                "recovery_allowed": False,
                "mfa_required": False,
                "message":
                    "Recovery OTP has already been used.",
                "development_otp": None,
                "expires_in_seconds": 0,
            }

        if not hmac.compare_digest(
            record.otp_hash,
            self._hash_otp(otp),
        ):

            return {
                "verified": False,
                "recovery_allowed": False,
                "mfa_required": False,
                "message":
                    "Invalid recovery OTP.",
                "development_otp": None,
                "expires_in_seconds": 0,
            }

        record.used = True

        return {
            "verified": True,
            "recovery_allowed": True,
            "mfa_required": False,
            "message":
                "Account recovery verified successfully.",
            "development_otp": None,
            "expires_in_seconds": 0,
        }


    # =====================================================
    # BE-001 DEVICE SECURITY
    # =====================================================

    def check_device_security(
        self,
        user_id: str,
        is_rooted: bool,
        is_jailbroken: bool,
    ):

        if is_rooted:

            return {
                "allowed": False,
                "message":
                    "Access denied. Rooted device detected.",
            }

        if is_jailbroken:

            return {
                "allowed": False,
                "message":
                    "Access denied. Jailbroken device detected.",
            }

        return {
            "allowed": True,
            "message":
                "Device security check passed.",
        }


    # =====================================================
    # BE-002 DEVICE REGISTRATION
    # =====================================================

    def register_device(
        self,
        user_id: str,
        device_id: str,
    ):

        key = (
            user_id,
            device_id,
        )

        existing = self._devices.get(
            key
        )

        if (
            existing is not None
            and existing.revoked_at is None
        ):

            return {
                "registered": True,
                "user_id":
                    user_id,
                "device_id":
                    device_id,
                "message":
                    "Device is already registered.",
            }

        self._devices[key] = DeviceRecord(
            user_id=user_id,
            device_id=device_id,
            registered_at=time.time(),
            revoked_at=None,
        )

        return {
            "registered": True,
            "user_id":
                user_id,
            "device_id":
                device_id,
            "message":
                "Device registered successfully.",
        }


    # =====================================================
    # BE-002 SESSION CREATION
    # =====================================================

    def create_session(
        self,
        user_id: str,
        device_id: str,
    ):

        key = (
            user_id,
            device_id,
        )

        device = self._devices.get(
            key
        )

        # -------------------------------------------------
        # Unregistered/revoked device
        # -------------------------------------------------

        if (
            device is None
            or device.revoked_at is not None
        ):

            return {
                "session_created": False,
                "session_id": None,
                "access_token": None,
                "refresh_token": None,
                "device_id":
                    device_id,
                "idle_expires_in_seconds": 0,
                "absolute_expires_in_seconds": 0,
                "step_up_required": True,
                "message":
                    "Device is not registered. Step-up verification is required.",
            }

        now = time.time()

        session_id = secrets.token_urlsafe(
            32
        )

        access_token = secrets.token_urlsafe(
            48
        )

        refresh_token = secrets.token_urlsafe(
            64
        )

        family_id = secrets.token_urlsafe(
            32
        )

        session = SessionRecord(
            session_id=session_id,
            user_id=user_id,
            device_id=device_id,
            family_id=family_id,
            access_token_hash=
                self._hash_session_token(
                    access_token
                ),
            refresh_token_hash=
                self._hash_session_token(
                    refresh_token
                ),
            created_at=now,
            last_activity_at=now,
            absolute_expires_at=(
                now
                + SESSION_ABSOLUTE_TIMEOUT_SECONDS
            ),
        )

        self._sessions[
            session_id
        ] = session

        return {
            "session_created": True,
            "session_id":
                session_id,
            "access_token":
                access_token,
            "refresh_token":
                refresh_token,
            "device_id":
                device_id,
            "idle_expires_in_seconds":
                SESSION_IDLE_TIMEOUT_SECONDS,
            "absolute_expires_in_seconds":
                SESSION_ABSOLUTE_TIMEOUT_SECONDS,
            "step_up_required": False,
            "message":
                "Session created successfully.",
        }


    # =====================================================
    # BE-002 REFRESH TOKEN ROTATION
    # =====================================================

    def refresh_session(
        self,
        refresh_token: str,
    ):

        token_hash = (
            self._hash_session_token(
                refresh_token
            )
        )

        matched_session = None

        for session in self._sessions.values():

            if (
                session.refresh_token_hash
                == token_hash
            ):

                matched_session = session

                break

        # -------------------------------------------------
        # Token not found
        # -------------------------------------------------

        if matched_session is None:

            # -------------------------------------------------
            # Previously rotated token
            # -------------------------------------------------

            family_id = (
                self._rotated_refresh_tokens.get(
                    token_hash
                )
            )

            if family_id is not None:

                affected = (
                    self._invalidate_session_family(
                        family_id
                    )
                )

                self._record_security_event(
                    "refresh_token_reuse",
                    family_id,
                )

                return {
                    "refreshed": False,
                    "session_id": None,
                    "access_token": None,
                    "refresh_token": None,
                    "idle_expires_in_seconds": 0,
                    "absolute_expires_in_seconds": 0,
                    "family_invalidated": True,
                    "security_event": True,
                    "message":
                        "Refresh-token reuse detected. Entire session family invalidated.",
                }

            return {
                "refreshed": False,
                "session_id": None,
                "access_token": None,
                "refresh_token": None,
                "idle_expires_in_seconds": 0,
                "absolute_expires_in_seconds": 0,
                "family_invalidated": False,
                "security_event": False,
                "message":
                    "Invalid refresh token.",
            }

        session = matched_session

        # -------------------------------------------------
        # Revoked session
        # -------------------------------------------------

        if session.revoked_at is not None:

            return {
                "refreshed": False,
                "session_id":
                    session.session_id,
                "access_token": None,
                "refresh_token": None,
                "idle_expires_in_seconds": 0,
                "absolute_expires_in_seconds": 0,
                "family_invalidated": False,
                "security_event": False,
                "message":
                    "Session has been revoked.",
            }

        now = time.time()

        # -------------------------------------------------
        # Idle timeout
        # -------------------------------------------------

        idle_expired = (
            now
            - session.last_activity_at
            > SESSION_IDLE_TIMEOUT_SECONDS
        )

        if idle_expired:

            session.revoked_at = now

            session.purge_offline_data = True

            return {
                "refreshed": False,
                "session_id":
                    session.session_id,
                "access_token": None,
                "refresh_token": None,
                "idle_expires_in_seconds": 0,
                "absolute_expires_in_seconds":
                    max(
                        0,
                        int(
                            session.absolute_expires_at
                            - now
                        ),
                    ),
                "family_invalidated": False,
                "security_event": False,
                "message":
                    "Session idle timeout exceeded.",
            }

        # -------------------------------------------------
        # Absolute timeout
        # -------------------------------------------------

        if now >= session.absolute_expires_at:

            session.revoked_at = now

            session.purge_offline_data = True

            return {
                "refreshed": False,
                "session_id":
                    session.session_id,
                "access_token": None,
                "refresh_token": None,
                "idle_expires_in_seconds": 0,
                "absolute_expires_in_seconds": 0,
                "family_invalidated": False,
                "security_event": False,
                "message":
                    "Session absolute expiry exceeded.",
            }

        # -------------------------------------------------
        # Rotate refresh token
        # -------------------------------------------------

        old_refresh_hash = (
            session.refresh_token_hash
        )

        new_access_token = (
            secrets.token_urlsafe(48)
        )

        new_refresh_token = (
            secrets.token_urlsafe(64)
        )

        session.access_token_hash = (
            self._hash_session_token(
                new_access_token
            )
        )

        session.refresh_token_hash = (
            self._hash_session_token(
                new_refresh_token
            )
        )

        session.last_activity_at = now

        # Store old token for reuse detection.
        self._rotated_refresh_tokens[
            old_refresh_hash
        ] = session.family_id

        absolute_remaining = max(
            0,
            int(
                session.absolute_expires_at
                - now
            ),
        )

        return {
            "refreshed": True,
            "session_id":
                session.session_id,
            "access_token":
                new_access_token,
            "refresh_token":
                new_refresh_token,
            "idle_expires_in_seconds":
                SESSION_IDLE_TIMEOUT_SECONDS,
            "absolute_expires_in_seconds":
                absolute_remaining,
            "family_invalidated": False,
            "security_event": False,
            "message":
                "Session refreshed successfully.",
        }


    # =====================================================
    # BE-002 SESSION STATUS
    # =====================================================

    def session_status(
        self,
        session_id: str,
    ):

        session = self._sessions.get(
            session_id
        )

        if session is None:

            return {
                "active": False,
                "session_id":
                    session_id,
                "user_id": None,
                "device_id": None,
                "idle_expired": False,
                "absolute_expired": False,
                "revoked": False,
                "purge_offline_data": False,
                "message":
                    "Session not found.",
            }

        now = time.time()

        idle_expired = (
            now
            - session.last_activity_at
            > SESSION_IDLE_TIMEOUT_SECONDS
        )

        absolute_expired = (
            now >= session.absolute_expires_at
        )

        if (
            idle_expired
            or absolute_expired
        ):

            session.revoked_at = now

            session.purge_offline_data = True

        revoked = (
            session.revoked_at is not None
        )

        return {
            "active":
                not revoked,
            "session_id":
                session.session_id,
            "user_id":
                session.user_id,
            "device_id":
                session.device_id,
            "idle_expired":
                idle_expired,
            "absolute_expired":
                absolute_expired,
            "revoked":
                revoked,
            "purge_offline_data":
                session.purge_offline_data,
            "message": (
                "Session is active."
                if not revoked
                else
                "Session is no longer active."
            ),
        }


    # =====================================================
    # BE-002 REMOTE LOGOUT
    # =====================================================

    def logout_session(
        self,
        session_id: str,
    ):

        session = self._sessions.get(
            session_id
        )

        if session is None:

            return {
                "logged_out": False,
                "session_id":
                    session_id,
                "purge_offline_data": False,
                "message":
                    "Session not found.",
            }

        session.revoked_at = time.time()

        session.purge_offline_data = True

        return {
            "logged_out": True,
            "session_id":
                session_id,
            "purge_offline_data": True,
            "message":
                "Session remotely logged out. Offline data purge signal issued.",
        }


    # =====================================================
    # BE-002 DEVICE REVOCATION
    # =====================================================

    def revoke_device(
        self,
        user_id: str,
        device_id: str,
    ):

        key = (
            user_id,
            device_id,
        )

        device = self._devices.get(
            key
        )

        if device is None:

            return {
                "revoked": False,
                "user_id":
                    user_id,
                "device_id":
                    device_id,
                "affected_sessions": 0,
                "purge_offline_data": False,
                "message":
                    "Device not found.",
            }

        device.revoked_at = time.time()

        affected_sessions = 0

        now = time.time()

        for session in self._sessions.values():

            if (
                session.user_id
                == user_id
                and session.device_id
                == device_id
                and session.revoked_at is None
            ):

                session.revoked_at = now

                session.purge_offline_data = True

                affected_sessions += 1

        return {
            "revoked": True,
            "user_id":
                user_id,
            "device_id":
                device_id,
            "affected_sessions":
                affected_sessions,
            "purge_offline_data": True,
            "message":
                "Device revoked successfully. All active sessions were invalidated.",
        }
        # =====================================================
    # ACCESS TOKEN VALIDATION
    # =====================================================

    def validate_access_token(
        self,
        access_token: str,
    ):
        token_hash = self._hash_session_token(
            access_token
        )

        matched_session = None

        for session in self._sessions.values():
            if (
                session.access_token_hash
                == token_hash
            ):
                matched_session = session
                break

        # Token not found
        if matched_session is None:
            return None

        session = matched_session
        now = time.time()

        # Revoked session
        if session.revoked_at is not None:
            return None

        # Absolute session expiry
        if now >= session.absolute_expires_at:
            session.revoked_at = now
            session.purge_offline_data = True
            return None

        # Idle session expiry
        if (
            now - session.last_activity_at
            > SESSION_IDLE_TIMEOUT_SECONDS
        ):
            session.revoked_at = now
            session.purge_offline_data = True
            return None

        # Update activity timestamp
        session.last_activity_at = now

        return {
            "user_id": session.user_id,
            "session_id": session.session_id,
            "device_id": session.device_id,
        }

    # =====================================================
    # BE-002 SESSION TOKEN HASH
    # =====================================================

    @staticmethod
    def _hash_session_token(
        token: str,
    ) -> str:

        return hashlib.sha256(
            token.encode("utf-8")
        ).hexdigest()


    # =====================================================
    # BE-002 INVALIDATE SESSION FAMILY
    # =====================================================

    def _invalidate_session_family(
        self,
        family_id: str,
    ) -> int:

        count = 0

        now = time.time()

        for session in self._sessions.values():

            if (
                session.family_id
                == family_id
                and session.revoked_at is None
            ):

                session.revoked_at = now

                session.purge_offline_data = True

                count += 1

        return count


    # =====================================================
    # BE-002 SECURITY EVENT
    # =====================================================

    def _record_security_event(
        self,
        event_type: str,
        family_id: str,
    ):

        self._security_events.append(
            {
                "event_type":
                    event_type,
                "family_id":
                    family_id,
                "timestamp":
                    time.time(),
            }
        )


    # =====================================================
    # BE-002 GET SECURITY EVENTS
    # =====================================================

    def get_security_events(self):

        return list(
            self._security_events
        )


# =========================================================
# GLOBAL AUTH SERVICE
# =========================================================

auth_service = AuthService()