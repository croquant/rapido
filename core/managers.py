"""Shared managers for tenant-scoped models.

`TenantOwnedManager` provides two methods:

- `for_organization(org)`: primitive used by tasks, management commands,
  admin, and tests. Filters on the model's path to `Organization`.
- `for_request(request)`: thin wrapper used by views; delegates to
  `for_organization(request.organization)`. Assumes the tenant middleware
  has populated `request.organization`.

Default `.objects` stays unscoped (Django convention). Models attach this
manager under a separate name (e.g. `tenant_objects`) when they pick it up.

For models where `Organization` is reached via a related field, override
`organization_lookup` on the subclass:

    class LocationMembershipManager(TenantOwnedManager):
        organization_lookup = "location__organization"
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import models
from django.http import HttpRequest

if TYPE_CHECKING:
    from core.models import Organization


class TenantOwnedManager(models.Manager):
    organization_lookup: str = "organization"

    def for_organization(self, organization: Organization) -> models.QuerySet:
        return self.get_queryset().filter(
            **{self.organization_lookup: organization}
        )

    def for_request(self, request: HttpRequest) -> models.QuerySet:
        return self.for_organization(request.organization)  # type: ignore[attr-defined]
