# EPIC #1 - Rapido foundation models

Multi-tenant POS for Belgian restaurants (frituur, brasserie, etc.). This doc specifies the foundation entities (Organization, Location, User, OrganizationMembership, LocationMembership) at field level so the initial migration is unambiguous.

## 1. Architecture decisions

| Decision          | Choice                                                                                              | Why                                                                                     |
| ----------------- | --------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Database          | Postgres in prod, SQLite dev/tests only                                                             | Concurrent POS writes, real `CHECK` constraints, `SELECT FOR UPDATE`                    |
| Multi-tenancy     | Shared DB, shared schema, FK-scoped (row-level), hand-rolled                                        | Simple ops, fits SMB scale, cross-tenant analytics trivial                              |
| Custom user model | `core.User`, set before first migration                                                             | `AUTH_USER_MODEL` is near-impossible to swap later                                      |
| Login field       | `email` (unique globally), no `username`                                                            | Simpler login UX                                                                        |
| Org membership    | `OrganizationMembership(user, organization, role)` from day 1                                       | Cross-org users (bookkeepers, multi-brand owners) common in BE                          |
| Platform staff    | Django `is_superuser` + zero memberships                                                            | No `SUPER_ADMIN` tenant role; don't conflate platform staff with tenant users           |
| ID strategy       | `BigAutoField` PK + `public_id` (UUIDv7) on Org / Location / User                                   | Fast PKs, time-ordered opaque external IDs, good index locality                         |
| Tenant routing    | Path-based `/o/<org-slug>/...`, login at `/login/` (no slug)                                        | One cert, one cookie domain; login page doesn't leak org existence                      |
| Audit             | Abstract `TimestampedModel` (`created_at`, `updated_at`)                                            | Universal need, no per-model boilerplate                                                |
| Soft delete       | `is_active` flag on Org / User / Location; true soft-delete only on transactional records (later)   | Avoids deletion footguns without query complexity                                       |
| FK delete policy  | `PROTECT` at tenant boundary, `CASCADE` intra-tenant                                                | Tenant purge = delete locations, then org; one purge function, stable as schema grows   |
| i18n              | Machinery day 1, translations as we go; locales `en-US`, `nl-BE`, `fr-BE`, `de-DE`; source = English | Multi-language BE market                                                                |

Library choices locked: skip `django-tenants` (using hand-rolled), `django-organizations` (M2M shape too prescriptive), `django-allauth` (no social login yet), `django-rules` / `django-guardian` (no object-level perms yet). Keep `factory-boy` for fixtures.

## 2. Entities

**Status:** all foundation entities built — `TimestampedModel`, `Organization`, `User` (custom, email login), `Role` enum, `OrganizationMembership`, `Location`, `LocationMembership`, and the `uuid7()` callable.

**Naming deviation from earlier spec:** `Restaurant` -> `Location`, `RestaurantMembership` -> `LocationMembership`. Reasons: §2 already subtitled "Restaurant (Location)"; POS industry standard (Toast / Square / Lightspeed) is Location; future-proofs for ghost kitchens, food trucks, popups without another rename. Brand still says "restaurant" externally; the model name is internal.

### Organization (Tenant) — implemented

Top-level billing and management entity (e.g. "Frituur Janssens Group"). Has 1:N Locations and 1:N Memberships.

| Field                       | Type                                                    | Notes                                                                          |
| --------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `id`                        | `BigAutoField`                                          | PK                                                                             |
| `public_id`                 | `UUIDField(unique=True, default=uuid7, editable=False)` | External-facing ID                                                             |
| `name`                      | `CharField(max_length=120)`                             | Display name                                                                   |
| `slug`                      | `SlugField(unique=True)`                                | `[a-z0-9-]+`, regex-validated, immutable in v1                                 |
| `country`                   | `CountryField(default="BE")`                            | `django-countries`; `COUNTRIES_ONLY` = BE/NL/LU/DE/FR                          |
| `default_timezone`          | `TimeZoneField(default="Europe/Brussels")`              | `django-timezone-field`; IANA tz                                               |
| `default_currency`          | `CurrencyField(default="EUR")`                          | `django-money`; `choices` = EUR/USD/GBP/JPY                                    |
| `default_language`          | `CharField(default="en-US")`                            | `choices=settings.LANGUAGES` (en-US/nl-BE/fr-BE/de-DE)                         |
| `vat_number`                | `CharField(max_length=14)`                              | Required; validated via `python-stdnum` `eu_vat`; prefix must match `country`  |
| `billing_email`             | `EmailField(max_length=254)`                            |                                                                                |
| `is_active`                 | `BooleanField(default=False)`                           | Activated after email verification                                             |
| `created_at` / `updated_at` | (via `TimestampedModel`)                                |                                                                                |

