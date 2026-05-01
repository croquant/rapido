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
