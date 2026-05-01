from django import forms
from django.template import Context, Template


class SampleForm(forms.Form):
    email = forms.EmailField(help_text="We never share this.")
    note = forms.CharField(disabled=True, required=False, initial="locked")


def render(tpl: str, **ctx: object) -> str:
    return Template("{% load forms %}" + tpl).render(Context(ctx))


def test_field_valid_bound_renders_label_hint_and_aria() -> None:
    form = SampleForm({"email": "ok@example.com"})
    assert form.is_valid()
    out = render("{% field form.email %}", form=form)

    assert '<label for="id_email">' in out
    assert 'aria-invalid="false"' in out
    assert 'aria-describedby="id_email_helptext"' in out
    assert '<small id="id_email_helptext"' in out
    assert "We never share this." in out


def test_field_invalid_bound_renders_error_and_aria_invalid() -> None:
    form = SampleForm({"email": "nope"})
    assert not form.is_valid()
    out = render("{% field form.email %}", form=form)

    assert 'aria-invalid="true"' in out
    assert 'aria-describedby="id_email_helptext"' in out
    assert 'class="error"' in out
    assert "valid email" in out.lower()


def test_field_unbound_has_no_aria_invalid() -> None:
    form = SampleForm()
    out = render("{% field form.email %}", form=form)

    assert "aria-invalid" not in out
    assert "We never share this." in out


def test_field_explicit_hint_overrides_help_text() -> None:
    form = SampleForm()
    out = render('{% field form.email hint="Custom hint." %}', form=form)

    assert "Custom hint." in out
    assert "We never share this." not in out


def test_field_disabled_attribute_preserved() -> None:
    form = SampleForm()
    out = render("{% field form.note %}", form=form)

    assert "disabled" in out


def test_submit_primary_only() -> None:
    out = render('{% submit "Save" %}')

    assert '<button type="submit">Save</button>' in out
    assert "<a " not in out


def test_submit_with_secondary() -> None:
    out = render(
        '{% submit "Save" secondary_label="Cancel" secondary_url="/back/" %}'
    )

    assert '<button type="submit">Save</button>' in out
    assert 'href="/back/"' in out
    assert ">Cancel<" in out
    assert 'class="secondary"' in out


def test_errors_partial_renders_non_field_errors() -> None:
    form = SampleForm({"email": "ok@example.com"})
    form.add_error(None, "Top-level boom.")
    form.is_valid()
    out = Template('{% include "forms/_errors.html" %}').render(
        Context({"form": form})
    )

    assert 'role="alert"' in out
    assert "Top-level boom." in out


def test_errors_partial_silent_when_clean() -> None:
    form = SampleForm({"email": "ok@example.com"})
    assert form.is_valid()
    out = Template('{% include "forms/_errors.html" %}').render(
        Context({"form": form})
    )

    assert out.strip() == ""