Deviations from earlier spec: field renamed `default_locale` -> `default_language`; default is `en-US` not `nl-BE`; `vat_number` is required (validator rejects blank). `clean()` re-runs VAT validation against `country`.

### Location (storefront) — implemented

A physical storefront. Belongs to exactly one Organization.

| Field                          | Type                                                    | Notes                                                            |
| ------------------------------ | ------------------------------------------------------- | ---------------------------------------------------------------- |
| `id`                           | `BigAutoField`                                          | PK                                                               |
| `public_id`                    | `UUIDField(unique=True, default=uuid7, editable=False)` | External-facing ID                                               |
| `organization`                 | `FK(Organization, on_delete=PROTECT)`                   | `related_name='locations'`                                       |
| `name`                         | `CharField(max_length=120)`                             |                                                                  |
| `slug`                         | `SlugField(validators=[validate_slug])`                 | Unique within org (constraint, not field-level)                  |
| `street`                       | `CharField(max_length=200)`                             | Required                                                         |
| `postal_code`                  | `CharField(max_length=16)`                              | Required                                                         |
| `city`                         | `CharField(max_length=120)`                             | Required                                                         |
| `phone`                        | `CharField(max_length=32, blank=True)`                  | Optional                                                         |
| `is_active`                    | `BooleanField(default=True)`                            |                                                                  |
| `created_at` / `updated_at`    | (via `TimestampedModel`)                                |                                                                  |

Constraint: `UniqueConstraint(fields=["organization","slug"], name="location_org_slug_unique")`. Opening hours = separate model (deferred). No timezone/currency override fields in v1; org defaults are the single source of truth.

Deviations from earlier spec: model renamed `Restaurant` -> `Location` (see §2 status note). `country` removed; derived from `organization.country` under the invariant "all locations of an org share its country" — re-add when the first cross-region org appears, paralleling §7's tz/currency deferral. `validate_org_slug` renamed to `validate_slug` (regex is generic).

### User (Account) — implemented

A person logging into the system. Identity only - tenant access lives on `Membership`. Inherits from `AbstractBaseUser + PermissionsMixin + TimestampedModel`.

| Field                        | Type                                                              | Notes                                                |
| ---------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------- |
| `id`                         | `BigAutoField`                                                    | PK                                                   |
| `public_id`                  | `UUIDField(unique=True, default=uuid7, editable=False)`           | External-facing ID                                   |
| `email`                      | `EmailField(unique=True)`                                         | Login. `USERNAME_FIELD = EMAIL_FIELD = "email"`      |
| `password`                   | (Django hash via `AbstractBaseUser`)                              |                                                      |
| `first_name`, `last_name`    | `CharField(max_length=150, blank=True)`                           |                                                      |
| `preferred_language`         | `CharField(max_length=8, choices=settings.LANGUAGES, blank=True)` | Empty string falls back to org default               |
| `is_active`                  | `BooleanField(default=True)`                                      |                                                      |
| `is_staff`                   | `BooleanField(default=False)`                                     | Django admin access                                  |
| `is_superuser`               | (via `PermissionsMixin`)                                          | Platform staff                                       |
| `groups`, `user_permissions` | (via `PermissionsMixin`)                                          | Reserved; not used in v1                             |
| `last_login`                 | (via `AbstractBaseUser`)                                          |                                                      |
| `created_at` / `updated_at`  | (via `TimestampedModel`)                                          | `created_at` doubles as join date                    |

Constraint: `UniqueConstraint(Lower("email"), name="user_email_ci_unique")` — case-insensitive email uniqueness in addition to `unique=True`. `UserManager.create_user` lowercases the email on save; `create_superuser` enforces `is_staff=True` and `is_superuser=True`. `REQUIRED_FIELDS = []` so `createsuperuser` prompts only for email + password.

