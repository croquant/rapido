from typing import cast

from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import get_language
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST

from core.forms.auth import LoginForm
from core.forms.signup import SignupForm
from core.models import OrganizationMembership, User
from core.services.activation import activate_from_token
from core.services.exceptions import AlreadyActiveError, NoAdminMembershipError
from core.services.login_redirect import login_redirect_for
from core.services.resend import resend_verification_email
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
    except signing.BadSignature:
        # SignatureExpired is a BadSignature subclass; one catch covers both.
        return render(request, "auth/verify_failed.html")
    except NoAdminMembershipError:
        return render(request, "auth/verify_failed.html")
    except AlreadyActiveError:
        return render(request, "auth/verify_already.html")
    auth_login(request, user)
    return redirect(login_redirect_for(user))


def login(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(login_redirect_for(cast(User, request.user)))
    next_param = request.POST.get("next") or request.GET.get("next") or ""
    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.get_user()
            assert user is not None  # form invariant when is_valid()
            auth_login(request, user)
            if next_param and url_has_allowed_host_and_scheme(
                next_param,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(next_param)
            return redirect(login_redirect_for(user))
    else:
        form = LoginForm()
    return render(
        request,
        "auth/login.html",
        {"form": form, "next": next_param},
    )


@require_POST
def logout(request: HttpRequest) -> HttpResponse:
    auth_logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)


@require_POST
def resend_verification(request: HttpRequest) -> HttpResponse:
    # Always renders the same "sent" page so the response can't be used to
    # enumerate accounts (whitepaper epic 2b §3, issue #56 acceptance).
    email = (request.POST.get("email") or "").strip().lower()
    resend_verification_email(email)
    return render(request, "auth/verify_resent.html")


@login_required
def org_picker(request: HttpRequest) -> HttpResponse:
    user = cast(User, request.user)
    memberships = list(
        OrganizationMembership.objects.filter(user=user, is_active=True)
        .select_related("organization")
        .order_by("organization__name")
    )
    if len(memberships) == 1:
        return redirect(login_redirect_for(user))
    return render(
        request,
        "auth/org_picker.html",
        {"memberships": memberships},
    )
