from django.conf import settings
from django.urls import path
from django.urls.resolvers import URLPattern

from . import views

app_name = "core"

urlpatterns: list[URLPattern] = [
    path(route="", view=views.index, name="index"),
]

if settings.DEBUG:
    urlpatterns += [
        path("__design__/", views.design_kitchen_sink, name="design_kitchen_sink"),
    ]
