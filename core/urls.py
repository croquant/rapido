from django.urls import path
from django.urls.resolvers import URLPattern

from . import views

app_name = "core"

urlpatterns: list[URLPattern] = [
    path(route="", view=views.index, name="index"),
]
