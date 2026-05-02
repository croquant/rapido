from typing import Any

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core.models import User


class LoginForm(forms.Form):
    email = forms.EmailField(
        label=_("Email"),
        max_length=254,
    )
    password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(render_value=False),
        strip=False,
    )

    # Class-level defaults; clean() rebinds them as instance attributes.
    user_cache: User | None = None
    # Set when password is correct but the account is unverified; the
    # template renders the resend form only when this is truthy.
    unverified_email: str | None = None

    def clean_email(self) -> str:
        return (self.cleaned_data.get("email") or "").lower().strip()

    def clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = super().clean() or {}
        email = cleaned.get("email")
        password = cleaned.get("password")
        if not (email and password):
            return cleaned
        user = User.objects.filter(email__iexact=email).first()
        if user is None or not user.check_password(password):
            raise ValidationError(_("Invalid email or password."))
        if not user.is_active:
            self.unverified_email = email
            raise ValidationError(
                _(
                    "Your email isn't verified yet. Check your inbox for the "
                    "verification link."
                )
            )
        self.user_cache = user
        return cleaned

    def get_user(self) -> User | None:
        return self.user_cache
