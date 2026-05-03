from typing import ClassVar

from django.conf import settings
from django.db import models
from django.db.models.fields import BooleanField, CharField
from django.utils.translation import gettext_lazy as _

from core.managers import TenantOwnedManager
from core.models.base import TimestampedModel
from core.models.location import Location
from core.models.organization import Organization


class LocationMembershipManager(TenantOwnedManager):
    organization_lookup = "location__organization"


class Role(models.TextChoices):
    ADMIN = "ADMIN", _("Admin")
    OPERATOR = "OPERATOR", _("Operator")


class OrganizationMembership(TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
        verbose_name=_("user"),
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        related_name="organization_memberships",
        verbose_name=_("organization"),
    )
    role: CharField[str] = models.CharField(
        max_length=16,
        choices=Role.choices,
        verbose_name=_("role"),
    )
    is_active: BooleanField[bool] = models.BooleanField(
        default=True, verbose_name=_("active")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("created by"),
    )

    objects: ClassVar[models.Manager[OrganizationMembership]] = models.Manager()  # type: ignore[assignment]
    tenant_objects: ClassVar[TenantOwnedManager] = TenantOwnedManager()

    class Meta(TimestampedModel.Meta):
        abstract = False
        ordering: ClassVar[list[str]] = ["organization", "user"]
        verbose_name = _("organization membership")
        verbose_name_plural = _("organization memberships")
        constraints: ClassVar[list[models.UniqueConstraint]] = [
            models.UniqueConstraint(
                fields=["user", "organization"],
                name="orgmembership_user_org_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.organization} ({self.role})"


class LocationMembership(TimestampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="location_memberships",
        verbose_name=_("user"),
    )
    location = models.ForeignKey(
        Location,
        on_delete=models.CASCADE,
        related_name="location_memberships",
        verbose_name=_("location"),
    )
    pin: CharField[str] = models.CharField(
        max_length=128,
        blank=True,
        verbose_name=_("PIN"),
    )
    is_active: BooleanField[bool] = models.BooleanField(
        default=True, verbose_name=_("active")
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("created by"),
    )

    objects: ClassVar[models.Manager[LocationMembership]] = models.Manager()  # type: ignore[assignment]
    tenant_objects: ClassVar[LocationMembershipManager] = (
        LocationMembershipManager()
    )

    class Meta(TimestampedModel.Meta):
        abstract = False
        ordering: ClassVar[list[str]] = ["location", "user"]
        verbose_name = _("location membership")
        verbose_name_plural = _("location memberships")
        constraints: ClassVar[list[models.UniqueConstraint]] = [
            models.UniqueConstraint(
                fields=["user", "location"],
                name="locmembership_user_location_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.location}"
