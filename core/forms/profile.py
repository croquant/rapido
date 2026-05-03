from collections.abc import Mapping
from typing import Any

from django import forms
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core.models import User


class ProfileForm(forms.Form):
    first_name = forms.CharField(
        label=_("First name"), max_length=150, required=False
    )
    last_name = forms.CharField(
        label=_("Last name"), max_length=150, required=False
    )
    preferred_language = forms.ChoiceField(
        label=_("Preferred language"),
        choices=[("", _("Use browser/org default")), *settings.LANGUAGES],
        required=False,
    )


class ChangePasswordForm(forms.Form):
    current_password = forms.CharField(
        label=_("Current password"),
        widget=forms.PasswordInput(render_value=False),
        strip=False,
    )
    new_password1 = forms.CharField(
        label=_("New password"),
        widget=forms.PasswordInput(render_value=False),
        strip=False,
    )
    new_password2 = forms.CharField(
        label=_("Confirm new password"),
        widget=forms.PasswordInput(render_value=False),
        strip=False,
    )

    def __init__(
        self, data: Mapping[str, Any] | None = None, *, user: User
    ) -> None:
        self.user = user
        super().__init__(data)

    def clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = super().clean() or {}
        p1 = cleaned.get("new_password1")
        p2 = cleaned.get("new_password2")
        if p1 and p2 and p1 != p2:
            self.add_error("new_password2", _("Passwords do not match."))
        if p1 and not self.has_error("new_password1"):
            try:
                validate_password(p1, user=self.user)
            except ValidationError as e:
                self.add_error("new_password1", e)
        return cleaned
