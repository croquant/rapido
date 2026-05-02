from django.conf import settings
from django.contrib.auth import login
from django.core import signing
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _

from core.forms.signup import SignupForm
from core.services.activation import activate_from_token
from core.services.exceptions import AlreadyActiveError, NoAdminMembershipError
from core.services.login_redirect import login_redirect_for
from core.services.signup import create_organization_with_admin


def signup(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            try:
                create_organization_with_admin(
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                    org_name=form.cleaned_data["org_name"],
                    org_slug=form.cleaned_data["org_slug"],
                    vat_number=form.cleaned_data["vat_number"],
                    billing_email=form.cleaned_data["email"],
                    default_language=form.cleaned_data["default_language"],
                    country=str(form.cleaned_data["country"]),
                )
            except IntegrityError:
                form.add_error(
                    None,
                    _("This email or organisation slug is already in use."),
                )
            else:
                return redirect("core:signup_done")
    else:
        # Django normalises Accept-Language to lowercase (nl-be), but
        # settings.LANGUAGES uses canonical case (nl-BE) which is what the
        # form choices expect. Case-insensitive lookup bridges the two.
        active = (get_language() or settings.LANGUAGE_CODE).lower()
        canonical = {code.lower(): code for code, _ in settings.LANGUAGES}
        initial_lang = canonical.get(active, settings.LANGUAGE_CODE)
        form = SignupForm(initial={"default_language": initial_lang})
    return render(request, "auth/signup.html", {"form": form})


def signup_done(request: HttpRequest) -> HttpResponse:
    return render(request, "auth/signup_done.html")


def verify(request: HttpRequest, token: str) -> HttpResponse:
    try:
        user = activate_from_token(token)
    except signing.BadSignature, NoAdminMembershipError:
        # SignatureExpired is a BadSignature subclass; one catch covers both.
        return render(request, "auth/verify_failed.html")
    except AlreadyActiveError:
        return render(request, "auth/verify_already.html")
    login(request, user)
    return redirect(login_redirect_for(user))
