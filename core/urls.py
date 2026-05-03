from django.conf import settings
from django.urls import path
from django.urls.resolvers import URLPattern

from .views import home
from .views.auth import (
    login,
    logout,
    org_picker,
    password_reset_confirm,
    password_reset_request,
    resend_verification,
    signup,
    signup_done,
    verify,
)
from .views.dashboard import dashboard
from .views.design import design_kitchen_sink
from .views.settings import (
    settings_invitations,
    settings_locations,
    settings_members,
    settings_organization,
)

app_name = "core"

urlpatterns: list[URLPattern] = [
    path(route="", view=home, name="home"),
    path(route="signup/", view=signup, name="signup"),
    path(route="signup/done/", view=signup_done, name="signup_done"),
    path(route="verify/<str:token>/", view=verify, name="verify"),
    path(route="login/", view=login, name="login"),
    path(route="logout/", view=logout, name="logout"),
    path(
        route="resend-verification/",
        view=resend_verification,
        name="resend_verification",
    ),
    path(
        route="password/reset/",
        view=password_reset_request,
        name="password_reset_request",
    ),
    path(
        route="password/reset/<str:token>/",
        view=password_reset_confirm,
        name="password_reset_confirm",
    ),
    path(route="orgs/", view=org_picker, name="org_picker"),
    path(route="o/<slug:slug>/", view=dashboard, name="org_dashboard"),
    path(
        route="o/<slug:slug>/settings/locations/",
        view=settings_locations,
        name="settings_locations",
    ),
    path(
        route="o/<slug:slug>/settings/members/",
        view=settings_members,
        name="settings_members",
    ),
    path(
        route="o/<slug:slug>/settings/invitations/",
        view=settings_invitations,
        name="settings_invitations",
    ),
    path(
        route="o/<slug:slug>/settings/organization/",
        view=settings_organization,
        name="settings_organization",
    ),
]

if settings.DEBUG:
    urlpatterns += [
        path(
            "__design__/",
            design_kitchen_sink,
            name="design_kitchen_sink",
        ),
    ]
