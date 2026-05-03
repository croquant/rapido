from django import forms
from django.utils.translation import gettext_lazy as _

from core.models import Role


class RoleChangeForm(forms.Form):
    role = forms.ChoiceField(choices=Role.choices, label=_("Role"))
