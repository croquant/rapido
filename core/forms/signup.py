from typing import Any

from django import forms
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django_countries.fields import CountryField

from core.models import Organization, User
from core.validators import validate_slug, validate_vat


class SignupForm(forms.Form):
    email = forms.EmailField(
        label=_("Email"),
        max_length=254,
    )
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(render_value=False),
        strip=False,
    )
    org_name = forms.CharField(
        label=_("Organisation name"),
        max_length=120,
    )
    org_slug = forms.CharField(
        label=_("URL slug"),
        max_length=50,
        validators=[validate_slug],
    )
    vat_number = forms.CharField(
        label=_("VAT number"),
        max_length=14,
    )
    country = CountryField(default="BE").formfield(label=_("Country"))
    default_language = forms.ChoiceField(
        label=_("Language"),
        choices=settings.LANGUAGES,
    )

    def clean_email(self) -> str:
        return self.cleaned_data["email"].lower()

    def clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = super().clean() or {}
        vat = cleaned.get("vat_number")
        country = cleaned.get("country")
        if vat and country:
            try:
                validate_vat(vat, str(country))
            except ValidationError as e:
                self.add_error("vat_number", e)
        slug = cleaned.get("org_slug")
        if slug and Organization.objects.filter(slug=slug).exists():
            self.add_error("org_slug", _("This slug is already taken."))
        email = cleaned.get("email")
        if email and User.objects.filter(email__iexact=email).exists():
            self.add_error(
                "email",
                _("An account with this email already exists."),
            )
        password = cleaned.get("password")
        if password and not self.has_error("password"):
            try:
                validate_password(password, user=User(email=email or ""))
            except ValidationError as e:
                self.add_error("password", e)
        return cleaned
