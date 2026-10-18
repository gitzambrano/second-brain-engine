#!/usr/bin/env python3
"""build_index.py - Cache de metadados da wiki: índice navegável de essays e tags.

Gera o catálogo consolidado de ensaios, títulos, tags e resumos de todos os tipos de página.
Evita re-parsear o frontmatter da wiki inteira a cada consulta (/query, /stats, /gaps, check_title).

Escopo:
    Geração mecânica de índices em DATA_ROOT/wiki/. Artefato derivado — nunca editar à mão;
    a fonte da verdade são os arquivos Markdown originais.

Entradas (Inputs):
    DATA_ROOT/wiki/ (essays, concepts, entities, insights) e wiki/sources/manifest.md.

Saídas (Outputs):
    wiki/index.json   Títulos, caminhos, tags, resumos, status e tags_in_use consolidado.
    wiki/index.md     Lista plana de essays ordenada por data decrescente de criação.
    Exit code: 0 em sucesso, 1 em falha de parsing.

Uso:
    python scripts/build_index.py             # regenera index.json e index.md
"""

import datetime
import json
import re
import sys
from collections import Counter
from pathlib import Path

import console_encoding  # noqa: F401  (UTF-8 no console; ver o módulo)
import visibility
import yaml
from repo_paths import CODE_ROOT, DATA_ROOT, WIKI_ROOT

ROOT_DIR = CODE_ROOT
ESSAYS_DIR = WIKI_ROOT / "essays"
CONCEPTS_DIR = WIKI_ROOT / "concepts"
ENTITIES_DIR = WIKI_ROOT / "entities"
INSIGHTS_DIR = WIKI_ROOT / "insights"
SOURCES_DIR = WIKI_ROOT / "sources"
MANIFEST_PATH = SOURCES_DIR / "manifest.md"
OUTPUT_DIR = WIKI_ROOT
OUTPUT_PATH = OUTPUT_DIR / "index.json"
OUTPUT_MD_PATH = OUTPUT_DIR / "index.md"


