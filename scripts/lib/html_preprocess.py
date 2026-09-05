#!/usr/bin/env python3
"""Explicit Obsidian callout preprocessor for Second Brain essays.

Contract:
- only ``> [!type]`` starts a callout;
- a plain ``>`` block is always a quote;
- no label/emoji/bold/text classification exists;
- unknown types and aliases are hard errors;
- nested callouts are supported to depth 2;
- the emitted fenced divs deliberately reuse the current HTML/PDF visual
  components, so the surrounding essay shell does not change.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Canonical callout IDs supported for authorship. Native IDs work in Obsidian
# directly; custom semantic IDs are styled by the vault snippet
# `.obsidian/snippets/second-brain-callouts.css`.
NATIVE_TYPES = {
    "note", "abstract", "info", "todo", "tip", "success", "question",
    "warning", "failure", "danger", "bug", "example", "quote",
}
CUSTOM_TYPES = {
    "concept", "definition", "experiment", "evidence", "argument",
    "assumption", "method", "result", "conclusion", "idea", "meta",
    "person", "book", "source", "pullquote", "epigraph", "code",
}
CANONICAL_TYPES = NATIVE_TYPES | CUSTOM_TYPES
ALIASES = {
    "summary", "tldr", "hint", "important", "check", "done", "help",
    "faq", "caution", "attention", "fail", "missing", "error", "cite",
}

DISPLAY = {
    "note": "Nota", "abstract": "Resumo", "info": "Informação",
    "todo": "A fazer", "tip": "Recomendação", "success": "Confirmado",
    "question": "Questão", "warning": "Atenção", "failure": "Falha",
    "danger": "Crítico", "bug": "Bug", "example": "Exemplo",
    "quote": "Citação", "concept": "Conceito", "definition": "Definição",
    "experiment": "Experimento mental", "evidence": "Evidência empírica",
    "argument": "Argumento", "assumption": "Premissa", "method": "Método",
    "result": "Resultado", "conclusion": "Conclusão", "idea": "Ideia",
    "meta": "Nota editorial", "person": "Pessoa", "book": "Obra",
    "source": "Fonte", "pullquote": "Destaque", "epigraph": "Epígrafe",
    "code": "Código",
}

# Semantic ID -> one of the visual families already defined by essay_template.
FAMILY = {
    "experiment": "experimento", "example": "experimento",
    "evidence": "evidencia", "info": "evidencia", "success": "evidencia",
    "result": "evidencia",
    "concept": "mapa", "definition": "mapa", "abstract": "mapa",
    "assumption": "mapa", "method": "mapa", "source": "mapa",
    "argument": "ataque", "question": "ataque", "failure": "ataque",
    "warning": "aviso", "danger": "aviso", "bug": "aviso",
    "idea": "ideia", "tip": "ideia", "conclusion": "ideia",
    "note": "generico", "todo": "generico", "meta": "generico",
    "code": "generico",
}

CALLOUT_RE = re.compile(
    r"^\[!([A-Za-z0-9_-]+)\]([+-])?(?:\s+(.*?))?\s*$"
)
QUOTE_RE = re.compile(r"^(\s*)>\s?(.*)$")
FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
ORNAMENT_RE = re.compile(r"^[·•∙∞⑂✻❦🌍🫧\s]{1,15}$")
META_LINE_RE = re.compile(r"^[A-Za-zÀ-ÿ][\wÀ-ÿ ]{0,18}:\s")
_IMG_LARGURA_RE = re.compile(r"!\[([^\]|]*)\|(\d+)\]\(([^)]+)\)")
_COLUNA_NOMINAL_PX = 700
GLYPH_MAP = {"\u2442": "\u2234"}


class CalloutError(ValueError):
    pass


@dataclass(frozen=True)
class Header:
    type: str
    fold: str | None
    title: str


def converter_larguras_de_imagem(body: str) -> str:
    def repl(m: re.Match[str]) -> str:
        alt, px, path = m.group(1), int(m.group(2)), m.group(3)
        pct = max(10, min(100, round(100 * px / _COLUNA_NOMINAL_PX)))
        return f"![{alt}]({path}){{width={pct}%}}"
    return _IMG_LARGURA_RE.sub(repl, body)


def _parse_header(text: str) -> Header | None:
    m = CALLOUT_RE.match(text.strip())
    if not m:
        return None
    typ = m.group(1).lower()
    if typ in ALIASES:
        raise CalloutError(f"non-canonical Obsidian alias: {typ}")
    if typ not in CANONICAL_TYPES:
        raise CalloutError(f"unknown callout type: {typ}")
    return Header(typ, m.group(2), (m.group(3) or "").strip())


def _strip_one_quote(line: str) -> str:
    m = QUOTE_RE.match(line)
    return m.group(2) if m else line


def _paragraphs(lines: list[str]) -> list[list[str]]:
    out: list[list[str]] = []
    cur: list[str] = []
    for line in lines:
        if line.strip():
            cur.append(line)
        elif cur:
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


def _div(open_spec: str, inner: list[str]) -> list[str]:
    return [f"::: {{{open_spec}}}", "", *inner, "", ":::"]


def _hardbreak_stanzas(lines: list[str]) -> list[str]:
    """Preserve the old export's visual line breaks inside quote-like blocks.

    The legacy preprocessor intentionally rendered each physical `>` line as a
    hard break, while an empty quoted line started a new paragraph.  Explicit
    callouts must not silently collapse those lines into one flowing paragraph.
    """
    out: list[str] = []
    for stanza in _paragraphs(lines):
        if out:
            out.append("")
        out.append("  \n".join(stanza))
    return out


def _legacy_box_body(lines: list[str]) -> list[str]:
    """Keep legacy box paragraph boundaries without breaking Markdown structures.

    In the corpus, each quoted prose line in a typed legacy box represented a
    separate paragraph.  Lists, tables, fenced code and nested callouts remain
    contiguous; ordinary prose lines are separated by a blank Markdown line.
    """
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        if not line.strip():
            if out and out[-1] != "":
                out.append("")
            i += 1
            continue

        fm = FENCE_RE.match(line)
        if fm:
            if out and out[-1] != "":
                out.append("")
            marker = fm.group(1)
            out.append(line); i += 1
            while i < n:
                out.append(lines[i])
                if re.match(r"^\s*" + re.escape(marker[0:3]), lines[i]):
                    i += 1
                    break
                i += 1
            continue

        # Nested callout / nested quote: keep the quoted run contiguous so the
        # next transform pass still sees it as one structural block.
        if QUOTE_RE.match(line):
            if out and out[-1] != "":
                out.append("")
            while i < n and QUOTE_RE.match(lines[i]):
                out.append(lines[i]); i += 1
            continue

        # Markdown list/table continuation remains one structure.
        if re.match(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|\|)", line):
            if out and out[-1] != "":
                out.append("")
            while i < n and lines[i].strip() and re.match(r"^\s*(?:[-*+]\s+|\d+[.)]\s+|\|)", lines[i]):
                out.append(lines[i]); i += 1
            continue

        if out and out[-1] != "":
            out.append("")
        out.append(line)
        i += 1

    while out and out[-1] == "":
        out.pop()
    return out


def _emit_box(h: Header, body: list[str], depth: int) -> list[str]:
    family = FAMILY[h.type]
    classes = f".box .{family}"
    if h.fold == "+": classes += " .callout-fold-open"
    elif h.fold == "-": classes += " .callout-fold-closed"

    content = body[:]
    badge: str | None = None
    title = h.title

    # Preserve the legacy visual grammar while the source becomes explicit.
    # The type determines the visual family; labels/titles below are presentation
    # structure only and are taken solely from the explicit callout header/body.
    if h.type == "idea" and h.title:
        badge, title = h.title, ""
    elif h.type in {"experiment", "evidence"}:
        badge = DISPLAY[h.type]
        if h.title and " — " in h.title:
            ordinal, title = h.title.split(" — ", 1)
            badge = f"{DISPLAY[h.type]} {ordinal}"
    elif h.type == "concept" and h.title in {"Mapa Conceitual", "Precisão Conceitual"}:
        badge = h.title
        # These two corpus components explicitly store their visual title as the
        # first callout body line, mirroring the old label + quote pair.
        while content and not content[0].strip():
            content.pop(0)
        if content:
            title = content.pop(0).strip()
    elif h.type == "argument" and h.title and (
            h.title.startswith("Ataque ") or h.title == "O Ataque Central"):
        badge = h.title
        while content and not content[0].strip():
            content.pop(0)
        if content:
            first = content.pop(0).strip()
            m = re.match(r"^\*\*(.*?)\*\*$", first)
            title = m.group(1) if m else first
    elif not h.title:
        # Untitled semantic boxes still need an author-visible label.
        badge = DISPLAY[h.type]

    out = [f"::: {{{classes}}}", ""]
    if badge:
        out += ["::: {.box-badge}", "", badge, "", ":::", ""]
    if title:
        out += ["::: {.box-title}", "", title, "", ":::", ""]
    inner = _transform_lines(_legacy_box_body(content), depth + 1)
    out += inner
    if out and out[-1] != "": out.append("")
    out += [":::"]
    return out


def _emit_result(h: Header, body: list[str], depth: int) -> list[str]:
    # Nested result/conclusion is a structural verdict footer. No search for
    # words such as "Veredicto" or "Resposta" occurs in body text.
    tag = h.title or DISPLAY[h.type]
    inner = _transform_lines(_legacy_box_body(body), depth + 1)
    out = ["::: {.box-verdict}", "", f"[{tag}]{{.verdict-tag}}", ""]
    out += inner
    if out and out[-1] != "": out.append("")
    out += [":::"]
    return out


def _emit_card(h: Header, body: list[str], depth: int) -> list[str]:
    cls = "filosofo" if h.type == "person" else ("livro" if h.type == "book" else "fonte")
    out = [f"::: {{.card .{cls}}}", ""]
    out += ["::: {.card-name}", "", h.title or DISPLAY[h.type], "", ":::", ""]
    # Legacy person/book cards use the first physical content line as compact
    # metadata and every following prose line as its own paragraph.
    content = body[:]
    while content and not content[0].strip():
        content.pop(0)
    if h.type in {"person", "book"} and content:
        meta = content.pop(0)
        out += ["::: {.card-meta}", "", meta, "", ":::", ""]
    while content and not content[0].strip():
        content.pop(0)
    out += _transform_lines(_legacy_box_body(content), depth + 1)
    if out and out[-1] != "": out.append("")
    out += [":::"]
    return out


def _emit_pull(h: Header, body: list[str], depth: int) -> list[str]:
    classes = ".pull-quote"
    if h.type == "epigraph": classes += " .epigraph"
    out = [f"::: {{{classes}}}", ""]
    if h.title:
        # Obsidian callout titles remain author-visible. For typographic quote
        # types the title is a compact lead line rather than a box badge.
        out += [f"**{h.title}**", ""]
    paras = _paragraphs(body)
    cite: list[str] | None = None
    # Attribution is structural: the author must put it in a final paragraph
    # separated by an empty quoted line. No dash/year/name regex is used.
    if len(paras) >= 2:
        cite = paras.pop()
    main: list[str] = []
    for i, p in enumerate(paras):
        if i: main.append("")
        main.append("  \n".join(p))
    out += _transform_lines(main, depth + 1)
    if cite:
        if out and out[-1] != "": out.append("")
        out += ["::: {.pq-cite}", "", *cite, "", ":::"]
    if out and out[-1] != "": out.append("")
    out += [":::"]
    return out


def _emit_quote(body: list[str], depth: int) -> list[str]:
    inner = _transform_lines(_hardbreak_stanzas(body), depth + 1)
    return _div(".quote", inner)


def _collect_quote(lines: list[str], i: int) -> tuple[list[str], int]:
    """Collect a contiguous blockquote, preserving nested quote markers."""
    raw: list[str] = []
    n = len(lines)
    while i < n and QUOTE_RE.match(lines[i]):
        raw.append(_strip_one_quote(lines[i]))
        i += 1
    return raw, i


def _transform_lines(lines: list[str], depth: int = 0) -> list[str]:
    if depth > 2:
        raise CalloutError("callout nesting deeper than 2 is not permitted")
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        fm = FENCE_RE.match(line)
        if fm:
            marker = fm.group(1)
            out.append(line); i += 1
            while i < n:
                out.append(lines[i])
                if re.match(r"^\s*" + re.escape(marker[0:3]), lines[i]):
                    i += 1; break
                i += 1
            continue
        if QUOTE_RE.match(line):
            body, i = _collect_quote(lines, i)
            if not body:
                continue
            h = _parse_header(body[0])
            if h:
                content = body[1:]
                # Drop at most one leading empty quoted line after header.
                if content and not content[0].strip(): content = content[1:]
                if depth >= 2:
                    raise CalloutError("callout nesting deeper than 2 is not permitted")
                if h.type in {"result", "conclusion"} and depth > 0:
                    out += _emit_result(h, content, depth)
                elif h.type in {"person", "book"}:
                    out += _emit_card(h, content, depth)
                elif h.type in {"pullquote", "epigraph"}:
                    out += _emit_pull(h, content, depth)
                elif h.type == "quote":
                    q = content
                    if h.title:
                        q = [f"**{h.title}**", "", *q]
                    out += _emit_quote(q, depth)
                else:
                    out += _emit_box(h, content, depth)
            else:
                out += _emit_quote(body, depth)
            out.append("")
            continue
        out.append(line)
        i += 1
    return out


def _convert_ornaments_and_agent_heads(lines: list[str]) -> list[str]:
    """Retain the current deterministic non-callout presentation helpers.

    This deliberately does NOT inspect blockquotes or callout text. It keeps
    the existing ornament glyphs and the IA agent/tool subtitle convention so
    before/after differences remain confined to highlighted components.
    """
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Standalone ornamental glyph paragraph.
        if line.strip() and ORNAMENT_RE.match(line.strip()):
            glyph = GLYPH_MAP.get(line.strip().split()[0], line.strip().split()[0])
            out += [f'<div class="ornament">{glyph}</div>', ""]
            i += 1
            continue
        # Preserve the current IA agent/tool heading convention. This is
        # presentation structure, not callout classification.
        if (line.strip() and not line.startswith('#') and len(line.strip()) <= 44
                and len(line.strip().split()) <= 5
                and not re.search(r'[.:!?;,)\]]$', line.strip())
                and i + 2 < len(lines) and lines[i + 1].strip() == ""
                and META_LINE_RE.match(lines[i + 2].strip())
                and '·' in lines[i + 2] and len(lines[i + 2].strip()) <= 70):
            out += ["### " + line.strip(), ""]
            i += 1
            continue
        out.append(line)
        i += 1
    return out


def transform_markdown(body: str) -> str:
    body = converter_larguras_de_imagem(body)
    lines = body.splitlines()
    transformed = _transform_lines(lines, 0)
    transformed = _convert_ornaments_and_agent_heads(transformed)
    result = "\n".join(transformed)
    for bad, good in GLYPH_MAP.items():
        result = result.replace(bad, good)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip() + "\n"


def lint_source(text: str) -> list[str]:
    errors: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        # Check any quote depth; nested explicit callouts are valid.
        m = re.match(r"^\s*(?:>\s*)+(\[![^\]]+\].*)$", line)
        if not m:
            continue
        try:
            _parse_header(m.group(1))
        except CalloutError as exc:
            errors.append(f"line {lineno}: {exc}")
    return errors
