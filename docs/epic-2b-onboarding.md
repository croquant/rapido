# EPIC #2b - Onboarding (signup, email verify, password reset)

Public signup -> email verification -> auto-login flow that activates both `User.is_active` and `Organization.is_active` (epic 1 §5). Wires `django-anymail`. Adds password reset and the login redirect chain (single-org shortcut, multi-org picker).

## 1. Architecture decisions

| Decision                     | Choice                                                                                                                                                                                                                                                  | Why                                                                                                                                                  |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------- |
| Verification & reset tokens  | `django.core.signing.dumps` per epic 1 §5; salts `verify-email` (max_age 7d), `password-reset` (max_age 1h)                                                                                                                                              | Zero schema, no expiry sweeper, matches epic 1 lock                                                                                                  |
| Email backend                | `django-anymail` added; `EMAIL_BACKEND` env-controlled. Dev = console. Prod default = SES (eu-west-1)                                                                                                                                                    | Anymail decouples provider; SES cheap at SMB scale, BE-OK                                                                                            |
| Email rendering              | `templates/email/<flow>.txt` + `.html`, both via Django templates. All extend `templates/email/_base.{txt,html}`                                                                                                                                          | No MJML, no extra dep; one base partial                                                                                                              |
| Email language               | `core/services/mail.py:send_templated(template_base, *, to, language=None, context)` switches active translation to recipient's `preferred_language` via `translation.override`                                                                          | Single place enforces epic 1 §6 rule (recipient pref wins over org default)                                                                          |
| Signup form fields           | email, password, org name, org slug, **VAT number, country (BE default), default_language (browser-preselected)**                                                                                                                                       | `Organization.vat_number` is required (epic 1 §2); preselect saves a wizard step; `billing_email` defaults to signup email                          |
| Auth routes                  | `/signup/`, `/login/`, `/logout/`, `/verify/<token>/`, `/password/reset/`, `/password/reset/<token>/`, `/orgs/` (picker)                                                                                                                                  | All anonymous-accessible; none under `/o/<slug>/` per epic 1 §5 ("login leaks no org")                                                              |
| Login redirect               | Single active membership -> `/o/<slug>/`. Multi -> `/orgs/`. OPERATOR with single LocationMembership -> `/o/<slug>/l/<lslug>/pos/` (route reserved; 404 until POS epic)                                                                                  | Locks epic 1 §5 redirect rule end-to-end now                                                                                                         |
| Activation atomicity         | Verify endpoint: `transaction.atomic()` + `select_for_update` on `User`, flips `User.is_active`, finds the user's first active ADMIN membership, flips `Organization.is_active`. Idempotent on second click                                              | Both flags must flip together (epic 1 §5); idempotency is a UX must                                                                                  |
| Auto-login after verify      | `django.contrib.auth.login()` only after activation succeeds, then redirect via login redirect rule                                                                                                                                                      | Lower friction; safe (we just verified the email)                                                                                                    |
| First-run experience         | No wizard. Auto-login lands the admin in the dashboard with empty-state CTAs ("Create your first location")                                                                                                                                              | Wizards age badly; empty-state CTAs link into 2c                                                                                                     |
| VAT validation               | Re-run `validate_vat` on the signup form (already on `Organization.clean()`); no live VIES lookup at signup                                                                                                                                              | Synchronous + offline-tolerant; live VIES = later "Verify" button on org settings                                                                    |
| Throttling                   | Defer (epic 1 §7 already deferred per-IP rate-limiting)                                                                                                                                                                                                  | Honor the deferral; single-use verify token is enough for v1                                                                                         |
| Email HTML version           | Ship both text and HTML on day one                                                                                                                                                                                                                       | Forces the email template plumbing now; cheaper than retrofitting                                                                                    |

Library choices locked: add `django-anymail`. Skip `django-allauth`, `django-otp`, `django-axes`, captcha (each is a later epic).

## 2. Entities

No new entities. Verification and password-reset use `django.core.signing` per epic 1 §5 - no DB row.

**Deviation flagged forward**: 2c introduces a persistent `Invitation` model (rationale lives in 2c §1). 2b stays signed-token-only because verify and reset are user-driven, one-off, and need no admin observability.

## 3. Constraints & invariants (deltas)

Service-layer (in `core/services/activation.py` and `core/services/mail.py`):

- **Single-use verify**: endpoint rejects with a friendly "already verified" page if `user.is_active` is already true (raises `AlreadyActiveError`).
- **Token salts unique per flow**: `verify-email`, `password-reset`, `invite` (latter from 2c). Prevents cross-flow reuse.
- **Atomic activation**: `User.is_active` and `Organization.is_active` flip in the same `transaction.atomic()`; the org `select_for_update`'d via the user's first active ADMIN membership.
- **Email send on commit**: `transaction.on_commit(lambda: send_templated(...))` so a rolled-back signup never leaks an email.
- **Never auto-login an unverified user**: login view rejects when `user.is_active=False` with a "check your inbox" message + resend link (resend re-issues a verify token; idempotent).

## 4. Auth flows

### Public signup

1. `GET /signup/` renders `SignupForm` (extends `base_public.html`). Fields: email, password (Django validators), org name, org slug, VAT number, country (default BE), default language (preselected from `Accept-Language`).
2. `POST /signup/`: form-level `clean()` runs `validate_vat(vat_number, country)`. On success, `core/services/signup.py:create_organization_with_admin(...)` wraps in `transaction.atomic()`: creates `Organization(is_active=False, default_language=lang, ...)`, `User(is_active=False, preferred_language=lang)`, `OrganizationMembership(role=ADMIN, is_active=True, created_by=None)`.
3. `transaction.on_commit(...)` enqueues `send_templated("email/verify", to=user, context={"verify_url": ...})`. Token = `signing.dumps({"user_id": user.pk}, salt="verify-email")`.
4. Redirect to `/signup/done/` ("check your inbox" page; no link to login).

