# EPIC #2c - Locations & users management

Admin-facing UI under `/o/<slug>/` for locations, users, invitations, and org settings. Org switcher in the top-bar. Self-service profile at `/me/`. Replaces "Django admin only" with a real product surface.

## 1. Architecture decisions

| Decision                  | Choice                                                                                                                                                                                                                                                                                       | Why                                                                                                                                          |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- |
| Invitation persistence    | New persistent `Invitation` model (token still signed: `signing.dumps`, salt `invite`, `max_age=7d`)                                                                                                                                                                                          | Admin-driven flow needs pending-list, resend, revoke without phantom `User` rows; deviation from epic 1 §5 (called out in §2)               |
| Invitation lifecycle      | `pending` -> `accepted` (sets `accepted_at`) \| `revoked` (sets `revoked_at`) \| `expired` (computed from `expires_at`, never persisted as a status)                                                                                                                                          | Idempotent transitions; clear states; no cron                                                                                                |
| Accept semantics          | If a `User` exists for `LOWER(email) = invitation.email` (cross-org case), reuse it (no password prompt); else create `User` + force password set on accept page                                                                                                                              | Handles BE bookkeeper-with-multi-org case epic 1 already designed for                                                                        |
| Navigation IA             | Top-bar always; left rail only on `/settings/*`. Routes under `/o/<slug>/`: `/`, `/settings/locations/`, `/settings/members/`, `/settings/invitations/`, `/settings/organization/`. Profile at `/me/` (not tenant-scoped); accept at `/invite/<token>/` (anonymous-accessible)                | Flat IA at SMB scale; profile is identity, not tenant data                                                                                   |
| HTMX swap inventory       | Invite modal: `hx-post` -> `outerHTML` swap of pending-invites table partial + `HX-Trigger: invitations:created`. Role change `<select>`: `hx-post` -> row-partial swap; `LastActiveAdminError` returns 422 + row in error state. Deactivate: link -> modal partial -> confirm form -> row swap. Location create: full page (too many fields for modal). Org switcher: form GET to `/orgs/` (no HTMX, preserves URL) | Explicit list keeps the HTMX surface auditable                                                                                               |
| Service layer             | `core/services/invitation.py` (`create`, `accept`, `revoke`, `resend`); `core/services/profile.py` (`update_profile`, `change_password`)                                                                                                                                                      | Mirrors `signup.py` / `membership.py` pattern; views never call `.save()` for state transitions                                              |
| Active-ADMIN invariant    | Reuse `core/services/membership.py`; never reimplement                                                                                                                                                                                                                                       | Epic 1 §3; one source of truth                                                                                                               |
| Audit log                 | Defer. Sketch `AuditLog(actor, action, target_ct, target_id, payload_hash, created_at)` in §7                                                                                                                                                                                                | `created_by` + `created_at` suffice for v1                                                                                                   |
| Bulk actions              | Defer (CSV import, bulk PIN reset)                                                                                                                                                                                                                                                           | SMB scale; revisit on demand                                                                                                                  |
| LocationMembership editing| Both surfaces: member-detail (toggle locations) and location-detail (toggle operators)                                                                                                                                                                                                       | Minor extra template work; large UX win for ADMINs juggling staff across locations                                                           |

Library choices locked: nothing new beyond 2a/2b. Skip `django-import-export`, `django-tables2` (hand-rolled tables fit Pico).

## 2. Entities

### Invitation (new)

`core/models/invitation.py`. Tenant-scoped via `TenantOwnedManager`; intra-tenant CASCADE per epic 1 §3.

| Field                       | Type                                                                              | Notes                                                            |
| --------------------------- | --------------------------------------------------------------------------------- | ---------------------------------------------------------------- |
| `id`                        | `BigAutoField`                                                                    | PK                                                               |
| `public_id`                 | `UUIDField(unique=True, default=uuid7, editable=False)`                           | External-facing                                                  |
| `organization`              | `FK(Organization, on_delete=CASCADE, related_name='invitations')`                 | Intra-tenant CASCADE                                             |
| `email`                     | `EmailField(max_length=254)`                                                      | Lowercased on save                                                |
| `role`                      | `CharField(max_length=16, choices=Role.choices)`                                  | ADMIN or OPERATOR                                                 |
| `locations`                 | `ManyToManyField(Location, blank=True, related_name='invitations')`               | Required iff `role=OPERATOR` (service-enforced)                  |
| `created_by`                | `FK(User, on_delete=PROTECT, related_name='+')`                                   | Inviter                                                          |
| `expires_at`                | `DateTimeField`                                                                   | Default = `now + 7d`                                             |
| `accepted_at`               | `DateTimeField(null=True, blank=True)`                                            | Set on accept                                                    |
| `revoked_at`                | `DateTimeField(null=True, blank=True)`                                            | Set on revoke                                                    |
| `created_at` / `updated_at` | (via `TimestampedModel`)                                                          |                                                                  |

