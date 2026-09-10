#!/usr/bin/env python3
"""
Modelo compartilhado da projeção pública.

Lê DATA_ROOT e nunca escreve lá. Tudo que é público passa por
``collect_public()``: um essay chega ao site só quando o frontmatter o autoriza
com ``visibility: public`` — ou com o legado ``visibility: publico`` e o antigo
booleano ``publish: true``. Qualquer outro valor, inclusive a ausência do campo,
é privado.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import visibility
import yaml
from repo_paths import ESSAYS_DIR

# --- Tempo de leitura ------------------------------------------------------
# Mora aqui, e não em `build_site.py`, porque três superfícies precisam do
# MESMO número: o catálogo, a página pública do essay e o export standalone.
# Enquanto cada uma tinha a sua conta, o mesmo essay anunciava 81 min numa e
# 73 na outra — e a página ainda contava o LaTeX cru como palavra, porque
# media antes de o MathJax tipografar.
WORDS_PER_MINUTE = 220

# A formula is read, not scanned word by word; counting `rac{a}{b}` as five
# words turned a 30-minute essay into a 100-minute one.
#
# A ordem das alternativas é a correção do bug: matemática de DISPLAY
# (`$$...$$` e `\[...\]`) precisa casar ANTES da inline. Com o padrão antigo
# `\$[^$]{1,400}\$`, um bloco `$$...$$` nunca casava inteiro — a classe `[^$]`
# barra o segundo cifrão —, então o motor casava `$<fórmula>$` e sobrava um
# cifrão ÓRFÃO, que em seguida pareava com o cifrão de ABERTURA do bloco
# seguinte. Toda a prosa entre duas fórmulas era engolida como se fosse
# fórmula: um essay de 3195 palavras contava 665 e virava "3 min".
#
# A inline também não pode atravessar quebra de linha: fórmula inline vive numa
# linha só, enquanto dois cifrões distantes quase sempre têm prosa — e parágrafo
# — no meio. `[^$\n]` transforma esse caso em não-casamento, que apenas deixa um
# cifrão solto na contagem, em vez de silenciar páginas inteiras.
MATH_SPAN = re.compile(
    r"\$\$[\s\S]{1,2000}?\$\$"       # display do corpus: $$ ... $$
    r"|\\\[[\s\S]{1,2000}?\\\]"      # display alternativo: \[ ... \]
    # Inline: `$x$`, numa linha só e sem espaço colado aos delimitadores. A
    # borda sem espaço é o que separa fórmula de dinheiro: em "R$ 50.000 e R$
    # 500.000" os dois cifrões são moeda, e sem essa guarda a prosa entre eles
    # sumiria da contagem exatamente como sumia entre dois blocos de display.
    r"|\$(?!\$)[^\s$](?:[^$\n]{0,397}[^\s$])?\$"
)
CODE_SPAN = re.compile(r"`[^`]{1,200}`")


def reading_minutes(text: str) -> int:
    """Rounded reading time over prose alone, never below one minute."""
    prose = CODE_SPAN.sub(" ", MATH_SPAN.sub(" ", text))
    return max(1, round(len(prose.split()) / WORDS_PER_MINUTE))



FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)
H1_RE = re.compile(r"(?m)^#\s+(.+?)\s*$")
CONNECTIONS_RE = re.compile(r"(?ms)^##\s+Conex[õo]es\s*\n(.*?)(?=^##\s+|\Z)")
SUMARIO_RE = re.compile(r"(?ms)^##\s+Sumário\s*\n(.*?)(?=^##\s+|\Z)")
WIKILINK_RE = re.compile(r"\[\[([^|\]]+)(?:\|([^\]]+))?\]\]")
# Sanitization runs before Pandoc converts Markdown to HTML. Keep fenced code
# opaque here: Python matrices such as ``np.array([[1.0]])`` have the exact
# same bracket shape as a wikilink but are source code, never wiki syntax.
FENCED_CODE_RE = re.compile(
    r"(?ms)^(?P<fence>`{3,}|~{3,})[^\r\n]*\r?\n.*?^(?P=fence)[ \t]*$"
)


@dataclass(frozen=True)
class PublicEssay:
    slug: str
    path: Path
    title: str
    summary: str
    tags: tuple[str, ...]
    updated: str
    created: str
    status: str
    body: str
    published: bool = True
    visibility: str = visibility.PUBLIC


def parse(path: Path) -> tuple[dict[str, Any], str]:
    """Return (frontmatter mapping, body) for a wiki page."""
    text = path.read_text(encoding="utf-8-sig")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    try:
        meta = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        # Unparseable frontmatter is not a licence to publish: treat it as if
        # the page declared nothing, which is the private default.
        return {}, text[match.end():]
    return (meta if isinstance(meta, dict) else {}), text[match.end():]


def strip_public_body(body: str) -> str:
    """Drop the parts of an essay that must not be republished verbatim.

    Removes the generated ``## Sumário``, the ``## Conexões`` block (private page
    names live there), the H1 (the template renders its own), and the byline
    blockquotes that precede the first section.
    """
    body = SUMARIO_RE.sub("", body)
    body = CONNECTIONS_RE.sub("", body)
    body = re.sub(r"(?m)^#\s+.+?\s*$\n?", "", body, count=1)

    lines = []
    in_preamble = True
    for line in body.splitlines():
        if in_preamble and line.startswith(">"):
            continue
        if line.startswith("## "):
            in_preamble = False
        lines.append(line)
    return "\n".join(lines).strip()


# Um título pode trazer ênfase inline — "Rotor _Teetering_ Controlado" — que é
# markdown legítimo no arquivo. Mas o título viaja para lugares que não
# renderizam markdown: <title>, og:title, o catálogo do site, os rótulos do
# grafo. Nesses ele vai como texto corrido; só a capa, que sabe desenhar
# itálico, recebe a versão marcada.
EMPHASIS_RE = re.compile(r"(?<!\w)([*_]{1,2})(?=\S)(.+?)(?<=\S)\1(?!\w)", re.S)


def title_plain(title: str) -> str:
    """The title as running text: emphasis markers dropped, words kept."""
    previous = None
    while previous != title:
        previous = title
        title = EMPHASIS_RE.sub(r"\2", title)
    return title


def title_html(title: str) -> str:
    """The title with its emphasis rendered, for a cover that can show it."""
    out = title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    previous = None
    while previous != out:
        previous = out
        out = EMPHASIS_RE.sub(
            lambda m: ("<strong>" + m.group(2) + "</strong>") if len(m.group(1)) == 2
            else ("<em>" + m.group(2) + "</em>"),
            out,
        )
    return out


def _essay(path: Path, meta: dict, body: str, level: str) -> PublicEssay:
    heading = H1_RE.search(body)
    tags = meta.get("tags") or []
    if not isinstance(tags, list):
        tags = []
    return PublicEssay(
        slug=path.stem,
        path=path,
        title=title_plain(heading.group(1).strip()) if heading else path.stem,
        summary=str(meta.get("summary") or "").strip(),
        tags=tuple(str(t) for t in tags),
        updated=str(meta.get("updated") or ""),
        created=str(meta.get("created") or ""),
        status=str(meta.get("status") or ""),
        body=body,
        published=level == visibility.PUBLIC,
        visibility=level,
    )


def collect_all() -> list[PublicEssay]:
    """Every essay the site may name, each flagged with whether it may be read.

    The catalogue lists public and private essays — title, summary, tags,
    status. Only the public ones carry a page, and only their body is ever
    rendered. Hidden essays are skipped entirely.
    """
    if not ESSAYS_DIR.exists():
        return []
    essays = []
    for path in sorted(ESSAYS_DIR.glob("*.md")):
        if path.name == ".gitkeep":
            continue
        meta, body = parse(path)
        level = visibility.of(meta)
        # `hidden` means absent, not merely unreadable: it never reaches the
        # catalogue, the search index or the map.
        if level == visibility.HIDDEN:
            continue
        essays.append(_essay(path, meta, body, level))
    return essays


def collect_public() -> list[PublicEssay]:
    """Every essay explicitly authorized for publication, in slug order."""
    return [essay for essay in collect_all() if essay.published]


def public_connections(essay: PublicEssay, allowed: set[str]) -> list[str]:
    """Connections of `essay` that point at another public essay, deduplicated."""
    match = CONNECTIONS_RE.search(essay.body)
    if not match:
        return []
    targets: list[str] = []
    for target, _display in WIKILINK_RE.findall(match.group(1)):
        slug = target.split("#", 1)[0].strip()
        if slug in allowed and slug != essay.slug and slug not in targets:
            targets.append(slug)
    return targets


def plain_text(markdown: str) -> str:
    """Flatten markdown to a single searchable line."""
    markdown = re.sub(r"```.*?```", " ", markdown, flags=re.S)
    markdown = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", markdown)
    markdown = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", markdown)
    markdown = WIKILINK_RE.sub(lambda m: m.group(2) or m.group(1), markdown)
    markdown = re.sub(r"[#>*_`|~]", " ", markdown)
    return re.sub(r"\s+", " ", markdown).strip()


def sanitize_private_wikilinks(markdown: str, allowed_public: set[str]) -> str:
    """Remove private link targets from the public prose/search projection.

    Public→public links keep their visible label. A private link with an explicit
    display keeps only that display text. A private link without a display becomes
    a neutral placeholder, so neither the private slug nor its title leaks.
    """
    def replace(match: re.Match[str]) -> str:
        raw = (match.group(1) or "").strip()
        display = (match.group(2) or "").strip()

        # `[[#Capítulo]]` points inside this very page — it is the essay's own
        # table of contents. Leave it for the renderer to turn into an anchor;
        # treating it as a foreign page destroyed every Sumário.
        if raw.startswith("#"):
            return match.group(0)

        target = raw.split("#", 1)[0].strip()
        if target in allowed_public:
            return match.group(0)
        return display or "referência interna"

    # Split instead of replacing through a single negative-lookaround: fences
    # can contain arbitrary newlines and bracket pairs, so preserving each
    # complete fenced block is both clearer and safer for every code language.
    chunks: list[str] = []
    cursor = 0
    for fence in FENCED_CODE_RE.finditer(markdown):
        chunks.append(WIKILINK_RE.sub(replace, markdown[cursor:fence.start()]))
        chunks.append(fence.group(0))
        cursor = fence.end()
    chunks.append(WIKILINK_RE.sub(replace, markdown[cursor:]))
    return "".join(chunks)


def public_body_for_index(essay: PublicEssay, allowed_public: set[str]) -> str:
    return sanitize_private_wikilinks(strip_public_body(essay.body), allowed_public)
