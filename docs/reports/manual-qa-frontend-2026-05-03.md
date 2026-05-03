# Manual QA + UI/UX Report — Frontend (2026-05-03)

Driver: Playwright MCP, Chromium. Stack under test: Django + HTMX + Alpine + Pico CSS.
Server: `uv run python manage.py runserver --noreload` against fresh sqlite DB.
Test data: created in-flow (one admin signup `qa-owner@example.com`, one operator invite `qa-operator@example.com`, one location `Main Branch v2 / main-branch`). No admin-bypass used except cookie-clear to escape an Operator-redirect 404 (see B-OPERATOR-404).

Screens visited at 1440px desktop and 390px mobile (sample). Screenshots in `qa-screens-2026-05-03/`.

## Summary

| Flow | Result |
|---|---|
| 1. Signup → verify → login → dashboard | PASS (with U-notes) |
| 2. Forgot password | PASS (with U-notes) |
| 3. Locations CRUD + HTMX toggle | PASS (no operator yet → toggle untestable on owner) |
| 4. Invite + accept member | **FAIL** — accept lands on a 404 (B-OPERATOR-404) |
| 5. Member admin (role / deactivate / locations) | PARTIAL — role + location toggle work; deactivate untested (would self-lock, see B-LASTADMIN); operator detail location-chip toggle PASS |
| 6. Profile self-service | PASS — name + password update; preferred_language saves but does **not** apply (B-I18N) |
| 7. Org settings | PASS (no flash on save, U21) |
| 8. Auth boundaries | logged-out org URL → 404 (not redirect-to-login); other-org slug → 404. Note, not bug. |

8 flows in scope. **1 failed** (invite accept), **2 partial**, 5 passed with UX notes.

## Blockers

- **B-OPERATOR-404** — every Operator-onboarding path lands on `/o/<slug>/l/<lslug>/pos/`, which is not registered in `config.urls`. See Bugs below. Blocks flow #4 end-to-end and prevents any Operator login from succeeding.

## Bugs

Severity: **critical** = breaks a core flow / data loss; **major** = visible regression on a real path; **minor** = cosmetic / non-blocking.

### Critical

- **B-OPERATOR-404** *(critical)* — `core/views/dashboard.py:31-32` and `core/services/login_redirect.py:32` redirect Operators to `/o/<slug>/l/<lslug>/pos/`. That URL pattern doesn't exist (`config/urls.py` has no `pos/` route). Effect:
  - Accepting an invite as Operator → 302 to /pos/ → 404 (`docs/reports/qa-screens-2026-05-03/invite-accept-redirect-404-1440.png`).
  - Logging in as Operator → 404.
  - Hitting `/login/` again while authed-as-Operator → re-redirect to 404. Only escape is to clear the session cookie (no logout button on the Django debug 404).
  Code comment ("route reserved; 404 until POS epic") shows this is known, but it has shipped to a state that ships an undeliverable product to every non-admin user. Fix options: (a) ship a stub `/o/<slug>/l/<lslug>/pos/` view ("POS coming soon" + a logout button), or (b) fall through Operators to `/o/<slug>/` until POS lands.
- **B-LASTADMIN** *(critical, combined with B-OPERATOR-404)* — Members list lets the only admin downgrade themselves to Operator or deactivate themselves. `core/views/members.py` has no last-admin guard. Combined with B-OPERATOR-404, a self-downgrade from the admin row instantly locks the org out: next request goes to /pos/ → 404, and there is no path back. Add a guard preventing role-change / deactivate of (a) the last active admin and (b) ideally yourself. Repro: Members → set the only Admin row's role select to "Operator" → confirm in DB or refresh → next click in nav → 404.
- **B-I18N** *(critical for non-English users)* — `core.i18n.resolve_locale` (`core/i18n.py:7`) is defined but **never called**. `User.preferred_language` and `Organization.default_language` are saved to the DB and reflected in form selects, but the rendered language stays `en-us` for everyone. `MIDDLEWARE` has `LocaleMiddleware` ahead of `AuthenticationMiddleware`, so wiring `request.user` into locale resolution requires either a custom middleware (placed after `AuthenticationMiddleware`) or stashing the resolved language into `session['_language']` on login + on profile/org-settings save. Repro: `/me/` → set Preferred language to Français → save → reload → all UI still in English.

### Major

