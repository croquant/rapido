# Translations

Source language is English (`en-US`). Translations live in per-locale `.po` files
generated from `gettext_lazy`-marked strings.

## Locale resolution precedence

`core.i18n.resolve_locale(user, org)` returns the first non-empty value of:

1. `User.preferred_language` (per-user override; empty = no preference)
2. `Organization.default_language` (per-tenant default)
3. `settings.LANGUAGE_CODE` (system default, currently `en-US`)

`LocaleMiddleware` is also enabled for anonymous flows (e.g. honors
`Accept-Language` on public pages). Email sends will use the recipient's
`preferred_language` (see EPIC #2), not the active request language.

## Regenerating message catalogs

```sh
uv run python manage.py makemessages -l nl_BE
uv run python manage.py makemessages -l fr_BE
uv run python manage.py makemessages -l de_DE
uv run python manage.py compilemessages
```

Supported locales: `en_US`, `nl_BE`, `fr_BE`, `de_DE`.
