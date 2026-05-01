"""Block raw `.objects.{all,filter,get}` in view layers.

Tenant-scoped models must be queried via `TenantOwnedManager.for_request`
or `for_organization`. Direct manager use in views/viewsets bypasses
tenant scoping. See CONTRIBUTING.md.

Per-line escape hatch: append `# noqa: tenant-lint`.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATH_RE = re.compile(r"(^|/)(views|viewsets)(\.py$|/[^/]+\.py$)")
BAD_RE = re.compile(r"\.objects\.(all|filter|get)\s*\(")
SKIP = "# noqa: tenant-lint"
EXCLUDE_DIRS = {".venv", "migrations", "__pycache__", ".git", "node_modules"}


def iter_default_files() -> list[Path]:
    root = Path(__file__).resolve().parent.parent
    out: list[Path] = []
    for p in root.rglob("*.py"):
        if any(part in EXCLUDE_DIRS for part in p.relative_to(root).parts):
            continue
        if PATH_RE.search(p.relative_to(root).as_posix()):
            out.append(p)
    return out


def check(paths: list[Path]) -> list[tuple[Path, int, str]]:
    hits: list[tuple[Path, int, str]] = []
    for path in paths:
        if not PATH_RE.search(path.as_posix()):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if SKIP in line:
                continue
            if BAD_RE.search(line):
                hits.append((path, lineno, line.strip()))
    return hits


def main(argv: list[str]) -> int:
    paths = [Path(a) for a in argv] if argv else iter_default_files()
    hits = check(paths)
    if not hits:
        return 0
    for path, lineno, src in hits:
        print(f"{path}:{lineno}: {src}", file=sys.stderr)
    print(
        "\ntenant-lint: use `.for_request(self.request)` or "
        "`.for_organization(org)` instead of raw `.objects.{all,filter,get}` "
        "in views/viewsets. Append `# noqa: tenant-lint` to opt out.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
