from __future__ import annotations

from typing import ClassVar
from uuid import UUID

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.db.models.fields import (
    CharField,
    EmailField,
    UUIDField,
)
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _

from core.models.base import TimestampedModel
from core.utils.ids import uuid7


class UserManager(BaseUserManager["User"]):
    def create_user(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> User:
        if not email:
            raise ValueError(_("Users must have an email address."))
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: object,
    ) -> User:
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(
                _("Superuser must have is_superuser=True.")
            )
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimestampedModel):
    public_id: UUIDField[UUID] = models.UUIDField(
        unique=True, default=uuid7, editable=False
    )
    email: EmailField[str] = models.EmailField(
        unique=True, verbose_name=_("email")
    )
    first_name: CharField[str] = models.CharField(
        max_length=150, blank=True, verbose_name=_("first name")
    )
    last_name: CharField[str] = models.CharField(
        max_length=150, blank=True, verbose_name=_("last name")
    )
    preferred_language: CharField[str] = models.CharField(
        max_length=8,
        choices=settings.LANGUAGES,
        blank=True,
        verbose_name=_("preferred language"),
    )
    is_active = models.BooleanField(  # type: ignore[assignment]
        default=True, verbose_name=_("active")
    )
    is_staff = models.BooleanField(
        default=False, verbose_name=_("staff status")
    )

    objects: ClassVar[UserManager] = UserManager()  # type: ignore[assignment]

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []  # noqa: RUF012

    class Meta(TimestampedModel.Meta):
        abstract = False
        ordering: ClassVar[list[str]] = ["email"]
        verbose_name = _("user")
        verbose_name_plural = _("users")
        constraints: ClassVar[list[models.UniqueConstraint]] = [
            models.UniqueConstraint(
                Lower("email"),
                name="user_email_ci_unique",
            ),
        ]

    def __str__(self) -> str:
        return self.email