Deviations from earlier spec: field renamed `preferred_locale` -> `preferred_language` (consistency with `Organization.default_language`); no separate `date_joined` (`created_at` from `TimestampedModel` is the join date); `preferred_language` is `blank=True` only — empty string is the "no preference" sentinel (Django convention for `CharField`); added case-insensitive uniqueness on `email`.

No `username` field. No `organization` FK, no `role` - both live on `OrganizationMembership`. OPERATOR users (POS staff) log in via the same `/login/` form as ADMIN.

### OrganizationMembership — implemented

A user's role within one organization. A user may hold memberships in multiple orgs. Inherits `TimestampedModel`.

| Field                       | Type                                                                  | Notes                |
| --------------------------- | --------------------------------------------------------------------- | -------------------- |
| `id`                        | `BigAutoField`                                                        | PK                   |
| `user`                      | `FK(User, on_delete=CASCADE, related_name='organization_memberships')`|                      |
| `organization`              | `FK(Organization, on_delete=PROTECT, related_name='organization_memberships')` |             |
| `role`                      | `CharField(max_length=16, choices=Role.choices)`                      | `ADMIN` / `OPERATOR` |
| `is_active`                 | `BooleanField(default=True)`                                          |                      |
| `created_by`                | `FK(User, related_name='+', on_delete=PROTECT, null=True, blank=True)`| Null for self-signup |
| `created_at` / `updated_at` | (via `TimestampedModel`)                                              |                      |

Constraint: `UniqueConstraint(fields=["user","organization"], name="orgmembership_user_org_unique")`.

Deviations from earlier spec: model renamed `Membership` -> `OrganizationMembership` (symmetry with `LocationMembership`, avoids ambiguous bare identifier); inherits `TimestampedModel` (gains `updated_at` for free, consistent with `Organization`/`User`); no `public_id` (intra-tenant join row).

`Role` is a `TextChoices` enum: `ADMIN`, `OPERATOR`.

### LocationMembership — implemented

Per-location scoping for OPERATOR users. Inherits `TimestampedModel`.

| Field                       | Type                                                                | Notes                                                             |
| --------------------------- | ------------------------------------------------------------------- | ----------------------------------------------------------------- |
| `id`                        | `BigAutoField`                                                      | PK                                                                |
| `user`                      | `FK(User, on_delete=CASCADE, related_name='location_memberships')`  |                                                                   |
| `location`                  | `FK(Location, on_delete=CASCADE, related_name='location_memberships')` |                                                                |
| `pin`                       | `CharField(max_length=128, blank=True)`                             | Hashed 4-6 digit; reserved for future PIN-switch on shared kiosks |
| `is_active`                 | `BooleanField(default=True)`                                        |                                                                   |
| `created_by`                | `FK(User, related_name='+', on_delete=PROTECT, null=True, blank=True)` | Who granted access; null for system-generated rows             |
| `created_at` / `updated_at` | (via `TimestampedModel`)                                            |                                                                   |

Constraint: `UniqueConstraint(fields=["user","location"], name="locmembership_user_location_unique")`. Validation: only users with an OPERATOR `OrganizationMembership` in the location's org may have `LocationMembership` rows; ADMIN has implicit access to all locations in their org. Cross-org validation is service-layer (see §3).

Deviations from earlier spec: model renamed `RestaurantMembership` -> `LocationMembership`; gained `updated_at` via `TimestampedModel`; `created_by` now nullable (matches `OrganizationMembership.created_by`).

## 3. Constraints & invariants

DB-enforced:

- `User`: case-insensitive unique `email` via `UniqueConstraint(Lower("email"))` (in addition to the field-level `unique=True`).
- `Location`: unique `(organization, slug)` (`location_org_slug_unique`).
- `OrganizationMembership`: unique `(user, organization)` (`orgmembership_user_org_unique`).
- `LocationMembership`: unique `(user, location)` (`locmembership_user_location_unique`).
- FKs crossing the tenant boundary (anything pointing at `Organization`, plus `Location.organization`) use `on_delete=PROTECT`. Intra-tenant FKs (e.g. future `Order.location`, `LocationMembership.location`) use `CASCADE`. Tenant purge = `org.locations.all().delete()` then `org.delete()` in a transaction.

Service-layer (lives in `core/services/`):

