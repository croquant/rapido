from django import forms
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _

ICON_NAMES = [
    "menu", "x", "plus", "edit", "trash", "check", "alert", "chevron-down",
    "search", "user", "building", "map-pin", "settings", "log-out", "eye",
    "eye-off", "mail", "lock", "calendar", "copy", "refresh", "more-vertical",
    "arrow-left", "arrow-right", "info",
]


class KitchenSinkForm(forms.Form):
    name = forms.CharField(label=_("Name"), help_text=_("Your full name."))
    email = forms.EmailField(label=_("Email"))
    role = forms.ChoiceField(
        label=_("Role"),
        choices=[("", "---"), ("owner", _("Owner")), ("staff", _("Staff"))],
    )
    accept = forms.BooleanField(label=_("Accept terms"))


def index(request: HttpRequest) -> HttpResponse:
    return render(request, template_name="index.html")


def design_kitchen_sink(request: HttpRequest) -> HttpResponse:
    invalid_form = KitchenSinkForm(
        data={"name": "", "email": "not-an-email", "role": ""},
    )
    invalid_form.is_valid()

    disabled_form = KitchenSinkForm(
        initial={"name": "Locked", "email": "locked@example.com"},
    )
    for f in disabled_form.fields.values():
        f.disabled = True

    return render(
        request,
        template_name="design/kitchen_sink.html",
        context={
            "clean_form": KitchenSinkForm(),
            "invalid_form": invalid_form,
            "disabled_form": disabled_form,
            "icon_names": ICON_NAMES,
        },
    )
