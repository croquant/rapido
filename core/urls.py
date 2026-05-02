from django.conf import settings
from django.urls import path
from django.urls.resolvers import URLPattern

from .views import home
from .views.auth import verify_placeholder
from .views.design import design_kitchen_sink

app_name = "core"

urlpatterns: list[URLPattern] = [
    path(route="", view=home, name="home"),
    path(route="verify/<str:token>/", view=verify_placeholder, name="verify"),
]

if settings.DEBUG:
    urlpatterns += [
        path(
            "__design__/",
            design_kitchen_sink,
            name="design_kitchen_sink",
        ),
    ]
