#!/usr/bin/env python3
"""
check_dedupe.py - Relatório de quase-duplicatas no corpus inteiro, em 4
classes: títulos de essays, títulos de concepts/entities, tags (acento/caixa/
hífen/singular-plural sobre tags_in_use) e referências repetidas entre
essays diferentes. Só lista candidatos - nunca funde nem apaga.

Lê:
    wiki/{essays,concepts,entities,insights}/*.md  (títulos, tags, referências)

Gera:
    stdout (relatório agrupado) ou JSON com --json

Uso:
    python scripts/check_dedupe.py                  # relatório completo
    python scripts/check_dedupe.py --json           # saída JSON
    python scripts/check_dedupe.py --threshold 0.9  # similaridade mínima

Flags:
    --threshold N   similaridade fuzzy mínima (default: 0.85)
    --json          saída JSON para parse programático
"""

import argparse
import difflib
import json
import re
import sys
import unicodedata
from collections import defaultdict

import console_encoding  # noqa: F401  (UTF-8 no console; ver o módulo)
from build_references import (
    collect_essay_references,
    normalize_citation,
    normalize_url,
)
from check_references import TAIL_LINK_RE, citation_and_note
from check_title import normalize as normalize_title
from repo_paths import CODE_ROOT, DATA_ROOT, WIKI_ROOT

ROOT_DIR = CODE_ROOT
ESSAYS_DIR = WIKI_ROOT / "essays"
CONCEPTS_DIR = WIKI_ROOT / "concepts"
ENTITIES_DIR = WIKI_ROOT / "entities"
INDEX_JSON = WIKI_ROOT / "index.json"

DEFAULT_THRESHOLD = 0.85

# Pares que já foram apresentados pelo /organize e revisados pelo Usuário como
# conceitos/pessoas distintos. A exceção é simétrica e se aplica apenas ao
# dedupe de títulos; tags e referências continuam usando as regras normais.
REVIEWED_TITLE_EXCEPTIONS = (
    ("Modelo de Influxo de Pitt–Peters", "Modelo de Influxo de Peters–He"),
    ("David Albert", "David Hilbert"),
    ("Evan Thompson", "Ken Thompson"),
)
REVIEWED_TITLE_EXCEPTION_KEYS = {
    frozenset((normalize_title(a), normalize_title(b)))
    for a, b in REVIEWED_TITLE_EXCEPTIONS
}