def load(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def get_h1(content):
    m = re.search(r"(?m)^# (.+)", content)
    return m.group(1).strip() if m else None


def get_frontmatter(content):
    m = re.match(r"^---\s*\n(.*?)\n---", content, flags=re.DOTALL)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return {}


def as_list(v):
    """Normaliza um campo do frontmatter para lista de strings, venha ele como
    lista, escalar ou ausente.
    """
    if isinstance(v, list):
        return [str(x).strip() for x in v]
    if v is None:
        return []
    return [str(v).strip()]


def as_str(v):
    """yaml.safe_load parseia datas YYYY-MM-DD como datetime.date — normaliza pra string."""
    return str(v) if v is not None else None


def index_pages(dir_path, node_type):
    """Indexa as páginas de um diretório, pulando as marcadas `visibility: hidden`."""
    entries = []
    if not dir_path.exists():
        return entries
    for f in sorted(dir_path.glob("*.md")):
        if f.name == ".gitkeep":
            continue
        content = load(f)
        title = get_h1(content)
        if not title:
            continue
        fm = get_frontmatter(content)
        # `visibility: hidden` removes a page from the wiki's own catalogue too.
        if visibility.is_hidden(fm):
            continue
        entry = {
            "title": title,
            "path": str(f.relative_to(DATA_ROOT)),
            "tags": as_list(fm.get("tags")),
            "created": as_str(fm.get("created")),
            "updated": as_str(fm.get("updated")),
        }
        if node_type == "essays":
            m = re.search(r"(?m)^> (Ensaio|White Paper|Brainstorm|Estudo|Análise)\s*$", content)
            entry["type"] = m.group(1) if m else None
            entry["summary"] = as_str(fm.get("summary"))
            entry["status"] = as_str(fm.get("status"))
        if node_type == "insights":
            entry["maturidade"] = as_str(fm.get("maturidade"))
        entries.append(entry)
    return entries


def index_sources():
    """Parse wiki/sources/manifest.md — uma entrada por fonte ingerida.

    Campos: Tipo, Tags (vocabulário controlado, mesmo de essays), Pasta,
    Virou, Verificação. Tags é opcional na leitura (fontes antigas podem
    não ter o campo ainda) para não quebrar o índice em wikis em migração.
    """
    entries = []
    if not MANIFEST_PATH.exists():
        return entries
    content = load(MANIFEST_PATH)
    blocks = re.split(r"(?m)^## \[(\d{4}-\d{2}-\d{2})\]\s+(.+)$", content)
    for i in range(1, len(blocks), 3):
        date, filename, body = blocks[i], blocks[i + 1], blocks[i + 2]
        tipo_m = re.search(r"(?m)^Tipo:\s*(.+?)\.?$", body)
        tags_m = re.search(r"(?m)^Tags:\s*(.+?)\.?$", body)
        pasta_m = re.search(r"(?m)^Pasta:\s*(.+?)\.?$", body)
        virou_m = re.search(r"(?m)^Virou:\s*(.+?)\.?$", body)
        verificacao_m = re.search(r"(?m)^Verificação:\s*(.+?)\.?$", body)
        tags = []
        if tags_m:
            raw = tags_m.group(1).strip()
            raw = raw[1:-1] if raw.startswith("[") and raw.endswith("]") else raw
            tags = [t.strip().strip('"').strip("'") for t in raw.split(",") if t.strip()]
        entries.append({
            "filename": filename.strip(),
            "date": date,
            "tipo": tipo_m.group(1).strip() if tipo_m else None,
            "tags": tags,
            "pasta": pasta_m.group(1).strip() if pasta_m else None,
            "virou": virou_m.group(1).strip() if virou_m else None,
            "verificacao": verificacao_m.group(1).strip() if verificacao_m else None,
        })
    return entries


def render_index_md(essays, generated):
    """Renderiza wiki/index.md: lista plana de essays, sem agrupamento por
    categoria — a classificação temática vem só de `tags` (ver
    conventions/SKILL.md, ## Formato do índice). Nunca editado à mão.

    Uma entrada por essay, ordenada por `created` decrescente:

        - [Título do Essay](essays/nome-do-arquivo.md) — Resumo de uma linha.
          `consciência` · `identidade-pessoal` · `filosofia-da-mente`
    """
    def sort_key(e):
        # created ausente vai para o final da lista (ordenação decrescente)
        return e["created"] or ""

    ordered = sorted(essays, key=sort_key, reverse=True)

    lines = [
        "# Índice",
        "",
        f"{len(ordered)} essay(s) — gerado em {generated}, "
        "ordenado por data de criação (mais recente primeiro). "
        "Artefato gerado por `scripts/build_index.py`, nunca editado à mão.",
        "",
    ]

    for e in ordered:
        rel_path = Path(e["path"]).name  # wiki/essays/<arquivo>.md -> <arquivo>.md
        title = e["title"] or rel_path
        summary = e.get("summary") or ""
        tags = " · ".join(f"`{t}`" for t in e.get("tags") or [])
        entry = f"- [{title}](essays/{rel_path})"
        if summary:
            entry += f" — {summary}"
        lines.append(entry)
        if tags:
            lines.append(f"  {tags}")

    lines.append("")
    return "\n".join(lines)


def build():
    """Monta o índice completo da wiki e o vocabulário de tags em uso."""
    essays = index_pages(ESSAYS_DIR, "essays")
    concepts = index_pages(CONCEPTS_DIR, "concepts")
    entities = index_pages(ENTITIES_DIR, "entities")
    insights = index_pages(INSIGHTS_DIR, "insights")
    sources = index_sources()

    tags_in_use = Counter()
    for e in essays:
        tags_in_use.update(e["tags"])
    for s in sources:
        tags_in_use.update(s["tags"])

    return {
        "generated": datetime.date.today().isoformat(),
        "essays": essays,
        "concepts": concepts,
        "entities": entities,
        "insights": insights,
        "sources": sources,
        "tags_in_use": dict(sorted(tags_in_use.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


def main():
    index = build()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    index_md = render_index_md(index["essays"], index["generated"])
    with open(OUTPUT_MD_PATH, "w", encoding="utf-8") as f:
        f.write(index_md)

    total_pages = len(index["essays"]) + len(index["concepts"]) + len(index["entities"]) + len(index["insights"])
    print(f"Índice gerado: {total_pages} página(s) + {len(index['sources'])} source(s) "
          f"em manifest.md, {len(index['tags_in_use'])} tag(s) em uso.")
    print(f"  {OUTPUT_PATH.relative_to(DATA_ROOT)}")
    print(f"  {OUTPUT_MD_PATH.relative_to(DATA_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