- Every active Organization must have at least one active `OrganizationMembership` with `role=ADMIN` whose `user.is_active=True`. Block any transition that would violate it (deactivate membership, deactivate user, change role, delete row).
- OPERATOR with zero active `LocationMembership` rows is allowed (suspended) but cannot enter any location view.
- A `LocationMembership` may only exist for a user whose org membership in `location.organization` has `role=OPERATOR` and `is_active=True`.
- Org signup creates `Organization` + `User` + ADMIN `OrganizationMembership` inside a single `transaction.atomic()`.
- All membership / user state transitions go through service functions, not raw `.save()`. Direct ORM writes bypass invariants.

## 4. Roles & permissions

MODIFY = CRUD on settings, menus, staff. OPERATE = daily tasks (orders, register, tickets).

| Role                                  | Scope                | MODIFY         | OPERATE                                      |
| ------------------------------------- | -------------------- | -------------- | -------------------------------------------- |
| Platform staff (`is_superuser`)       | System-wide          | Any org        | Any location                                 |
| ADMIN (`OrganizationMembership`)      | The membership's org | Yes (org-wide) | Yes (any location in org)                    |
| OPERATOR (`OrganizationMembership`)   | Assigned locations   | No             | Yes (only their `LocationMembership` rows)   |

Role storage = single `role` enum on `OrganizationMembership`. Django `Groups` are reserved for finer-grained grants later (not used in v1).

### Enforcement (defense in depth)

1. **Tenant middleware**: parses `/o/<slug>/` from the URL, resolves `request.organization`. Verifies an `OrganizationMembership` exists for `(request.user, request.organization)`, or `request.user.is_superuser`. Returns 404 on mismatch (not 403, to avoid leaking org existence).
2. **Manager**: `TenantOwnedManager` exposes `for_organization(org)` (primitive, used by tasks / management commands / tests / admin) and `for_request(request)` (thin wrapper, used by views). Default `.objects` stays unscoped (Django convention). CI lint blocks raw `.objects.(all|filter|get)` in viewsets.
3. **DRF permission classes**: `IsOrgAdmin`, `IsLocationOperator`. Every viewset re-filters in `get_queryset`.

Platform-staff elevation: same path-based URL `/o/<slug>/...`; middleware bypass keyed on `is_superuser`. No impersonation feature in v1.

## 5. Auth flows

### Org signup

1. Anonymous form: email, password, org name, org slug.
2. `transaction.atomic()`:
   - Create `Organization(slug, name, is_active=False)`.
   - Create `User(email, is_active=False)`.
   - Create `OrganizationMembership(user, organization=org, role=ADMIN, is_active=True)`.
3. Email verification link sent (`signing.dumps({"user_id": ...}, salt="verify-email")`). Click activates `User.is_active` and `Organization.is_active`.

### Staff invitation

1. ADMIN form: email, role (ADMIN or OPERATOR), locations (if OPERATOR).
2. Server creates `User(email, is_active=False)`, `OrganizationMembership(user, org, role)`, and `LocationMembership` rows for each selected location.
3. Token signed via `django.core.signing.dumps({"user_id": ...}, salt="invite")`. Verified with `loads(token, max_age=7*24*3600)`. No `exp` in payload.
4. Invitee follows link, sets password, account becomes `is_active=True`. Activation endpoint rejects if `user.is_active` is already true (single-use).
5. Revocation: delete the unverified `User` row (cascades the pending memberships).
6. No `django-allauth`.

### Password reset

Same shape as invite, `salt="password-reset"`. Different salt prevents token reuse across flows.

### Day-to-day login (incl. POS)

- `/login/` (no slug, no org leak). Email + password (same form for ADMIN and OPERATOR).
- DRF `SessionAuthentication` is sufficient for v1. Per-device tokens + PIN-switch revisited when offline-first POS lands; `LocationMembership.pin` is reserved for that.
- Post-login redirect: single membership -> `/o/<slug>/`; multi -> org picker. OPERATOR with a single `LocationMembership` -> `/o/<slug>/l/<lslug>/pos/`.

## 6. i18n

