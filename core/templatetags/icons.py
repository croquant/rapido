from django import template
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.utils.safestring import SafeString

register = template.Library()


@register.simple_tag
def icon(name: str, css_class: str = "") -> SafeString:
    return render_to_string(
        "_partials/icon.html",
        {
            "name": name,
            "css_class": css_class,
            "sprite_url": static("icons/sprite.svg"),
        },
    )
