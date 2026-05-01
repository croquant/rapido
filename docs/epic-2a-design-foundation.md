# EPIC #2a - Frontend design foundation

Lock the CSS, template, layout, HTMX, a11y, and i18n primitives that 2b (onboarding) and 2c (locations & users management) build on. No business logic: only template/static plumbing + a dev-only kitchen-sink page.

## 1. Architecture decisions

| Decision                  | Choice                                                                                                                                                                                                                       | Why                                                                                                                                                  |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| CSS framework             | **Pico CSS v2** (class-light flavor), vendored at `static/css/pico.min.css` from the official GitHub release; brand overrides in `static/css/brand.css` (loaded after Pico)                                                  | Semantic-HTML defaults (button / form / table / `<dialog>`) cut ~80% of CSS we'd otherwise author; agents stay focused on layout + brand + interactions |
| Design tokens             | Brand vars in `static/css/brand.css` `:root` override Pico's `--pico-*` defaults (palette, brand radii, shadow, type scale). Spacing / typography inherits from Pico unless explicitly overridden                            | Native cascade; dark mode = Pico's `[data-theme=dark]` block; zero toolchain                                                                         |
| Component templating      | Django 6.0 built-in `{% partialdef %}` / `{% partial %}` (no third-party package; `django-template-partials` was absorbed into core)                                                                                         | Addressable HTMX swap targets without a second templating dialect; skip `django-cotton` (slot DX not worth it at this scale), skip include-only (no swap targets) |
| Form rendering            | `{% field form.x %}` template tag (in `core/templatetags/forms.py`) renders semantic `<label for>` + control + `<small>` (hint) + Pico's `aria-invalid` + helper text on error                                              | Skip `django-crispy-forms` (Bootstrap/Tailwind-shaped); Pico styles fields automatically; partial just wires Django form errors into Pico's helper-text + `aria-invalid` convention |
| Layout shells             | Three: `base_public.html` (centered single column), `base_picker.html` (org picker), `base_org.html` (top-bar always, left rail only on `/settings/*`); all extend a thin `_base.html`                                       | Top-bar matches POS operator mental model; left rail only where management depth justifies it                                                        |
| HTMX usage                | Inline form validation, modal open/close, row-level row actions, dashboard table refresh. Full page loads for navigation between sections                                                                                    | HTMX earns its keep on local mutations; URL state stays real                                                                                          |
| HTMX response convention  | Return swapped partial fragment (via `django-template-partials`); use `HX-Trigger` for cross-component refresh; `422` + form partial on validation error so the swap still happens                                            | Predictable; no JSON DSL                                                                                                                              |
| Icons                     | Hand-curated SVG sprite at `static/icons/sprite.svg`, used via `{% icon "name" %}` template tag (`<svg><use href=".../sprite.svg#name"/></svg>`)                                                                              | Zero runtime, accessible (`aria-hidden`), GDPR-clean (no CDN); seeded from Lucide (MIT) by copy                                                       |
| Typography                | System font stack + self-hosted **Inter** (woff2, weights 400 + 600) for headings/brand, declared via `@font-face` in `brand.css`; overrides Pico's `--pico-font-family`                                                      | Distinctive without CDN call; GDPR-clean for BE audience                                                                                              |
| A11y baseline             | WCAG 2.1 AA: `:focus-visible` ring, skip-link in public + org shells, semantic landmarks, `<label for>` always, `aria-describedby` for errors, contrast >= 4.5:1 in tokens                                                    | EU EAA in force 2025-06-28; cheaper to bake in now                                                                                                    |
| Live reload               | `django-browser-reload` in `dev.py` only                                                                                                                                                                                     | Enables CSS-without-bundler workflow                                                                                                                  |
| Template tests            | Pytest fixture renders one page per shell; asserts skip-link present, single `<main>`, correct `lang` attr, Pico + brand stylesheets included in correct order                                                                | Cheap structural guard; visual review stays human                                                                                                     |
| Browser support           | Latest 2 of Chrome, Edge, Firefox, Safari                                                                                                                                                                                    | No legacy POS hardware constraint yet                                                                                                                 |
| Pico starting flavor      | `pico.min.css` (default) + brand overrides; no bundled color variant                                                                                                                                                         | Maximum control over palette via `brand.css`                                                                                                          |
| Dark mode                 | Tokens / `[data-theme=dark]` ready; no toggle UI at launch                                                                                                                                                                   | Defer UI work; CSS plumbing is free                                                                                                                   |

Library choices locked: skip Tailwind, Alpine, Node toolchain, `django-crispy-forms`, `django-cotton`, Google Fonts CDN, `django-htmx-modal` (Pico styles `<dialog>`). Add `django-browser-reload` (dev dep group only). Vendor Pico CSS v2, HTMX, and Inter (not Python deps; self-hosted under `static/`). Template partials use Django 6.0's built-in tags - no `django-template-partials` package needed.

## 2. Layout shells & shared partials

All shells extend `templates/_base.html`, which owns `<head>` (lang attribute via `{% get_current_language %}`, viewport, CSS link tags in order: `pico.min.css` then `brand.css`, self-hosted HTMX from `/static/js/htmx.min.js`), and exposes blocks `title`, `extra_head`, `body_class`, `content`.

`base_public.html` - centered single-column shell for `/`, `/signup/`, `/login/`, `/verify/...`, `/password/reset/...`. No nav. Skip-link to `<main>`. Used by 2b.

