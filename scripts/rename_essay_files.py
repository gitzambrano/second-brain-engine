#!/usr/bin/env python3
"""rename_essay_files.py - Renomeia arquivos de essays para o slug determinístico de seu H1.

Aplica a convenção normativa de nomenclatura: o nome do arquivo em wiki/essays/
deve ser exatamente o slug kebab-case do seu título H1:
- Renomeia o arquivo Markdown correspondente.
- Renomeia os assets associados (<slug>_figN.ext).
- Reaponta automaticamente todos os [[wikilinks]] no corpus inteiro.

Escopo:
    Mutador determinístico da wiki em DATA_ROOT/wiki/.
    Sem argumentos opera em modo dry-run (apenas lista os planos de renomeação).

Entradas (Inputs):
    Arquivos Markdown em DATA_ROOT/wiki/essays/*.md e assets em wiki/assets/.
    Argumentos CLI opcionais:
        --apply    Executa as renomeações e atualizações de links em disco

Saídas (Outputs):
    Stdout: Lista de arquivos a renomear e contagem de referências atualizadas.
    Sistema de arquivos: Arquivos renomeados e wikilinks atualizados quando --apply é usado.
    Exit code: 0 em sucesso, 1 em caso de conflito de slug.

Uso:
    python scripts/rename_essay_files.py          # dry-run consultivo
    python scripts/rename_essay_files.py --apply  # aplica renomeações e reaponta links
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
