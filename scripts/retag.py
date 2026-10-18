#!/usr/bin/env python3
"""retag.py - Renomeia ou consolida tags em todo o corpus da wiki.

Atualiza metadados de tags no frontmatter das páginas da wiki e no manifest.md:
- Substitui uma tag antiga por uma nova em todas as páginas afetadas.
- Padrão sem argumentos opera em modo read-only imprimindo o inventário de tags em uso.

Escopo:
    Mutador de metadados em DATA_ROOT/wiki/. Altera apenas a lista de tags no frontmatter.

Entradas (Inputs):
    Arquivos em wiki/essays, concepts, entities, insights e wiki/sources/manifest.md.
    Argumentos CLI:
        old_tag    Tag existente a ser substituída (posicional opcional)
        new_tag    Novo nome da tag (posicional opcional)
        --apply    Confirma a escrita em disco (sem --apply opera em dry-run)

Saídas (Outputs):
    Stdout: Inventário de tags em uso ou lista de arquivos modificados com contagens.
    Exit code: 0 em sucesso, 1 em argumentos parciais ou inválidos.

Uso:
    python scripts/retag.py                       # lista todas as tags em uso
    python scripts/retag.py "TagAntiga" "TagNova" # dry-run da renomeação
    python scripts/retag.py "TagAntiga" "TagNova" --apply
"""
import argparse
import re
import sys
from collections import Counter

import console_encoding  # noqa: F401
import yaml
from repo_paths import WIKI_ROOT, relative_display

PAGE_DIRS = [WIKI_ROOT / d for d in ("essays", "concepts", "entities", "insights")]
MANIFEST_PATH = WIKI_ROOT / "sources" / "manifest.md"
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def load(path):
    with open(path, "r", encoding="utf-8-sig") as file_obj:
        return file_obj.read()


def inventory():
    counts = Counter()
    pages = 0
    for directory in PAGE_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            if path.name == ".gitkeep":
                continue
            pages += 1
            match = FRONTMATTER_RE.match(load(path))
            if not match:
                continue
            frontmatter = yaml.safe_load(match.group(1)) or {}
            counts.update(str(tag) for tag in (frontmatter.get("tags") or []))
    if MANIFEST_PATH.exists():
        for raw in re.findall(r"(?m)^Tags:\s*(.+?)\.?$", load(MANIFEST_PATH)):
            inner = raw.strip().strip("[]")
            counts.update(
                tag.strip().strip('"').strip("'")
                for tag in inner.split(",")
                if tag.strip()
            )
    print(f"Tag inventory: {len(counts)} tag(s), {pages} page(s).")
    for tag, count in sorted(counts.items(), key=lambda item: (-item[1], item[0].casefold())):
        print(f"  {tag}: {count}")
    if not counts:
        print("  (no tags found — valid skeleton/empty corpus)")
    return 0


def retag_page(path, old_tag, new_tag, dry_run):
    content = load(path)
    match = FRONTMATTER_RE.match(content)
    if not match:
        return False
    frontmatter = yaml.safe_load(match.group(1)) or {}
    tags = frontmatter.get("tags") or []
    if old_tag not in tags:
        return False

    new_tags = [tag for tag in tags if tag != old_tag]
    if new_tag not in new_tags:
        new_tags.append(new_tag)
    frontmatter["tags"] = new_tags
    dumped = yaml.safe_dump(
        frontmatter,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=None,
    )
    new_frontmatter = "---\n" + dumped + "---\n"
    new_content = FRONTMATTER_RE.sub(lambda _: new_frontmatter, content, count=1)
    if not dry_run:
        path.write_text(new_content, encoding="utf-8")
    return True


def retag_manifest(old_tag, new_tag, dry_run):
    if not MANIFEST_PATH.exists():
        return 0
    content = load(MANIFEST_PATH)
    count = 0

    def replace_line(match):
        nonlocal count
        raw = match.group(1).strip()
        bracketed = raw.startswith("[") and raw.endswith("]")
        inner = raw[1:-1] if bracketed else raw
        tags = [
            tag.strip().strip('"').strip("'")
            for tag in inner.split(",")
            if tag.strip()
        ]
        if old_tag not in tags:
            return match.group(0)
        tags = [tag for tag in tags if tag != old_tag]
        if new_tag not in tags:
            tags.append(new_tag)
        count += 1
        rebuilt = ", ".join(tags)
        return f"Tags: [{rebuilt}]" if bracketed else f"Tags: {rebuilt}"

    new_content = re.sub(r"(?m)^Tags:\s*(.+?)\.?$", replace_line, content)
    if count and not dry_run:
        MANIFEST_PATH.write_text(new_content, encoding="utf-8")
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "old_tag",
        nargs="?",
        help="tag to replace; omit both positionals for inventory",
    )
    parser.add_argument("new_tag", nargs="?", help="replacement tag")
    parser.add_argument("--dry-run", action="store_true", help="list changes without writing")
    args = parser.parse_args()

    if args.old_tag is None and args.new_tag is None:
        return inventory()
    if not args.old_tag or not args.new_tag:
        print(
            "ERRO: forneça old_tag e new_tag juntos; sem argumentos o script mostra o inventário.",
            file=sys.stderr,
        )
        return 1
    if args.old_tag == args.new_tag:
        print("ERRO: tag antiga e nova são iguais.", file=sys.stderr)
        return 1

    changed_pages = []
    for directory in PAGE_DIRS:
        if not directory.exists():
            continue
        for path in sorted(directory.glob("*.md")):
            if retag_page(path, args.old_tag, args.new_tag, args.dry_run):
                changed_pages.append(path)
    manifest_count = retag_manifest(args.old_tag, args.new_tag, args.dry_run)

    verb = "seriam alteradas" if args.dry_run else "alteradas"
    action = "Would retag" if args.dry_run else "Retagged"
    for path in changed_pages:
        print(f"{action}: {relative_display(path)}")
    print(
        f"\n{len(changed_pages)} página(s) {verb}; "
        f"{manifest_count} entrada(s) de manifest.md {verb}."
    )
    if changed_pages or manifest_count:
        if args.dry_run:
            print("Dry-run — nada foi escrito.")
        else:
            print("Rode `python scripts/build_index.py` para regenerar tags_in_use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
