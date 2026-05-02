from django.conf import settings
from django.db import transaction
from django.urls import reverse

from core.models import Organization, OrganizationMembership, Role, User
from core.services.mail import send_templated
from core.services.tokens import VERIFY_SALT, make_token


def create_organization_with_admin(
    *,
    email: str,
    password: str,
    org_name: str,
    org_slug: str,
    vat_number: str,
    billing_email: str,
    default_language: str,
    country: str = "BE",
) -> tuple[Organization, User, OrganizationMembership]:
    with transaction.atomic():
        org = Organization(
            name=org_name,
            slug=org_slug,
            vat_number=vat_number,
            billing_email=billing_email,
            country=country,
            default_language=default_language,
            is_active=False,
        )
        # Run slug regex + VAT/country invariant. Skip uniqueness so
        # duplicate slug/email surface as IntegrityError per issue #14.
        org.full_clean(validate_unique=False)
        org.save()
        user = User.objects.create_user(
            email=email,
            password=password,
            is_active=False,
            preferred_language=default_language,
        )
        membership = OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role=Role.ADMIN,
            is_active=True,
            created_by=None,
        )
        token = make_token(user, salt=VERIFY_SALT)
        verify_url = (
            f"{settings.SITE_URL}{reverse('core:verify', args=[token])}"
        )
        transaction.on_commit(
            lambda: send_templated(
                "email/verify",
                to=user,
                language=org.default_language,
                context={"verify_url": verify_url, "org_name": org.name},
            )
        )
        return org, user, membership
