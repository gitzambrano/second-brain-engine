#!/usr/bin/env python3
"""build_references.py - Agrega e consolida a seção '## Referências' de todos os essays.

Extrai todas as citações bibliográficas estruturadas, deduplica fontes, valida URLs
e constrói o índice geral de referências da wiki.

Escopo:
    Geração mecânica de catálogo bibliográfico em DATA_ROOT/wiki/. Artefato derivado gerado
    a partir das seções '## Referências' dos ensaios. Nunca editar à mão.

Entradas (Inputs):
    DATA_ROOT/wiki/essays/*.md.

Saídas (Outputs):
    wiki/references.json  Estrutura normalizada com ID, citação, autor, ano, link e backlinks.
    wiki/references.md    Catálogo navegável em Markdown de todas as fontes citadas.
    Exit code: 0 em sucesso, 1 em erro de parsing.

Uso:
    python scripts/build_references.py        # reconstrói catálogo bibliográfico
"""

import datetime
import json
import re
import sys
import unicodedata
from urllib.parse import urlparse

import console_encoding  # noqa: F401  (UTF-8 no console; ver o módulo)
from repo_paths import CODE_ROOT, DATA_ROOT, WIKI_ROOT

ROOT_DIR = CODE_ROOT
ESSAYS_DIR = WIKI_ROOT / "essays"
OUTPUT_JSON_PATH = WIKI_ROOT / "references.json"
OUTPUT_MD_PATH = WIKI_ROOT / "references.md"

DOMAIN_GROUPS = (
    ("doi.org", "doi"),
    ("nasa.gov", "nasa"),
    ("ntrs.nasa.gov", "nasa"),
    ("aiaa.org", "aiaa"),
    ("plato.stanford.edu", "sep"),
    ("wikipedia.org", "wikipedia"),
    ("github.com", "github"),
)

DOMAIN_GROUP_LABELS = {
    "doi": "DOI",
    "nasa": "NASA",
    "aiaa": "AIAA",
    "sep": "Stanford Encyclopedia of Philosophy",
    "wikipedia": "Wikipedia",
    "github": "GitHub",
    "institucional": "Institucional",
    "sem-link": "Sem link",
}

REFERENCE_LINE_RE = re.compile(r"^\[(\d+)\]\s+(.+)$")
LINKED_RE = re.compile(r"^\[(?P<text>.+?)\]\((?P<url>(?:[^()\s]|\([^()\s]*\))+)\)(?P<trailing>.*)$")
CANONICAL_LINK_RE = re.compile(r"\[[Ll]ink\]\((?P<url>https?://(?:[^()\s]|\([^()\s]*\))+)\)")
LINKED_TITLE_RE = re.compile(r"\[(?P<title>\*[^*\n]+\*)\]\((?P<url>https?://(?:[^()\s]|\([^()\s]*\))+)\)")
ANY_MD_LINK_RE = re.compile(r"\[[^\]]*\]\(https?://")
FIRST_ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")

# Nome do autor para ordenação: o que vem antes da primeira vírgula, sem
# artigo inicial e sem marcação, para "Barrow, J. D." cair em B.
SORT_KEY_STRIP_RE = re.compile(r"^[\*_\[\s]+|^(?:o|a|os|as|the|an|el|la)\s+", re.IGNORECASE)


