from dataclasses import dataclass


@dataclass(frozen=True)
class UserContext:
    user_id: str
    role: str
    organization_id: str


class PermissionDeniedError(Exception):
    """Raised when a user is not authorized to access AI data."""


class PermissionService:

    def can_access(
        self,
        user: UserContext,
        resource_organization_id: str,
    ) -> bool:

        return (
            user.organization_id
            == resource_organization_id
        )

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