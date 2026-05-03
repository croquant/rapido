from django.db import transaction

from core.models import Location


def deactivate_location(location: Location) -> None:
    if not location.is_active:
        return
    with transaction.atomic():
        locked = Location.objects.select_for_update().get(pk=location.pk)
        if not locked.is_active:
            return
        locked.is_active = False
        locked.save(update_fields=["is_active", "updated_at"])
        location.is_active = False
        location.updated_at = locked.updated_at


def reactivate_location(location: Location) -> None:
    if location.is_active:
        return
    with transaction.atomic():
        locked = Location.objects.select_for_update().get(pk=location.pk)
        if locked.is_active:
            return
        locked.is_active = True
        locked.save(update_fields=["is_active", "updated_at"])
        location.is_active = True
        location.updated_at = locked.updated_at
