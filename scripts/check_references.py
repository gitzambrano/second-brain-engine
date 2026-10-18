#!/usr/bin/env python3
"""check_references.py - Valida o conteúdo e a formatação da seção '## Referências'.

Audita a integridade bibliográfica dos ensaios:
- Numeração estrita e ordem crescente ([1], [2], ...).
- Todas as citações no corpo devem existir nas referências, e vice-versa.
- Presença de data de acesso para fontes mutáveis (links web, artigos online).
- Links válidos com esquema https:// ou doi.org.

Escopo:
    Validação read-only em DATA_ROOT/wiki/essays/*.md. Não modifica arquivos.

Entradas (Inputs):
    Arquivos de ensaio em DATA_ROOT/wiki/essays/*.md.
    Argumentos CLI opcionais:
        slug          Slug opcional de um ensaio específico para validar isoladamente
        --json        Emite diagnóstico formatado em JSON

Saídas (Outputs):
    Stdout: Lista de inconformidades bibliográficas agrupadas por ensaio e código.
    JSON: {"check": "references", "status": "pass"|"warn"|"fail", "issues": [...]}
    Exit code: 0 em conformidade, 1 se houver erros bibliográficos bloqueantes.

Uso:
    python scripts/check_references.py              # audita todos os ensaios
    python scripts/check_references.py meu-ensaio   # audita um ensaio específico
    python scripts/check_references.py --json       # saída estruturada em JSON
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import console_encoding  # noqa: F401  (UTF-8 no console; ver o módulo)
from build_references import (
    extract_referencias_section,
    normalize_url,
)
from repo_paths import CODE_ROOT, WIKI_ROOT

ROOT_DIR = CODE_ROOT
ESSAYS_DIR = WIKI_ROOT / "essays"

# `LINK_NOT_IN_REFERENCIAS` só vale para link que é de fato uma fonte. A regra 3
# de `## Estrutura obrigatória do essay` obriga link externo para todo termo
# técnico na primeira ocorrência, então a maioria esmagadora dos links do corpo é
# glossário (verbete de enciclopédia para um termo citado), não bibliografia —
# exigir entrada em `## Referências` para todos eles marcaria ~2000 falsos erros
# no corpus atual. Estes são os domínios/formatos que caracterizam uma obra
# citável. Para voltar ao comportamento estrito, esvazie esta tupla.
CITATION_LIKE = (
    "doi.org",
    "arxiv.org",
    "biorxiv.org",
    "ntrs.nasa.gov",
    "aiaa.org",
    "sciencedirect.com",
    "springer.com",
    "link.springer.com",
    "jstor.org",
    "nature.com",
    "science.org",
    "ieee.org",
    "ieeexplore.ieee.org",
    "acm.org",
    "dl.acm.org",
    "pubmed.ncbi.nlm.nih.gov",
    "journals.aps.org",
    "royalsocietypublishing.org",
)

# Padrão do link da obra: a palavra "Link", clicável, como **última coisa da
# entrada**, depois do ponto final. A citação inteira fica texto limpo — nenhum
# pedaço dela vira hyperlink — e o itálico do título fica legível, que
# sublinhado de link estragaria. Tudo num lugar só, fácil de varrer com o olho.
URL_PAT = r"https?://(?:[^()\s]|\([^()\s]*\))+"
# Aceita o "link" minúsculo de passadas anteriores, para fix_lint.py migrar.
TAIL_LINK_RE = re.compile(r"\[Link\]\((?P<url>" + URL_PAT + r")\)\s*$")
# Link envolvendo o título: `[*Título*](url)` e também `*[Título](url)*`.
ANY_MD_LINK_RE = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<url>" + URL_PAT + r")\)")

NUMBERED_RE = re.compile(r"^\[(\d+)\]\s+(.+)$")
BULLET_RE = re.compile(r"^[-*]\s+(.+)$")
MD_LINK_RE = re.compile(r"\[(?P<text>[^\]]*)\]\((?P<url>https?://(?:[^()\s]|\([^()\s]*\))+)\)")
# Itálico de verdade: um asterisco de cada lado, nunca dois. Sem os lookarounds
# esta regex entra dentro de `**negrito**` — casa o segundo `*` da abertura com
# o primeiro `*` do fechamento — e aí qualquer reescrita corrompe o texto.
ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
# Itálico Markdown com _underscore_ em vez de *asterisco* — variante válida do
# Markdown, mas fora do padrão AIAA da wiki (## Formato de "## Referências").
# Lookaround em `\w` (não em `_`) para não casar dentro de identificador tipo
# `nome_var` ou `x_1`: ali o caractere antes/depois do underscore é letra/dígito,
# então o boundary falha e a regex não entra.
UNDERSCORE_ITALIC_RE = re.compile(r"(?<!\w)_([^_\n]+)_(?!\w)")
DOUBLE_QUOTE_SPAN_RE = re.compile(r'["\u201c]([^"\u201d\n]+)["\u201d]')


def load(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def strip_fences(text):
    """Esvazia o interior de blocos ```...```, preservando a contagem de linhas.

    Sem isso, indexação Python (`q[0]`, `x[2]`) dentro de um bloco de código é
    lida como citação numérica `[N]`, e a bibliografia inteira acima daquele
    número aparece como `REFERENCIA_NAO_USADA`. Mesmo tratamento que
    `check_wiki.py` aplica às regras de prosa.
    """
    out, in_fence = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            out.append("")
        else:
            out.append("" if in_fence else line)
    return "\n".join(out)


def split_body(content):
    """Corpo argumentativo: sem frontmatter, sem `## Referências` em diante e
    sem o interior de blocos de código."""
    body = re.sub(r"(?s)\A---\r?\n.*?\r?\n---\r?\n", "", content, count=1)
    m = re.search(r"(?m)^## Referências\s*$", body)
    body = body[: m.start()] if m else body
    return strip_fences(body)


def citation_and_note(rest_of_line):
    """Separa a citação da nota opcional que vem depois de ' — '.

    Nem todo travessão separa nota: no arranjo `Autor — *Título*. Editora, Ano.`
    ele separa o autor do resto da própria citação, e cortar ali reduziria a
    citação ao nome do autor. O título em itálico desempata — se o pedaço antes
    do travessão não tem itálico, ele não é uma citação completa.
    """
    # O travessão candidato tem que estar FORA do itálico: títulos como
    # "*Aeronautical Design Standard — Performance Specification*" contêm um,
    # e cortar ali partiria o título ao meio e trataria metade dele como nota.
    procura = 0
    while True:
        pos = rest_of_line.find(" — ", procura)
        if pos == -1:
            return rest_of_line.strip(), None
        head = rest_of_line[:pos]
        if head.count("*") % 2 == 0 and ITALIC_RE.search(head):
            return head.strip(), rest_of_line[pos + 3 :].strip()
        procura = pos + 3


def is_citation_like(url):
    """A URL aponta para uma obra citável, e não para um verbete de glossário?"""
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    if urlparse(url).path.lower().endswith(".pdf"):
        return True
    return any(netloc == d or netloc.endswith("." + d) for d in CITATION_LIKE)


def has_italic_title(citation):
    """Todo título vai em itálico, sem exceção por tipo de fonte."""
    return any(m.group(1).strip() for m in ITALIC_RE.finditer(citation))


def has_underscore_title(citation):
    """Título marcado com `_underscore_` — itálico Markdown válido, mas fora
    do padrão AIAA da wiki (asterisco). Mecanicamente corrigível."""
    return any(m.group(1).strip() for m in UNDERSCORE_ITALIC_RE.finditer(citation))


def try_fix_quoted_title(citacao):
    """Converte um título entre aspas duplas para itálico — só quando é
    inequívoco: nenhum itálico (`*` ou `_`) já presente na citação, e
    EXATAMENTE um par de aspas duplas nela. Duas ou mais aspas na mesma
    citação podem ser nota/citação direta embutida, não o título — nesse
    caso retorna None e a entrada continua sinalizada para revisão manual.
    Nunca aplicado à nota (só recebe `citacao`, já separada de `nota` por
    `citation_and_note`), então uma aspa dentro da nota nunca é tocada aqui.
    """
    if has_italic_title(citacao) or has_underscore_title(citacao):
        return None
    spans = list(DOUBLE_QUOTE_SPAN_RE.finditer(citacao))
    if len(spans) != 1:
        return None
    inner = spans[0].group(1).strip()
    if not inner:
        return None
    m = spans[0]
    return citacao[: m.start()] + f"*{inner}*" + citacao[m.end() :]


def parse_entries(section):
    """Cada linha não vazia da seção, classificada por formato."""
    entries = []
    for lineno, raw in enumerate(section.splitlines()):
        line = raw.strip()
        if not line:
            continue
        m = NUMBERED_RE.match(line)
        if m:
            entries.append(
                {"kind": "numbered", "number": int(m.group(1)), "rest": m.group(2), "raw": line}
            )
            continue
        m = BULLET_RE.match(line)
        if m:
            entries.append({"kind": "bullet", "number": None, "rest": m.group(1), "raw": line})
            continue
        entries.append({"kind": "unknown", "number": None, "rest": line, "raw": line})
    return entries


def check_essay(path):
    """Audita a seção `## Referências` de um essay.

    A ausência da seção não é reportada aqui: NO_REFERENCIAS é responsabilidade
    de check_wiki.py.
    """
    content = load(path)
    issues = []
    section = extract_referencias_section(content)

    if section is None:
        # NO_REFERENCIAS é responsabilidade de check_wiki.py.
        return {"name": path.name, "slug": path.stem, "issues": issues, "skipped": True}

    entries = parse_entries(section)
    body = split_body(content)

    seen_urls = {}
    for position, entry in enumerate(entries, start=1):
        label = entry["raw"][:70]

        if entry["kind"] != "numbered":
            issues.append(
                {
                    "code": "REFERENCIA_FORMATO_INVALIDO",
                    "severity": "ERROR",
                    "fixable": entry["kind"] == "bullet",
                    "message": (
                        f"entrada {position} não está no padrão `[N] ...`: {label}"
                        + ("  (corrigível com fix_lint.py)" if entry["kind"] == "bullet" else "")
                    ),
                }
            )
            continue

        if entry["number"] != position:
            issues.append(
                {
                    "code": "REFERENCIA_FORMATO_INVALIDO",
                    "severity": "ERROR",
                    "fixable": True,
                    "message": (
                        f"numeração fora de ordem: entrada {position} está como "
                        f"[{entry['number']}]  (corrigível com fix_lint.py)"
                    ),
                }
            )

        # A URL da obra é a do âncora `[Link]` no fim da entrada. A citação em
        # si não pode ter link nenhum; o que houver na nota é glossário.
        no_fim = TAIL_LINK_RE.search(entry["rest"])
        url = no_fim.group("url") if no_fim else None
        has_link = bool(url)
        citacao_sem_nota, _nota = citation_and_note(entry["rest"])
        links_na_citacao = [
            m.group("url")
            for m in ANY_MD_LINK_RE.finditer(TAIL_LINK_RE.sub("", citacao_sem_nota))
        ]

        if not has_italic_title(entry["rest"]):
            if has_underscore_title(entry["rest"]):
                issues.append(
                    {
                        "code": "REFERENCIA_FORMATO_INVALIDO",
                        "severity": "ERROR",
                        "fixable": True,
                        "message": (
                            f"entrada [{entry['number']}] usa itálico com _underscore_ em vez de "
                            f"*asterisco*: {label}  (corrigível com fix_lint.py)"
                        ),
                    }
                )
            elif try_fix_quoted_title(citacao_sem_nota) is not None:
                issues.append(
                    {
                        "code": "REFERENCIA_FORMATO_INVALIDO",
                        "severity": "ERROR",
                        "fixable": True,
                        "message": (
                            f"entrada [{entry['number']}] tem título entre aspas em vez de "
                            f"itálico: {label}  (corrigível com fix_lint.py)"
                        ),
                    }
                )
            else:
                issues.append(
                    {
                        "code": "REFERENCIA_FORMATO_INVALIDO",
                        "severity": "ERROR",
                        "fixable": False,
                        "message": f"entrada [{entry['number']}] sem título em itálico: {label}",
                    }
                )
        elif links_na_citacao:
            issues.append(
                {
                    "code": "REFERENCIA_FORMATO_INVALIDO",
                    "severity": "ERROR",
                    "fixable": True,
                    "message": (
                        f"entrada [{entry['number']}]: link dentro da citação; o link é a "
                        f"palavra `[Link]` no fim da entrada  (corrigível com "
                        f"fix_lint.py): {label}"
                    ),
                }
            )

        if not has_link and not links_na_citacao:
            issues.append(
                {
                    "code": "REFERENCIA_SEM_LINK",
                    "severity": "WARNING",
                    "fixable": False,
                    "message": (
                        f"entrada [{entry['number']}] sem link; só é legítimo para fonte "
                        f"sem edição digital confiável: {label}"
                    ),
                }
            )
        # Dedup só é possível com a URL da obra. Entrada cuja única URL está
        # solta na nota já foi sinalizada como formato inválido acima; sem
        # âncora `[link]` não dá para dizer qual das URLs identifica a fonte.
        if url:
            key = normalize_url(url)
            if key in seen_urls:
                issues.append(
                    {
                        "code": "DUPLICATE_REFERENCIA",
                        "severity": "ERROR",
                        "fixable": False,
                        "message": (
                            f"entradas [{seen_urls[key]}] e [{entry['number']}] apontam "
                            f"para a mesma URL normalizada: {key}"
                        ),
                    }
                )
            else:
                seen_urls[key] = entry["number"]


    for m in MD_LINK_RE.finditer(body):
        url = m.group("url")
        if not is_citation_like(url):
            continue
        key = normalize_url(url)
        if key not in seen_urls:
            issues.append(
                {
                    "code": "LINK_NOT_IN_REFERENCIAS",
                    "severity": "ERROR",
                    "fixable": False,
                    "message": (
                        f"link do corpo sem entrada em `## Referências`: "
                        f"{m.group('url')}"
                    ),
                }
            )

    return {"name": path.name, "slug": path.stem, "issues": issues, "skipped": False}


def resolve_essay(slug):
    """Resolve um slug para o arquivo do essay, aceitando também um caminho direto."""
    p = Path(slug)
    if p.exists():
        return p.resolve()
    for ext in ("", ".md"):
        candidate = ESSAYS_DIR / (slug + ext)
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"Essay '{slug}' não encontrado em {ESSAYS_DIR} nem como caminho direto"
    )


def build_parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "slug", nargs="?", default=None,
        help="Checa apenas este essay (slug, nome do arquivo, ou caminho completo).",
    )
    p.add_argument(
        "--file", "-f", dest="file_slug", metavar="SLUG", default=None,
        help="Alias de compatibilidade para o slug posicional.",
    )
    p.add_argument("--json", action="store_true", help="saída JSON para a skill parsear")
    return p


def main():
    args = build_parser().parse_args()
    target = args.slug or args.file_slug

    if target:
        try:
            essay_paths = [resolve_essay(target)]
        except FileNotFoundError as e:
            print(f"ERRO: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        essay_paths = sorted(ESSAYS_DIR.glob("*.md"))
        if not essay_paths:
            print(f"Nenhum essay encontrado em {ESSAYS_DIR}", file=sys.stderr)
            sys.exit(0)

    results = [check_essay(p) for p in essay_paths]

    if args.json:
        print(json.dumps({"essays": results}, ensure_ascii=False, indent=2))
        return

    severity_order = {"ERROR": 0, "WARNING": 1}
    icons = {"ERROR": "❌", "WARNING": "⚠️ "}
    by_code = {}
    total_issues = 0
    clean = 0

    for result in results:
        if result["skipped"]:
            continue
        issues = result["issues"]
        if not issues:
            print(f"✅ {result['name']}")
            clean += 1
            continue
        print(f"\n{'─' * 60}")
        print(f"📄 {result['name']}")
        for issue in sorted(issues, key=lambda x: severity_order.get(x["severity"], 9)):
            print(f"   {icons.get(issue['severity'], '•')} [{issue['code']}] {issue['message']}")
            by_code[issue["code"]] = by_code.get(issue["code"], 0) + 1
        total_issues += len(issues)

    checked = sum(1 for r in results if not r["skipped"])
    print(f"\n{'=' * 60}")
    print(f"Resultado: {clean}/{checked} essay(s) limpo(s), {total_issues} issue(s) no total")
    for code, count in sorted(by_code.items(), key=lambda kv: -kv[1]):
        print(f"  {code}: {count}")
    if by_code.get("REFERENCIA_FORMATO_INVALIDO"):
        print("\nParte disso é mecânica: `python scripts/fix_lint.py`.")


if __name__ == "__main__":
    main()
