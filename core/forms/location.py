from typing import Any, ClassVar

from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from core.models import Location, Organization


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields: ClassVar[list[str]] = [
            "name",
            "slug",
            "street",
            "postal_code",
            "city",
            "phone",
        ]

    def __init__(
        self,
        *args: Any,  # noqa: ANN401
        organization: Organization,
        editing: bool = False,
        **kwargs: Any,  # noqa: ANN401
    ) -> None:
        super().__init__(*args, **kwargs)
        self._organization = organization
        if editing:
            self.fields.pop("slug", None)

    def clean_slug(self) -> str:
        slug = self.cleaned_data["slug"]
        qs = Location.tenant_objects.for_organization(  # type: ignore[attr-defined]
            self._organization
        ).filter(slug=slug)
        if self.instance.pk is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(
                _(
                    "A location with this URL already exists in this "
                    "organization."
                )
            )
        return slug
