#!/usr/bin/env python3
"""find_text.py - Busca textual contextualizada no corpus da wiki sem grep externo.

Permite pesquisar termos exatos, padrões regex e wikilinks na base de conhecimento:
- Agrupa ocorrências próximas mesclando linhas de contexto para leitura fluida.
- Suporta filtragem por escopo de pastas (essays, concepts, entities, insights, sources).
- Padrão sem argumentos imprime o inventário do corpus pesquisável em vez de falhar.

Escopo:
    Ferramenta de pesquisa read-only no diretório DATA_ROOT/wiki/.

Entradas (Inputs):
    Arquivos Markdown da wiki em DATA_ROOT/wiki/.
    Argumentos CLI:
        pattern           Termo ou regex a pesquisar (posicional opcional)
        --scope ESCOPO    Subconjunto de pastas (padrão: essays, concepts, entities, insights)
        -C, --context INT Número de linhas de contexto antes e depois (padrão: 2)
        -i, --ignore-case Ignora maiúsculas/minúsculas na busca

Saídas (Outputs):
    Stdout: Ocorrências formatadas com caminho do arquivo, número da linha e contexto.
    Exit code: 0 em sucesso, 1 se nenhum resultado for encontrado.

Uso:
    python scripts/find_text.py                     # inventário do corpus pesquisável
    python scripts/find_text.py "termo"             # busca simples com contexto
    python scripts/find_text.py "termo" --scope essays -C 3
"""
import argparse
import re
import sys

import console_encoding  # noqa: F401
from repo_paths import WIKI_ROOT, relative_display

SCOPE_DIRS = {
    "essays": WIKI_ROOT / "essays",
    "concepts": WIKI_ROOT / "concepts",
    "entities": WIKI_ROOT / "entities",
    "insights": WIKI_ROOT / "insights",
    "handouts": WIKI_ROOT / "handouts",
    "sources": WIKI_ROOT / "sources",
}
DEFAULT_SCOPE = ["essays", "concepts", "entities", "insights"]


def load(path):
    try:
        return path.read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, OSError):
        return None


def collect_files(scopes):
    files = []
    for scope in scopes:
        d = SCOPE_DIRS.get(scope)
        if not d or not d.exists():
            continue
        iterator = d.rglob("*") if scope == "sources" else d.glob("*.md")
        files.extend(f for f in sorted(iterator) if f.is_file() and f.name != ".gitkeep")
    return files


def inventory(scopes):
    print("Searchable corpus inventory:")
    total_files = total_lines = 0
    for scope in scopes:
        files = collect_files([scope])
        lines = 0
        readable = 0
        for f in files:
            text = load(f)
            if text is not None:
                readable += 1
                lines += len(text.splitlines())
        total_files += readable
        total_lines += lines
        print(f"  {scope:<10} {readable:>4} file(s), {lines:>7} line(s)")
    print(f"Total: {total_files} readable file(s), {total_lines} line(s).")
    return 0


def build_pattern(query, use_regex, ignore_case):
    flags = re.IGNORECASE if ignore_case else 0
    pattern = query if use_regex else re.escape(query)
    try:
        return re.compile(pattern, flags)
    except re.error as e:
        print(f"Regex inválida: {e}", file=sys.stderr)
        raise SystemExit(1)


def merge_ranges(ranges):
    if not ranges:
        return []
    ranges = sorted(ranges)
    merged = [ranges[0]]
    for start, end in ranges[1:]:
        ls, le = merged[-1]
        if start <= le + 1:
            merged[-1] = (ls, max(le, end))
        else:
            merged.append((start, end))
    return merged


def search_file(path, pattern, context):
    content = load(path)
    if content is None:
        return None, 0
    lines = content.split("\n")
    match_lines = [i for i, line in enumerate(lines) if pattern.search(line)]
    if not match_lines:
        return [], 0
    ranges = [
        (max(0, index - context), min(len(lines) - 1, index + context))
        for index in match_lines
    ]
    blocks = []
    for start, end in merge_ranges(ranges):
        blocks.append(
            (
                start + 1,
                end + 1,
                lines[start : end + 1],
                {index + 1 for index in match_lines if start <= index <= end},
            )
        )
    return blocks, len(match_lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", help="term/pattern; omit for corpus inventory")
    parser.add_argument("--scope", nargs="+", choices=list(SCOPE_DIRS), default=DEFAULT_SCOPE)
    parser.add_argument("--regex", action="store_true")
    parser.add_argument("--context", type=int, default=2)
    parser.add_argument("--ignore-case", action="store_true")
    parser.add_argument("--list-only", action="store_true")
    args = parser.parse_args()
    if not args.query:
        return inventory(args.scope)
    pattern = build_pattern(args.query, args.regex, args.ignore_case)
    files = collect_files(args.scope)
    if not files:
        print(f"Nenhum arquivo encontrado no escopo: {', '.join(args.scope)}")
        return 1
    total_matches = files_with_hits = 0
    for path in files:
        blocks, n_matches = search_file(path, pattern, args.context)
        if blocks is None or n_matches == 0:
            continue
        files_with_hits += 1
        total_matches += n_matches
        rel = relative_display(path)
        if args.list_only:
            print(f"{rel}: {n_matches} ocorrência(s)")
            continue
        print(f"\n=== {rel} ({n_matches} ocorrência(s)) ===")
        for start, end, block_lines, match_line_nums in blocks:
            for offset, line in enumerate(block_lines):
                lineno = start + offset
                marker = ">" if lineno in match_line_nums else " "
                print(f"{marker} {lineno:>5} | {line}")
            if len(blocks) > 1:
                print("  ...")
    print(
        f"\n{total_matches} ocorrência(s) em {files_with_hits} arquivo(s) "
        f"(escopo: {', '.join(args.scope)})."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
