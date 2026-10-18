#!/usr/bin/env python3
"""visibility.py - Leitor e validador de visibilidade de ensaios a partir do frontmatter.

Centraliza as regras de permissão de publicação de ensaios:
- Identifica os níveis canônicos: public (público), private (privado) e hidden (oculto).
- Suporta valores legados (ex: publish: true/false, visibility: publico/privado/oculto).
- Classifica ensaios ausentes ou com valores inválidos estritamente como privados por segurança.

Escopo:
    Módulo utilitário e CLI read-only.
    Padrão sem argumentos imprime a distribuição e resumo de visibilidade do corpus.

Entradas (Inputs):
    Arquivos Markdown em DATA_ROOT/wiki/essays/*.md.

Saídas (Outputs):
    Stdout: Estatísticas consolidadas de contagem de essays públicos, privados e ocultos.
    Python: Funções utilitárias is_public(), is_hidden(), get_visibility() para outros scripts.
    Exit code: 0 em sucesso.

Uso:
    python scripts/visibility.py                  # exibe resumo da distribuição de visibilidade
"""
from __future__ import annotations

import argparse
import json

PUBLIC = "public"
PRIVATE = "private"
HIDDEN = "hidden"

LEVELS = (PUBLIC, PRIVATE, HIDDEN)

# Portuguese spellings are accepted because the corpus is written in Portuguese.
ALIASES = {
    "public": PUBLIC, "publico": PUBLIC, "público": PUBLIC,
    "private": PRIVATE, "privado": PRIVATE,
    "hidden": HIDDEN, "oculto": HIDDEN, "occult": HIDDEN,
}


def of(meta: dict) -> str:
    """Return the visibility level for a page's frontmatter mapping."""
    raw = meta.get("visibility")
    if isinstance(raw, str):
        level = ALIASES.get(raw.strip().casefold())
        if level:
            return level
        # An unrecognized value must not silently publish.
        return PRIVATE
    # Legacy: only the YAML boolean true ever authorized publication.
    if meta.get("publish") is True:
        return PUBLIC
    return PRIVATE


def is_public(meta: dict) -> bool:
    return of(meta) == PUBLIC


def is_hidden(meta: dict) -> bool:
    return of(meta) == HIDDEN


def invalid_value(meta: dict) -> str | None:
    """Return the offending value when `visibility:` is set but unusable."""
    raw = meta.get("visibility")
    if raw is None:
        if "publish" in meta and meta.get("publish") not in (True, False, None):
            return repr(meta.get("publish"))
        return None
    if not isinstance(raw, str) or raw.strip().casefold() not in ALIASES:
        return repr(raw)
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    from repo_paths import ESSAYS_DIR
    from site_common import parse

    counts = {level: [] for level in LEVELS}
    invalid = []
    if ESSAYS_DIR.exists():
        for path in sorted(ESSAYS_DIR.glob("*.md")):
            if path.name == ".gitkeep":
                continue
            meta, _body = parse(path)
            counts[of(meta)].append(path.stem)
            bad = invalid_value(meta)
            if bad:
                invalid.append({"slug": path.stem, "value": bad})

    if args.json:
        print(json.dumps(
            {"counts": {k: len(v) for k, v in counts.items()},
             "essays": counts, "invalid": invalid},
            ensure_ascii=False, indent=2))
        return 0

    for level in LEVELS:
        print(f"{level:8s} {len(counts[level]):3d}")
        for slug in counts[level][:200]:
            if level != PRIVATE:
                print(f"           {slug}")
    for bad in invalid:
        print(f"  INVALID {bad['slug']}: visibility={bad['value']}")
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
