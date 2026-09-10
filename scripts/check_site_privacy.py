#!/usr/bin/env python3
"""
Impõe o que o site público pode e o que não pode expor.

A decisão do Usuário, que este checador codifica:

    público  título, resumo, tags, datas, status de rascunho, conexões e a URL
             externa de uma entrada de bibliografia — para a base inteira
    privado  o corpo de qualquer página, qualquer caminho para dentro do repo
             privado, e link que abra algo que não seja um essay autorizado

Ou seja: um essay não publicado é catalogado e mapeado, por título e resumo, e
não abre. Um site estático não esconde o que serve: tudo na linha "público"
acima é legível por qualquer pessoa.

Os mapas embutem os dados como base64 deflacionado dentro do HTML, então este
checador infla essa carga e inspeciona os nós de verdade, em vez de procurar
texto com grep. Cada nó é validado contra a allowlist de
`build_public_map.assert_public_schema`: chave fora do schema reprova.

O corpo de cada essay privado é varrido inteiro, em n-gramas deslizantes, contra
todos os arquivos publicados — ver `audit_bodies` para o tamanho da janela e o
desconto do que já é público.

Default sem argumentos: auditar SITE_ROOT e reportar PASS/FAIL.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import zlib

from build_public_map import assert_public_schema
from repo_paths import SITE_ROOT
from site_common import collect_all, strip_public_body
from unidecode import unidecode

MAP_FILES = ("graph.html", "sphere.html")
# `graph.json` saiu daqui junto com a publicação: o payload que o navegador
# lê está embutido nos mapas, e é ele que `audit_maps` infla e audita. Exigir
# o arquivo solto reprovaria todo site correto.
MACHINE_FILES = ("search-index.json", "site-manifest.json")
SCANNED_SUFFIXES = {".html", ".json"}

EMBEDDED_PAYLOAD = re.compile(r'id="sb-graph-data">([^<]*)<')

# --- Varredura de corpo -----------------------------------------------------
FINGERPRINT_WORDS = 12
WORD_RE = re.compile(r"[a-z0-9]+")
REFERENCES_RE = re.compile(r"(?ms)^##\s+Refer[êe]ncias\s*\n.*?(?=^##\s+|\Z)")
# URL não é prosa. Um endereço citado no corpo de um essay privado aparece,
# legitimamente, no nó de referência que o mapa publica — e depois de
# normalizado (`https ocw mit edu courses 16 346 astrodynamics fall 2008`) ele
# vira uma sequência longa de "palavras" que casa perfeitamente. Duas citações
# assim acusavam vazamento no artefato que as publica de propósito. O texto do
# link continua sendo prosa e continua sendo comparado; só o alvo sai.
URL_RE = re.compile(r"<?https?://[^\s<>)\]\"']+>?")
# O nome de um asset segue `<slug>_figN`. Quando o slug é o H1 inteiro,
# ele pode ter 12+ palavras e coincidir com o título (que é metadado público)
# em `index.html` ou no catálogo de busca. O alvo do Markdown não é prosa e
# não deve compor a impressão digital; o alt continua sendo inspecionado.
IMAGE_TARGET_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")

# A generated link or metadata value must never point into the private
# repository. Prose may legitimately *mention* these paths — several essays are
# about this very system — so the check inspects link targets and JSON path
# values, not free text.
PRIVATE_TARGET = re.compile(
    r"""(?:href|src|action|data-[\w-]+)\s*=\s*["']([^"']*)["']"""
    r"""|"(?:url|path|file|htmlFile)"\s*:\s*"([^"]*)\"""",
    re.I,
)
PRIVATE_PATH = re.compile(r"(?:\A|/|\.\./)(?:data/)?(?:wiki|plan|raw|output)/", re.I)
EXTERNAL_URL = re.compile(r"\s*(?:[a-z][a-z0-9+.-]*:|//)", re.I)


def inflate(encoded: str) -> dict:
    """Undo `_deflate_b64` from build_graph: raw deflate, base64 wrapped."""
    return json.loads(zlib.decompress(base64.b64decode(encoded), -15))


def audit_nodes(nodes, allowed: set[str], where: str) -> list[str]:
    """The map may name everything; it may not open or embody anything."""
    errors: list[str] = []
    for node in nodes:
        node_id = node.get("id")
        slug = str(node_id or "").partition(":")[2]
        readable = bool(node.get("public"))

        if readable and slug not in allowed:
            errors.append(f"{where}: node marked public but not authorized: {node_id}")

        link = str(node.get("htmlFile") or "")
        if link and (not readable or link != f"essays/{slug}.html"):
            errors.append(f"{where}: unauthorized read link: {node_id} -> {link}")

        url = str(node.get("url") or "")
        if url and not url.startswith(("http://", "https://")):
            errors.append(f"{where}: non-external url: {node_id} -> {url}")

    # Allowlist, não blacklist: qualquer chave fora de `PUBLIC_NODE_FIELDS`
    # reprova, mesmo uma que ninguém previu. Uma lista de campos proibidos só
    # pega o vazamento que já foi imaginado.
    errors.extend(f"{where}: {e}" for e in assert_public_schema(nodes))
    return errors


def audit_maps(allowed: set[str]) -> list[str]:
    errors: list[str] = []

    data = SITE_ROOT / "graph.json"
    if data.exists():
        payload = json.loads(data.read_text(encoding="utf-8"))
        errors.extend(audit_nodes(payload.get("nodes", []), allowed, "graph.json"))

    for name in MAP_FILES:
        path = SITE_ROOT / name
        if not path.exists():
            errors.append(f"missing {name}")
            continue
        match = EMBEDDED_PAYLOAD.search(path.read_text(encoding="utf-8"))
        if not match:
            errors.append(f"{name}: embedded graph payload not found")
            continue
        try:
            payload = inflate(match.group(1))
        except (ValueError, zlib.error) as exc:
            errors.append(f"{name}: embedded payload unreadable: {exc}")
            continue
        errors.extend(audit_nodes(payload.get("nodes", []), allowed, name))
    return errors


def audit_catalogue(allowed: set[str]) -> list[str]:
    """The reading index catalogues everything; only the authorized carry text."""
    errors: list[str] = []
    path = SITE_ROOT / "search-index.json"
    if not path.exists():
        return errors
    for entry in json.loads(path.read_text(encoding="utf-8")):
        slug = entry.get("slug")
        if entry.get("published"):
            if slug not in allowed:
                errors.append(f"search index: published but not authorized: {slug}")
        else:
            if entry.get("text"):
                errors.append(f"search index: body text for unpublished essay: {slug}")
            if entry.get("url"):
                errors.append(f"search index: link for unpublished essay: {slug}")
    return errors


def audit_pages(allowed: set[str]) -> list[str]:
    """Only an authorized essay may have a rendered page."""
    errors: list[str] = []
    essays_dir = SITE_ROOT / "essays"
    if essays_dir.exists():
        extra = {p.stem for p in essays_dir.glob("*.html")} - allowed
        if extra:
            errors.append(f"rendered page for unauthorized essay: {sorted(extra)}")
    return errors


def normalize_words(text: str) -> list[str]:
    """Reduz o texto à sequência de palavras que sobrevive a uma reformatação.

    Um vazamento não chega ao site idêntico ao arquivo: passa por markdown,
    escape de HTML, JSON, quebra de linha diferente, aspas curvas, e às vezes
    perde o acento. Comparar texto cru erraria por qualquer uma dessas coisas,
    então caixa, acento e pontuação são descartados e só a sequência de palavras
    é comparada.
    """
    return WORD_RE.findall(unidecode(text).lower())


def fingerprints(words: list[str]) -> set[str]:
    """Todas as janelas de `FINGERPRINT_WORDS` palavras, deslizando de uma em uma."""
    return {
        " ".join(words[i:i + FINGERPRINT_WORDS])
        for i in range(len(words) - FINGERPRINT_WORDS + 1)
    }


def private_prose(essay) -> str:
    """O corpo de um essay privado, menos o que é publicado de propósito.

    `strip_public_body` tira H1, byline, `## Sumário` e `## Conexões`. Faltam
    duas coisas, e as duas pelo mesmo motivo — são públicas por decisão do
    Usuário, não vazamento:

    - `## Referências`: os nós de referência do mapa carregam a citação AIAA
      inteira, então toda citação longa de um essay privado acusaria vazamento
      no artefato que a publica de propósito;
    - **URL**: o endereço citado no corpo é o mesmo que vai para o nó de
      referência, e normalizado (`https ocw mit edu courses 16 346
      astrodynamics`) ele vira uma sequência longa de palavras que casa
      perfeitamente. O TEXTO do link continua sendo prosa e continua comparado;
      só o alvo sai.
    """
    prose = REFERENCES_RE.sub("", strip_public_body(essay.body))
    prose = IMAGE_TARGET_RE.sub(r"\1", prose)
    return URL_RE.sub(" ", prose)


def audit_bodies() -> list[str]:
    """No unpublished essay's prose may appear anywhere in the output.

    A versão anterior sorteava UMA janela de 12 palavras por essay privado,
    começando na palavra 60, 200 ou 400. Um parágrafo vazado em qualquer outro
    ponto do texto passava intacto — a checagem provava quase nada. Aqui o corpo
    privado inteiro é impresso em n-gramas deslizantes e todos são procurados em
    todo arquivo publicado.

    As duas escolhas que decidem se o portão é útil ou só barulhento:

    1. **Tamanho da janela.** 12 palavras, dentro da faixa 8–15. Com 8, prosa de
       ligação em português ("de modo que o que estava em jogo não era mais")
       colide por acaso entre dois textos do mesmo autor sobre o mesmo assunto —
       e é exatamente esse o corpus aqui. Com 15, um parágrafo curto vazado
       inteiro pode não chegar ao comprimento mínimo e escapa. 12 é longo o
       bastante para que a coincidência exija plágio de si mesmo.
    2. **Desconto do que já é público.** Um essay privado compartilha trechos
       legítimos com um público: citação, título de obra, definição técnica,
       parágrafo reaproveitado. Todo n-grama que também ocorre no corpo de algum
       essay PÚBLICO é removido da impressão digital antes da busca — se aquele
       texto já está publicado por decisão do Usuário, encontrá-lo no site não é
       vazamento. O que sobra é prosa que só existe no privado, e aí qualquer
       acerto é vazamento de verdade.

    Custo: o conjunto de n-gramas privados é montado uma vez e a busca é
    associativa (`in set`), então o tempo é linear no tamanho do site, não no
    produto n-gramas × arquivos.
    """
    essays = collect_all()
    private = [e for e in essays if not e.published]
    if not private:
        return []

    public_grams: set[str] = set()
    for essay in essays:
        if essay.published:
            public_grams |= fingerprints(normalize_words(private_prose(essay)))

    # n-grama -> slug do essay privado que o contém. O primeiro dono basta: o
    # relatório aponta um vazamento, e o Usuário abre o arquivo.
    private_grams: dict[str, str] = {}
    for essay in private:
        for gram in fingerprints(normalize_words(private_prose(essay))) - public_grams:
            private_grams.setdefault(gram, essay.slug)
    if not private_grams:
        return []

    errors: list[str] = []
    reported: set[tuple[str, str]] = set()
    for path in sorted(SITE_ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SCANNED_SUFFIXES:
            continue
        rel = path.relative_to(SITE_ROOT).as_posix()
        words = normalize_words(path.read_text(encoding="utf-8", errors="replace"))
        for i in range(len(words) - FINGERPRINT_WORDS + 1):
            gram = " ".join(words[i:i + FINGERPRINT_WORDS])
            slug = private_grams.get(gram)
            if slug is None or (slug, rel) in reported:
                continue
            reported.add((slug, rel))
            errors.append(
                f"body text of unpublished essay '{slug}' found in {rel}: \"{gram}\"")
    return errors


def audit() -> list[str]:
    errors: list[str] = []
    if not SITE_ROOT.exists():
        return [f"SITE_ROOT does not exist: {SITE_ROOT}"]

    allowed = {e.slug for e in collect_all() if e.published}

    for name in MACHINE_FILES:
        if not (SITE_ROOT / name).exists():
            errors.append(f"missing {name}")

    errors.extend(audit_maps(allowed))
    errors.extend(audit_catalogue(allowed))
    errors.extend(audit_pages(allowed))
    errors.extend(audit_bodies())

    for path in sorted(SITE_ROOT.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SCANNED_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in PRIVATE_TARGET.finditer(text):
            target = match.group(1) or match.group(2) or ""
            # An external URL cannot reach the private repository, and plenty of
            # them legitimately contain a /wiki/ segment (Wikipedia, for one).
            if EXTERNAL_URL.match(target):
                continue
            if PRIVATE_PATH.search(target):
                errors.append(
                    f"link into the private repository in "
                    f"{path.relative_to(SITE_ROOT)}: {target[:120]}")

    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    errors = audit()
    if args.json:
        print(json.dumps(
            {"status": "fail" if errors else "pass", "errors": errors},
            ensure_ascii=False, indent=2,
        ))
    else:
        print("site-privacy: PASS" if not errors else "site-privacy: FAIL")
        for error in errors:
            print(f"  ERROR {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