Constraint: `UniqueConstraint(fields=["organization", "email"], condition=Q(accepted_at__isnull=True, revoked_at__isnull=True), name="invitation_one_pending_per_email_per_org")`.

**Deviation from epic 1 §5**: epic 1 designed invitations as signed-token-only (no DB row). 2c persists invitations because admin-driven flows need (a) pending-list visibility, (b) resend without recreating users, (c) revoke without `User.delete()` cascade footguns, (d) audit trail for who invited whom. The signed-token approach scales for verify/reset (one-off, user-driven) but not for invites (admin-driven, observable).

## 3. Constraints & invariants (deltas)

DB-enforced:

- One pending invitation per `(organization, email)` (partial unique constraint above). Resend re-issues the token but does not create a new row; revoke + re-invite is the explicit dance for "I sent it to the wrong email".

Service-layer (in `core/services/invitation.py`):

- **No invite for existing active member**: `create_invitation` rejects if an active `OrganizationMembership` already exists for `(LOWER(email), organization)`. Raises `AlreadyMemberError`.
- **Locations required for OPERATOR**: `create_invitation(role=OPERATOR, locations=[])` raises `OperatorRequiresLocationsError`.
- **Accept revalidates state**: `accept_invitation(token, password=None)` re-runs role + locations validation against current org state (a location may have been deactivated since invite). Stale locations -> validation error with the bad locations listed.
- **Existing-user accept**: if `User.objects.filter(email__iexact=invitation.email).exists()`, reuse it (do not prompt for password; the user already has one). Else create `User(is_active=True, ...)` and require password on the accept page.
- **Idempotent terminal states**: accept on accepted -> `BadStateError("already_accepted")`. Revoke on accepted -> `BadStateError("already_accepted")`. Resend on revoked -> `BadStateError("revoked")`. Etc.
- **Active-ADMIN invariant**: re-uses existing `core/services/membership.py`. Reactivating a deactivated member is just `change_role` / `reactivate` flowing through the same guards.

## 4. Roles & permissions delta

| Role                              | Dashboard               | Locations          | Members  | Invitations | Org settings | Profile |
| --------------------------------- | ----------------------- | ------------------ | -------- | ----------- | ------------ | ------- |
| Platform staff (`is_superuser`)   | Any org                 | CRUD any           | CRUD any | CRUD any    | RW any       | Own     |
| ADMIN                             | Own org                 | CRUD               | CRUD     | CRUD        | RW           | Own     |
| OPERATOR                          | Redirect to POS landing | Read assigned only | None     | None        | None         | Own     |

Enforcement: every view double-filters via `tenant_objects.for_request(request)` + a new `permission_required(role)` decorator (`core/decorators.py`) that checks the membership role for `request.organization`. DRF perm classes from epic 1 §4 reserved for the API epic.

## 5. Flows

### Invite member

1. ADMIN clicks "Invite" on `/o/<slug>/settings/members/` -> HTMX swaps a `<dialog>` body with the `InvitationForm` partial; `dialog.showModal()` triggered via `HX-Trigger: modal:open`.
2. Form submit (`hx-post /o/<slug>/settings/invitations/`): `create_invitation(org, email, role, locations, created_by=user)`.
3. Service writes `Invitation(...)` and `transaction.on_commit(lambda: send_templated("email/invitation", ...))`. Token = `signing.dumps({"invitation_id": invitation.pk}, salt="invite")`.
4. Response: pending-invites table partial swapped via `outerHTML`; flash via `HX-Trigger: invitations:created`.

### Accept invitation

1. `GET /invite/<token>/`: `signing.loads(token, max_age=7*24*3600, salt="invite")` -> `{"invitation_id": ...}`. Lookup `Invitation`; reject if `accepted_at`, `revoked_at`, or `expires_at < now`.
2. If `User.objects.filter(email__iexact=invitation.email).exists()` -> render "Accept" page with no password field; POST creates `OrganizationMembership(user, org, role)` and `LocationMembership` rows for each `invitation.locations`, sets `accepted_at=now`. Atomic.
3. Else -> render "Set password" page; POST creates `User(email, password, is_active=True)`, then memberships, sets `accepted_at`. Atomic.
4. `auth.login(request, user)`; redirect via login redirect rule (epic 1 §5).

### Revoke / resend

- Revoke: ADMIN clicks "Revoke" -> confirm modal -> `hx-post /o/<slug>/settings/invitations/<pk>/revoke/`. Sets `revoked_at=now`. Idempotent on revoked. Row removed from pending table; moved to revoked archive (read-only).
- Resend: ADMIN clicks "Resend" -> `hx-post /o/<slug>/settings/invitations/<pk>/resend/`. Re-issues the token (same payload, fresh signature), bumps `expires_at` by 7d, fires email. Raises `BadStateError` on accepted/revoked.

### Role change

