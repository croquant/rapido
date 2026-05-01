from django.conf import settings


def resolve_locale(user, org) -> str:
    """User preference > org default > system default."""
    if user is not None and getattr(user, "is_authenticated", False):
        pref = getattr(user, "preferred_language", "") or ""
        if pref:
            return pref
    if org is not None:
        default = getattr(org, "default_language", "") or ""
        if default:
            return default
    return settings.LANGUAGE_CODE
