from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any


# ============================================================
# BE-012: Transport & At-Rest Encryption
# ============================================================


class SecurityConfigurationError(Exception):
    """Raised when a required security configuration is invalid."""


class EncryptionError(Exception):
    """Raised when encryption/decryption fails."""


class IncidentError(Exception):
    """Raised for invalid incident operations."""


class IncidentSeverity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    CONTAINED = "CONTAINED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


@dataclass
class SecurityHeaders:
    """
    Recommended transport-security headers.

    TLS itself is normally configured at the reverse proxy /
    load balancer. These headers represent the application-side
    security configuration.
    """

    strict_transport_security: str
    x_content_type_options: str
    x_frame_options: str
    referrer_policy: str


@dataclass
class TLSConfiguration:
    minimum_version: str = "TLSv1.2"
    preferred_version: str = "TLSv1.3"
    hsts_enabled: bool = True
    certificate_pinning_required: bool = True


@dataclass
class EncryptedValue:
    """
    Serializable encrypted value.

    The implementation uses AES-GCM when the `cryptography`
    package is available.
    """

    algorithm: str
    nonce: str
    ciphertext: str
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AESGCMEncryption:
    """
    AES-GCM encryption helper.

    Used for:
    - database sensitive fields
    - object-storage sensitive values
    - backup sensitive values
    - queue payloads that contain sensitive values

    The encryption key must be supplied by secure configuration
    in production. It must never be committed to Git.
    """

    ALGORITHM = "AES-256-GCM"
    NONCE_SIZE = 12
    KEY_SIZE = 32

    def __init__(self, key: bytes | str | None = None):
        self._cryptography_available = False

        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM

            self._AESGCM = AESGCM
            self._cryptography_available = True

        except ImportError:
            self._AESGCM = None

        if key is None:
            # Development-only ephemeral key.
            #
            # IMPORTANT:
            # This key changes when the application restarts.
            # Production must provide a persistent secret from a
            # proper secret-management system.
            key = secrets.token_bytes(self.KEY_SIZE)

        if isinstance(key, str):
            key = self._decode_key(key)

        if len(key) not in {16, 24, 32}:
            raise SecurityConfigurationError(
                "AES key must be 16, 24, or 32 bytes."
            )

        if not self._cryptography_available:
            raise SecurityConfigurationError(
                "The 'cryptography' package is required for AES-GCM "
                "encryption. Install it before using this service."
            )

        self._key = key
        self._aes = self._AESGCM(self._key)

    # --------------------------------------------------------
    # Key Handling
    # --------------------------------------------------------

    @staticmethod
    def _decode_key(key: str) -> bytes:
        """
        Accept either:
        - base64 encoded key
        - hexadecimal key
        """

        value = key.strip()

        # Try base64 first.
        try:
            decoded = base64.urlsafe_b64decode(
                value.encode("utf-8")
            )

            if len(decoded) in {16, 24, 32}:
                return decoded

        except Exception:
            pass

        # Try hexadecimal.
        try:
            decoded = bytes.fromhex(value)

            if len(decoded) in {16, 24, 32}:
                return decoded

        except ValueError:
            pass

        raise SecurityConfigurationError(
            "Encryption key must be a valid base64 or hexadecimal key."
        )

    @staticmethod
    def generate_key() -> str:
        """
        Generate a 256-bit base64 key.

        Store the generated value in a secret manager or environment
        variable. Do NOT commit it to Git.
        """

        return base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).decode("utf-8")

    # --------------------------------------------------------
    # Encryption
    # --------------------------------------------------------

    def encrypt(
        self,
        value: str | bytes,
        associated_data: str | bytes | None = None,
    ) -> EncryptedValue:
        """
        Encrypt a value using AES-256-GCM.
        """

        try:
            if isinstance(value, str):
                plaintext = value.encode("utf-8")
            else:
                plaintext = value

            if associated_data is None:
                aad = None
            elif isinstance(associated_data, str):
                aad = associated_data.encode("utf-8")
            else:
                aad = associated_data

            nonce = secrets.token_bytes(self.NONCE_SIZE)

            ciphertext = self._aes.encrypt(
                nonce,
                plaintext,
                aad,
            )

            return EncryptedValue(
                algorithm=self.ALGORITHM,
                nonce=base64.urlsafe_b64encode(
                    nonce
                ).decode("utf-8"),
                ciphertext=base64.urlsafe_b64encode(
                    ciphertext
                ).decode("utf-8"),
            )

        except Exception as exc:
            raise EncryptionError(
                "Encryption failed."
            ) from exc

    # --------------------------------------------------------
    # Decryption
    # --------------------------------------------------------

    def decrypt(
        self,
        encrypted: EncryptedValue | dict[str, Any],
        associated_data: str | bytes | None = None,
    ) -> bytes:
        """
        Decrypt an AES-GCM encrypted value.
        """

        try:
            if isinstance(encrypted, dict):
                encrypted = EncryptedValue(
                    algorithm=encrypted["algorithm"],
                    nonce=encrypted["nonce"],
                    ciphertext=encrypted["ciphertext"],
                    version=int(
                        encrypted.get("version", 1)
                    ),
                )

            if encrypted.algorithm != self.ALGORITHM:
                raise EncryptionError(
                    "Unsupported encryption algorithm."
                )

            nonce = base64.urlsafe_b64decode(
                encrypted.nonce.encode("utf-8")
            )

            ciphertext = base64.urlsafe_b64decode(
                encrypted.ciphertext.encode("utf-8")
            )

            if associated_data is None:
                aad = None
            elif isinstance(associated_data, str):
                aad = associated_data.encode("utf-8")
            else:
                aad = associated_data

            return self._aes.decrypt(
                nonce,
                ciphertext,
                aad,
            )

        except EncryptionError:
            raise

        except Exception as exc:
            raise EncryptionError(
                "Decryption failed or ciphertext was tampered with."
            ) from exc

    def decrypt_text(
        self,
        encrypted: EncryptedValue | dict[str, Any],
        associated_data: str | bytes | None = None,
    ) -> str:
        return self.decrypt(
            encrypted,
            associated_data,
        ).decode("utf-8")