1. Members table row has a `<select>` for role (ADMIN / OPERATOR), with `hx-post /o/<slug>/settings/members/<pk>/role/`.
2. Service: `change_role(membership, role, by=request.user)` (existing service; epic 1 §3 invariant). Returns row partial.
3. On `LastActiveAdminError`: response 422 + row partial with the `<select>` reverted and an inline error toast (`HX-Trigger: members:role_change_failed`).

### Deactivate / reactivate user

1. Click "Deactivate" -> confirm modal -> `hx-post /o/<slug>/settings/members/<pk>/deactivate/`. Service `deactivate_membership(membership, by=request.user)`; honors invariant. Row swapped to "deactivated" state.
2. Reactivate: row "Reactivate" button -> `hx-post .../reactivate/`. Service flips `is_active=True`; no invariant needed (only growing the active set).

### Deactivate / reactivate location

Same shape as user, but no active-ADMIN invariant. Deactivating a location does not delete `LocationMembership` rows (they stay; the location is just hidden from operators). Reactivation restores visibility.

### Org switch

If `request.user.organization_memberships.filter(is_active=True, organization__is_active=True).count() > 1`, top-bar shows org-switcher dropdown. Selecting an org submits a `<form>` GET to `/orgs/?next=/o/<slug>/`. Single-org users see static org name (no dropdown).

### Profile (self-service)

- `GET /me/`: `ProfileForm` (first_name, last_name, preferred_language) + `ChangePasswordForm`.
- `POST /me/profile/`: `update_profile(user, ...)`. `POST /me/password/`: `change_password(user, current, new)`. Logs the user out of all other sessions on password change.

## 6. i18n

- Invitation email language: invitee's `preferred_language` if existing user; else org's `default_language`.
- All admin templates wrapped in `{% trans %}` / `{% blocktrans %}`.
- Locale fallback chain (epic 1 §6): user pref -> org default -> `LANGUAGE_CODE` (`en-US`).

## 7. Out of scope (deliberately deferred)

- **Bulk invite via CSV**.
- **Bulk PIN reset / PIN UX**: lives in POS epic.
- **`AuditLog` model and screen**: `created_by` + `created_at` suffice for v1. Sketch for later: `AuditLog(actor, action, target_ct, target_id, payload_hash, created_at)`.
- **Granular permissions / Django Groups customization**: reserved by epic 1 §4 ("Django `Groups` are reserved for finer-grained grants later").
- **Org-level notifications inbox**.
- **Email change with verification round-trip**: profile lets user change name + language + password only; email change deferred (needs verify + uniqueness handling).
- **`Organization.slug` rename UX**: stays immutable per epic 1 §2; revisit when slug squatting becomes a real concern.
- **Account deletion / GDPR scrub** (epic 1 §7).

## Implementation order

- [ ] `core/models/invitation.py` + register in `core/models/__init__.py`.
- [ ] `core/migrations/0004_invitation.py` with the partial unique constraint (`Q(accepted_at__isnull=True, revoked_at__isnull=True)`).
- [ ] `core/services/invitation.py`: `create_invitation`, `accept_invitation`, `revoke_invitation`, `resend_invitation`, exceptions (`AlreadyMemberError`, `OperatorRequiresLocationsError`, `BadStateError`).
- [ ] `core/services/profile.py`: `update_profile`, `change_password`.
- [ ] `core/decorators.py:permission_required(role: Role | None = None)` (membership-role based).
- [ ] `core/forms/invitation.py:InvitationForm`, `core/forms/location.py:LocationForm`, `core/forms/member.py:RoleChangeForm`, `core/forms/profile.py:ProfileForm, ChangePasswordForm`.
- [ ] `core/views/dashboard.py:dashboard`.
- [ ] `core/views/locations.py:list_view, create, edit, deactivate, reactivate`.
- [ ] `core/views/members.py:list_view, change_role, deactivate, reactivate`.
- [ ] `core/views/invitations.py:list_view, create, resend, revoke, accept`.
- [ ] `core/views/organization.py:settings_view, update`.
- [ ] `core/views/profile.py:me, change_password`.
- [ ] Templates: `templates/dashboard/index.html`; `templates/locations/{list,create,edit,row}.html`; `templates/members/{list,row}.html`; `templates/invitations/{list,form,row,accept_set_password,accept_existing}.html`; `templates/organization/settings.html`; `templates/profile/{me,password}.html`. List pages expose table partials via `django-template-partials` for HTMX swaps.
- [ ] Email templates: `templates/email/invitation.{txt,html}`, optional `templates/email/invitation_revoked.txt`.
- [ ] URL wiring in `core/urls.py` (org-scoped under `/o/<slug>/...`); top-level `/me/` and `/invite/<token>/` includes outside `/o/<slug>/`.
- [ ] Tests: `tests/test_invitation_model.py`, `test_services_invitation.py`, `test_views_locations.py`, `test_views_members.py`, `test_views_invitations.py`, `test_views_profile.py`, `test_org_switcher.py`.
