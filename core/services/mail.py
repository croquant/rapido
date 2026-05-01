"""Templated transactional mail.

Convention for ``send_templated(template_base, ...)``:

- ``<template_base>.txt`` (required) - plain-text body. Should
  ``{% extends "email/_base.txt" %}``.
- ``<template_base>.html`` (optional) - HTML alternative. Attached only when
  the template exists.
- ``<template_base>_subject.txt`` (required) - subject line. Rendered, then
  ``.strip()``'d to a single line.

Rendering and sending happen inside ``translation.override(lang)`` where
``lang = language or to.preferred_language or settings.LANGUAGE_CODE``. Per
epic 2b §5, the ``Organization.default_language`` step is the caller's
responsibility (pass ``language=`` explicitly).
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string
from django.utils import translation

from core.models import User


def send_templated(
    template_base: str,
    *,
    to: User,
    language: str | None = None,
    context: dict[str, Any] | None = None,
) -> None:
    lang = language or to.preferred_language or settings.LANGUAGE_CODE
    ctx: dict[str, Any] = {
        "recipient": to,
        "brand": settings.SITE_BRAND,
        **(context or {}),
    }
    with translation.override(lang):
        subject = render_to_string(f"{template_base}_subject.txt", ctx).strip()
        text_body = render_to_string(f"{template_base}.txt", ctx)
        try:
            html_body: str | None = render_to_string(
                f"{template_base}.html", ctx
            )
        except TemplateDoesNotExist:
            html_body = None
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[to.email],
        )
        if html_body is not None:
            msg.attach_alternative(html_body, "text/html")
        msg.send()
