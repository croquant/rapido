---
name: translate-django-po
description: Fill in missing and fuzzy translations across a Django project's .po catalogs by spawning one parallel translator agent per target language. Use this skill whenever the user mentions translations, i18n, gettext, .po files, locale files, missing translations, fuzzy entries, makemessages output, or asks to translate strings in a Django project — even if they don't say "skill" or use the word "translate" explicitly. Reads supported languages from settings.LANGUAGES, gives each translator agent the source code context for ambiguous strings, preserves placeholders and plural forms, and writes results directly to each language's django.po.
---

# Translate Django .po files

Fills missing + fuzzy entries in a Django project's gettext catalogs. One translator subagent per non-source language, in parallel, writing to `locale/<lang>/LC_MESSAGES/django.po`.

If new `gettext` / `{% trans %}` calls were added but the catalog hasn't been regenerated, suggest `python manage.py makemessages -a` first — this skill only fills entries that already exist as `msgid`s.

## Workflow

### 1. Discover target languages

Look up `settings.LANGUAGES` (often re-exported from a module like `config/languages.py` — grep if not in `settings.py`). Source language is `settings.LANGUAGE_CODE` (default `"en-us"`); skip it. Fall back to globbing `locale/*/LC_MESSAGES/django.po`.

Locale codes use hyphens (`en-us`); locale **directories** use underscores and uppercase the country (`en_US`).

### 2. Detect missing entries per language

```
python <skill-dir>/scripts/find_missing.py <path-to-django.po>
```

Emits JSON per entry: `msgid`, `msgctxt`, `msgid_plural`, current `msgstr`/`msgstr_plural`, `is_fuzzy`, `previous_msgid` (old msgid if fuzzy), `source_refs` (e.g., `core/admin.py:215`), `extracted_comments`.

Skip languages with zero missing entries.

### 3. Spawn translator agents in parallel

For each language with missing entries, spawn a separate `Agent` (subagent_type=general-purpose) **in the same tool-call block** — they write to disjoint files, no conflicts.

Per-agent prompt template (substitute bracketed placeholders):

> You are filling in Django translations from English to **[LANG_NAME]** (locale `[LANG_CODE]`).
>
> **File:** `[PO_PATH]`
> **Project root:** `[PROJECT_ROOT]`
> **Skill dir:** `[SKILL_DIR]`
>
> 1. Run `python [SKILL_DIR]/scripts/find_missing.py [PO_PATH]` to get the JSON list.
>
> 2. Calibrate tone: skim 10–20 already-translated entries to gauge formality (German `Sie` vs `du`, French `vous` vs `tu`, Dutch `u` vs `je`) and project terminology. Match what's there.
>
> 3. For each missing entry:
>    - **Read the source code at each `source_refs` location.** Single biggest quality lever — "Order" is a verb in one place and a noun in another. Translate by use, not by literal text. Open the file, read 5–10 lines around the ref.
>    - If `msgctxt` is set, use it as disambiguation.
>    - For fuzzy entries: existing `msgstr` translates the *old* `previous_msgid`. Rewrite if it doesn't fit the new `msgid`.
>    - Translate naturally. Preserve `%(name)s`, `%s`, `%d`, `{name}`, `%(count)d` exactly. Preserve leading/trailing whitespace and `\n`.
>
> 4. Edit `[PO_PATH]` in place:
>    - Replace empty `msgstr ""` with the translation.
>    - For plurals, fill every `msgstr[0]`, `msgstr[1]`, ... per the file's `Plural-Forms:` header.
>    - For fuzzy entries: write the new translation **and** delete the `#, fuzzy` flag and any `#| msgid` / `#| msgctxt` previous-source lines.
>    - Inside `msgstr`, escape `"` as `\"`, `\` as `\\`.
>
> 5. If `msgfmt` is on PATH, run `msgfmt -c --check-format -o /dev/null [PO_PATH]` and fix any errors.
>
> Report: count of translated entries (new vs fuzzy-fixed) and any left untranslated with reason.

### 4. Aggregate and report

Per-language counts + anything skipped. Tell the user to `git diff locale/` to review before committing.

## Out of scope

- Don't run `makemessages` or `compilemessages` (user/CI's call).
- Don't commit.
- Don't translate outside `locale/` (model labels, templates, etc.).
