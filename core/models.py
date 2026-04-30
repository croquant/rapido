from datetime import datetime
from typing import ClassVar
from uuid import UUID

from django.conf import settings
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.fields import (
    BooleanField,
    CharField,
    DateTimeField,
    EmailField,
    SlugField,
    UUIDField,
)
from django.db.models.functions import Lower
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField
from djmoney.models.fields import CurrencyField
from timezone_field import TimeZoneField

from config.currencies import SUPPORTED_CURRENCIES
from core.utils.ids import uuid7
from core.validators import (
    validate_currency,
    validate_org_slug,
    validate_vat,
)


class TimestampedModel(models.Model):
    created_at: DateTimeField[datetime] = models.DateTimeField(
        auto_now_add=True
    )
    updated_at: DateTimeField[datetime] = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Organization(TimestampedModel):
    public_id: UUIDField[UUID] = models.UUIDField(
        unique=True, default=uuid7, editable=False
    )
    name: CharField[str] = models.CharField(
        max_length=120, verbose_name=_("name")
    )
    slug: SlugField[str] = models.SlugField(
        unique=True,
        validators=[validate_org_slug],
        verbose_name=_("slug"),
    )
    country = CountryField(
        default="BE",
        verbose_name=_("country"),
    )
    default_timezone = TimeZoneField(
        default="Europe/Brussels",
        verbose_name=_("default timezone"),
    )
    default_currency = CurrencyField(
        default="EUR",
        choices=SUPPORTED_CURRENCIES,
        validators=[validate_currency],
        verbose_name=_("default currency"),
    )
    default_language: CharField[str] = models.CharField(
        max_length=8,
        choices=settings.LANGUAGES,
        default=settings.LANGUAGE_CODE,
        verbose_name=_("default language"),
    )
    vat_number: CharField[str] = models.CharField(
        max_length=14,
        verbose_name=_("VAT number"),
    )
    billing_email: EmailField[str] = models.EmailField(
        max_length=254, verbose_name=_("billing email")
    )
    is_active: BooleanField[bool] = models.BooleanField(
        default=False, verbose_name=_("active")
    )

    class Meta(TimestampedModel.Meta):
        abstract = False
        ordering: ClassVar[list[str]] = ["name"]
        verbose_name = _("organization")
        verbose_name_plural = _("organizations")

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()
        try:
            validate_vat(self.vat_number, str(self.country))
        except ValidationError as e:
            raise ValidationError({"vat_number": e}) from e


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
