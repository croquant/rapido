from typing import Any

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core.models import Location, Organization, Role


class InvitationForm(forms.Form):
    email = forms.EmailField(label=_("Email"))
    role = forms.ChoiceField(choices=Role.choices, label=_("Role"))
    locations = forms.ModelMultipleChoiceField(
        queryset=Location.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label=_("Locations"),
    )

    def __init__(
        self,
        *args: Any,  # noqa: ANN401
        organization: Organization,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        super().__init__(*args, **kwargs)
        self._organization = organization
        self.fields["locations"].queryset = (  # type: ignore[attr-defined]
            Location.tenant_objects.for_organization(organization)
            .filter(is_active=True)
            .order_by("name")
        )

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        if cleaned.get("role") == Role.OPERATOR and not cleaned.get(
            "locations"
        ):
            raise ValidationError(
                {
                    "locations": _(
                        "Operators must be assigned at least one location."
                    )
                }
            )
        return cleaned


class InviteAcceptForm(forms.Form):
    new_password = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(render_value=False),
        strip=False,
    )
    confirm_password = forms.CharField(
        label=_("Confirm password"),
        widget=forms.PasswordInput(render_value=False),
        strip=False,
    )

    def clean(self) -> dict[str, Any]:
        cleaned: dict[str, Any] = super().clean() or {}
        p1 = cleaned.get("new_password")
        p2 = cleaned.get("confirm_password")
        if p1 and p2 and p1 != p2:
            self.add_error("confirm_password", _("Passwords do not match."))
        if p1 and not self.has_error("new_password"):
            try:
                validate_password(p1)
            except ValidationError as e:
                self.add_error("new_password", e)
        return cleaned
