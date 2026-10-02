from dataclasses import dataclass


@dataclass(frozen=True)
class UserContext:
    user_id: str
    role: str
    organization_id: str


class PermissionDeniedError(Exception):
    """Raised when a user is not authorized to access AI data."""


class PermissionService:

    # AI-002: Feature-level role permissions.
    # Leadership features are restricted to leadership users.
    FEATURE_ROLES = {
        "copilot": {"leader"},
        "leader_briefing": {"leader"},
    }

    def can_access(
        self,
        user: UserContext,
        resource_organization_id: str,
    ) -> bool:

        return (
            user.organization_id
            == resource_organization_id
        )

    def can_access_feature(
        self,
        user: UserContext,
        feature: str,
    ) -> bool:

        allowed_roles = self.FEATURE_ROLES.get(
            feature.lower()
        )

        if allowed_roles is None:
            return False

        return user.role.lower() in allowed_roles

    def enforce_access(
        self,
        user: UserContext,
        resource_organization_id: str,
    ) -> None:

        if not self.can_access(
            user,
            resource_organization_id,
        ):
            raise PermissionDeniedError(
                "User is not authorized to access this resource"
            )

    def enforce_feature_access(
        self,
        user: UserContext,
        feature: str,
    ) -> None:

        if not self.can_access_feature(
            user,
            feature,
        ):
            raise PermissionDeniedError(
                "User role is not authorized for this AI feature"
            )