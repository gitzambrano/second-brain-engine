#!/usr/bin/env python3
"""Renomeia essays para o slug determinístico de seu H1 e repara referências.

O nome canônico é o título completo do essay transliterado para kebab-case.
Além dos Markdown, o migrador renomeia assets ``<slug>_figN`` e reaponta
wikilinks no corpus inteiro.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from unidecode import unidecode

from repo_paths import ASSETS_DIR, DATA_ROOT, ESSAYS_DIR

H1 = re.compile(r"(?m)^#\s+(.+?)\s*$")


def title_slug(title: str) -> str:
    plain = re.sub(r"[*_`]", "", title)
    return re.sub(r"[^a-z0-9]+", "-", unidecode(plain).lower()).strip("-")


def mapping() -> dict[str, str]:
    names: dict[str, str] = {}
    targets: set[str] = set()
    for path in sorted(ESSAYS_DIR.glob("*.md")):
        match = H1.search(path.read_text(encoding="utf-8-sig"))
        target = title_slug(match.group(1) if match else path.stem)
        if not target:
            raise ValueError(f"H1 sem slug utilizável: {path}")
        if target in targets and target != path.stem:
            raise ValueError(f"colisão de slug: {target}")
        targets.add(target)
        if target != path.stem:
            names[path.stem] = target
    return names


def apply(renames: dict[str, str]) -> None:
    for path in DATA_ROOT.rglob("*.md"):
        text = path.read_text(encoding="utf-8-sig")
        changed = text
        for old, new in renames.items():
            changed = re.sub(rf"\[\[{re.escape(old)}(?=[|#\]])", f"[[{new}", changed)
            changed = changed.replace(f"{old}_fig", f"{new}_fig")
        if changed != text:
            path.write_text(changed, encoding="utf-8")

    for old, new in renames.items():
        for asset in ASSETS_DIR.glob(f"{old}_fig*"):
            asset.rename(asset.with_name(asset.name.replace(old + "_fig", new + "_fig", 1)))

    for old, new in renames.items():
        (ESSAYS_DIR / f"{old}.md").rename(ESSAYS_DIR / f"{new}.md")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="efetiva a migração; sem isso apenas lista")
    args = parser.parse_args(argv)
    renames = mapping()
    for old, new in renames.items():
        print(f"{old} -> {new}")
    if args.apply:
        apply(renames)
        print(f"renomeados: {len(renames)}")
    else:
        print(f"prévia: {len(renames)} rename(s); use --apply para efetivar")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
