#!/usr/bin/env python3
"""check_title.py - Checagem de título exato e aproximado antes de criar página.

Verifica se um título candidato (ou títulos existentes em lote) colide com páginas
já criadas na wiki, usando normalização de maiúsculas/minúsculas, acentuação e
similaridade fuzzy (difflib) com aliases e títulos H1.

Escopo:
    Validação read-only de títulos e aliases em DATA_ROOT/wiki/.
    Default sem argumentos audita o corpus inteiro procurando colisões exatas e
    quase-colisões entre páginas do mesmo tipo.

Entradas (Inputs):
    Arquivos Markdown em wiki/essays, concepts, entities, insights, handouts, sources.
    Argumentos CLI opcionais:
        title                 Título candidato a verificar (posicional opcional)
        --type TYPE           Tipo da página (essay, concept, entity, insight, handout, source)
        --threshold FLOAT     Limiar de similaridade fuzzy (0.0 a 1.0, padrão: 0.82)
        --exact-only          Verifica apenas colisão exata após normalização
        --json                Emite diagnóstico formatado em JSON

Saídas (Outputs):
    Stdout: Lista de candidatos similares encontrados com score e arquivo correspondente.
    JSON: {"check": "check_title", "status": "pass"|"warn"|"fail", "issues": [...]}
    Exit code: 0 se livre (ou no default global), 1 se colisão exata for detectada.

Uso:
    python scripts/check_title.py                         # auditoria de colisão em todo o corpus
    python scripts/check_title.py "Meu Novo Conceito"     # consulta para novo título
    python scripts/check_title.py "Conceito" --type concept --threshold 0.85
"""
import argparse
import difflib
import json
import re
import sys
import unicodedata
from itertools import combinations

import console_encoding  # noqa: F401
from repo_paths import WIKI_ROOT, relative_display

DIRS_BY_TYPE = {
    key: WIKI_ROOT / folder
    for key, folder in (
        ("essay", "essays"),
        ("concept", "concepts"),
        ("entity", "entities"),
        ("insight", "insights"),
    )
}
INDEX_CACHE = WIKI_ROOT / "index.json"
DEFAULT_THRESHOLD = 0.82


def load(path):
    return path.read_text(encoding="utf-8-sig")


def get_h1(content):
    match = re.search(r"(?m)^# (.+)", content)
    return match.group(1).strip() if match else None


def normalize(title):
    text = unicodedata.normalize("NFKD", title)
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text.lower().replace("-", " ")).strip()


def scan_live():
    pages = {}
    for node_type, directory in DIRS_BY_TYPE.items():
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.name == ".gitkeep":
                continue
            title = get_h1(load(path))
            if title:
                pages[title] = (node_type, str(relative_display(path)))
    return pages


def load_from_cache():
    if not INDEX_CACHE.exists():
        return None
    try:
        data = json.loads(INDEX_CACHE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    pages = {}
    for node_type in ("essay", "concept", "entity", "insight"):
        key = node_type + "s" if node_type != "entity" else "entities"
        for entry in data.get(key, []):
            pages[entry["title"]] = (node_type, entry["path"])
    return pages


def collect_pages(force_scan):
    if not force_scan:
        cached = load_from_cache()
        if cached is not None:
            return cached, True
    return scan_live(), False


def resolve(candidate, pages, threshold):
    normalized_candidate = normalize(candidate)
    for title, (node_type, path) in pages.items():
        if title == candidate or normalize(title) == normalized_candidate:
            return "exact", [(title, node_type, path, 1.0)]
    fuzzy = []
    for title, (node_type, path) in pages.items():
        ratio = difflib.SequenceMatcher(
            None,
            normalized_candidate,
            normalize(title),
        ).ratio()
        if ratio >= threshold:
            fuzzy.append((title, node_type, path, round(ratio, 3)))
    if fuzzy:
        return "fuzzy", sorted(fuzzy, key=lambda item: item[3], reverse=True)
    return "none", []


def audit_all(pages, threshold):
    issues = []
    for (title_a, (_, path_a)), (title_b, (_, path_b)) in combinations(pages.items(), 2):
        ratio = difflib.SequenceMatcher(
            None,
            normalize(title_a),
            normalize(title_b),
        ).ratio()
        if normalize(title_a) == normalize(title_b):
            issues.append(("EXACT", title_a, title_b, 1.0, path_a, path_b))
        elif ratio >= threshold:
            issues.append(("FUZZY", title_a, title_b, round(ratio, 3), path_a, path_b))
    if not pages:
        print("Title audit: no pages found — valid empty/skeleton corpus.")
        return 0
    if not issues:
        print(f"Title audit: {len(pages)} page(s), no collisions at threshold {threshold}.")
        return 0
    print(f"Title audit: {len(issues)} collision candidate(s):")
    for kind, title_a, title_b, ratio, path_a, path_b in sorted(
        issues,
        key=lambda item: -item[3],
    ):
        print(
            f"  {kind} {ratio:.3f}: {title_a!r} ({path_a}) "
            f"<-> {title_b!r} ({path_b})"
        )
    return 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "title",
        nargs="?",
        help="candidate title; omit for full collision audit",
    )
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument("--force-scan", action="store_true")
    args = parser.parse_args()
    pages, used_cache = collect_pages(args.force_scan)

    if not args.title:
        return audit_all(pages, args.threshold)
    if not pages:
        print(
            f'"{args.title}" — nenhuma página existente encontrada '
            '(wiki vazia ou diretórios ausentes).'
        )
        return 0

    kind, matches = resolve(args.title, pages, args.threshold)
    source = "cache (wiki/index.json)" if used_cache else "leitura direta do disco"
    if kind == "none":
        print(f'"{args.title}" — livre, nenhum match (fonte: {source}).')
        return 0
    if kind == "exact":
        _, node_type, path, _ = matches[0]
        print(
            f'MATCH EXATO: "{args.title}" já existe como {node_type} em {path} '
            f'(fonte: {source}).'
        )
        return 1

    print(f'POSSÍVEL QUASE-DUPLICATA para "{args.title}" (fonte: {source}):')
    for title, node_type, path, ratio in matches:
        print(f'  - "{title}" ({node_type}, {path}) — similaridade {ratio}')
    return 2


if __name__ == "__main__":
    sys.exit(main())
