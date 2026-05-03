#!/usr/bin/env python3
"""Parse a Django .po file and emit JSON for entries needing translation.

An entry needs translation if it is:
  - empty (msgstr "" or any msgstr[i] "")
  - marked #, fuzzy

Output is a JSON list. Each entry has: msgid, msgctxt, msgid_plural,
msgstr (str | dict[int,str]), is_fuzzy, previous_msgid, source_refs,
extracted_comments. Header and obsolete entries are skipped.

stdlib only - no polib dependency.
"""

import json
import re
import sys
from pathlib import Path


def _unquote(s):
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    return s.encode("latin-1", "backslashreplace").decode("unicode_escape")


def _join(lines):
    return "".join(_unquote(l) for l in lines)


def _collect_continuation(lines, i):
    """Collect consecutive '"..."' continuation lines starting at i."""
    accum = []
    while i < len(lines) and lines[i].lstrip().startswith('"'):
        accum.append(lines[i])
        i += 1
    return accum, i


def parse_entry(lines):
    e = {
        "source_refs": [],
        "extracted_comments": [],
        "translator_comments": [],
        "flags": [],
        "previous_msgid": None,
        "msgctxt": None,
        "msgid": None,
        "msgid_plural": None,
        "msgstr": None,
        "msgstr_plural": {},
        "is_obsolete": False,
    }
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("#~"):
            e["is_obsolete"] = True
            i += 1
        elif line.startswith("#:"):
            e["source_refs"].extend(line[2:].split())
            i += 1
        elif line.startswith("#,"):
            e["flags"].extend(f.strip() for f in line[2:].split(","))
            i += 1
        elif line.startswith("#."):
            e["extracted_comments"].append(line[2:].strip())
            i += 1
        elif line.startswith("#|"):
            content = line[2:].strip()
            if content.startswith("msgid "):
                first = content[len("msgid ") :]
                accum = [first]
                i += 1
                while i < len(lines) and lines[i].startswith("#|"):
                    inner = lines[i][2:].strip()
                    if inner.startswith('"'):
                        accum.append(inner)
                        i += 1
                    else:
                        break
                e["previous_msgid"] = _join(accum)
            else:
                i += 1
        elif line.startswith("#"):
            e["translator_comments"].append(line[1:].lstrip())
            i += 1
        elif line.startswith("msgctxt "):
            accum = [line[len("msgctxt ") :]]
            i += 1
            cont, i = _collect_continuation(lines, i)
            accum.extend(cont)
            e["msgctxt"] = _join(accum)
        elif line.startswith("msgid_plural "):
            accum = [line[len("msgid_plural ") :]]
            i += 1
            cont, i = _collect_continuation(lines, i)
            accum.extend(cont)
            e["msgid_plural"] = _join(accum)
        elif line.startswith("msgid "):
            accum = [line[len("msgid ") :]]
            i += 1
            cont, i = _collect_continuation(lines, i)
            accum.extend(cont)
            e["msgid"] = _join(accum)
        elif m := re.match(r"msgstr\[(\d+)\]\s+(.*)", line):
            idx = int(m.group(1))
            accum = [m.group(2)]
            i += 1
            cont, i = _collect_continuation(lines, i)
            accum.extend(cont)
            e["msgstr_plural"][idx] = _join(accum)
        elif line.startswith("msgstr "):
            accum = [line[len("msgstr ") :]]
            i += 1
            cont, i = _collect_continuation(lines, i)
            accum.extend(cont)
            e["msgstr"] = _join(accum)
        else:
            i += 1
    return e


def parse_po(text):
    entries = []
    buf = []
    for line in text.splitlines():
        if line.strip() == "":
            if buf:
                entries.append(parse_entry(buf))
                buf = []
        else:
            buf.append(line)
    if buf:
        entries.append(parse_entry(buf))
    return entries


def needs_translation(e):
    if e["is_obsolete"]:
        return False
    if e["msgid"] is None or e["msgid"] == "":
        return False
    if "fuzzy" in e["flags"]:
        return True
    if e["msgid_plural"] is not None:
        if not e["msgstr_plural"]:
            return True
        return any(v == "" for v in e["msgstr_plural"].values())
    return e["msgstr"] in (None, "")


def public_view(e):
    return {
        "msgid": e["msgid"],
        "msgctxt": e["msgctxt"],
        "msgid_plural": e["msgid_plural"],
        "msgstr": e["msgstr"],
        "msgstr_plural": {str(k): v for k, v in e["msgstr_plural"].items()}
        or None,
        "is_fuzzy": "fuzzy" in e["flags"],
        "previous_msgid": e["previous_msgid"],
        "source_refs": e["source_refs"],
        "extracted_comments": e["extracted_comments"],
    }


def main():
    if len(sys.argv) < 2:
        print("Usage: find_missing.py <po-file>", file=sys.stderr)
        sys.exit(2)
    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")
    entries = parse_po(text)
    missing = [public_view(e) for e in entries if needs_translation(e)]
    json.dump(missing, sys.stdout, indent=2, ensure_ascii=False)
    print()


if __name__ == "__main__":
    main()
