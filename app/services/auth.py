import hashlib
import json
import secrets
import time
from dataclasses import asdict, dataclass
from pathlib import Path


# =========================================================
# Configuration
# =========================================================

OTP_EXPIRY_SECONDS = 300
MAX_OTP_ATTEMPTS = 5

LOCKOUT_DURATIONS = [30, 60, 120, 300]

DATA_DIR = Path(".auth_data")
LOCKOUT_FILE = DATA_DIR / "lockouts.json"


# Elevated roles require MFA.
ELEVATED_ROLES = {
    "leader",
    "org admin",
    "compliance",
    "security admin",
    "platform operator",
}


# =========================================================
# Data Models
# =========================================================

@dataclass
class OTPRecord:
    otp_hash: str
    expires_at: float
    attempts: int = 0
    used: bool = False


@dataclass
class LockoutRecord:
    failures: int = 0
    locked_until: float = 0.0


# =========================================================
# Authentication Service
# =========================================================

class AuthService:

    def __init__(self):
        # Normal OTP store
        self._otp_store: dict[str, OTPRecord] = {}

        # MFA OTP store
        self._mfa_store: dict[str, OTPRecord] = {}

        # Recovery OTP store
        self._recovery_store: dict[str, OTPRecord] = {}

        # Identity verified through normal OTP
        self._verified_identities: set[str] = set()

        # Persistent lockout records
        self._lockouts: dict[str, LockoutRecord] = {}

        self._load_lockouts()

    # =====================================================
    # Common Helpers
    # =====================================================

    @staticmethod
    def _hash_otp(otp: str) -> str:
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
    def is_elevated_role(role: str) -> bool:
        return role.strip().lower() in ELEVATED_ROLES

    # =====================================================
    # Persistent Lockout
    # =====================================================

    def _load_lockouts(self):
        DATA_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        if not LOCKOUT_FILE.exists():
            return

        try:
            data = json.loads(
                LOCKOUT_FILE.read_text(
                    encoding="utf-8"
                )
            )

            for key, value in data.items():
                self._lockouts[key] = LockoutRecord(
                    failures=value.get(
                        "failures",
                        0,
                    ),
                    locked_until=value.get(
                        "locked_until",
                        0.0,
                    ),
                )

        except (
            json.JSONDecodeError,
            OSError,
        ):
            self._lockouts = {}

    def _save_lockouts(self):
        DATA_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        data = {
            key: asdict(record)
            for key, record in self._lockouts.items()
        }

        LOCKOUT_FILE.write_text(
            json.dumps(
                data,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _get_lockout(
        self,
        identity: str,
        source: str,
    ) -> LockoutRecord:

        key = self._lockout_key(
            identity,
            source,
        )

        if key not in self._lockouts:
            self._lockouts[key] = LockoutRecord()

        return self._lockouts[key]

    def _is_locked(
        self,
        identity: str,
        source: str,
    ) -> bool:

        record = self._get_lockout(
            identity,
            source,
        )

        if record.locked_until <= 0:
            return False

        if time.time() >= record.locked_until:
            record.locked_until = 0.0
            self._save_lockouts()
            return False

        return True

    def _register_failed_attempt(
        self,
        identity: str,
        source: str,
    ) -> tuple[bool, int]:

        record = self._get_lockout(
            identity,
            source,
        )

        record.failures += 1

        if record.failures % MAX_OTP_ATTEMPTS == 0:

            lock_number = (
                record.failures
                // MAX_OTP_ATTEMPTS
            )

            duration_index = min(
                lock_number - 1,
                len(LOCKOUT_DURATIONS) - 1,
            )

            duration = LOCKOUT_DURATIONS[
                duration_index
            ]

            record.locked_until = (
                time.time()
                + duration
            )

            self._save_lockouts()

            return True, duration

        self._save_lockouts()

        return False, 0

    # =====================================================
    # Normal OTP
    # =====================================================

    def issue_otp(
        self,
        phone_number: str,
    ) -> dict:

        otp = self._generate_otp()

        self._otp_store[phone_number] = OTPRecord(
            otp_hash=self._hash_otp(otp),
            expires_at=(
                time.time()
                + OTP_EXPIRY_SECONDS
            ),
        )

        return {
            "message": "OTP issued successfully.",
            "expires_in_seconds": OTP_EXPIRY_SECONDS,
            "attempts_remaining": MAX_OTP_ATTEMPTS,
            "development_otp": otp,
        }

    def verify_otp(
        self,
        phone_number: str,
        otp: str,
        source: str = "unknown",
    ) -> dict:

        if self._is_locked(
            phone_number,
            source,
        ):
            return {
                "verified": False,
                "message": "Identity is temporarily locked.",
                "attempts_remaining": 0,
                "locked": True,
            }

        record = self._otp_store.get(
            phone_number
        )

        if record is None:
            return {
                "verified": False,
                "message": "No active OTP found.",
                "attempts_remaining": 0,
                "locked": False,
            }

        if record.used:
            return {
                "verified": False,
                "message": "OTP has already been used.",
                "attempts_remaining": 0,
                "locked": False,
            }

        if time.time() > record.expires_at:

            del self._otp_store[
                phone_number
            ]

            return {
                "verified": False,
                "message": "OTP has expired.",
                "attempts_remaining": 0,
                "locked": False,
            }

        if not secrets.compare_digest(
            record.otp_hash,
            self._hash_otp(otp),
        ):

            record.attempts += 1

            locked, _ = (
                self._register_failed_attempt(
                    phone_number,
                    source,
                )
            )

            if locked:
                return {
                    "verified": False,
                    "message": (
                        "Too many failed attempts. "
                        "Identity temporarily locked."
                    ),
                    "attempts_remaining": 0,
                    "locked": True,
                }

            remaining = max(
                MAX_OTP_ATTEMPTS
                - record.attempts,
                0,
            )

            return {
                "verified": False,
                "message": "Invalid OTP.",
                "attempts_remaining": remaining,
                "locked": False,
            }

        # Single-use OTP
        record.used = True

        # Mark identity as verified.
        self._verified_identities.add(
            phone_number
        )

        return {
            "verified": True,
            "message": "OTP verified successfully.",
            "attempts_remaining": MAX_OTP_ATTEMPTS,
            "locked": False,
        }

    # =====================================================
    # MFA
    # =====================================================

    def issue_mfa(
        self,
        user_id: str,
        role: str,
    ) -> dict:

        if not self.is_elevated_role(role):
            return {
                "verified": False,
                "mfa_required": False,
                "message": (
                    "MFA is not required for this role."
                ),
                "development_otp": None,
                "expires_in_seconds": 0,
            }

        otp = self._generate_otp()

        self._mfa_store[user_id] = OTPRecord(
            otp_hash=self._hash_otp(otp),
            expires_at=(
                time.time()
                + OTP_EXPIRY_SECONDS
            ),
        )

        return {
            "verified": False,
            "mfa_required": True,
            "message": "MFA OTP issued successfully.",
            "development_otp": otp,
            "expires_in_seconds": OTP_EXPIRY_SECONDS,
        }

    def verify_mfa(
        self,
        user_id: str,
        role: str,
        otp: str,
        source: str = "unknown",
    ) -> dict:

        if not self.is_elevated_role(role):
            return {
                "verified": True,
                "mfa_required": False,
                "message": (
                    "MFA is not required for this role."
                ),
            }

        if self._is_locked(
            f"mfa:{user_id}",
            source,
        ):
            return {
                "verified": False,
                "mfa_required": True,
                "message": "Identity is temporarily locked.",
            }

        record = self._mfa_store.get(
            user_id
        )

        if record is None:
            return {
                "verified": False,
                "mfa_required": True,
                "message": "No active MFA OTP found.",
            }

        if record.used:
            return {
                "verified": False,
                "mfa_required": True,
                "message": "MFA OTP has already been used.",
            }

        if time.time() > record.expires_at:

            del self._mfa_store[user_id]

            return {
                "verified": False,
                "mfa_required": True,
                "message": "MFA OTP has expired.",
            }

        if not secrets.compare_digest(
            record.otp_hash,
            self._hash_otp(otp),
        ):

            locked, _ = (
                self._register_failed_attempt(
                    f"mfa:{user_id}",
                    source,
                )
            )

            if locked:
                return {
                    "verified": False,
                    "mfa_required": True,
                    "message": (
                        "Too many failed attempts. "
                        "Identity temporarily locked."
                    ),
                }

            return {
                "verified": False,
                "mfa_required": True,
                "message": "Invalid MFA OTP.",
            }

        record.used = True

        return {
            "verified": True,
            "mfa_required": True,
            "message": "MFA verified successfully.",
        }

    # =====================================================
    # Account Recovery
    # =====================================================

    def issue_recovery(
        self,
        user_id: str,
        phone_number: str,
        role: str,
    ) -> dict:

        elevated = self.is_elevated_role(role)

        # Identity must first be verified using normal OTP.
        if phone_number not in self._verified_identities:
            return {
                "verified": False,
                "recovery_allowed": False,
                "mfa_required": elevated,
                "message": (
                    "Verified identity is required "
                    "before account recovery."
                ),
                "development_otp": None,
                "expires_in_seconds": 0,
            }

        otp = self._generate_otp()

        self._recovery_store[user_id] = OTPRecord(
            otp_hash=self._hash_otp(otp),
            expires_at=(
                time.time()
                + OTP_EXPIRY_SECONDS
            ),
        )

        return {
            "verified": False,
            "recovery_allowed": False,
            "mfa_required": elevated,
            "message": "Recovery OTP issued successfully.",
            "development_otp": otp,
            "expires_in_seconds": OTP_EXPIRY_SECONDS,
        }

    def verify_recovery(
        self,
        user_id: str,
        phone_number: str,
        role: str,
        otp: str,
        source: str = "unknown",
    ) -> dict:

        elevated = self.is_elevated_role(role)

        # -------------------------------------------------
        # Verified identity is mandatory
        # -------------------------------------------------

        if phone_number not in self._verified_identities:
            return {
                "verified": False,
                "recovery_allowed": False,
                "mfa_required": elevated,
                "message": (
                    "Verified identity is required "
                    "for account recovery."
                ),
            }

        # -------------------------------------------------
        # Elevated roles cannot silently bypass MFA
        # -------------------------------------------------

        if elevated:
            return {
                "verified": False,
                "recovery_allowed": False,
                "mfa_required": True,
                "message": (
                    "MFA verification is required "
                    "for recovery of an elevated account."
                ),
            }

        # -------------------------------------------------
        # Recovery lockout
        # -------------------------------------------------

        if self._is_locked(
            f"recovery:{user_id}",
            source,
        ):
            return {
                "verified": False,
                "recovery_allowed": False,
                "mfa_required": False,
                "message": "Identity is temporarily locked.",
            }

        record = self._recovery_store.get(
            user_id
        )

        if record is None:
            return {
                "verified": False,
                "recovery_allowed": False,
                "mfa_required": False,
                "message": "No active recovery OTP found.",
            }

        if record.used:
            return {
                "verified": False,
                "recovery_allowed": False,
                "mfa_required": False,
                "message": "Recovery OTP has already been used.",
            }

        if time.time() > record.expires_at:

            del self._recovery_store[
                user_id
            ]

            return {
                "verified": False,
                "recovery_allowed": False,
                "mfa_required": False,
                "message": "Recovery OTP has expired.",
            }

        if not secrets.compare_digest(
            record.otp_hash,
            self._hash_otp(otp),
        ):

            locked, _ = (
                self._register_failed_attempt(
                    f"recovery:{user_id}",
                    source,
                )
            )

            if locked:
                return {
                    "verified": False,
                    "recovery_allowed": False,
                    "mfa_required": False,
                    "message": (
                        "Too many failed attempts. "
                        "Identity temporarily locked."
                    ),
                }

            return {
                "verified": False,
                "recovery_allowed": False,
                "mfa_required": False,
                "message": "Invalid recovery OTP.",
            }

        # Recovery OTP is single-use.
        record.used = True

        return {
            "verified": True,
            "recovery_allowed": True,
            "mfa_required": False,
            "message": (
                "Account recovery identity verified successfully."
            ),
        }

    # =====================================================
    # Device Security
    # =====================================================

    def check_device_security(
        self,
        user_id: str,
        is_rooted: bool = False,
        is_jailbroken: bool = False,
    ) -> dict:

        if is_rooted:
            return {
                "allowed": False,
                "message": (
                    "Access denied. Rooted device detected."
                ),
            }

        if is_jailbroken:
            return {
                "allowed": False,
                "message": (
                    "Access denied. Jailbroken device detected."
                ),
            }

        return {
            "allowed": True,
            "message": (
                "Device security check passed."
            ),
        }


auth_service = AuthService()