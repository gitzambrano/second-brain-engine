#!/usr/bin/env python3
"""
Caminhos canônicos da estrutura de três repositórios aninhados.

Padrão:
    CODE_ROOT = este checkout público do second-brain-engine
    DATA_ROOT = CODE_ROOT / "data"  (repo Git privado aninhado)
    SITE_ROOT = CODE_ROOT / "site"  (repo Git público aninhado)

Testes e worktrees podem sobrescrever as raízes aninhadas com:
    SECOND_BRAIN_DATA_ROOT
    SECOND_BRAIN_SITE_ROOT

Default sem argumentos é read-only e imprime os caminhos efetivos.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

CODE_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = CODE_ROOT

DATA_ROOT = Path(
    os.environ.get("SECOND_BRAIN_DATA_ROOT", CODE_ROOT / "data")
).expanduser().resolve()

SITE_ROOT = Path(
    os.environ.get("SECOND_BRAIN_SITE_ROOT", CODE_ROOT / "site")
).expanduser().resolve()

# Estado local do engine (cooldowns, perfis de navegador, depuração, caches de
# validação). Nunca versionado: `.local/` está no .gitignore.
LOCAL_DIR = Path(
    os.environ.get("SECOND_BRAIN_LOCAL_DIR", CODE_ROOT / ".local")
).expanduser().resolve()

SCRIPTS_DIR = CODE_ROOT / "scripts"
LIB_DIR = SCRIPTS_DIR / "lib"
if str(LIB_DIR) not in sys.path:
    sys.path.insert(0, str(LIB_DIR))

AGENTS_DIR = CODE_ROOT / ".agents"
SKILLS_DIR = AGENTS_DIR / "skills"
SUBAGENTS_DIR = AGENTS_DIR / "agents"
SITE_SRC_DIR = SCRIPTS_DIR / "site_src"

WIKI_ROOT = DATA_ROOT / "wiki"
ESSAYS_DIR = WIKI_ROOT / "essays"
CONCEPTS_DIR = WIKI_ROOT / "concepts"
ENTITIES_DIR = WIKI_ROOT / "entities"
INSIGHTS_DIR = WIKI_ROOT / "insights"
HANDOUTS_DIR = WIKI_ROOT / "handouts"
PODCASTS_DIR = WIKI_ROOT / "podcasts"
ASSETS_DIR = WIKI_ROOT / "assets"
SOURCES_DIR = WIKI_ROOT / "sources"
REFERENCES_JSON = WIKI_ROOT / "references.json"

PLAN_DIR = DATA_ROOT / "plan"
RAW_DIR = DATA_ROOT / "raw"
OUTPUT_DIR = DATA_ROOT / "output"
HTML_DIR = OUTPUT_DIR / "html"
PDF_DIR = OUTPUT_DIR / "pdf"
HANDOUT_OUTPUT_DIR = OUTPUT_DIR / "handouts"
STATS_DIR = OUTPUT_DIR / "stats"
GRAPH_DIR = OUTPUT_DIR / "graph"

PAGE_DIRS = (ESSAYS_DIR, CONCEPTS_DIR, ENTITIES_DIR, INSIGHTS_DIR)


def _is_within(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def path_layout_valid() -> bool:
    """Validate logical roots, including external overrides used by tests."""
    code, data, site = CODE_ROOT.resolve(), DATA_ROOT.resolve(), SITE_ROOT.resolve()
    if len({code, data, site}) != 3:
        return False
    if _is_within(data, site) or _is_within(site, data):
        return False
    # DATA/SITE may intentionally be children of CODE_ROOT. They may also be
    # external when env overrides are used in tests/worktrees.
    return True


def _has_md(directory: Path) -> bool:
    return directory.is_dir() and any(
        p.name != ".gitkeep" for p in directory.glob("*.md")
    )


def corpus_has_pages() -> bool:
    return any(_has_md(d) for d in PAGE_DIRS)


def corpus_has_essays() -> bool:
    return _has_md(ESSAYS_DIR)


def relative_data(path: Path) -> Path:
    path = Path(path).resolve()
    try:
        return path.relative_to(DATA_ROOT)
    except ValueError:
        return path


def relative_display(path: Path) -> Path:
    """Stable display path for corpus files.

    Corpus paths are shown relative to DATA_ROOT; engine paths relative to
    CODE_ROOT. Synthetic fixtures may live outside both, so absolute paths are
    returned unchanged.
    """
    path = Path(path).resolve()
    for base in (DATA_ROOT, CODE_ROOT):
        try:
            return path.relative_to(base)
        except ValueError:
            continue
    return path


def print_paths() -> None:
    print(f"CODE_ROOT={CODE_ROOT}")
    print(f"DATA_ROOT={DATA_ROOT}")
    print(f"SITE_ROOT={SITE_ROOT}")
    print(f"WIKI_ROOT={WIKI_ROOT}")
    print(f"OUTPUT_DIR={OUTPUT_DIR}")
    print(f"path_layout_valid={'yes' if path_layout_valid() else 'NO'}")
    print(f"data_exists={'yes' if DATA_ROOT.is_dir() else 'no'}")
    print(f"data_git={'yes' if (DATA_ROOT / '.git').exists() else 'no'}")
    print(f"site_exists={'yes' if SITE_ROOT.is_dir() else 'no'}")
    print(f"site_git={'yes' if (SITE_ROOT / '.git').exists() else 'no'}")
    print(f"corpus={'yes' if corpus_has_pages() else 'no'}")


if __name__ == "__main__":
    print_paths()
