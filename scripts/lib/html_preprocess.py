#!/usr/bin/env python3
"""Explicit native Obsidian callout preprocessor for Second Brain exports.

Contract:
- only ``> [!type] Optional title`` starts a callout;
- only canonical Obsidian types are accepted;
- the type identifier alone selects the visual family;
- title and body are never inspected to infer or change the type;
- a plain ``>`` block is always a normal quote;
- Markdown inside a callout remains Markdown, including headings, lists,
  tables, fenced code and nested callouts;
- the surrounding essay shell is untouched.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

NATIVE_TYPES = {
    "note", "abstract", "info", "todo", "tip", "success", "question",
    "warning", "failure", "danger", "bug", "example", "quote",
}
ALIASES = {
    "summary", "tldr", "hint", "important", "check", "done", "help",
    "faq", "caution", "attention", "fail", "missing", "error", "cite",
}

CALLOUT_RE = re.compile(r"^\[!([A-Za-z0-9_-]+)\]([+-])?(?:\s+(.*?))?\s*$")
QUOTE_RE = re.compile(r"^(\s*)>\s?(.*)$")
FENCE_RE = re.compile(r"^\s*(```+|~~~+)")
ORNAMENT_RE = re.compile(r"^[·•∙∞⑂✻❦🌍🫧\s]{1,15}$")
META_LINE_RE = re.compile(r"^[A-Za-zÀ-ÿ][\wÀ-ÿ ]{0,18}:\s")
_IMG_LARGURA_RE = re.compile(r"!\[([^\]|]*)\|(\d+)\]\(([^)]+)\)")
_COLUNA_NOMINAL_PX = 700
GLYPH_MAP = {"\u2442": "\u2234"}
MAX_NESTING = 4


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
    if typ not in NATIVE_TYPES:
        raise CalloutError(f"unknown or non-native callout type: {typ}")
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
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


def _div(open_spec: str, inner: list[str]) -> list[str]:
    return [f"::: {{{open_spec}}}", "", *inner, "", ":::"]


def _hardbreak_stanzas(lines: list[str]) -> list[str]:
    out: list[str] = []
    for stanza in _paragraphs(lines):
        if out:
            out.append("")
        out.append("  \n".join(stanza))
    return out


def _box_body(lines: list[str]) -> list[str]:
    """Preserve Markdown structure inside a callout without classifying it."""
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
            out.append(line)
            i += 1
            while i < n:
                out.append(lines[i])
                if re.match(r"^\s*" + re.escape(marker[0:3]), lines[i]):
                    i += 1
                    break
                i += 1
            continue

        if QUOTE_RE.match(line):
            if out and out[-1] != "":
                out.append("")
            while i < n and QUOTE_RE.match(lines[i]):
                out.append(lines[i])
                i += 1
            continue

        # Keep Markdown block structures contiguous, including headings.
        if re.match(r"^\s*(?:#{1,6}\s+|[-*+]\s+|\d+[.)]\s+|\|)", line):
            if out and out[-1] != "":
                out.append("")
            is_heading = bool(re.match(r"^\s*#{1,6}\s+", line))
            out.append(line)
            i += 1
            if not is_heading:
                while i < n and lines[i].strip() and re.match(
                    r"^\s*(?:[-*+]\s+|\d+[.)]\s+|\|)", lines[i]
                ):
                    out.append(lines[i])
                    i += 1
            continue

        if out and out[-1] != "":
            out.append("")
        out.append(line)
        i += 1

    while out and out[-1] == "":
        out.pop()
    return out



def _mark_callout_inner_headings(lines: list[str]) -> list[str]:
    """Attach a structural class to headings that live inside a callout.

    The class lets the PDF renderer suppress chapter/subchapter ornaments such
    as the gold numeric prefix. It depends only on explicit containment, never
    on title text, dates, names, numbers, or callout body semantics.
    """
    out: list[str] = []
    for line in lines:
        m = re.match(r"^(\s*#{1,6}\s+.*?)(?:\s+\{([^{}]*)\})?\s*$", line)
        if not m:
            out.append(line)
            continue
        base, attrs = m.group(1), (m.group(2) or "").strip()
        tokens = attrs.split() if attrs else []
        if '.callout-inner-heading' not in tokens:
            tokens.append('.callout-inner-heading')
        out.append(f"{base} {{{' '.join(tokens)}}}")
    return out


def _decorate_explicit_box_structure(callout_type: str, lines: list[str]) -> list[str]:
    """Attach presentation hooks from explicit type + explicit Markdown only.

    This is structural, not heuristic: the type is already authored. ``todo``
    reserves its authored ``####`` as entity metadata; ``warning`` reserves an
    authored ``---`` as the divider before the source/note portion.
    """
    if callout_type == "todo":
        out: list[str] = []
        for line in lines:
            m = re.match(r"^(\s*####\s+)(.*?)(\s*)$", line)
            if not m:
                out.append(line)
                continue
            head, title, tail = m.groups()
            attrs = re.search(r"\s+\{([^}]*)\}\s*$", title)
            if attrs:
                base = title[: attrs.start()].rstrip()
                inside = attrs.group(1).strip()
                title = f"{base} {{{inside} .entity-meta}}"
            else:
                title = f"{title.rstrip()} {{.entity-meta}}"
            out.append(head + title + tail)
        return out

    if callout_type == "warning":
        for i, line in enumerate(lines):
            if line.strip() != "---":
                continue
            before = lines[:i]
            after = lines[i + 1:]
            out = [*before]
            if out and out[-1] != "":
                out.append("")
            out += ["::: {.stat-divider}", "", ":::"]
            if after:
                out += ["", "::: {.stat-source}", "", *after, "", ":::"]
            return out

    return lines

def _emit_box(h: Header, body: list[str], depth: int) -> list[str]:
    # Canonical rendering carries only the native Obsidian type class.
    # Visual identity is attached directly to .callout-<type> in HTML/PDF.
    classes = f".box .callout-{h.type}"
    if not h.title:
        # Structural only: absence of an authored title is explicit syntax.
        classes += " .box-untitled"
    if h.fold == "+":
        classes += " .callout-fold-open"
    elif h.fold == "-":
        classes += " .callout-fold-closed"

    out = [f"::: {{{classes}}}", ""]
    # The native callout type is metadata/style only. Never print "Nota",
    # "Resumo", "Exemplo", etc. The only visible header is authored text.
    if h.title:
        out += ["::: {.box-title}", "", h.title, "", ":::", ""]
    structured = _decorate_explicit_box_structure(h.type, _box_body(body))
    structured = _mark_callout_inner_headings(structured)
    out += _transform_lines(structured, depth + 1, parent_kind="callout")
    if out and out[-1] != "":
        out.append("")
    out += [":::"]
    return out


def _emit_nested_success(h: Header, body: list[str], depth: int) -> list[str]:
    inner_body = _mark_callout_inner_headings(_box_body(body))
    inner = _transform_lines(inner_body, depth + 1, parent_kind="callout")
    out = ["::: {.box-verdict .callout-success}", ""]
    if h.title:
        out += [f"[{h.title}]{{.verdict-tag}}", ""]
    out += inner
    if out and out[-1] != "":
        out.append("")
    out += [":::"]
    return out


def _trim_blank(lines: list[str]) -> list[str]:
    lines = list(lines)
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _join_paragraphs(paragraphs: list[list[str]]) -> list[str]:
    out: list[str] = []
    for paragraph in paragraphs:
        if out:
            out.append("")
        out.extend(paragraph)
    return out


def _split_quote_parts(
    body: list[str], *, fallback_last_paragraph: bool = False
) -> tuple[list[str], list[str]]:
    """Split quoted words from attribution without semantic guessing.

    Canonical syntax uses explicit quotation marks. Everything through the
    closing mark is quote text; everything after it is attribution. For old
    explicit [!quote] blocks only, a final separate paragraph is accepted as a
    migration fallback so existing author/work lines are not lost.
    """
    lines = _trim_blank(body)
    if not lines:
        return [], []

    first = next((i for i, line in enumerate(lines) if line.strip()), None)
    if first is not None:
        stripped = lines[first].lstrip()
        opener = "“" if stripped.startswith("“") else '"' if stripped.startswith('"') else None
        if opener:
            closer = "”" if opener == "“" else '"'
            indent = lines[first][: len(lines[first]) - len(lines[first].lstrip())]
            lines[first] = indent + stripped[1:]
            for j in range(len(lines) - 1, first - 1, -1):
                # After stripping exactly one Markdown quote level, a nested
                # quote still starts with `>`. Its closing mark belongs to the
                # inner quote and must never close the outer quotation.
                if QUOTE_RE.match(lines[j]):
                    continue
                pos = lines[j].rfind(closer)
                if pos < 0:
                    continue
                after = lines[j][pos + len(closer):].strip()
                quote_lines = lines[: j + 1]
                quote_lines[-1] = lines[j][:pos].rstrip()
                attribution = ([after] if after else []) + lines[j + 1:]
                return _trim_blank(quote_lines), _trim_blank(attribution)

    if fallback_last_paragraph:
        paragraphs = _paragraphs(lines)
        if len(paragraphs) >= 2:
            return _join_paragraphs(paragraphs[:-1]), paragraphs[-1]

    return lines, []


def _emit_quote_container(
    classes: str,
    body: list[str],
    depth: int,
    *,
    label: str = "",
    fallback_last_paragraph: bool = False,
) -> list[str]:
    quote_text, attribution = _split_quote_parts(
        body, fallback_last_paragraph=fallback_last_paragraph
    )
    out = [f"::: {{{classes}}}", ""]
    if label:
        out += ["::: {.quote-label}", "", label, "", ":::", ""]
    if quote_text:
        out += ["::: {.quote-text}", ""]
        out += _transform_lines(_box_body(quote_text), depth, parent_kind="quote")
        if out and out[-1] != "":
            out.append("")
        out += [":::", ""]
    if attribution:
        out += ["::: {.quote-attribution}", ""]
        out += _transform_lines(_box_body(attribution), depth, parent_kind="quote")
        if out and out[-1] != "":
            out.append("")
        out += [":::", ""]
    if out and out[-1] == "":
        out.pop()
    out += [":::"]
    return out


def _emit_pull_quote(h: Header, body: list[str], depth: int) -> list[str]:
    return _emit_quote_container(
        ".pull-quote .callout-quote",
        body,
        depth,
        label=h.title,
        fallback_last_paragraph=True,
    )


def _emit_quote(body: list[str], depth: int) -> list[str]:
    return _emit_quote_container(".quote", body, depth)


def _collect_quote(lines: list[str], i: int) -> tuple[list[str], int]:
    raw: list[str] = []
    n = len(lines)
    while i < n and QUOTE_RE.match(lines[i]):
        raw.append(_strip_one_quote(lines[i]))
        i += 1
    return raw, i


def _transform_lines(lines: list[str], depth: int = 0, parent_kind: str = "root") -> list[str]:
    # `depth` counts callouts only. Plain/nested quotes preserve Markdown
    # hierarchy but do not consume the callout nesting budget.
    if depth > MAX_NESTING:
        raise CalloutError(f"callout nesting deeper than {MAX_NESTING} is not permitted")
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        fm = FENCE_RE.match(line)
        if fm:
            marker = fm.group(1)
            out.append(line)
            i += 1
            while i < n:
                out.append(lines[i])
                if re.match(r"^\s*" + re.escape(marker[0:3]), lines[i]):
                    i += 1
                    break
                i += 1
            continue

        if QUOTE_RE.match(line):
            body, i = _collect_quote(lines, i)
            if not body:
                continue
            h = _parse_header(body[0])
            if h:
                content = body[1:]
                if content and not content[0].strip():
                    content = content[1:]
                if depth >= MAX_NESTING:
                    raise CalloutError(f"callout nesting deeper than {MAX_NESTING} is not permitted")
                if h.type == "success" and parent_kind == "callout":
                    out += _emit_nested_success(h, content, depth)
                elif h.type == "quote":
                    out += _emit_pull_quote(h, content, depth)
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
    """Retain deterministic non-callout presentation helpers already in use."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() and ORNAMENT_RE.match(line.strip()):
            # Preserve the complete authored ornament sequence. This is a
            # literal structural conversion only; no glyph count or meaning is inferred.
            glyph = " ".join(GLYPH_MAP.get(tok, tok) for tok in line.strip().split())
            out += [f'<div class="ornament">{glyph}</div>', ""]
            i += 1
            continue
        if (
            line.strip()
            and not line.startswith("#")
            and len(line.strip()) <= 44
            and len(line.strip().split()) <= 5
            and not re.search(r"[.:!?;,)\]]$", line.strip())
            and i + 2 < len(lines)
            and lines[i + 1].strip() == ""
            and META_LINE_RE.match(lines[i + 2].strip())
            and "·" in lines[i + 2]
            and len(lines[i + 2].strip()) <= 70
        ):
            out += ["### " + line.strip(), ""]
            i += 1
            continue
        out.append(line)
        i += 1
    return out


def transform_markdown(body: str) -> str:
    body = converter_larguras_de_imagem(body)
    transformed = _transform_lines(body.splitlines(), 0)
    transformed = _convert_ornaments_and_agent_heads(transformed)
    result = "\n".join(transformed)
    for bad, good in GLYPH_MAP.items():
        result = result.replace(bad, good)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip() + "\n"


def lint_source(text: str) -> list[str]:
    errors: list[str] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        m = re.match(r"^\s*(?:>\s*)+(\[![^\]]+\].*)$", line)
        if not m:
            continue
        try:
            _parse_header(m.group(1))
        except CalloutError as exc:
            errors.append(f"line {lineno}: {exc}")
    return errors