def load(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def get_h1(content):
    m = re.search(r"(?m)^# (.+)", content)
    return m.group(1).strip() if m else None


def titles_in(directory):
    """(título, caminho relativo) de cada página de um diretório."""
    if not directory.is_dir():
        return []
    out = []
    for path in sorted(directory.glob("*.md")):
        title = get_h1(load(path)) or path.stem
        out.append((title, path.relative_to(DATA_ROOT).as_posix()))
    return out


def normalize_tag(tag):
    """Acento, caixa, hífen e plural — a heurística que era aplicada a Categoria."""
    t = unicodedata.normalize("NFKD", tag)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower().replace("-", " ").replace("_", " ")
    t = re.sub(r"\s+", " ", t).strip()
    # Plural do português: -oes/-aes/-ais/-eis/-is/-ns/-es/-s, do mais
    # específico para o mais geral, para "razoes" e "razao" colidirem.
    for suffix, singular in (("oes", "ao"), ("aes", "ao"), ("ais", "al"), ("eis", "el")):
        if t.endswith(suffix):
            return t[: -len(suffix)] + singular
    if t.endswith("ns"):
        return t[:-2] + "m"
    if t.endswith("es") and len(t) > 4:
        return t[:-2]
    if t.endswith("s") and len(t) > 3:
        return t[:-1]
    return t


ORDINAL_RE = re.compile(r"\b([ivx]+|\d+)\b")


def differ_only_by_ordinal(a, b):
    """"Erro Tipo I" e "Erro Tipo II" são conceitos distintos, não duplicatas.

    Numeral romano ou arábico é justamente o que separa páginas de uma série
    (Erro Tipo I/II, Lei 1/2, Parte 3), e é também a diferença de menor peso
    para o difflib — a combinação produz falso positivo com alta similaridade.
    """
    ordinals_a = ORDINAL_RE.findall(a)
    ordinals_b = ORDINAL_RE.findall(b)
    if ordinals_a == ordinals_b:
        return False
    return ORDINAL_RE.sub("#", a) == ORDINAL_RE.sub("#", b)


def is_reviewed_title_exception(a, b):
    """True quando o par de títulos já foi revisado como não duplicado."""
    key = frozenset((normalize_title(a), normalize_title(b)))
    return key in REVIEWED_TITLE_EXCEPTION_KEYS


def near_duplicate_pairs(items, key, threshold):
    """Pares (a, b) cujas chaves normalizadas batem ou passam do threshold."""
    pairs = []
    normalized = [(key(item), item) for item in items]
    for i in range(len(normalized)):
        norm_a, item_a = normalized[i]
        if not norm_a:
            continue
        for j in range(i + 1, len(normalized)):
            norm_b, item_b = normalized[j]
            if not norm_b:
                continue
            if norm_a == norm_b:
                pairs.append((item_a, item_b, 1.0))
                continue
            if differ_only_by_ordinal(norm_a, norm_b):
                continue
            ratio = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()
            if ratio >= threshold:
                pairs.append((item_a, item_b, round(ratio, 3)))
    return pairs


def check_titles(directory_pairs, threshold):
    """Quase-duplicatas de título dentro de cada grupo de diretórios."""
    items = []
    for directory in directory_pairs:
        items.extend(titles_in(directory))
    pairs = near_duplicate_pairs(items, lambda it: normalize_title(it[0]), threshold)
    pairs = [
        (a, b, ratio)
        for a, b, ratio in pairs
        if not is_reviewed_title_exception(a[0], b[0])
    ]
    return [
        {
            "a": {"title": a[0], "path": a[1]},
            "b": {"title": b[0], "path": b[1]},
            "similarity": ratio,
        }
        for a, b, ratio in pairs
    ]


def load_tags_in_use():
    if not INDEX_JSON.exists():
        return None
    data = json.loads(load(INDEX_JSON))
    tags = data.get("tags_in_use")
    if isinstance(tags, dict):
        return sorted(tags.keys())
    return sorted(tags or [])


def check_tags(threshold):
    tags = load_tags_in_use()
    if tags is None:
        return None
    pairs = near_duplicate_pairs(tags, normalize_tag, threshold)
    return [{"a": a, "b": b, "similarity": ratio} for a, b, ratio in pairs]


def reference_core(citation):
    """Núcleo bibliográfico, sem nota contextual nem o `[Link]` final.

    A mesma obra pode ter notas diferentes em essays diferentes; isso não é
    divergência bibliográfica e não deve aparecer como candidato de dedupe.
    """
    text = TAIL_LINK_RE.sub("", citation).rstrip()
    core, _note = citation_and_note(text)
    return normalize_citation(core)


def check_references(threshold):
    """Mesma fonte citada em essays diferentes com grafia distinta."""
    by_url = defaultdict(list)   # url normalizada -> [(slug, citação)]
    citations = []               # (slug, citação) para o fuzzy sem URL

    for path in sorted(ESSAYS_DIR.glob("*.md")):
        slug, _title, refs = collect_essay_references(path)
        for ref in refs:
            citation = ref["citation_aiaa"]
            if ref["url"]:
                by_url[normalize_url(ref["url"])].append((slug, citation))
            else:
                citations.append((slug, citation))

    findings = []

    # Mesma URL, essays diferentes, citação escrita de forma diferente.
    for url, occurrences in sorted(by_url.items()):
        slugs = {slug for slug, _ in occurrences}
        variants = {reference_core(c): c for _, c in occurrences}
        if len(slugs) > 1 and len(variants) > 1:
            findings.append(
                {
                    "kind": "mesma-url",
                    "url": url,
                    "essays": sorted(slugs),
                    "variants": sorted(variants.values()),
                }
            )

    # Sem URL: citação quase-idêntica em essays diferentes.
    for a, b, ratio in near_duplicate_pairs(
        citations, lambda it: reference_core(it[1]), threshold
    ):
        if a[0] == b[0]:
            continue  # mesmo essay é DUPLICATE_REFERENCIA, do check_references.py
        if reference_core(a[1]) == reference_core(b[1]):
            # Mesma citação, caractere a caractere, em essays diferentes: é a
            # mesma obra corretamente reutilizada (ver conventions/SKILL.md,
            # "procure a mesma fonte em wiki/references.md antes de redigir
            # uma nova"), não grafia divergente. build_references.py já funde
            # isso numa entrada só via normalize_citation; reportar aqui de
            # novo é ruído sem decisão nenhuma para o Usuário tomar.
            continue
        findings.append(
            {
                "kind": "citacao-parecida",
                "url": None,
                "essays": sorted({a[0], b[0]}),
                "variants": [a[1], b[1]],
                "similarity": ratio,
            }
        )

    return findings


def run(threshold):
    return {
        "threshold": threshold,
        "essay_titles": check_titles([ESSAYS_DIR], threshold),
        "support_titles": check_titles([CONCEPTS_DIR, ENTITIES_DIR], threshold),
        "tags": check_tags(threshold),
        "references": check_references(threshold),
    }


def print_report(result):
    def header(title, count):
        print(f"\n{'─' * 60}")
        print(f"{title}: {count} candidato(s)")

    header("1. Títulos de essays", len(result["essay_titles"]))
    for item in result["essay_titles"]:
        print(f"   • {item['a']['title']}")
        print(f"     {item['b']['title']}   (similaridade {item['similarity']})")
        print(f"     {item['a']['path']}  |  {item['b']['path']}")

    header("2. Títulos de concepts/entities", len(result["support_titles"]))
    for item in result["support_titles"]:
        print(f"   • {item['a']['title']}")
        print(f"     {item['b']['title']}   (similaridade {item['similarity']})")
        print(f"     {item['a']['path']}  |  {item['b']['path']}")

    if result["tags"] is None:
        print(f"\n{'─' * 60}")
        print("3. Tags: wiki/index.json não existe — rode `python scripts/build_index.py`")
    else:
        header("3. Tags", len(result["tags"]))
        for item in result["tags"]:
            print(f"   • {item['a']}  ~  {item['b']}   (similaridade {item['similarity']})")

    header("4. Referências entre essays diferentes", len(result["references"]))
    for item in result["references"]:
        if item["kind"] == "mesma-url":
            print(f"   • mesma URL, citações divergentes: {item['url']}")
        else:
            print(f"   • citações quase-idênticas (similaridade {item['similarity']})")
        print(f"     essays: {', '.join(item['essays'])}")
        for variant in item["variants"]:
            print(f"       - {variant}")

    total = (
        len(result["essay_titles"])
        + len(result["support_titles"])
        + len(result["tags"] or [])
        + len(result["references"])
    )
    print(f"\n{'=' * 60}")
    print(f"{total} candidato(s) a quase-duplicata no total.")
    print(
        "Este script não funde nem deleta nada. Cada candidato precisa de "
        "decisão do Usuário, caso a caso, via /organize."
    )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--json", action="store_true", help="saída JSON para a skill parsear")
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"similaridade mínima para reportar um par (padrão {DEFAULT_THRESHOLD})",
    )
    args = parser.parse_args()

    if not ESSAYS_DIR.is_dir():
        print(f"ERRO: {ESSAYS_DIR} não existe", file=sys.stderr)
        sys.exit(1)

    result = run(args.threshold)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print_report(result)


if __name__ == "__main__":
    main()
