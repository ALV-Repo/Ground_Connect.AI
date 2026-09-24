from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

from app.core.audit import audit_service
from app.schemas.authorization import (
    AuthorizationDecision,
    AuthorizationRequest,
)


class AuthorizationEngine:
    """
    Central authorization engine.

    Security principles:
    - Default deny
    - Server-side identity is authoritative
    - Tenant isolation
    - Branch isolation
    - Explicit grants
    - Role based permissions
    - Organizational hierarchy
    - Authorization decision caching
    - Authorization cache TTL <= 60 seconds
    - Authorization decisions are audited
    """

    # BE-005:
    # Authorization-decision cache must expire within 60 seconds.
    CACHE_TTL_SECONDS = 60

    def __init__(self) -> None:
        # Server-side identity store.
        self._identities: Dict[str, Dict[str, Any]] = {}

        # Explicit grants:
        # (
        #     subject_id,
        #     tenant_id,
        #     resource_type,
        #     resource_id,
        #     action,
        #     branch_id
        # )
        self._grants: Dict[
            Tuple[str, str, str, str, str, Optional[str]],
            Dict[str, Any],
        ] = {}

        # Cache value:
        # (AuthorizationDecision, cached_at_timestamp)
        self._cache: Dict[
            Tuple[Any, ...],
            Tuple[AuthorizationDecision, float],
        ] = {}

    # ============================================================
    # Identity Management
    # ============================================================

    def register_identity(
        self,
        subject_id: str,
        tenant_id: str,
        branch_id: Optional[str],
        role: str,
        active: bool = True,
        parent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Register a server-side identity.

        parent_id represents the direct parent/manager of the
        identity in the organizational hierarchy.

        Example:

            admin
              |
            leader-1
              |
            member-1

        member-1.parent_id == leader-1

        parent_id is optional to preserve backward compatibility
        with existing identity registrations.
        """

        if not subject_id:
            raise ValueError("Subject ID is required.")

        if not tenant_id:
            raise ValueError("Tenant ID is required.")

        if not role:
            raise ValueError("Role is required.")

        # An identity cannot be its own parent.
        if parent_id == subject_id:
            raise ValueError(
                "An identity cannot be its own parent."
            )

        # If a parent is supplied, it must already exist.
        if parent_id is not None:
            parent = self._identities.get(parent_id)

            if parent is None:
                raise ValueError(
                    f"Parent identity does not exist: {parent_id}"
                )

            # Parent must belong to the same tenant.
            if parent.get("tenant_id") != tenant_id:
                raise PermissionError(
                    "Parent identity must belong to the same tenant."
                )

        identity = {
            "subject_id": subject_id,
            "tenant_id": tenant_id,
            "branch_id": branch_id,
            "role": role,
            "active": active,
            "parent_id": parent_id,
        }

        self._identities[subject_id] = identity

        # Identity/role/hierarchy change invalidates cached decisions.
        self.invalidate_subject_cache(subject_id)
        self.invalidate_all_cache()

        return identity.copy()

    def get_identity(
        self,
        subject_id: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Return a copy of the server-side identity.
        """

        identity = self._identities.get(subject_id)

        if identity is None:
            return None

        return identity.copy()

    def deactivate_identity(
        self,
        subject_id: str,
    ) -> Dict[str, Any]:
        """
        Deactivate an identity.
        """

        identity = self._identities.get(subject_id)

        if identity is None:
            raise KeyError(
                f"Identity not found: {subject_id}"
            )

        identity["active"] = False

        self.invalidate_subject_cache(subject_id)
        self.invalidate_all_cache()

        return identity.copy()

    def activate_identity(
        self,
        subject_id: str,
    ) -> Dict[str, Any]:
        """
        Activate an identity.
        """

        identity = self._identities.get(subject_id)

        if identity is None:
            raise KeyError(
                f"Identity not found: {subject_id}"
            )

        identity["active"] = True

        self.invalidate_subject_cache(subject_id)
        self.invalidate_all_cache()

        return identity.copy()

    # ============================================================
    # Organizational Hierarchy
    # ============================================================

    def is_descendant(
        self,
        ancestor_id: str,
        descendant_id: str,
        *,
        tenant_id: Optional[str] = None,
    ) -> bool:
        """
        Check whether descendant_id exists below ancestor_id
        in the organizational hierarchy.

        The check walks upward:

            descendant
                |
              parent
                |
              parent
                |
              ancestor

        The relationship must remain within the same tenant.
        """

        # A person is not considered their own descendant.
        if ancestor_id == descendant_id:
            return False

        ancestor = self._identities.get(ancestor_id)
        descendant = self._identities.get(descendant_id)

        if ancestor is None or descendant is None:
            return False

        # Tenant isolation.
        if tenant_id is not None:
            if ancestor.get("tenant_id") != tenant_id:
                return False

            if descendant.get("tenant_id") != tenant_id:
                return False

        # Additional safety: ancestor and descendant must belong
        # to the same tenant even when tenant_id wasn't supplied.
        if ancestor.get("tenant_id") != descendant.get("tenant_id"):
            return False

        current_id = descendant_id
        visited: set[str] = set()

        while current_id:
            # Protect against malformed/cyclic hierarchy.
            if current_id in visited:
                return False

            visited.add(current_id)

            current = self._identities.get(current_id)

            if current is None:
                return False

            parent_id = current.get("parent_id")

            if parent_id == ancestor_id:
                return True

            current_id = parent_id

        return False

    def can_delegate_to(
        self,
        *,
        assigner_id: str,
        assignee_id: str,
        tenant_id: str,
    ) -> bool:
        """
        BE-009 / TSK-02

        Delegation is allowed only downward within the assigner's
        organizational subtree.

        Therefore:

            A -> B -> C

        A can delegate to B.
        A can delegate to C.
        B can delegate to C.

        But:

        B cannot delegate to A.
        C cannot delegate to A.
        C cannot delegate to B.
        """

        assigner = self._identities.get(assigner_id)
        assignee = self._identities.get(assignee_id)

        if assigner is None or assignee is None:
            return False

        if not assigner.get("active", False):
            return False

        if not assignee.get("active", False):
            return False

        # Tenant isolation.
        if assigner.get("tenant_id") != tenant_id:
            return False

        if assignee.get("tenant_id") != tenant_id:
            return False

        return self.is_descendant(
            ancestor_id=assigner_id,
            descendant_id=assignee_id,
            tenant_id=tenant_id,
        )

    def get_descendants(
        self,
        subject_id: str,
        *,
        tenant_id: Optional[str] = None,
        active_only: bool = False,
    ) -> list[Dict[str, Any]]:
        """
        Return identities that are below subject_id in the
        organizational hierarchy.
        """

        identity = self._identities.get(subject_id)

        if identity is None:
            return []

        if tenant_id is not None:
            if identity.get("tenant_id") != tenant_id:
                return []

        # Build a parent -> children index once.
        children_by_parent: Dict[str, list[str]] = {}

        for candidate_id, candidate in self._identities.items():
            parent_id = candidate.get("parent_id")

            if parent_id is None:
                continue

            if tenant_id is not None:
                if candidate.get("tenant_id") != tenant_id:
                    continue

            children_by_parent.setdefault(
                parent_id,
                [],
            ).append(candidate_id)

        # Traverse the hierarchy downward from subject_id.
        descendants: list[Dict[str, Any]] = []
        stack = list(
            children_by_parent.get(subject_id, [])
        )
        visited: set[str] = set()

        while stack:
            candidate_id = stack.pop()

            # Protect against malformed/cyclic hierarchy.
            if candidate_id in visited:
                continue

            visited.add(candidate_id)

            candidate = self._identities.get(candidate_id)

            if candidate is None:
                continue

            # Preserve tenant isolation.
            if candidate.get("tenant_id") != identity.get("tenant_id"):
                continue

            if active_only and not candidate.get(
                "active",
                False,
            ):
                continue

            descendants.append(candidate.copy())

            # Continue traversal through this identity's children.
            stack.extend(
                children_by_parent.get(
                    candidate_id,
                    [],
                )
            )

        return descendants

    # ============================================================
    # Grant Management
    # ============================================================

    def add_grant(
        self,
        subject_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        if subject_id not in self._identities:
            raise ValueError(
                "Identity does not exist."
            )

        identity = self._identities[subject_id]

        if identity["tenant_id"] != tenant_id:
            raise PermissionError(
                "Cross-tenant grant is not allowed."
            )

        if (
            branch_id is not None
            and identity.get("branch_id") != branch_id
        ):
            raise PermissionError(
                "Cross-branch grant is not allowed."
            )

        grant = {
            "subject_id": subject_id,
            "tenant_id": tenant_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "branch_id": branch_id,
        }

        key = self._grant_key(
            subject_id,
            tenant_id,
            resource_type,
            resource_id,
            action,
            branch_id,
        )

        self._grants[key] = grant

        # Grant change => immediate authorization
        # cache invalidation.
        self.invalidate_subject_cache(subject_id)

        return grant.copy()

    def revoke_grant(
        self,
        subject_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        branch_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        key = self._grant_key(
            subject_id,
            tenant_id,
            resource_type,
            resource_id,
            action,
            branch_id,
        )

        grant = self._grants.get(key)

        if grant is None:
            raise KeyError("Grant not found.")

        del self._grants[key]

        # Grant change => immediate authorization
        # cache invalidation.
        self.invalidate_subject_cache(subject_id)

        return {
            "revoked": True,
            **grant,
        }

    # ============================================================
    # Authorization
    # ============================================================

    def authorize(
        self,
        request: AuthorizationRequest,
    ) -> AuthorizationDecision:

        cache_key = self._cache_key(request)

        # --------------------------------------------------------
        # Authorization cache lookup
        # --------------------------------------------------------

        cached = self._cache.get(cache_key)

        if cached is not None:
            cached_decision, cached_at = cached

            cache_age = time.time() - cached_at

            # Cache is valid for maximum 60 seconds.
            if cache_age <= self.CACHE_TTL_SECONDS:
                return cached_decision.model_copy(
                    update={"cache_hit": True}
                )

            # TTL expired.
            del self._cache[cache_key]

        rules_evaluated: list[str] = []

        # --------------------------------------------------------
        # 1. Identity existence
        # --------------------------------------------------------

        rules_evaluated.append(
            "IDENTITY_EXISTS"
        )

        identity = self._identities.get(
            request.subject_id
        )

        if identity is None:
            decision = self._deny(
                request=request,
                reason="Identity does not exist.",
                failing_rule="IDENTITY_EXISTS",
                rules_evaluated=rules_evaluated,
            )

            self._record_audit(
                request,
                decision,
            )

            return decision

        # --------------------------------------------------------
        # 2. Identity active
        # --------------------------------------------------------

        rules_evaluated.append(
            "IDENTITY_ACTIVE"
        )

        if not identity.get("active", False):
            decision = self._deny(
                request=request,
                reason="Identity is inactive.",
                failing_rule="IDENTITY_ACTIVE",
                rules_evaluated=rules_evaluated,
            )

            self._record_audit(
                request,
                decision,
            )

            return decision

              # --------------------------------------------------------
        # 3. Client identity is never trusted
        # --------------------------------------------------------

        rules_evaluated.append(
            "CLIENT_IDENTITY_NOT_TRUSTED"
        )

        # Client-supplied identity information must never
        # override server-side identity.
        client_identity = getattr(
            request,
            "client_identity",
            None,
        )

        if client_identity:
            decision = self._deny(
                request=request,
                reason="Client-supplied identity values are not trusted.",
                failing_rule="CLIENT_IDENTITY_NOT_TRUSTED",
                rules_evaluated=rules_evaluated,
            )

            self._record_audit(
                request,
                decision,
            )

            return decision

        # --------------------------------------------------------
        # 4. Tenant isolation
        # --------------------------------------------------------
        # --------------------------------------------------------
        # 4. Tenant isolation
        # --------------------------------------------------------

        rules_evaluated.append(
            "TENANT_ISOLATION"
        )

        if (
            request.tenant_id is not None
            and identity["tenant_id"]
            != request.tenant_id
        ):
            decision = self._deny(
                request=request,
                reason="Cross-tenant access denied.",
                failing_rule="TENANT_ISOLATION",
                rules_evaluated=rules_evaluated,
            )

            self._record_audit(
                request,
                decision,
            )

            return decision

        # --------------------------------------------------------
        # 5. Branch isolation
        # --------------------------------------------------------

        rules_evaluated.append(
            "BRANCH_ISOLATION"
        )

        if (
            request.branch_id is not None
            and identity.get("branch_id")
            != request.branch_id
        ):
            decision = self._deny(
                request=request,
                reason="Cross-branch access denied.",
                failing_rule="BRANCH_ISOLATION",
                rules_evaluated=rules_evaluated,
            )

            self._record_audit(
                request,
                decision,
            )

            return decision

        # --------------------------------------------------------
        # 6. Role permission
        # --------------------------------------------------------

        rules_evaluated.append(
            "ROLE_PERMISSION"
        )

        role = str(
            identity.get("role", "")
        ).lower()

        if self._role_allows(
            role=role,
            action=request.action,
            resource_type=request.resource_type,
        ):
            decision = self._allow(
                request=request,
                reason="Role is authorized for this action.",
                rules_evaluated=rules_evaluated,
            )

            self._cache[cache_key] = (
                decision,
                time.time(),
            )

            self._record_audit(
                request,
                decision,
            )

            return decision

        # --------------------------------------------------------
        # 7. Explicit grant
        # --------------------------------------------------------

        rules_evaluated.append(
            "EXPLICIT_GRANT"
        )

        if self._has_explicit_grant(request):
            decision = self._allow(
                request=request,
                reason="Explicit resource grant is authorized.",
                rules_evaluated=rules_evaluated,
            )

            self._cache[cache_key] = (
                decision,
                time.time(),
            )

            self._record_audit(
                request,
                decision,
            )

            return decision

        # --------------------------------------------------------
        # 8. Default deny
        # --------------------------------------------------------

        decision = self._deny(
            request=request,
            reason="Role is not authorized for this action.",
            failing_rule="ROLE_PERMISSION",
            rules_evaluated=rules_evaluated,
        )

        self._cache[cache_key] = (
            decision,
            time.time(),
        )

        self._record_audit(
            request,
            decision,
        )

        return decision

    # ============================================================
    # Audit Integration
    # ============================================================

    @staticmethod
    def _record_audit(
        request: AuthorizationRequest,
        decision: AuthorizationDecision,
    ) -> None:
        """
        Persist authorization decisions to the audit service.

        Both ALLOW and DENY decisions are recorded.
        """

        try:
            audit_service.record_decision(
                subject_id=request.subject_id,
                action=request.action,
                resource_type=request.resource_type,
                resource_id=request.resource_id,
                allowed=decision.allowed,
                reason=decision.reason,
                rules_evaluated=decision.rules_evaluated,
                failing_rule=decision.failing_rule,
                tenant_id=request.tenant_id,
                branch_id=request.branch_id,
                correlation_id=None,
                source="authorization_engine",
            )

        except Exception:
            # Authorization must not fail only because audit
            # persistence has an unexpected error.
            pass

    # ============================================================
    # Role Permissions
    # ============================================================

    def _role_allows(
        self,
        role: str,
        action: str,
        resource_type: str,
    ) -> bool:

        role_permissions = {
            "platform operator": {
                "*": {
                    "READ",
                    "WRITE",
                    "UPDATE",
                    "DELETE",
                    "ADMIN",
                },
            },

            "org admin": {
                "*": {
                    "READ",
                    "WRITE",
                    "UPDATE",
                    "DELETE",
                },
            },

            "leader": {
                "message": {
                    "READ",
                    "WRITE",
                    "UPDATE",
                },
                "task": {
                    "READ",
                    "WRITE",
                    "UPDATE",
                },
                "member": {
                    "READ",
                },
            },

            "compliance": {
                "message": {
                    "READ",
                },
                "task": {
                    "READ",
                },
                "audit": {
                    "READ",
                },
            },

            "security admin": {
                "security": {
                    "READ",
                    "WRITE",
                    "UPDATE",
                },
                "audit": {
                    "READ",
                },
                "identity": {
                    "READ",
                    "UPDATE",
                },
            },

            "member": {
                "message": {
                    "READ",
                },
                "task": {
                    "READ",
                    "UPDATE",
                },
            },

            "vendor": {
                "task": {
                    "READ",
                },
            },
        }

        permissions = role_permissions.get(role)

        if permissions is None:
            return False

        action = action.upper()
        resource_type = resource_type.lower()

        if "*" in permissions:
            return action in permissions["*"]

        allowed_actions = permissions.get(
            resource_type,
            set(),
        )

        return action in allowed_actions

    # ============================================================
    # Explicit Grants
    # ============================================================

    def _has_explicit_grant(
        self,
        request: AuthorizationRequest,
    ) -> bool:

        key = self._grant_key(
            request.subject_id,
            request.tenant_id or "",
            request.resource_type,
            request.resource_id,
            request.action,
            request.branch_id,
        )

        if key in self._grants:
            return True

        # Also support a grant stored without branch restriction.
        branchless_key = self._grant_key(
            request.subject_id,
            request.tenant_id or "",
            request.resource_type,
            request.resource_id,
            request.action,
            None,
        )

        return branchless_key in self._grants

    # ============================================================
    # Helpers
    # ============================================================

    @staticmethod
    def _grant_key(
        subject_id: str,
        tenant_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        branch_id: Optional[str],
    ) -> Tuple[
        str,
        str,
        str,
        str,
        str,
        Optional[str],
    ]:

        return (
            subject_id,
            tenant_id,
            resource_type,
            resource_id,
            action.upper(),
            branch_id,
        )

    @staticmethod
    def _cache_key(
        request: AuthorizationRequest,
    ) -> Tuple[Any, ...]:

        return (
            request.subject_id,
            request.tenant_id,
            request.branch_id,
            request.action.upper(),
            request.resource_type,
            request.resource_id,
        )

    @staticmethod
    def _allow(
        request: AuthorizationRequest,
        reason: str,
        rules_evaluated: list[str],
    ) -> AuthorizationDecision:

        return AuthorizationDecision(
            allowed=True,
            subject_id=request.subject_id,
            action=request.action,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            reason=reason,
            failing_rule=None,
            rules_evaluated=rules_evaluated,
            cache_hit=False,
            timestamp=time.time(),
        )

    @staticmethod
    def _deny(
        request: AuthorizationRequest,
        reason: str,
        failing_rule: str,
        rules_evaluated: list[str],
    ) -> AuthorizationDecision:

        return AuthorizationDecision(
            allowed=False,
            subject_id=request.subject_id,
            action=request.action,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            reason=reason,
            failing_rule=failing_rule,
            rules_evaluated=rules_evaluated,
            cache_hit=False,
            timestamp=time.time(),
        )

    # ============================================================
    # Cache
    # ============================================================

    def invalidate_subject_cache(
        self,
        subject_id: str,
    ) -> int:

        keys_to_delete = [
            key
            for key in self._cache
            if key[0] == subject_id
        ]

        for key in keys_to_delete:
            del self._cache[key]

        return len(keys_to_delete)

    def invalidate_all_cache(self) -> int:

        count = len(self._cache)

        self._cache.clear()

        return count

    def clear(self) -> None:

        self._identities.clear()
        self._grants.clear()
        self._cache.clear()


# ================================================================
# Singleton Authorization Engine
# ================================================================

authorization_engine = AuthorizationEngine()