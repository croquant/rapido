# pyright: reportPrivateImportUsage=false, reportIncompatibleVariableOverride=false
from datetime import timedelta

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from core.models import (
    Invitation,
    Location,
    LocationMembership,
    Organization,
    OrganizationMembership,
    Role,
    User,
)


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    class Params:
        staff = factory.Trait(is_staff=True)
        superuser = factory.Trait(is_staff=True, is_superuser=True)

    email = factory.Sequence(lambda n: f"user{n}@example.be")
    is_active = True
    password = factory.PostGenerationMethodCall("set_password", "password")


class OrganizationFactory(DjangoModelFactory):
    class Meta:
        model = Organization

    name = factory.Sequence(lambda n: f"Org {n}")
    slug = factory.Sequence(lambda n: f"org-{n}")
    vat_number = "BE0417710407"
    billing_email = factory.Sequence(lambda n: f"billing{n}@example.be")
    is_active = True


class OrganizationMembershipFactory(DjangoModelFactory):
    class Meta:
        model = OrganizationMembership

    user = factory.SubFactory(UserFactory)
    organization = factory.SubFactory(OrganizationFactory)
    role = Role.ADMIN


class LocationFactory(DjangoModelFactory):
    class Meta:
        model = Location

    organization = factory.SubFactory(OrganizationFactory)
    name = factory.Sequence(lambda n: f"Location {n}")
    slug = factory.Sequence(lambda n: f"location-{n}")
    street = "Rue de la Loi 16"
    postal_code = "1000"
    city = "Brussels"


class LocationMembershipFactory(DjangoModelFactory):
    class Meta:
        model = LocationMembership

    user = factory.SubFactory(UserFactory)
    location = factory.SubFactory(LocationFactory)


class InvitationFactory(DjangoModelFactory):
    class Meta:
        model = Invitation

    organization = factory.SubFactory(OrganizationFactory)
    email = factory.Sequence(lambda n: f"invite{n}@example.be")
    role = Role.OPERATOR
    created_by = factory.SubFactory(UserFactory)
    expires_at = factory.LazyFunction(
        lambda: timezone.now() + timedelta(days=7)
    )
