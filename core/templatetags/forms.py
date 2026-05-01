from django import template
from django.forms import BoundField
from django.template.loader import render_to_string
from django.utils.safestring import SafeString

register = template.Library()


@register.simple_tag
def field(bound_field: BoundField, hint: str = "") -> SafeString:
    has_error = bool(bound_field.errors)
    is_bound = bound_field.form.is_bound

    if has_error:
        helper_text = " ".join(str(e) for e in bound_field.errors)
    elif hint:
        helper_text = hint
    else:
        helper_text = bound_field.help_text or ""

    helper_id = f"{bound_field.auto_id}_helptext" if helper_text else ""

    attrs: dict[str, str] = {}
    if has_error:
        attrs["aria-invalid"] = "true"
    elif is_bound:
        attrs["aria-invalid"] = "false"
    if helper_id:
        attrs["aria-describedby"] = helper_id

    control = bound_field.as_widget(attrs=attrs)  # type: ignore[arg-type]

    return render_to_string(
        "forms/_field.html",
        {
            "field": bound_field,
            "control": control,
            "helper_text": helper_text,
            "helper_id": helper_id,
            "has_error": has_error,
        },
    )


@register.simple_tag
def submit(
    primary_label: str,
    secondary_label: str = "",
    secondary_url: str = "",
) -> SafeString:
    return render_to_string(
        "forms/_submit.html",
        {
            "primary_label": primary_label,
            "secondary_label": secondary_label,
            "secondary_url": secondary_url,
        },
    )