# ============================================================
# Field-Level Encryption
# ============================================================


class SensitiveFieldEncryptor:
    """
    Field-level encryption helper.

    Intended for particularly sensitive PII fields.

    Example:
        {
            "name": "Example",
            "phone": "<encrypted>",
            "identity_number": "<encrypted>"
        }
    """

    DEFAULT_SENSITIVE_FIELDS = {
        "phone_number",
        "phone",
        "email",
        "address",
        "identity_number",
        "government_id",
        "citizen_id",
        "location",
    }

    def __init__(
        self,
        encryption: AESGCMEncryption,
        sensitive_fields: set[str] | None = None,
    ):
        self.encryption = encryption
        self.sensitive_fields = (
            sensitive_fields
            or self.DEFAULT_SENSITIVE_FIELDS.copy()
        )

    def encrypt_fields(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Encrypt configured sensitive fields.

        Non-sensitive fields remain unchanged.
        """

        result = dict(data)

        for field_name in self.sensitive_fields:

            if field_name not in result:
                continue

            value = result[field_name]

            if value is None:
                continue

            if isinstance(value, (dict, list)):
                value = json.dumps(
                    value,
                    ensure_ascii=False,
                )

            encrypted = self.encryption.encrypt(
                str(value),
                associated_data=field_name,
            )

            result[field_name] = {
                "__encrypted__": True,
                **encrypted.to_dict(),
            }

        return result

    def decrypt_fields(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Decrypt fields previously encrypted by encrypt_fields().
        """

        result = dict(data)

        for field_name in self.sensitive_fields:

            value = result.get(field_name)

            if not isinstance(value, dict):
                continue

            if not value.get("__encrypted__"):
                continue

            encrypted_data = {
                key: item
                for key, item in value.items()
                if key != "__encrypted__"
            }

            result[field_name] = self.encryption.decrypt_text(
                encrypted_data,
                associated_data=field_name,
            )

        return result


# ============================================================
# Transport Security
# ============================================================


class TransportSecurity:
    """
    Application-level representation of transport security.

    Actual TLS negotiation and mobile certificate pinning are
    normally enforced by infrastructure/mobile-client configuration.
    """

    def __init__(
        self,
        minimum_tls_version: str = "TLSv1.2",
        preferred_tls_version: str = "TLSv1.3",
        hsts_enabled: bool = True,
        certificate_pinning_required: bool = True,
    ):
        self.configuration = TLSConfiguration(
            minimum_version=minimum_tls_version,
            preferred_version=preferred_tls_version,
            hsts_enabled=hsts_enabled,
            certificate_pinning_required=certificate_pinning_required,
        )

    def validate(self) -> dict[str, Any]:
        supported_versions = {
            "TLSv1.2": 1.2,
            "TLSv1.3": 1.3,
        }

        minimum = supported_versions.get(
            self.configuration.minimum_version
        )

        preferred = supported_versions.get(
            self.configuration.preferred_version
        )

        if minimum is None:
            raise SecurityConfigurationError(
                "Minimum TLS version must be TLSv1.2 or TLSv1.3."
            )

        if preferred is None:
            raise SecurityConfigurationError(
                "Preferred TLS version must be TLSv1.2 or TLSv1.3."
            )

        if minimum < 1.2:
            raise SecurityConfigurationError(
                "TLS versions below 1.2 are not permitted."
            )

        if preferred < minimum:
            raise SecurityConfigurationError(
                "Preferred TLS version cannot be below minimum TLS version."
            )

        return {
            "valid": True,
            "minimum_tls_version": (
                self.configuration.minimum_version
            ),
            "preferred_tls_version": (
                self.configuration.preferred_version
            ),
            "hsts_enabled": (
                self.configuration.hsts_enabled
            ),
            "certificate_pinning_required": (
                self.configuration.certificate_pinning_required
            ),
        }

    def security_headers(self) -> SecurityHeaders:
        return SecurityHeaders(
            strict_transport_security=(
                "max-age=31536000; includeSubDomains"
            ),
            x_content_type_options="nosniff",
            x_frame_options="DENY",
            referrer_policy="no-referrer",
        )


# ============================================================
# BE-013: Incident Response
# ============================================================


@dataclass
class Incident:
    incident_id: str
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus

    created_at: float
    updated_at: float

    assigned_to: str | None = None
    escalation_level: int = 0

    evidence_ids: list[str] | None = None

    containment_notes: str | None = None
    resolution_notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)

        data["severity"] = self.severity.value
        data["status"] = self.status.value

        return data


