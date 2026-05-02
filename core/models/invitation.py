from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from django.conf import settings
from django.db import models
from django.db.models.fields import (
    CharField,
    DateTimeField,
    EmailField,
    UUIDField,
)
from django.utils.translation import gettext_lazy as _

from core.managers import TenantOwnedManager
from core.models.base import TimestampedModel
from core.models.location import Location
from core.models.membership import Role
from core.models.organization import Organization
from core.utils.ids import uuid7


class Invitation(TimestampedModel):
    public_id: UUIDField[UUID] = models.UUIDField(
        unique=True, default=uuid7, editable=False
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="invitations",
        verbose_name=_("organization"),
    )
    email: EmailField[str] = models.EmailField(
        max_length=254, verbose_name=_("email")
    )
    role: CharField[str] = models.CharField(
        max_length=16,
        choices=Role.choices,
        verbose_name=_("role"),
    )
    locations = models.ManyToManyField(
        Location,
        blank=True,
        related_name="invitations",
        verbose_name=_("locations"),
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name=_("created by"),
    )
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="+",
        null=True,
        blank=True,
        verbose_name=_("revoked by"),
    )
    expires_at: DateTimeField = models.DateTimeField(
        verbose_name=_("expires at")
    )
    accepted_at: DateTimeField = models.DateTimeField(
        null=True, blank=True, verbose_name=_("accepted at")
    )
    revoked_at: DateTimeField = models.DateTimeField(
        null=True, blank=True, verbose_name=_("revoked at")
    )

    objects: ClassVar[models.Manager[Invitation]] = models.Manager()  # type: ignore[assignment]
    tenant_objects: ClassVar[TenantOwnedManager] = TenantOwnedManager()

    class Meta(TimestampedModel.Meta):
        abstract = False
        ordering: ClassVar[list[str]] = ["-created_at"]
        verbose_name = _("invitation")
        verbose_name_plural = _("invitations")
        constraints: ClassVar[list[models.UniqueConstraint]] = [
            models.UniqueConstraint(
                fields=["organization", "email"],
                condition=models.Q(
                    accepted_at__isnull=True, revoked_at__isnull=True
                ),
                name="invitation_one_pending_per_email_per_org",
            ),
        ]

    def save(self, *args: object, **kwargs: object) -> None:
        if self.email:
            self.email = self.email.lower()
        super().save(*args, **kwargs)  # type: ignore[arg-type]

    def __str__(self) -> str:
        return f"{self.email} -> {self.organization} ({self.role})"
