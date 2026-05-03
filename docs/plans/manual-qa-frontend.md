# Manual QA + UI/UX Usability Test Plan (Frontend)

Autonomous Playwright agent: walk every screen, exercise flows, capture issues. Stack: Django + HTMX + Alpine + Pico CSS.

## Setup

1. Start dev server: `uv run python manage.py runserver` (http://127.0.0.1:8000).
2. Apply migrations + create a superuser if DB empty.
3. Test data: create accounts via the signup flow itself (it's part of the test). For email-verification tokens, read them from the Django console (dev backend prints emails to stdout) or from `MailHog`-style logs if configured. If a verification link cannot be retrieved, mark it as a blocker and continue with admin-bypass.
4. Use admin (`/admin/`) only as last resort to unblock a flow; note any flow that *requires* admin to complete.

## Test matrix

For each screen below: visit, screenshot (desktop 1440px + mobile 390px), inspect.

### Public
- `/` home
- `/signup/` signup
- `/signup/done/` post-signup
- `/login/` login (also: trigger unverified-email branch -> resend button)
- `/password/reset/` request, `/password/reset/<token>/` confirm, plus sent / failed variants
- `/verify/<token>/` success, already-verified, failed, resent variants
- `/invite/<token>/` accept_existing, accept_set_password, accept_error

### Picker / profile
- `/orgs/` org picker (test both: with memberships, with none -> empty state)
- `/me/` profile (update profile form + change password form on same page)

### Org-scoped (`/o/<slug>/...`)
- `/` dashboard
- `settings/locations/` list, `new/`, `<id>/` detail, `<id>/edit/`
- `settings/members/` list (incl. invite modal, pending invitations, archive `<details>`)
- `settings/members/<id>/` detail (role change, deactivate/reactivate, location toggles)
- `settings/organization/` org settings

### Debug-only
- `/__design__/` kitchen sink (visual reference; flag any component that visibly breaks)

## End-to-end flows (run in order)

1. **Signup -> verify -> login -> dashboard**: signup with new org, follow verification, log in, land on dashboard via picker if multi-org.
2. **Forgot password**: request reset, follow link, set new password, log in.
3. **Locations CRUD**: create, edit, deactivate, reactivate; verify list reflects state; open detail, toggle an operator chip (HTMX).
4. **Invite + accept member**: open invite modal (Alpine `dialog`), submit, verify pending row appears via HTMX swap, resend, revoke. Then accept the invite as a new browser session (use invite link).
5. **Member admin**: change role, deactivate, reactivate, toggle locations on detail page.
6. **Profile self-service**: update name + preferred language, change password, log out, log back in with new password.
7. **Org settings**: edit name / country / VAT / default language; confirm slug is read-only.
8. **Auth boundaries**: hit an org URL while logged out -> redirected to login; hit another org's slug -> 404/permission error (note behavior).

## What to evaluate per screen

- **Functional**: every link/button reachable; forms submit; HTMX swaps land in expected target; no JS console errors; no 500s in server log.
- **Validation**: submit empty + invalid inputs; check error messages are visible, associated with the field, and human-readable.
- **State feedback**: success messages after save; loading state on slow actions; disabled state on duplicate submit.
- **Navigation**: back-link works; breadcrumbs/headers show correct context (org name, current section); active rail item highlighted.
- **Empty states**: every list shows a usable empty state (locations, members, pending invitations, archive, org picker with 0 orgs).
- **Modals/dialogs**: invite modal opens via `<button>`, closes via Esc, backdrop click, and after successful submit; focus trap; focus returns to trigger.
- **Responsive**: 390px mobile, 768px tablet, 1440px desktop -> no horizontal scroll, tables don't overflow silently, rail/menu still usable.
- **Accessibility (quick pass)**: every input has a `<label>`; headings hierarchical (one h1 per page); buttons vs links used correctly; color contrast on Pico defaults; keyboard-only run of a representative flow (signup or invite).
- **i18n**: switch `preferred_language` (or `?lang=` if available) and confirm strings translate; flag untranslated strings.
- **Copy / UX**: ambiguous labels, missing hints, redundant fields, unclear error wording, inconsistent button verbs ("Save" vs "Update" vs "Submit").
- **Visual**: alignment, spacing, overflow, broken icons, inconsistent button styles vs `__design__` reference.

## Output

Write a single report `docs/reports/manual-qa-frontend-<YYYY-MM-DD>.md` with:

- **Summary**: pass/fail counts per flow.
- **Blockers**: anything that prevents finishing a flow.
- **Bugs**: per item -> screen, repro steps, expected vs actual, severity (critical/major/minor), screenshot path.
- **UX improvements**: per item -> screen, observation, suggestion, effort guess (S/M/L).
- **Accessibility findings**: separate list, WCAG-ish severity.
- **Console / server errors log**: deduplicated.

Keep entries terse. One bullet per finding. Group by screen.