### Email verification

1. `GET /verify/<token>/` calls `activate_from_token(token)`:
   - `signing.loads(token, max_age=7*24*3600, salt="verify-email")` -> `{"user_id": ...}`. `BadSignature` / `SignatureExpired` -> `verify_failed.html`.
   - `transaction.atomic()` + `select_for_update`: set `User.is_active=True`, find first `OrganizationMembership(user, role=ADMIN, is_active=True)`, set `Organization.is_active=True`. If user is already active, raise `AlreadyActiveError` -> idempotent "already verified" page.
2. `auth.login(request, user)`; redirect via login redirect rule (single membership -> `/o/<slug>/`).

### Password reset

1. `GET /password/reset/`: `PasswordResetRequestForm` (email).
2. `POST /password/reset/`: look up user by `LOWER(email)`. If found and active, `send_templated("email/password_reset", to=user, context={"reset_url": ...})` with token `signing.dumps({"user_id": ...}, salt="password-reset")`. Always render a generic "if the email exists, you'll get a link" page (no enumeration).
3. `GET /password/reset/<token>/`: validate (max_age 1h, salt `password-reset`); render `PasswordResetConfirmForm`. `POST` sets new password, logs the user in, redirects via login redirect rule.

### Day-to-day login

Per epic 1 §5: `/login/` (no slug). Email + password. `LoginForm.clean()` rejects inactive users with the "check your inbox" message. Post-login: single active membership -> `/o/<slug>/`. Multi -> `/orgs/`. OPERATOR with a single `LocationMembership` -> `/o/<slug>/l/<lslug>/pos/` (route reserved; 404 until POS epic).

**Deviations from earlier spec**: epic 1 §5 listed signup fields as email + password + org name + slug. 2b adds VAT + country + default_language because (a) `Organization.vat_number` is required at the model level so postponing means a half-baked org row, (b) preselecting language saves a wizard step the empty-state dashboard cannot capture, (c) country is BE default but explicit so future BE-NL-LU rollouts do not need a migration.

## 5. i18n

- Browser `Accept-Language` -> signup form preselect (default language `<select>`); persisted on `Organization.default_language` and seeded onto `User.preferred_language`.
- Email body in recipient's `preferred_language` via `translation.override` in `send_templated`.
- Locale fallback chain: `User.preferred_language` -> `Organization.default_language` -> `LANGUAGE_CODE` (`en-US`).

## 6. Out of scope (deliberately deferred)

- **Social login / SSO**: no `django-allauth`.
- **MFA / TOTP**.
- **CAPTCHA / per-IP signup throttling** (epic 1 §7).
- **Slug-squatting TTL on unverified orgs** (epic 1 §7).
- **Live VIES VAT lookup**: lands as a 2c (or later) "Verify" button on org settings.
- **Marketing site / landing page**: `/signup/` reachable from a thin `/` view (`base_public.html` with a hero block).
- **Account deletion / GDPR scrub UI** (epic 1 §7).

## Implementation order

- [ ] `pyproject.toml`: add `django-anymail`.
- [ ] `config/settings/base.py`: `EMAIL_BACKEND=env('EMAIL_BACKEND', default='django.core.mail.backends.console.EmailBackend')`, `ANYMAIL` block, `DEFAULT_FROM_EMAIL`, `LOGIN_URL='/login/'`, `LOGIN_REDIRECT_URL='/orgs/'`, `LOGOUT_REDIRECT_URL='/'`. Stub SES env vars in `prod.py`.
- [ ] `core/services/tokens.py`: `make_token(user, salt)`, `verify_token(token, salt, max_age)`. Centralizes salts (`VERIFY_SALT`, `RESET_SALT`, `INVITE_SALT`) and max_ages.
- [ ] `core/services/mail.py`: `send_templated(template_base, *, to, language=None, context)` -> renders `<base>.txt` and optional `<base>.html` under `translation.override(language or to.preferred_language or settings.LANGUAGE_CODE)`.
- [ ] Extend `core/services/signup.py:create_organization_with_admin` to accept `default_language`; replace the inline email send with `transaction.on_commit(...)`.
- [ ] `core/services/activation.py:activate_from_token(token) -> User`; raises `BadSignature`, `SignatureExpired`, `AlreadyActiveError`.
- [ ] Refactor `core/views.py` -> `core/views/` package; add `core/views/auth.py` with `signup`, `signup_done`, `verify`, `verify_failed`, `verify_already`, `login`, `logout`, `password_reset_request`, `password_reset_sent`, `password_reset_confirm`, `password_reset_done`, `org_picker`.
- [ ] `core/forms/__init__.py`, `core/forms/signup.py:SignupForm`, `core/forms/auth.py:LoginForm, PasswordResetRequestForm, PasswordResetConfirmForm`.
- [ ] Templates under `templates/auth/`: `signup.html`, `signup_done.html`, `verify_done.html`, `verify_failed.html`, `verify_already.html`, `login.html`, `password_reset_request.html`, `password_reset_sent.html`, `password_reset_confirm.html`, `password_reset_done.html`, `org_picker.html`.
- [ ] Email templates: `templates/email/_base.txt`, `_base.html`, `verify.txt`, `verify.html`, `password_reset.txt`, `password_reset.html`.
- [ ] `core/urls.py`: register all auth routes; thin `/` view at `core/views/__init__.py:home`.
- [ ] Tests: `tests/test_auth_signup.py`, `test_auth_verify.py`, `test_auth_password_reset.py`, `test_auth_login_redirect.py`, `test_email_language.py`, `test_services_activation.py`.
