from django.conf import settings
from django.urls import path
from django.urls.resolvers import URLPattern

from .views import home
from .views.design import design_kitchen_sink

app_name = "core"

urlpatterns: list[URLPattern] = [
    path(route="", view=home, name="home"),
]

if settings.DEBUG:
    urlpatterns += [
        path(
            "__design__/",
            design_kitchen_sink,
            name="design_kitchen_sink",
        ),
    ]
