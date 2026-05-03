from typing import cast

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from core.forms.profile import ChangePasswordForm, ProfileForm
from core.models import User
from core.services.exceptions import WeakPasswordError, WrongPasswordError
from core.services.profile import change_password, update_profile


def _profile_initial(user: User) -> dict[str, str]:
    return {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "preferred_language": user.preferred_language,
    }


@login_required
def me(request: HttpRequest) -> HttpResponse:
    user = cast(User, request.user)
    return render(
        request,
        "profile/me.html",
        {
            "profile_form": ProfileForm(initial=_profile_initial(user)),
            "password_form": ChangePasswordForm(user=user),
        },
    )


@require_POST
@login_required
def update_profile_view(request: HttpRequest) -> HttpResponse:
    user = cast(User, request.user)
    form = ProfileForm(request.POST)
    if form.is_valid():
        try:
            update_profile(
                user,
                first_name=form.cleaned_data["first_name"],
                last_name=form.cleaned_data["last_name"],
                preferred_language=form.cleaned_data["preferred_language"],
            )
        except DjangoValidationError as exc:
            for field, errors in exc.message_dict.items():
                for message in errors:
                    form.add_error(field, message)
        else:
            messages.success(request, _("Profile updated."))
            return redirect("core:profile")
    return render(
        request,
        "profile/me.html",
        {
            "profile_form": form,
            "password_form": ChangePasswordForm(user=user),
        },
    )


@require_POST
@login_required
def change_password_view(request: HttpRequest) -> HttpResponse:
    user = cast(User, request.user)
    form = ChangePasswordForm(request.POST, user=user)
    if form.is_valid():
        try:
            change_password(
                request,
                current_password=form.cleaned_data["current_password"],
                new_password=form.cleaned_data["new_password1"],
            )
        except WrongPasswordError:
            form.add_error(
                "current_password", _("Current password is incorrect.")
            )
        except WeakPasswordError as exc:
            for message in exc.messages:
                form.add_error("new_password1", message)
        else:
            messages.success(
                request,
                _("Password changed. Other sessions have been signed out."),
            )
            return redirect("core:profile")
    return render(
        request,
        "profile/me.html",
        {
            "profile_form": ProfileForm(initial=_profile_initial(user)),
            "password_form": form,
        },
    )
