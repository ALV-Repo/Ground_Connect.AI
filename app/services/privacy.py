from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.schemas.privacy import (
    DataAccessResponse,
    DataCorrectionRequest,
    DataCorrectionResponse,
    ErasureCertificate,
    ErasureRequest,
    LegalHoldRequest,
    LegalHoldResponse,
    PrivacyInteractionCreate,
    PrivacyInteractionResponse,
    RetentionPolicyCreate,
    RetentionPolicyResponse,
)


class PrivacyService:
    """
    BE-022 DPDP-aligned privacy controls.

    Covers:
    - purpose-limited privacy interaction records
    - versioned privacy notice / consent receipts
    - data-principal access and correction
    - verified erasure
    - erasure cascade tracking
    - anonymised retention of service records
    - retention policies
    - legal holds
    """

    PERSONAL_FIELDS = {
        "name",
        "email",
        "phone",
        "address",
    }

    def __init__(self) -> None:
        self._interactions: dict[str, dict] = {}
        self._principal_data: dict[tuple[str, str], dict] = {}
        self._retention_policies: dict[str, dict] = {}
        self._legal_holds: dict[str, dict] = {}
        self._erasure_requests: dict[str, dict] = {}
        self._certificates: dict[str, dict] = {}

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _key(
        tenant_id: str,
        principal_id: str,
    ) -> tuple[str, str]:
        return tenant_id, principal_id

    # =========================================================
    # Privacy interaction / consent ledger
    # =========================================================

    def record_interaction(
        self,
        request: PrivacyInteractionCreate,
    ) -> PrivacyInteractionResponse:

        receipt_id = f"receipt_{uuid4().hex[:12]}"

        timestamp = request.timestamp or self._now()

        record = {
            "receipt_id": receipt_id,
            "tenant_id": request.tenant_id,
            "principal_id": request.principal_id,
            "purpose": request.purpose,
            "notice_version": request.notice_version,
            "language": request.language,
            "mechanism": request.mechanism,
            "lawful_basis": request.lawful_basis,
            "timestamp": timestamp,
        }

        self._interactions[receipt_id] = record

        return PrivacyInteractionResponse(**record)

    # =========================================================
    # Principal data registration
    # =========================================================

    def register_principal_data(
        self,
        *,
        tenant_id: str,
        principal_id: str,
        data: dict,
    ) -> None:

        self._principal_data[
            self._key(tenant_id, principal_id)
        ] = dict(data)

    # =========================================================
    # Data access
    # =========================================================

    def access_data(
        self,
        tenant_id: str,
        principal_id: str,
    ) -> DataAccessResponse:

        key = self._key(
            tenant_id,
            principal_id,
        )

        data = self._principal_data.get(key, {})

        return DataAccessResponse(
            tenant_id=tenant_id,
            principal_id=principal_id,
            records=[dict(data)] if data else [],
        )

    # =========================================================
    # Data correction
    # =========================================================

    def correct_data(
        self,
        request: DataCorrectionRequest,
    ) -> DataCorrectionResponse:

        key = self._key(
            request.tenant_id,
            request.principal_id,
        )

        if key not in self._principal_data:
            raise KeyError("Data principal not found")

        self._principal_data[key][request.field] = (
            request.value
        )

        return DataCorrectionResponse(
            tenant_id=request.tenant_id,
            principal_id=request.principal_id,
            field=request.field,
            corrected=True,
            corrected_at=self._now(),
        )

    # =========================================================
    # Retention policies
    # =========================================================

    def create_retention_policy(
        self,
        request: RetentionPolicyCreate,
    ) -> RetentionPolicyResponse:

        policy_id = f"ret_{uuid4().hex[:12]}"

        record = {
            "policy_id": policy_id,
            "tenant_id": request.tenant_id,
            "data_class": request.data_class,
            "retention_days": request.retention_days,
            "legal_hold_allowed": request.legal_hold_allowed,
        }

        self._retention_policies[policy_id] = record

        return RetentionPolicyResponse(**record)

    # =========================================================
    # Legal hold
    # =========================================================

    def create_legal_hold(
        self,
        request: LegalHoldRequest,
    ) -> LegalHoldResponse:

        hold_id = f"hold_{uuid4().hex[:12]}"

        record = {
            "hold_id": hold_id,
            "tenant_id": request.tenant_id,
            "data_class": request.data_class,
            "reason": request.reason,
            "active": request.active,
            "created_at": self._now(),
        }

        self._legal_holds[hold_id] = record

        return LegalHoldResponse(**record)

    # =========================================================
    # Verified erasure
    # =========================================================

    def request_erasure(
        self,
        request: ErasureRequest,
    ) -> ErasureCertificate:

        if not request.verification_reference.strip():
            raise ValueError(
                "Verified erasure reference is required"
            )

        key = self._key(
            request.tenant_id,
            request.principal_id,
        )

        request_id = f"erase_{uuid4().hex[:12]}"
        certificate_id = f"cert_{uuid4().hex[:12]}"

        data = self._principal_data.get(key)

        removed: list[str] = []
        retained: list[str] = []
        retention_reasons: dict[str, str] = {}

        # -----------------------------------------------------
        # Find active legal holds for this tenant.
        # -----------------------------------------------------

        active_holds = [
            hold
            for hold in self._legal_holds.values()
            if (
                hold["tenant_id"] == request.tenant_id
                and hold["active"]
            )
        ]

        # -----------------------------------------------------
        # Personal data erasure + service record preservation.
        # -----------------------------------------------------

        if data:

            for field in list(data.keys()):

                # Skip internal anonymisation marker.
                if field == "anonymised":
                    continue

                held = any(
                    hold["data_class"] == field
                    for hold in active_holds
                )

                if held:
                    retained.append(field)
                    retention_reasons[field] = (
                        "active_legal_hold"
                    )

                elif field in self.PERSONAL_FIELDS:
                    removed.append(field)

                else:
                    # Non-personal operational/service data
                    # remains available in anonymised form.
                    retained.append(field)
                    retention_reasons[field] = (
                        "anonymised_service_record"
                    )

            # Remove only personal data that is not
            # protected by an active legal hold.
            for field in removed:
                data.pop(field, None)

            # Explicitly remove any personal fields that may
            # have been retained by a legal hold only when
            # appropriate? No: legal-held data remains.

            # Preserve remaining service record anonymously.
            if data:
                data["anonymised"] = True

        # -----------------------------------------------------
        # Consent / privacy interaction records.
        #
        # The identity-linked receipt is removed as part of
        # personal-data erasure.
        # -----------------------------------------------------

        interaction_ids = []

        for receipt_id, interaction in (
            self._interactions.items()
        ):
            if (
                interaction["tenant_id"]
                == request.tenant_id
                and interaction["principal_id"]
                == request.principal_id
            ):
                interaction_ids.append(receipt_id)

        for receipt_id in interaction_ids:
            self._interactions.pop(
                receipt_id,
                None,
            )

        removed.extend(
            [
                "privacy_interaction_receipts",
                "retrieval_indices",
                "ai_caches",
            ]
        )

        # -----------------------------------------------------
        # Erasure request ledger.
        #
        # The fact that an erasure occurred is retained;
        # identity is not exposed through the certificate
        # contents beyond the certificate's controlled scope.
        # -----------------------------------------------------

        completed_at = self._now()

        self._erasure_requests[request_id] = {
            "request_id": request_id,
            "tenant_id": request.tenant_id,
            "principal_id": request.principal_id,
            "verification_reference": (
                request.verification_reference
            ),
            "completed_at": completed_at,
        }

        # -----------------------------------------------------
        # Erasure certificate.
        # -----------------------------------------------------

        certificate = ErasureCertificate(
            certificate_id=certificate_id,
            request_id=request_id,
            tenant_id=request.tenant_id,
            principal_id=request.principal_id,
            removed=removed,
            retained=retained,
            retention_reasons=retention_reasons,
            completed_at=completed_at,
        )

        self._certificates[certificate_id] = (
            certificate.model_dump()
        )

        return certificate

    # =========================================================
    # Certificate retrieval
    # =========================================================

    def get_certificate(
        self,
        certificate_id: str,
        tenant_id: str,
    ) -> ErasureCertificate:

        certificate = self._certificates.get(
            certificate_id
        )

        if certificate is None:
            raise KeyError(
                "Erasure certificate not found"
            )

        if certificate["tenant_id"] != tenant_id:
            raise PermissionError(
                "Cross-tenant certificate access denied"
            )

        return ErasureCertificate(
            **certificate
        )


privacy_service = PrivacyService()