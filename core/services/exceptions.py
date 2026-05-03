from collections.abc import Sequence

from core.models import Organization


class LastActiveAdminError(Exception):
    """Operation would leave one or more orgs without a qualifying ADMIN."""

    def __init__(self, organizations: Sequence[Organization]) -> None:
        self.organizations: list[Organization] = list(organizations)
        slugs = ", ".join(o.slug for o in self.organizations)
        super().__init__(
            f"Operation would leave organization(s) without an active "
            f"ADMIN: {slugs}"
        )


class AlreadyActiveError(Exception):
    """User is already active; verify token reuse is a no-op at the page."""


class NoAdminMembershipError(Exception):
    """User has no active ADMIN membership to anchor org activation."""


class AlreadyMemberError(Exception):
    """An active OrganizationMembership already exists for (email, org)."""

    def __init__(self, email: str, organization: Organization) -> None:
        self.email = email
        self.organization = organization
        super().__init__(
            f"{email} is already an active member of {organization.slug}"
        )


class OperatorRequiresLocationsError(Exception):
    """OPERATOR invitation must list at least one valid, active location."""

    def __init__(self, message: str | None = None) -> None:
        super().__init__(
            message or "OPERATOR invitations require at least one location."
        )


class BadStateError(Exception):
    """Invitation operation rejected due to terminal/invalid state.

    `reason` is the contract caller views match on:
    `pending_exists`, `already_accepted`, `already_revoked`, `expired`,
    `stale_locations`, `invalid_token`, `already_member`.
    """

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class WeakPasswordError(Exception):
    """Password failed Django's validators on new-user invite accept."""

    def __init__(self, messages: list[str]) -> None:
        self.messages = messages
        super().__init__("; ".join(messages))


class WrongPasswordError(Exception):
    """User-supplied current password did not match stored hash."""