- **B-INVITE-RESEND-NO-FEEDBACK** *(major)* — Pending invitations: clicking **Resend** issues a fresh token (verified: Expires column updates from 18:50 → 18:51) but produces no toast/flash/aria-live. User can't tell the action succeeded. Add a status message.
- **B-MOBILE-OVERFLOW** *(major)* — Locations list at 390px overflows horizontally: `document.documentElement.scrollWidth = 520` against `innerWidth = 390`. Same pattern likely on members list at 390px (table with ≥4 columns). Wrap tables in `<figure role=region>` per Pico, or collapse to cards below a breakpoint. Screenshot: `locations-390.png`.
- **B-DASHBOARD-EMPTY** *(major)* — `/o/<slug>/` for an Admin is just an `<h1>Dashboard</h1>` plus a 3-link list (Locations / Members / Organization). No data, no widgets, no empty-state copy, no shortcuts. The page reads as broken. At minimum, frame it as a settings hub ("Set up your organisation: 1) Add a location, 2) Invite members, 3) ...") or use the design-system empty-state pattern that already exists at `/__design__/`.
- **B-MEMBERS-H2** *(major)* — Members page renders `<h1>Members</h1>` and a sub-section `<h2>Members</h2>` for the active members table. Two identical headings break heading-hierarchy semantics (screen-reader users hear "Members ... Members"). Rename the H2 to "Active members" (or drop the H1 and use only one Members heading).
- **B-HEADER-EMPTY-LI** *(major)* — Every authed page renders an empty `<li></li>` between the left header nav and the user menu (verified via `outerHTML`: `<li>\n</li>`). Visible as awkward whitespace; semantically meaningless to AT users. Either remove the placeholder or fill it (e.g. with a "Switch organisation" trigger when the user has multiple orgs).

### Minor

- **B-FAVICON** *(minor)* — `GET /favicon.ico` → 404 on every page (console error). Ship a favicon or wire `/favicon.ico` to a static asset.
- **B-VAT-HINT-MISLEADING** *(minor)* — Signup form hint reads `Format: BE0123456789`, but that exact value fails the EU checksum validator (`stdnum.eu.vat`). New users will copy the hint and get an "Invalid BE VAT number" error. Replace with either a real example (`Format: BE1234567894`) or a checksum-aware copy ("BE + 10 digits incl. checksum").
- **B-TITLE-MISMATCH** *(minor)* — `/signup/` `<title>` is "Create your account" but `<h1>` is "Create your organisation". Pick one.
- **B-PW-ERRORS-CONCAT** *(minor)* — Password reset confirm: when the new password fails multiple validators (too short + too common), errors render as a single concatenated paragraph. Other forms use `<ul>`. Consistency.
- **B-FR-CATALOG-INCOMPLETE** *(minor, contingent on B-I18N)* — `locale/fr_BE/LC_MESSAGES/django.po` has 37 entries with empty `msgstr`. `nl_BE`/`de_DE` likely similar (not measured). Run `manage.py makemessages -a` and translate.

## UX improvements

