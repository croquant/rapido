from django.db import transaction

from core.models import Organization, OrganizationMembership, Role, User


def create_organization_with_admin(
    *,
    email: str,
    password: str,
    org_name: str,
    org_slug: str,
    vat_number: str,
    billing_email: str,
    country: str = "BE",
) -> tuple[Organization, User, OrganizationMembership]:
    with transaction.atomic():
        org = Organization(
            name=org_name,
            slug=org_slug,
            vat_number=vat_number,
            billing_email=billing_email,
            country=country,
            is_active=False,
        )
        # Run slug regex + VAT/country invariant. Skip uniqueness so
        # duplicate slug/email surface as IntegrityError per issue #14.
        org.full_clean(validate_unique=False)
        org.save()
        user = User.objects.create_user(
            email=email, password=password, is_active=False
        )
        membership = OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role=Role.ADMIN,
            is_active=True,
            created_by=None,
        )
        return org, user, membership
