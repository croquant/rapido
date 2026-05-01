from typing import ClassVar
from uuid import UUID

from django.db import models
from django.db.models.fields import (
    BooleanField,
    CharField,
    SlugField,
    UUIDField,
)
from django.utils.translation import gettext_lazy as _

from core.models.base import TimestampedModel
from core.models.organization import Organization
from core.utils.ids import uuid7
from core.validators import validate_slug


class Location(TimestampedModel):
    public_id: UUIDField[UUID] = models.UUIDField(
        unique=True, default=uuid7, editable=False
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="locations",
        verbose_name=_("organization"),
    )
    name: CharField[str] = models.CharField(
        max_length=120, verbose_name=_("name")
    )
    slug: SlugField[str] = models.SlugField(
        validators=[validate_slug],
        verbose_name=_("URL"),
        help_text=_("Used in web addresses for this location."),
    )
    street: CharField[str] = models.CharField(
        max_length=200, verbose_name=_("street")
    )
    postal_code: CharField[str] = models.CharField(
        max_length=16, verbose_name=_("postal code")
    )
    city: CharField[str] = models.CharField(
        max_length=120, verbose_name=_("city")
    )
    phone: CharField[str] = models.CharField(
        max_length=32, blank=True, verbose_name=_("phone")
    )
    is_active: BooleanField[bool] = models.BooleanField(
        default=True, verbose_name=_("active")
    )

    class Meta(TimestampedModel.Meta):
        abstract = False
        ordering: ClassVar[list[str]] = ["organization", "name"]
        verbose_name = _("location")
        verbose_name_plural = _("locations")
        constraints: ClassVar[list[models.UniqueConstraint]] = [
            models.UniqueConstraint(
                fields=["organization", "slug"],
                name="location_org_slug_unique",
            ),
        ]

    def __str__(self) -> str:
        return self.name