| ID | Screen | Observation | Suggestion | Effort |
|---|---|---|---|---|
| U1 | All authed | "Acme QA Cafe" in header is plain text, not a link | Make it the dashboard link, or stage as an org-switcher when len(orgs) > 1 | S |
| U2 | All authed | Settings nav (Locations / Members / Organization) only appears on dashboard, not on the inner pages | Promote to a persistent left rail (or top sub-nav) inside `/o/<slug>/settings/...` | M |
| U3 | Login (unverified branch) | Email + (cleared) Password show Pico's green-check "valid" indicator after the email-not-verified error | Drop `aria-invalid=false` styling on form-level errors, or set `aria-invalid=true` on every field on submit failure | S |
| U4 | Login | "Resend verification email" navigates away to a separate "Check your inbox" page | Stay on /login/ with a flash banner so user can sign in immediately after clicking the new link | S |
| U5 | Signup | Validation error wipes password (Django default) with no copy explaining why | Add a help row "Re-enter your password" when re-rendering with errors | S |
| U6 | Signup, password reset, profile | No password-rules hint until the validator complains | Show "8+ characters; not a common password" under the New password field | S |
| U7 | Locations list | Empty state is the table chrome with one cell "No locations yet." | Use the design-system empty-state card (icon + headline + CTA) — already in `/__design__/` | S |
| U8 | Locations list | Actions cell stacks `Edit` link above a full-width `Deactivate` button; misaligned | Single horizontal toolbar, consistent button styling (or icon-only buttons) | S |
| U9 | Location detail | Only shows Active + Edit; address / phone are hidden | Show all entered fields (street, postal, city, phone) | S |
| U10 | Location edit | No flash on save; back-link missing | Mirror the detail page's `← Locations` link; flash "Saved." on success | S |
| U11 | Locations list | Deactivate has no confirmation prompt | Confirm before deactivating (especially if location has active members) | S |
| U12 | Members list | Pending-invitation Expires shown as `2026-05-10 18:50` with no timezone | Use Django's `naturaltime`/`localtime` template filter, or append "(your local time)" | S |
| U13 | Invite modal | Cancel + Send invitation buttons sit awkwardly: small Cancel left, full-width Send right | Equal-width button row; place Cancel on the left, primary action right | S |
| U14 | Member detail | No role-change or deactivate controls; only location chips | Mirror member-list controls (role select + deactivate) on the detail page so it's a real "edit" surface | S |
| U15 | Org settings | Save returns silently with no flash | Add success flash | S |
| U16 | Password reset success | Auto-login + redirect to dashboard with no confirmation message | Flash "Password updated" | S |
| U17 | Profile | Profile + change-password share a page but no spacing between H2s | Add visible separator / `<hr>` between sections, or wrap each in `<article>` cards | S |
| U18 | All authed (mobile 390px) | Tables overflow with no visible scroll affordance | See B-MOBILE-OVERFLOW — wrap in `<figure role=region>` or collapse to cards | M |
| U19 | Dashboard | Sub-nav (Locations / Members / Organization) lives inside the H1 page; settings nav location is non-obvious | Tie to U2: lift into a global rail | M |
| U20 | Locations + Members | "Yes/No" plain text in Active column | Use a status pill / badge for scannability | S |
| U21 | Header | Logout is buried two clicks deep (open user menu → submit form) | Acceptable, but the user menu trigger doesn't visually look clickable on mobile (no chevron at 390px) | S |

## Accessibility findings

- **A1** — `<li></li>` empty list-item in header on every authed page (B-HEADER-EMPTY-LI). AT will announce an empty list-item. WCAG 1.3.1 (info-and-relationships).
- **A2** — Members page double-Members heading (B-MEMBERS-H2). WCAG 1.3.1, 2.4.6 (headings).
- **A3** — Login unverified state shows green "valid" check on cleared password field (U3). WCAG 3.3.1 (error identification).
- **A4** — Mobile horizontal overflow on data lists (B-MOBILE-OVERFLOW). WCAG 1.4.10 (reflow).
- **A5** — Pico's primary blue button on white passes AA contrast; Pico secondary (slate) on white also passes. Not measured for muted-secondary on dark backgrounds — only one path uses it (Cancel button on /me/password/, fine).
- **A6** — Skip-to-content link present on every page (good).
- **A7** — Modal focus: the invite modal moves focus to Email on open (good); Esc closes (good); not verified that Tab is trapped — `<dialog>` element provides this natively, so likely fine. Backdrop click closes (verified visually).

## Console / server errors

Deduplicated:
- `GET /favicon.ico → 404` (every page) — see B-FAVICON.
- `GET /o/acme-qa-cafe/l/main-branch/pos/ → 404` (after invite accept, after Operator login) — see B-OPERATOR-404.
- `Not Found: /o/some-other-org/` (intentional, on negative auth-boundary test).
- `POST /invite/<token>/ → 422` (intentional, on first password-mismatch attempt).

No 500s. No JS console errors except the favicon 404.

## Empty-state coverage

Verified:
- Locations list (no items) → "No locations yet." in a table cell (B / U7).
- Members → Pending invitations (no items) → "No pending invitations." in a table cell.
- Members → Archive collapsed `<details>` → opens to "Archive is empty." (verified via DOM, not screenshot).
- Operators on location detail → "No operators in this organization yet." (good, plain copy).
- Org picker (1 org) → auto-redirects to that org's dashboard (skips picker; good). Picker with 0 orgs not exercised — would require creating a user with no membership.

## Untested / out of scope

- Org picker with **two** memberships and with **zero** memberships (would need a second org / a stripped user).
- Invite acceptance for an **existing user** (`/invite/<token>/` accept_existing branch) — the only token issued in this run was for a brand-new email, which routed through the set-password branch.
- Operator-driven flows beyond invite-accept (blocked by B-OPERATOR-404).
- Last-admin self-deactivate (would brick the test org; behaviour inferred from absence of guard in `core/views/members.py`).
- Keyboard-only run end-to-end (skip-link is present and modal focus behaves; full-flow keyboard run not performed).

---

Screenshots (1440 + 390 selected): `docs/reports/qa-screens-2026-05-03/`.
