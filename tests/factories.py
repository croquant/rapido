# pyright: reportPrivateImportUsage=false, reportIncompatibleVariableOverride=false
import factory
from factory.django import DjangoModelFactory

from core.models import Organization, OrganizationMembership, Role, User


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.be")


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
