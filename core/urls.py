from django.conf import settings
from django.urls import path
from django.urls.resolvers import URLPattern

from .views import home
from .views.auth import (
    login,
    logout,
    org_picker,
    resend_verification,
    signup,
    signup_done,
    verify,
)
from .views.design import design_kitchen_sink

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
    path(route="orgs/", view=org_picker, name="org_picker"),
]

if settings.DEBUG:
    urlpatterns += [
        path(
            "__design__/",
            design_kitchen_sink,
            name="design_kitchen_sink",
        ),
    ]
