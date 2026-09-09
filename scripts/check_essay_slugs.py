#!/usr/bin/env python3
"""Valida que os nomes de arquivos em ``wiki/essays`` sejam slugs estáveis.

Um slug de essay deve conter apenas letras ASCII minúsculas e números separados
por hífens simples. O título (H1) permanece independente, para que alterações
editoriais não alterem URLs, wikilinks ou artefatos publicados.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from repo_paths import ESSAYS_DIR, relative_data

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def audit(essays_dir: Path = ESSAYS_DIR) -> list[dict[str, str]]:
    """Return one blocking finding for each non-canonical essay filename."""
    if not essays_dir.exists():
        return []
    issues: list[dict[str, str]] = []
    for path in sorted(essays_dir.glob("*.md")):
        if path.name == ".gitkeep" or SLUG_RE.fullmatch(path.stem):
            continue
        issues.append({
            "code": "ESSAY_SLUG_NOT_KEBAB",
            "path": str(relative_data(path)),
            "message": (
                f"essay filename must be a stable ASCII kebab-case slug: {path.name}"
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
