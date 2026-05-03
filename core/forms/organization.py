from typing import ClassVar

from django import forms

from core.models import Organization


class OrganizationSettingsForm(forms.ModelForm):
    class Meta:
        model = Organization
        fields: ClassVar[list[str]] = [
            "name",
            "country",
            "vat_number",
            "default_language",
        ]