def load(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def get_h1(content):
    m = re.search(r"(?m)^# (.+)", content)
    return m.group(1).strip() if m else None


def normalize_citation(text):
    """Normaliza citação para dedup exato (acento/case/espaço) quando não há URL."""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = t.lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t


def normalize_url(url):
    """Normaliza URL pra dedup: sem query/fragment, sem barra final, sem www."""
    p = urlparse(url.strip())
    netloc = p.netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    path = p.path.rstrip("/")
    return f"{p.scheme}://{netloc}{path}"


def domain_group_for(url):
    netloc = urlparse(url).netloc.lower()
    for suffix, group in DOMAIN_GROUPS:
        if netloc == suffix or netloc.endswith("." + suffix):
            return group
    return "institucional"


def extract_referencias_section(content):
    """Corpo de `## Referências`: da heading até a próxima `## ` ou fim do arquivo."""
    m = re.search(r"(?m)^## Referências\s*$", content)
    if not m:
        return None
    rest = content[m.end():]
    next_h2 = re.search(r"(?m)^## ", rest)
    return rest[: next_h2.start()] if next_h2 else rest


def parse_reference_line(rest_of_line):
    """Extrai (citation_aiaa, url, has_link) de uma entrada `[N] ...`."""
    # Padrão atual: a URL da obra mora no âncora `[link]`, logo depois do
    # título em itálico. Qualquer outro link da entrada é de glossário, dentro
    # da nota, e não identifica a fonte.
    m = CANONICAL_LINK_RE.search(rest_of_line)
    if m:
        return rest_of_line.strip(), m.group("url").strip(), True


    # Formatos anteriores, ainda presentes no corpus até `fix_lint.py` passar:
    # link envolvendo a citação inteira, ou envolvendo só o título.
    m = LINKED_RE.match(rest_of_line)
    if m:
        citation = m.group("text").strip()
        url = m.group("url").strip()
        return citation, url, True

    m = LINKED_TITLE_RE.search(rest_of_line)
    if m:
        return rest_of_line.strip(), m.group("url").strip(), True
    # Sem link envolvendo a citação inteira: o texto até " — " *pode* ser a
    # citação, com uma nota depois. Mas nem todo travessão separa nota — no
    # arranjo `[N] Autor — [*Título*](url). Container, Ano.` ele separa o autor
    # do resto da própria citação, e cortar ali reduziria a citação ao nome do
    # autor. O título em itálico é o desempate: se o pedaço antes do travessão
    # não tem itálico, ele não é uma citação completa, e a linha inteira é.
    head, sep, _tail = rest_of_line.partition(" — ")
    citation = head.strip() if sep and re.search(r"\*[^*]+\*", head) else rest_of_line.strip()
    return citation, None, False


def collect_essay_references(path):
    content = load(path)
    title = get_h1(content) or path.stem
    slug = path.stem
    section = extract_referencias_section(content)
    refs = []
    if not section:
        return slug, title, refs
    for line in section.splitlines():
        line = line.strip()
        if not line:
            continue
        m = REFERENCE_LINE_RE.match(line)
        if not m:
            continue
        citation, url, has_link = parse_reference_line(m.group(2))
        refs.append({"citation_aiaa": citation, "url": url, "has_link": has_link})
    return slug, title, refs


def sort_key(citation):
    """Chave alfabética estável: acento e marcação não deslocam a entrada."""
    t = re.sub(r"\[[Ll]ink\]\([^\)]*\)", "", citation)
    t = SORT_KEY_STRIP_RE.sub("", t).strip()
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", "", t.lower()).strip()


def title_key(citation):
    """Título da obra, normalizado — a chave que identifica a mesma obra.

    A dedup por URL não basta: a mesma obra costuma aparecer com link num
    essay e sem link em outro, o que gera duas chaves e duas linhas no
    arquivo gerado, com grafias diferentes. O título em itálico é o que as
    duas versões têm em comum.
    """
    m = FIRST_ITALIC_RE.search(re.sub(r"\[[Ll]ink\]\([^\)]*\)", "", citation))
    if not m:
        return None
    t = re.sub(r"\[([^\]]*)\]\([^\)]*\)", r"\1", m.group(1))
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9]", "", t.lower())
    return t if len(t) > 12 else None


def merge_by_title(references):
    """Funde entradas que são a mesma obra, mantendo a versão mais informativa.

    Só o artefato gerado é consolidado; os essays continuam como estão. Uniformizar
    a citação na origem é decisão editorial, e sai por `/linkify`.
    """
    por_titulo = {}
    saida = []
    for ref in references:
        chave = title_key(ref["citation_aiaa"])
        if chave is None:
            saida.append(ref)
            continue
        anterior = por_titulo.get(chave)
        if anterior is None:
            por_titulo[chave] = ref
            saida.append(ref)
            continue
        for slug in ref["cited_by"]:
            if slug not in anterior["cited_by"]:
                anterior["cited_by"].append(slug)
        # A versão que vence é a que tem link; empatando, a mais completa.
        melhor = (bool(ref["url"]), len(ref["citation_aiaa"]))
        atual = (bool(anterior["url"]), len(anterior["citation_aiaa"]))
        if melhor > atual:
            anterior["citation_aiaa"] = ref["citation_aiaa"]
            anterior["url"] = ref["url"] or anterior["url"]
            anterior["has_link"] = anterior["has_link"] or ref["has_link"]
            anterior["domain_group"] = ref["domain_group"] or anterior["domain_group"]
    return saida


