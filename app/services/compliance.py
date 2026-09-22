from __future__ import annotations

from uuid import uuid4

from app.schemas.compliance import (
    ComplianceMode,
    ComplianceProfileActivateRequest,
    ComplianceProfileCreate,
    ComplianceProfileResponse,
    ComplianceProfileStatusResponse,
)


class ComplianceService:
    """
    BE-023 Compliance Mode Profiles.

    Supports:
    - tenant-scoped compliance profiles
    - configurable compliance controls
    - profile activation
    - active-profile status
    - cross-tenant isolation
    """

    def __init__(self) -> None:
        self._profiles: dict[str, dict] = {}
        self._active_profiles: dict[str, str] = {}

    # ---------------------------------------------------------
    # Profile creation
    # ---------------------------------------------------------

    def create_profile(
        self,
        request: ComplianceProfileCreate,
    ) -> ComplianceProfileResponse:

        profile_id = f"profile_{uuid4().hex[:12]}"

        record = {
            "profile_id": profile_id,
            "tenant_id": request.tenant_id,
            "profile_name": request.profile_name,
            "mode": request.mode,
            "description": request.description,
            "controls": dict(request.controls),
            "active": False,
        }

        self._profiles[profile_id] = record

        return ComplianceProfileResponse(**record)

    # ---------------------------------------------------------
    # Profile activation
    # ---------------------------------------------------------

    def activate_profile(
        self,
        request: ComplianceProfileActivateRequest,
    ) -> ComplianceProfileResponse:

        profile = self._profiles.get(request.profile_id)

        if profile is None:
            raise KeyError("Compliance profile not found")

        if profile["tenant_id"] != request.tenant_id:
            raise PermissionError(
                "Cross-tenant compliance profile access denied"
            )

        previous_profile_id = self._active_profiles.get(
            request.tenant_id
        )

        if previous_profile_id:
            previous = self._profiles.get(previous_profile_id)

            if previous:
                previous["active"] = False

        profile["active"] = True

        self._active_profiles[
            request.tenant_id
        ] = request.profile_id

        return ComplianceProfileResponse(**profile)

    # ---------------------------------------------------------
    # Profile retrieval
    # ---------------------------------------------------------

    def get_profile(
        self,
        *,
        tenant_id: str,
        profile_id: str,
    ) -> ComplianceProfileResponse:

        profile = self._profiles.get(profile_id)

        if profile is None:
            raise KeyError("Compliance profile not found")

        if profile["tenant_id"] != tenant_id:
            raise PermissionError(
                "Cross-tenant compliance profile access denied"
            )

        return ComplianceProfileResponse(**profile)

    # ---------------------------------------------------------
    # Active compliance status
    # ---------------------------------------------------------

    def get_status(
        self,
        tenant_id: str,
    ) -> ComplianceProfileStatusResponse:

        profile_id = self._active_profiles.get(
            tenant_id
        )

        if profile_id is None:
            return ComplianceProfileStatusResponse(
                tenant_id=tenant_id,
                active_profile_id=None,
                mode=None,
                controls={},
            )

        profile = self._profiles.get(profile_id)

        if profile is None:
            return ComplianceProfileStatusResponse(
                tenant_id=tenant_id,
                active_profile_id=None,
                mode=None,
                controls={},
            )

        return ComplianceProfileStatusResponse(
            tenant_id=tenant_id,
            active_profile_id=profile["profile_id"],
            mode=profile["mode"],
            controls=dict(profile["controls"]),
        )

    # ---------------------------------------------------------
    # Mode validation helper
    # ---------------------------------------------------------

    @staticmethod
    def default_controls(
        mode: ComplianceMode,
    ) -> dict[str, bool]:

        if mode == ComplianceMode.STANDARD:
            return {
                "audit_required": True,
                "consent_required": True,
                "strict_erasure": False,
                "enhanced_review": False,
            }

        if mode == ComplianceMode.STRICT:
            return {
                "audit_required": True,
                "consent_required": True,
                "strict_erasure": True,
                "enhanced_review": True,
            }

        if mode == ComplianceMode.HIGH_RISK:
            return {
                "audit_required": True,
                "consent_required": True,
                "strict_erasure": True,
                "enhanced_review": True,
                "second_approval_required": True,
            }

        return {}


compliance_service = ComplianceService()