#!/usr/bin/env python3
"""bootstrap_repositories.py - Cria os esqueletos dos repositórios aninhados data/ e site/.

Inicializa a árvore canônica de diretórios para os repositórios Git aninhados:
- data/: raw, plan, wiki (essays, concepts, entities, insights, handouts, sources), output.
- site/: assets, essays, index.html, 404.html.

Escopo:
    Provisionamento inicial e testes. Sem argumentos executa dry-run.
    Nunca sobrescreve corpus existente, nunca cria remotes no GitHub e nunca
    altera o índice Git do engine.

Entradas (Inputs):
    Argumentos CLI opcionais:
        --create    Cria a árvore de diretórios e arquivos mínimos ausentes
        --init-git  Inicializa os repositórios Git em data/ e site/ (branch main)

Saídas (Outputs):
    Stdout: Lista de diretórios e arquivos criados ou planejados (dry-run).
    Sistema de arquivos: Diretórios e arquivos esqueleto sob DATA_ROOT e SITE_ROOT.
    Exit code: 0 em sucesso, 1 em erro de criação ou permissão.

Uso:
    python scripts/bootstrap_repositories.py            # dry-run
    python scripts/bootstrap_repositories.py --create   # cria diretórios ausentes
    python scripts/bootstrap_repositories.py --create --init-git # cria e inicializa Git
"""
from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

import visibility
from repo_paths import CODE_ROOT, DATA_ROOT, SITE_ROOT

DATA_DIRS = [
    "raw",
    "plan/drafts",
    "wiki/essays", "wiki/concepts", "wiki/entities", "wiki/insights",
    "wiki/handouts", "wiki/assets", "wiki/book-chapters",
    "wiki/sources/ensaio-importado", "wiki/sources/web-clipping",
    "wiki/sources/artigo-academico", "wiki/sources/livro",
    "wiki/sources/documentacao-tecnica", "wiki/sources/transcricao",
    "wiki/sources/ideias", "wiki/sources/outro", "wiki/sources/resumos",
    "output/html", "output/pdf", "output/handouts", "output/stats", "output/graph",
]

DATA_GITIGNORE = """# Raw source documents are local-only; metadata/resumos remain versionable.
wiki/sources/**
!wiki/sources/**/
!wiki/sources/**/.gitkeep
!wiki/sources/manifest.md
!wiki/sources/map.md
!wiki/sources/resumos/
!wiki/sources/resumos/**
!wiki/sources/resumos/**/.gitkeep

# Generated outputs are reproducible.
output/**
!output/**/
!output/**/.gitkeep

# Migration reports are private/local.
.migration/

# Semantic-search caches.
.qmd-cache/
.qmd-config/
.qmd-output/

# Obsidian: version the portable vault configuration, not third-party plugin code.
.obsidian/*
!.obsidian/app.json
!.obsidian/appearance.json
!.obsidian/core-plugins.json
!.obsidian/community-plugins.json
!.obsidian/graph.json
!.obsidian/hotkeys.json
!.obsidian/snippets/
!.obsidian/plugins/
.obsidian/plugins/*/*
!.obsidian/plugins/*/data.json
.obsidian/workspace*
.obsidian/cache/

# Harness-local state in the data repository.
.agents/*
.claude/*

# OS/Python/editor.
.DS_Store
Thumbs.db
__pycache__/
*.tmp
*.bak
"""

DATA_GITATTRIBUTES = """* text=auto
*.md text eol=lf
*.json text eol=lf
*.yaml text eol=lf
*.yml text eol=lf
"""

DATA_README = """# Second Brain Data

PRIVATE repository. Contains the Markdown knowledge corpus, plan, raw inbox and
portable Obsidian vault configuration. Open this repository root as the Obsidian
vault; agents and scripts operate on the same files directly.

Raw documents under `wiki/sources/` and generated artifacts under `output/` are
local-only. Portable Obsidian settings are versioned, but workspace/cache state
and third-party plugin code are not.

This repository must never be used as a GitHub Pages source.
"""

# O nível autorizado vem de `visibility.py`, a mesma fonte que o build consulta,
# para que este README não possa voltar a descrever um contrato que já mudou —
# foi exatamente assim que ele ficou preso em `publish: true`. Só o token é
# derivável: o nome do campo e a grafia legada não são constantes lá.
SITE_README = f"""# Second Brain Site

PUBLIC generated Digital Garden.

Everything committed here must be safe for public Internet access. Content is
generated only by `../scripts/build_site.py` from essays whose frontmatter says
`visibility: {visibility.PUBLIC}`. The legacy boolean `publish: true` is still
accepted as the old spelling of that same level. Any other value, and the
absence of the field, means private: the body is never published.

Do not copy files manually from the private data repository.
"""

SITE_GITIGNORE = """.DS_Store
Thumbs.db
__pycache__/
"""


def put(path: Path, text: str = "") -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def create() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    for rel in DATA_DIRS:
        d = DATA_ROOT / rel
        d.mkdir(parents=True, exist_ok=True)
        put(d / ".gitkeep")
    put(DATA_ROOT / "README.md", DATA_README)
    put(DATA_ROOT / ".gitignore", DATA_GITIGNORE)
    put(DATA_ROOT / ".gitattributes", DATA_GITATTRIBUTES)

    SITE_ROOT.mkdir(parents=True, exist_ok=True)
    put(SITE_ROOT / "README.md", SITE_README)
    put(SITE_ROOT / ".gitignore", SITE_GITIGNORE)
    put(SITE_ROOT / ".nojekyll")
    put(SITE_ROOT / ".second-brain-site",
        "Generated public projection. Safe build target.\n")


def init_git(root: Path) -> None:
    if (root / ".git").exists():
        print(f"git already initialized: {root}")
        return
    init = subprocess.run(["git", "-C", str(root), "init", "-b", "main"])
    if init.returncode:
        subprocess.run(["git", "-C", str(root), "init"], check=True)
        subprocess.run(["git", "-C", str(root), "symbolic-ref", "HEAD",
                        "refs/heads/main"], check=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--create", action="store_true")
    ap.add_argument("--init-git", action="store_true")
    args = ap.parse_args()

    if not args.create and not args.init_git:
        print(f"engine={CODE_ROOT}")
        print(f"would create private repo at {DATA_ROOT}")
        print(f"would create public site repo at {SITE_ROOT}")
        print("no changes made")
        return 0

    if args.create:
        create()
    if args.init_git:
        if not DATA_ROOT.exists() or not SITE_ROOT.exists():
            raise SystemExit("run --create before --init-git")
        init_git(DATA_ROOT)
        init_git(SITE_ROOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
