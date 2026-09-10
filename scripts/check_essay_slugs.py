#!/usr/bin/env python3
"""Valida que o arquivo de cada essay seja o slug do seu H1 completo."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from unidecode import unidecode

from repo_paths import ESSAYS_DIR, relative_data

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
H1_RE = re.compile(r"(?m)^#\s+(.+?)\s*$")


def title_slug(title: str) -> str:
    title = re.sub(r"[*_`]", "", title)
    return re.sub(r"[^a-z0-9]+", "-", unidecode(title).lower()).strip("-")


def audit(essays_dir: Path = ESSAYS_DIR) -> list[dict[str, str]]:
    """Return one blocking finding for each non-canonical essay filename."""
    if not essays_dir.exists():
        return []
    issues: list[dict[str, str]] = []
    for path in sorted(essays_dir.glob("*.md")):
        if path.name == ".gitkeep":
            continue
        body = path.read_text(encoding="utf-8-sig")
        heading = H1_RE.search(body)
        expected = title_slug(heading.group(1) if heading else path.stem)
        if SLUG_RE.fullmatch(path.stem) and path.stem == expected:
            continue
        issues.append({
            "code": "ESSAY_FILENAME_TITLE_MISMATCH",
            "path": str(relative_data(path)),
            "message": (
                f"essay filename must be '{expected}.md' from its H1, received {path.name}"
            ),
        })
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable report")
    args = parser.parse_args()

    issues = audit()
    report = {
        "check": "essay-slugs",
        "status": "fail" if issues else "pass",
        "errors": len(issues),
        "issues": issues,
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif issues:
        print("essay slugs: FAIL")
        for issue in issues:
            print(f"  ERROR {issue['path']}: {issue['message']}")
    else:
        print("essay slugs: PASS")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