- Machinery in place day 1: `LocaleMiddleware` wired, `USE_I18N=True`, `LOCALE_PATHS=[BASE_DIR/'locale']`, `gettext_lazy` used on Organization field labels, locale folders scaffolded for `nl_BE`, `fr_BE`, `de_DE` (no .po content yet).
- Locales: `en-US`, `nl-BE`, `fr-BE`, `de-DE`. Source language = English (Django convention); `LANGUAGE_CODE = "en-US"`.
- Org default on `Organization.default_language` (default `en-US`). User override on `User.preferred_language` (`blank=True`; empty string falls back to org default). Email language will use the recipient's `preferred_language`, not the org default.
- Translations populate over time; missing strings fall back to English.

## 7. Out of scope (deliberately deferred)

- **GDPR right-to-erasure scrub**: pre-launch checklist item. User scrub will set `email='deleted+<id>@invalid'`, null PII fields, mark `is_active=False`, password unusable, add `scrubbed_at`. Row stays for FK integrity. Build before first real customer.
- **Slug squatting mitigation**: TTL on unverified orgs + signup rate-limit per IP. Add when adversarial signups appear.
- **BE GKS / FDM (fiscal blackbox)**: mandatory once a location passes EUR 25k/yr food revenue. Out of scope for this doc; will get its own design.
- **Location-level country / timezone / currency overrides**: re-add when the first cross-region org appears.
- **Offline-first POS**: avoid hard "must-be-online" assumptions in critical write paths.
- **Subscription / Plan**: re-open when a payment provider is chosen.

## Implementation order

- [x] `core/models.py`: `TimestampedModel` abstract base, UUIDv7 default callable. *(PR #19, issue #2)*
- [x] `core.User` (custom, no `organization`, no `role`) and `Organization`. `AUTH_USER_MODEL = "core.User"` set in `config/settings/base.py`. *Organization in issue #3; `User` + `UserManager` (`create_user` / `create_superuser`) + `AUTH_USER_MODEL` in issue #4.*
- [x] `makemigrations core`. *`0001_initial.py` covers `Organization` + `User` (with `Lower("email")` unique constraint, references `auth.0012` for `PermissionsMixin` M2Ms). `0002_organizationmembership.py` adds `OrganizationMembership` (issue #5). `0003_location_locationmembership.py` adds `Location` + `LocationMembership` (issues #6 / #7).*
- [x] Add `Role` enum, `OrganizationMembership`, `Location`, `LocationMembership`. *`Role` + `OrganizationMembership` done in issue #5. `Location` + `LocationMembership` done in issues #6 / #7 (rename: was `Restaurant` / `RestaurantMembership`).*
- [x] `core/services/membership.py`: `deactivate_membership`, `change_role`, `deactivate_user` (each enforces the "last active ADMIN" invariant). *Issues #11/#12/#13. Also adds `core/services/signup.py:create_organization_with_admin` (issue #14) and `core/services/exceptions.py:LastActiveAdminError`.*
- [x] `core/managers.py`: `TenantOwnedManager` with `for_organization` and `for_request`. *Issue #8; supports indirect lookup via `organization_lookup` (e.g. `"location__organization"`). CI lint in `scripts/tenant_lint.py` blocks raw `.objects.{all|filter|get}` in views/viewsets (issue #9).*
- [x] Tenant middleware: resolves `request.organization` from `/o/<slug>/`, checks `OrganizationMembership` or `is_superuser`. *Issue #10; 404 on mismatch (no org-existence leak).*
- [x] `config/settings/base.py`: `LANGUAGES`, `LocaleMiddleware`, `locale/` folder, `USE_I18N=True`.
- [x] Register all entities in `core/admin.py`. *`Organization`, `User`, `OrganizationMembership`, `Location`, `LocationMembership` registered. Issue #16 added `OrganizationMembership` / `LocationMembership` inlines on `Organization` / `Location`, fleshed out `OrganizationAdmin` (`list_display`, `readonly_fields`, fieldsets), and routed admin saves of `is_active` / `role` through `core/services/membership.py` so the "last active ADMIN" invariant is enforced for admin edits too.*
- [~] `factory-boy` factories; cover the three role scenarios in tests (platform-staff, ADMIN, OPERATOR with/without `LocationMembership`). *`UserFactory`, `OrganizationFactory`, `OrganizationMembershipFactory`, `LocationFactory`, `LocationMembershipFactory` in `tests/factories.py`. Role-scenario coverage pending.*
