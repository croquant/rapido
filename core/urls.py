from django.conf import settings
from django.urls import path
from django.urls.resolvers import URLPattern

from .views import home, invitations, locations, members
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
from .views.organization import settings_view as settings_organization

app_name = "core"

urlpatterns: list[URLPattern] = [
    path(route="", view=home, name="home"),
    path(route="signup/", view=signup, name="signup"),
    path(route="signup/done/", view=signup_done, name="signup_done"),
    path(route="verify/<str:token>/", view=verify, name="verify"),
    path(
        route="invite/<str:token>/",
        view=invitations.accept,
        name="invitation_accept",
    ),
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
        view=locations.list_view,
        name="settings_locations",
    ),
    path(
        route="o/<slug:slug>/settings/locations/new/",
        view=locations.create,
        name="settings_locations_create",
    ),
    path(
        route="o/<slug:slug>/settings/locations/<int:pk>/",
        view=locations.detail,
        name="settings_locations_detail",
    ),
    path(
        route="o/<slug:slug>/settings/locations/<int:pk>/edit/",
        view=locations.edit,
        name="settings_locations_edit",
    ),
    path(
        route="o/<slug:slug>/settings/locations/<int:pk>/deactivate/",
        view=locations.deactivate,
        name="settings_locations_deactivate",
    ),
    path(
        route="o/<slug:slug>/settings/locations/<int:pk>/reactivate/",
        view=locations.reactivate,
        name="settings_locations_reactivate",
    ),
    path(
        route="o/<slug:slug>/settings/locations/<int:pk>/operators/<int:upk>/toggle/",
        view=locations.toggle_operator,
        name="settings_locations_toggle_operator",
    ),
    path(
        route="o/<slug:slug>/settings/members/",
        view=members.list_view,
        name="settings_members",
    ),
    path(
        route="o/<slug:slug>/settings/members/<int:pk>/",
        view=members.detail,
        name="settings_members_detail",
    ),
    path(
        route="o/<slug:slug>/settings/members/<int:pk>/role/",
        view=members.change_role,
        name="settings_members_change_role",
    ),
    path(
        route="o/<slug:slug>/settings/members/<int:pk>/deactivate/",
        view=members.deactivate,
        name="settings_members_deactivate",
    ),
    path(
        route="o/<slug:slug>/settings/members/<int:pk>/reactivate/",
        view=members.reactivate,
        name="settings_members_reactivate",
    ),
    path(
        route="o/<slug:slug>/settings/members/<int:pk>/locations/<int:lpk>/toggle/",
        view=members.toggle_location,
        name="settings_members_toggle_location",
    ),
    path(
        route="o/<slug:slug>/settings/invitations/",
        view=invitations.create,
        name="settings_invitations_create",
    ),
    path(
        route="o/<slug:slug>/settings/invitations/<int:pk>/resend/",
        view=invitations.resend,
        name="settings_invitations_resend",
    ),
    path(
        route="o/<slug:slug>/settings/invitations/<int:pk>/revoke/",
        view=invitations.revoke,
        name="settings_invitations_revoke",
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