`base_picker.html` - shell for `/orgs/` (org picker after multi-org login). Top-bar with brand + user menu only, no left rail. Used by 2b.

`base_org.html` - tenant-scoped shell for `/o/<slug>/...`. Top-bar with org name, language menu, user menu, org switcher (when multi-org). Left rail visible only when `body_class` includes `with-rail` (used by `/settings/*` screens in 2c). Skip-link to `<main>`. Used by 2c.

Partials inventory under `templates/_partials/`:

- `nav_top.html` - brand + org name + lang switcher + user menu.
- `user_menu.html` - signed-in user dropdown (name, profile link, logout form).
- `lang_switcher.html` - language form posting to Django's `/i18n/setlang/`.
- `flash.html` - Django messages, swappable via HTMX (`#flash` target, `outerHTML`).
- `modal.html` - native `<dialog>`; open/close via HTMX swap of dialog body, `dialog.showModal()` triggered by `HX-Trigger: modal:open`.
- `icon.html` - the SVG `<use>` snippet rendered by the `{% icon %}` tag.

Form partials under `templates/forms/`:

- `_field.html` - one `<label for>` + control + `<small>` hint + error helper text with `aria-invalid` on the control when invalid.
- `_errors.html` - non-field errors block at top of form.
- `_submit.html` - primary `<button type=submit>` + optional secondary action.

## 3. i18n in templates

- `{% load i18n %}` at the top of every template that surfaces user-facing strings. `{% trans %}` for one-liners, `{% blocktrans trimmed %}` for multi-word with placeholders.
- `_partials/lang_switcher.html` posts to Django's `/i18n/setlang/`; visible only when `request.user.is_anonymous` or has no `preferred_language` set (signed-in users with a stored preference are not nagged).
- Locale regen: `python manage.py makemessages -l nl_BE -i 'venv/*' -i 'node_modules/*'` per locale; `python manage.py compilemessages` before image build (already in epic 1's implementation order).
- Email language rule (epic 1 §6) re-stated and centralized: recipient's `preferred_language` wins over org default. Implementation lands in 2b (`core/services/mail.py`).

## 4. Out of scope (deliberately deferred)

- **Dark mode toggle UX**: tokens / Pico's `[data-theme=dark]` ready, but UI toggle deferred to a later UX slice.
- **POS-specific touch components**: own epic; chromeless full-bleed shell, large hit targets, gesture handling not in 2a.
- **Receipt print stylesheets**: deferred to first POS slice.
- **Storybook-equivalent component browser**: kitchen-sink page (`/__design__/`, DEBUG-only) is the v1 substitute.
- **Email HTML templates**: lives in 2b.
- **Automated visual regression**: structural snapshot tests only in v1.

## Implementation order

- [x] `pyproject.toml`: add `django-browser-reload` (dev dep group). Template partials are built into Django 6.0 - no extra package.
- [x] `config/settings/dev.py`: append `django_browser_reload.middleware.BrowserReloadMiddleware`; add `django_browser_reload` to `INSTALLED_APPS`; include `django_browser_reload.urls` under `__reload__/` in `config/urls.py`, gated by `settings.DEBUG`.
- [x] Vendor Pico CSS v2.1.1: `static/css/pico.min.css` is byte-identical to the upstream release (upstream's own header comment names the version).
- [x] Author `static/css/brand.css`: override `--pico-*` palette (brand teal `#0d6e63`, AA-pass 6.1:1 vs white), radii, font-family; declare `@font-face` for self-hosted Inter; `[data-theme=dark]` token block; focus ring; skip-link styling; icon defaults.
- [x] Self-host Inter v4.1: `static/fonts/inter-regular.woff2` (400), `inter-semibold.woff2` (600) from rsms.me/inter (OFL).
- [x] Self-host HTMX 2.0.4: `static/js/htmx.min.js` (file vendored; `<script>` `src` swap lands when `_base.html` is built).
- [x] SVG sprite: `static/icons/sprite.svg` seeded with the 25 Lucide v0.265.0 icons (menu, x, plus, edit, trash, check, alert, chevron-down, search, user, building, map-pin, settings, log-out, eye, eye-off, mail, lock, calendar, copy, refresh, more-vertical, arrow-left, arrow-right, info). Note: "edit" sourced from Lucide `pencil.svg` (no `edit.svg` in this release).
- [x] `core/templatetags/__init__.py` (empty), `core/templatetags/icons.py` (`{% icon "name" [class] %}` - renders `_partials/icon.html`).
- [ ] `core/templatetags/forms.py` (`{% field form.x [hint] %}`).
- [ ] `templates/_base.html`, `templates/base_public.html`, `templates/base_picker.html`, `templates/base_org.html`. Replace the old 12-line `templates/base.html` (delete it). Wire `<script src="{% static 'js/htmx.min.js' %}">` here.
- [x] Partials: `_partials/icon.html`. Remaining: `_partials/{nav_top,user_menu,lang_switcher,flash,modal}.html`.
- [ ] Form partials: `forms/{_field,_errors,_submit}.html`.
- [ ] `core/views/__init__.py:design_kitchen_sink` (DEBUG-only); URL `path("__design__/", views.design_kitchen_sink, name="design_kitchen_sink")`. Renders every component state on one page (buttons, forms in valid/invalid/disabled state, tables, dialogs, toasts, empty states).
- [ ] `tests/test_design_shells.py`: render each shell with a stub view; assert `lang="en-US"`, single `<main>`, skip-link present (public + org shells), Pico + brand stylesheets included in correct order.