def build():
    entries = {}  # dedup key -> entry dict
    essays_seen = 0

    if ESSAYS_DIR.exists():
        for f in sorted(ESSAYS_DIR.glob("*.md")):
            if f.name == ".gitkeep":
                continue
            essays_seen += 1
            slug, title, refs = collect_essay_references(f)
            for ref in refs:
                if ref["url"]:
                    key = ("url", normalize_url(ref["url"]))
                    domain_group = domain_group_for(ref["url"])
                else:
                    key = ("text", normalize_citation(ref["citation_aiaa"]))
                    # Ausência de link não é um tipo de fonte: uma obra sem
                    # edição digital continua sendo livro, paper ou verbete.
                    # `domain_group` fica nulo, e a entrada aparece na lista
                    # junto com todas as outras, apenas sem a palavra "link".
                    domain_group = None

                if key not in entries:
                    entries[key] = {
                        "url": ref["url"],
                        "citation_aiaa": ref["citation_aiaa"],
                        "domain_group": domain_group,
                        "cited_by": [],
                        "has_link": ref["has_link"],
                    }
                entry = entries[key]
                if slug not in entry["cited_by"]:
                    entry["cited_by"].append(slug)

    references = merge_by_title(list(entries.values()))
    references.sort(key=lambda e: sort_key(e["citation_aiaa"]))
    return {
        "generated": datetime.date.today().isoformat(),
        "essays_scanned": essays_seen,
        "references": references,
    }


def render_references_md(data):
    lines = [
        "# Referências",
        "",
        f"_Artefato gerado — nunca edite à mão, rode `python scripts/build_references.py`. "
        f"{len(data['references'])} referência(s) única(s) em {data['essays_scanned']} essay(s), "
        f"gerado em {data['generated']}._",
        "",
    ]

    # Lista única em ordem alfabética. Sem agrupar por domínio: agrupar por onde
    # a obra está hospedada separaria o livro do paper do mesmo autor, e criava
    # um balde "Sem link" que dizia respeito à disponibilidade digital, não ao
    # tipo de fonte. Bibliografia se lê por autor.
    for ref in data["references"]:
        citation = ref["citation_aiaa"]
        # O âncora `[link]` só entra quando a citação não traz link nenhum.
        # Antes esta condição olhava só para `[link](...)`, e uma entrada cujo
        # título já era hyperlink recebia o âncora de novo, com a mesma URL —
        # o que produzia 93 linhas com o link repetido duas vezes.
        if ref["url"] and not ANY_MD_LINK_RE.search(citation):
            citation = f"{citation.rstrip()} [link]({ref['url']})"
        lines.append(f"- {citation}")
        # Markdown puro, sem HTML: a versão anterior abria um `<span>` de estilo
        # e nunca o fechava, e o Obsidian engolia o resto da entrada, incluindo
        # o link externo da obra. O arquivo é lido no Obsidian antes de qualquer
        # outro lugar, então ele manda no formato.
        lines.append(f"  `{', '.join(ref['cited_by'])}`")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main():
    data = build()
    WIKI_ROOT.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    with open(OUTPUT_MD_PATH, "w", encoding="utf-8") as f:
        f.write(render_references_md(data))

    no_link = sum(1 for r in data["references"] if not r["has_link"])
    print(f"Referências indexadas: {len(data['references'])} única(s) em {data['essays_scanned']} essay(s) "
          f"({no_link} sem link).")
    print(f"  {OUTPUT_JSON_PATH.relative_to(DATA_ROOT)}")
    print(f"  {OUTPUT_MD_PATH.relative_to(DATA_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
