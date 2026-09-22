from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

from app.core.authorization import AuthorizationEngine
from app.schemas.authorization import AuthorizationRequest


class AuthorizationService:
    """
    Authorization service layer.

    BE-005:
    - Per-field authorization by role
    - Field-level authorization cache
    - Cache invalidation
    """

    FIELD_CACHE_TTL_SECONDS = 60

    def __init__(self) -> None:
        self.engine = AuthorizationEngine()

        # --------------------------------------------------------
        # Field-level policy storage
        #
        # Key:
        #   (role, resource_type, field)
        #
        # Value:
        #   set of allowed actions
        # --------------------------------------------------------
        self._field_policies: Dict[
            Tuple[str, str, str],
            set[str],
        ] = {}

        # --------------------------------------------------------
        # Field authorization cache
        #
        # Key:
        #   (
        #       subject_id,
        #       tenant_id,
        #       branch_id,
        #       resource_type,
        #       resource_id,
        #       action,
        #       fields
        #   )
        #
        # Value:
        #   {
        #       "timestamp": float,
        #       "result": dict
        #   }
        # --------------------------------------------------------
        self._field_cache: Dict[
            Tuple[Any, ...],
            Dict[str, Any],
        ] = {}

    # ============================================================
    # Identity Registration
    # ============================================================

    def register_identity(
        self,
        *,
        identity_id: str,
        tenant_id: str,
        role: str,
        branch_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:

        result = self.engine.register_identity(
            subject_id=identity_id,
            tenant_id=tenant_id,
            branch_id=branch_id,
            role=role,
        )

        # Identity/role change must invalidate field cache.
        self._invalidate_field_cache_for_subject(identity_id)

        return result

    # ============================================================
    # Get Identity
    # ============================================================

    def get_identity(
        self,
        *,
        subject_id: str,
    ) -> Optional[Dict[str, Any]]:

        return self.engine.get_identity(
            subject_id=subject_id,
        )

    # ============================================================
    # Add Grant
    # ============================================================

    def add_grant(
        self,
        *,
        subject_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        result = self.engine.add_grant(
            subject_id=subject_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            branch_id=branch_id,
        )

        # Grant change => immediate field-cache invalidation.
        self._invalidate_field_cache_for_subject(subject_id)

        return result

    # ============================================================
    # Revoke Grant
    # ============================================================

    def revoke_grant(
        self,
        *,
        subject_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        result = self.engine.revoke_grant(
            subject_id=subject_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            branch_id=branch_id,
        )

        # Grant change => immediate field-cache invalidation.
        self._invalidate_field_cache_for_subject(subject_id)

        return result

    # ============================================================
    # Authorization Check
    # ============================================================

    def authorize(
        self,
        *,
        subject_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        branch_id: Optional[str] = None,
    ):

        request = AuthorizationRequest(
            subject_id=subject_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            branch_id=branch_id,
        )

        return self.engine.authorize(request)

    # ============================================================
    # Access Check
    # ============================================================

    def can_access(
        self,
        *,
        subject_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        branch_id: Optional[str] = None,
    ):

        request = AuthorizationRequest(
            subject_id=subject_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            branch_id=branch_id,
        )

        return self.engine.authorize(request)

    # ============================================================
    # Decision Details
    # ============================================================

    def decision_details(
        self,
        *,
        subject_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        branch_id: Optional[str] = None,
    ):

        request = AuthorizationRequest(
            subject_id=subject_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            branch_id=branch_id,
        )

        return self.engine.authorize(request)

    # ============================================================
    # BE-005: Create Field Policy
    # ============================================================

    def create_field_policy(
        self,
        *,
        role: str,
        resource_type: str,
        field: str,
        actions: list[str],
    ) -> Dict[str, Any]:

        normalized_role = role.strip().lower()
        normalized_resource = resource_type.strip().lower()
        normalized_field = field.strip()

        if not normalized_role:
            raise ValueError("Role is required.")

        if not normalized_resource:
            raise ValueError("Resource type is required.")

        if not normalized_field:
            raise ValueError("Field is required.")

        if not actions:
            raise ValueError("At least one action is required.")

        normalized_actions = {
            action.strip().upper()
            for action in actions
            if action.strip()
        }

        if not normalized_actions:
            raise ValueError("At least one valid action is required.")

        key = (
            normalized_role,
            normalized_resource,
            normalized_field,
        )

        self._field_policies[key] = normalized_actions

        # Policy change must immediately invalidate field cache.
        self._invalidate_field_cache_for_role(
            normalized_role
        )

        return {
            "success": True,
            "role": normalized_role,
            "resource_type": normalized_resource,
            "field": normalized_field,
            "actions": sorted(normalized_actions),
        }

    # ============================================================
    # BE-005: Field Authorization Check
    # ============================================================

    def check_fields(
        self,
        *,
        subject_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        tenant_id: str,
        branch_id: Optional[str],
        fields: list[str],
    ) -> Dict[str, Any]:

        if not fields:
            raise ValueError("At least one field is required.")

        identity = self.engine.get_identity(subject_id)

        if identity is None:
            raise KeyError(
                f"Identity not found: {subject_id}"
            )

        if identity.get("tenant_id") != tenant_id:
            raise PermissionError(
                "Cross-tenant field access denied."
            )

        if (
            branch_id is not None
            and identity.get("branch_id") != branch_id
        ):
            raise PermissionError(
                "Cross-branch field access denied."
            )

        if not identity.get("active", False):
            raise PermissionError(
                "Identity is inactive."
            )

        role = str(
            identity.get("role", "")
        ).strip().lower()

        normalized_resource = resource_type.strip().lower()
        normalized_action = action.strip().upper()

        normalized_fields = tuple(
            sorted(
                {
                    field.strip()
                    for field in fields
                    if field.strip()
                }
            )
        )

        cache_key = (
            subject_id,
            tenant_id,
            branch_id,
            normalized_resource,
            resource_id,
            normalized_action,
            normalized_fields,
        )

        # --------------------------------------------------------
        # Check field cache
        # --------------------------------------------------------

        cached = self._field_cache.get(cache_key)

        if cached is not None:
            age = time.time() - cached["timestamp"]

            if age <= self.FIELD_CACHE_TTL_SECONDS:
                result = dict(cached["result"])

                # Useful for testing/verification.
                result["cache_hit"] = True

                return result

            # TTL expired.
            del self._field_cache[cache_key]

        # --------------------------------------------------------
        # Check resource-level authorization first
        # --------------------------------------------------------

        decision = self.authorize(
            subject_id=subject_id,
            tenant_id=tenant_id,
            resource_type=normalized_resource,
            resource_id=resource_id,
            action=normalized_action,
            branch_id=branch_id,
        )

        if not decision.allowed:
            result = {
                "allowed": False,
                "subject_id": subject_id,
                "resource_type": normalized_resource,
                "resource_id": resource_id,
                "action": normalized_action,
                "allowed_fields": [],
                "denied_fields": list(normalized_fields),
                "reason": decision.reason,
            }

            self._field_cache[cache_key] = {
                "timestamp": time.time(),
                "result": result,
            }

            return result

        # --------------------------------------------------------
        # Per-field policy evaluation
        # --------------------------------------------------------

        allowed_fields: list[str] = []
        denied_fields: list[str] = []

        for field in normalized_fields:

            policy_key = (
                role,
                normalized_resource,
                field,
            )

            allowed_actions = self._field_policies.get(
                policy_key,
                set(),
            )

            if normalized_action in allowed_actions:
                allowed_fields.append(field)
            else:
                denied_fields.append(field)

        # If no field policy exists, do NOT expose fields.
        # Default deny is safer for field-level authorization.
        result = {
            "allowed": len(denied_fields) == 0,
            "subject_id": subject_id,
            "resource_type": normalized_resource,
            "resource_id": resource_id,
            "action": normalized_action,
            "allowed_fields": allowed_fields,
            "denied_fields": denied_fields,
            "reason": (
                "All requested fields are authorized."
                if not denied_fields
                else "One or more requested fields are not authorized."
            ),
        }

        # --------------------------------------------------------
        # Store result in cache
        # --------------------------------------------------------

        self._field_cache[cache_key] = {
            "timestamp": time.time(),
            "result": result,
        }

        return result

    # ============================================================
    # BE-005: Field Cache Invalidation
    # ============================================================

    def invalidate_field_cache(
        self,
        *,
        subject_id: Optional[str] = None,
        role: Optional[str] = None,
        resource_type: Optional[str] = None,
    ) -> Dict[str, Any]:

        normalized_role = (
            role.strip().lower()
            if role is not None
            else None
        )

        normalized_resource = (
            resource_type.strip().lower()
            if resource_type is not None
            else None
        )

        keys_to_delete = []

        for key in self._field_cache:

            key_subject_id = key[0]
            key_resource_type = key[3]

            matches_subject = (
                subject_id is None
                or key_subject_id == subject_id
            )

            matches_resource = (
                normalized_resource is None
                or key_resource_type == normalized_resource
            )

            matches_role = True

            if normalized_role is not None:
                identity = self.engine.get_identity(
                    key_subject_id
                )

                matches_role = (
                    identity is not None
                    and str(
                        identity.get("role", "")
                    ).lower()
                    == normalized_role
                )

            if (
                matches_subject
                and matches_role
                and matches_resource
            ):
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self._field_cache[key]

        return {
            "success": True,
            "invalidated": len(keys_to_delete),
            "message": "Field authorization cache invalidated",
        }

    # ============================================================
    # BE-005: Clear Field Cache
    # ============================================================

    def clear_field_cache(self) -> str:
        count = len(self._field_cache)

        self._field_cache.clear()

        return (
            f"Field authorization cache cleared "
            f"({count} entries)"
        )

    # ============================================================
    # Internal Cache Helpers
    # ============================================================

    def _invalidate_field_cache_for_subject(
        self,
        subject_id: str,
    ) -> None:

        keys = [
            key
            for key in self._field_cache
            if key[0] == subject_id
        ]

        for key in keys:
            del self._field_cache[key]

    def _invalidate_field_cache_for_role(
        self,
        role: str,
    ) -> None:

        normalized_role = role.lower()

        keys_to_delete = []

        for key in self._field_cache:

            subject_id = key[0]

            identity = self.engine.get_identity(
                subject_id
            )

            if (
                identity is not None
                and str(
                    identity.get("role", "")
                ).lower()
                == normalized_role
            ):
                keys_to_delete.append(key)

        for key in keys_to_delete:
            del self._field_cache[key]

    # ============================================================
    # Normal Authorization Cache
    # ============================================================

    def invalidate_cache(
        self,
        *,
        subject_id: Optional[str] = None,
    ):

        if subject_id is not None:

            invalidated = (
                self.engine.invalidate_subject_cache(
                    subject_id
                )
            )

            self._invalidate_field_cache_for_subject(
                subject_id
            )

            return {
                "success": True,
                "invalidated": invalidated,
                "subject_id": subject_id,
            }

        invalidated = (
            self.engine.invalidate_all_cache()
        )

        self._field_cache.clear()

        return {
            "success": True,
            "invalidated": invalidated,
        }

    # ============================================================
    # Clear Cache
    # ============================================================

    def clear_cache(self):

        invalidated = (
            self.engine.invalidate_all_cache()
        )

        self._field_cache.clear()

        return {
            "success": True,
            "invalidated": invalidated,
            "message": "Authorization cache cleared",
        }


# ================================================================
# Singleton Service
# ================================================================

authorization_service = AuthorizationService()