from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, AnonymousUser

from core.models import Organization


def resolve_locale(
    user: AbstractBaseUser | AnonymousUser | None,
    org: Organization | None,
    *,
    default: str | None = settings.LANGUAGE_CODE,
) -> str | None:
    """User preference > org default > `default`."""
    if user is not None and getattr(user, "is_authenticated", False):
        pref = getattr(user, "preferred_language", "") or ""
        if pref:
            return pref
    if org is not None:
        explicit = getattr(org, "default_language", "") or ""
        if explicit:
            return explicit
    return default
