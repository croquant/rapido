from types import SimpleNamespace

import pytest

from core.managers import TenantOwnedManager
from core.models import Location, LocationMembership

from tests.factories import (
    LocationFactory,
    LocationMembershipFactory,
    OrganizationFactory,
)


class _LocationMembershipTenantManager(TenantOwnedManager):
    organization_lookup = "location__organization"


TenantOwnedManager().contribute_to_class(Location, "tenant_objects")
_LocationMembershipTenantManager().contribute_to_class(
    LocationMembership, "tenant_objects"
)


@pytest.mark.django_db
def test_for_organization_direct_path() -> None:
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    a1 = LocationFactory(organization=org_a)
    a2 = LocationFactory(organization=org_a)
    LocationFactory(organization=org_b)

    qs = Location.tenant_objects.for_organization(org_a)  # type: ignore[attr-defined]

    assert set(qs) == {a1, a2}


@pytest.mark.django_db
def test_for_organization_indirect_path() -> None:
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    loc_a = LocationFactory(organization=org_a)
    loc_b = LocationFactory(organization=org_b)
    m1 = LocationMembershipFactory(location=loc_a)
    m2 = LocationMembershipFactory(location=loc_a)
    LocationMembershipFactory(location=loc_b)

    qs = LocationMembership.tenant_objects.for_organization(org_a)  # type: ignore[attr-defined]

    assert set(qs) == {m1, m2}


@pytest.mark.django_db
def test_for_request_delegates_to_for_organization() -> None:
    org_a = OrganizationFactory()
    org_b = OrganizationFactory()
    LocationFactory(organization=org_a)
    LocationFactory(organization=org_b)

    request = SimpleNamespace(organization=org_a)

    direct = Location.tenant_objects.for_organization(org_a)  # type: ignore[attr-defined]
    via_request = Location.tenant_objects.for_request(request)  # type: ignore[attr-defined]

    assert list(via_request) == list(direct)