@dataclass
class EvidenceRecord:
    evidence_id: str
    incident_id: str
    evidence_type: str
    integrity_hash: str
    captured_at: float
    captured_by: str

    # Do not store raw sensitive evidence here.
    location_reference: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IncidentResponseService:
    """
    BE-013 incident-response service.

    Provides:
    - severity classification
    - escalation
    - evidence preservation metadata
    - incident ownership
    - vulnerability SLA lookup
    - production pentest release gate
    """

    # Vulnerability remediation targets.
    VULNERABILITY_SLA_HOURS = {
        "CRITICAL": 24,
        "HIGH": 72,
        "MEDIUM": 168,
        "LOW": 720,
    }

    def __init__(
        self,
        pentest_required_before_production: bool = False,
    ):
        self.pentest_required_before_production = (
            pentest_required_before_production
        )

        self._incidents: dict[str, Incident] = {}
        self._evidence: dict[str, EvidenceRecord] = {}

        self._security_responsibilities = {
            "incident_commander": None,
            "security_lead": None,
            "engineering_lead": None,
            "communications_lead": None,
            "evidence_custodian": None,
        }

        self._pentest_status = {
            "completed": False,
            "critical_findings": 0,
            "high_findings": 0,
            "release_approved": False,
            "last_test_at": None,
        }

    # --------------------------------------------------------
    # Incident Creation
    # --------------------------------------------------------

    def create_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity | str,
        assigned_to: str | None = None,
    ) -> dict[str, Any]:

        severity = self._normalize_severity(severity)

        now = time.time()

        incident_id = (
            "INC-"
            + secrets.token_hex(8).upper()
        )

        incident = Incident(
            incident_id=incident_id,
            title=self._safe_text(title),
            description=self._safe_text(description),
            severity=severity,
            status=IncidentStatus.OPEN,
            created_at=now,
            updated_at=now,
            assigned_to=assigned_to,
            escalation_level=self._initial_escalation_level(
                severity
            ),
            evidence_ids=[],
        )

        self._incidents[incident_id] = incident

        return incident.to_dict()

    # --------------------------------------------------------
    # Incident Retrieval
    # --------------------------------------------------------

    def get_incident(
        self,
        incident_id: str,
    ) -> dict[str, Any] | None:

        incident = self._incidents.get(incident_id)

        if incident is None:
            return None

        return incident.to_dict()

    def list_incidents(
        self,
        severity: IncidentSeverity | str | None = None,
        status: IncidentStatus | str | None = None,
    ) -> list[dict[str, Any]]:

        normalized_severity = (
            self._normalize_severity(severity)
            if severity is not None
            else None
        )

        normalized_status = (
            self._normalize_status(status)
            if status is not None
            else None
        )

        results = []

        for incident in self._incidents.values():

            if (
                normalized_severity is not None
                and incident.severity != normalized_severity
            ):
                continue

            if (
                normalized_status is not None
                and incident.status != normalized_status
            ):
                continue

            results.append(
                incident.to_dict()
            )

        return sorted(
            results,
            key=lambda item: item["created_at"],
            reverse=True,
        )

    # --------------------------------------------------------
    # Status Management
    # --------------------------------------------------------

    def update_status(
        self,
        incident_id: str,
        status: IncidentStatus | str,
        notes: str | None = None,
    ) -> dict[str, Any]:

        incident = self._get_incident_or_raise(
            incident_id
        )

        incident.status = self._normalize_status(status)
        incident.updated_at = time.time()

        if notes:
            safe_notes = self._safe_text(notes)

            if incident.status == IncidentStatus.CONTAINED:
                incident.containment_notes = safe_notes

            elif incident.status in {
                IncidentStatus.RESOLVED,
                IncidentStatus.CLOSED,
            }:
                incident.resolution_notes = safe_notes

        return incident.to_dict()

    # --------------------------------------------------------
    # Assignment / Escalation
    # --------------------------------------------------------

    def assign_incident(
        self,
        incident_id: str,
        assignee: str,
    ) -> dict[str, Any]:

        incident = self._get_incident_or_raise(
            incident_id
        )

        incident.assigned_to = self._safe_text(
            assignee
        )

        incident.updated_at = time.time()

        return incident.to_dict()

    def escalate(
        self,
        incident_id: str,
    ) -> dict[str, Any]:

        incident = self._get_incident_or_raise(
            incident_id
        )

        incident.escalation_level += 1
        incident.updated_at = time.time()

        return incident.to_dict()

    # --------------------------------------------------------
    # Evidence Preservation
    # --------------------------------------------------------

    def preserve_evidence(
        self,
        incident_id: str,
        evidence_type: str,
        evidence_bytes: bytes,
        captured_by: str,
        location_reference: str | None = None,
    ) -> dict[str, Any]:

        incident = self._get_incident_or_raise(
            incident_id
        )

        if not isinstance(evidence_bytes, bytes):
            raise IncidentError(
                "Evidence must be supplied as bytes."
            )

        integrity_hash = hashlib.sha256(
            evidence_bytes
        ).hexdigest()

        evidence_id = (
            "EVD-"
            + secrets.token_hex(8).upper()
        )

        record = EvidenceRecord(
            evidence_id=evidence_id,
            incident_id=incident_id,
            evidence_type=self._safe_text(
                evidence_type
            ),
            integrity_hash=integrity_hash,
            captured_at=time.time(),
            captured_by=self._safe_text(
                captured_by
            ),
            location_reference=(
                self._safe_text(location_reference)
                if location_reference
                else None
            ),
        )

        self._evidence[evidence_id] = record

        if incident.evidence_ids is None:
            incident.evidence_ids = []

        incident.evidence_ids.append(
            evidence_id
        )

        incident.updated_at = time.time()

        return record.to_dict()

    def get_evidence(
        self,
        evidence_id: str,
    ) -> dict[str, Any] | None:

        record = self._evidence.get(
            evidence_id
        )

        if record is None:
            return None

        return record.to_dict()

    # --------------------------------------------------------
    # Responsibility Assignment
    # --------------------------------------------------------

    def assign_responsibility(
        self,
        responsibility: str,
        person_id: str,
    ) -> dict[str, Any]:

        allowed = set(
            self._security_responsibilities.keys()
        )

        if responsibility not in allowed:
            raise IncidentError(
                f"Unknown responsibility: {responsibility}"
            )

        self._security_responsibilities[
            responsibility
        ] = self._safe_text(person_id)

        return dict(
            self._security_responsibilities
        )

    def get_responsibilities(self) -> dict[str, str | None]:
        return dict(
            self._security_responsibilities
        )

    # --------------------------------------------------------
    # Vulnerability SLA
    # --------------------------------------------------------

    def vulnerability_sla(
        self,
        severity: IncidentSeverity | str,
    ) -> dict[str, Any]:

        normalized = self._normalize_severity(
            severity
        )

        hours = self.VULNERABILITY_SLA_HOURS[
            normalized.value
        ]

        return {
            "severity": normalized.value,
            "remediation_sla_hours": hours,
        }

    # --------------------------------------------------------
    # Pentest
    # --------------------------------------------------------

    def record_pentest(
        self,
        *,
        critical_findings: int,
        high_findings: int,
        completed: bool = True,
    ) -> dict[str, Any]:

        if critical_findings < 0:
            raise IncidentError(
                "Critical finding count cannot be negative."
            )

        if high_findings < 0:
            raise IncidentError(
                "High finding count cannot be negative."
            )

        self._pentest_status = {
            "completed": completed,
            "critical_findings": critical_findings,
            "high_findings": high_findings,
            "release_approved": (
                completed
                and critical_findings == 0
                and high_findings == 0
            ),
            "last_test_at": time.time(),
        }

        return dict(
            self._pentest_status
        )

    def production_release_check(self) -> dict[str, Any]:
        """
        Determine whether the application-side pentest gate
        permits production release.

        When pentest_required_before_production=False,
        the check is reported as advisory rather than enforced.
        """

        if not self.pentest_required_before_production:
            return {
                "allowed": True,
                "enforced": False,
                "reason": (
                    "Pentest release gate is configured as advisory."
                ),
                "pentest": dict(
                    self._pentest_status
                ),
            }

        pentest = self._pentest_status

        allowed = (
            pentest["completed"]
            and pentest["critical_findings"] == 0
            and pentest["high_findings"] == 0
        )

        if allowed:
            reason = (
                "Pentest completed and critical/high findings are resolved."
            )
        else:
            reason = (
                "Production release blocked until pentest is completed "
                "and critical/high findings are resolved."
            )

        return {
            "allowed": allowed,
            "enforced": True,
            "reason": reason,
            "pentest": dict(pentest),
        }

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------

    def _get_incident_or_raise(
        self,
        incident_id: str,
    ) -> Incident:

        incident = self._incidents.get(
            incident_id
        )

        if incident is None:
            raise IncidentError(
                f"Incident '{incident_id}' not found."
            )

        return incident

    @staticmethod
    def _normalize_severity(
        severity: IncidentSeverity | str,
    ) -> IncidentSeverity:

        if isinstance(
            severity,
            IncidentSeverity,
        ):
            return severity

        try:
            return IncidentSeverity(
                str(severity).upper()
            )
        except ValueError as exc:
            raise IncidentError(
                f"Invalid incident severity: {severity}"
            ) from exc

    @staticmethod
    def _normalize_status(
        status: IncidentStatus | str,
    ) -> IncidentStatus:

        if isinstance(
            status,
            IncidentStatus,
        ):
            return status

        try:
            return IncidentStatus(
                str(status).upper()
            )
        except ValueError as exc:
            raise IncidentError(
                f"Invalid incident status: {status}"
            ) from exc

    @staticmethod
    def _initial_escalation_level(
        severity: IncidentSeverity,
    ) -> int:

        levels = {
            IncidentSeverity.LOW: 0,
            IncidentSeverity.MEDIUM: 1,
            IncidentSeverity.HIGH: 2,
            IncidentSeverity.CRITICAL: 3,
        }

        return levels[severity]

    @staticmethod
    def _safe_text(
        value: Any,
    ) -> str:

        text = str(value)

        # Do not accidentally persist obvious secrets.
        sensitive_terms = (
            "password",
            "otp",
            "access_token",
            "refresh_token",
            "api_key",
            "secret",
        )

        lowered = text.lower()

        if any(
            term in lowered
            for term in sensitive_terms
        ):
            return "[REDACTED]"

        return text


# ============================================================
# Global Security Services
# ============================================================


transport_security = TransportSecurity()

# Development key only.
# Production should initialise this using a secure environment/
# secret-management value.
encryption_service = AESGCMEncryption()

field_encryptor = SensitiveFieldEncryptor(
    encryption_service
)

incident_response_service = IncidentResponseService(
    pentest_required_before_production=True
)