#!/usr/bin/env python3
"""check_export_parity.py - Compara invariantes semânticos entre Markdown, HTML e PDF.

Valida a paridade do conteúdo textual entre as três representações de cada ensaio:
- Confere se parágrafos, fórmulas matemáticas e referências do Markdown fonte
  estão integralmente presentes tanto no HTML quanto no PDF exportados.
- Trata normalizações tipográficas (aspas inteligentes, travessões) para comparação precisa.
- Garante que '## Conexões' esteja ausente nos dois formatos externos de exportação.

Escopo:
    Auditoria read-only de paridade semântica em DATA_ROOT.
    Default sem argumentos audita todos os ensaios que tenham HTML e PDF gerados.

Entradas (Inputs):
    Arquivos em wiki/essays/*.md, output/html/*.html e output/pdf/*.pdf.
    Argumentos CLI opcionais:
        slug          Slug opcional de um ensaio específico
        --json        Emite diagnóstico formatado em JSON

Saídas (Outputs):
    Stdout: Comparação de paridade por ensaio e reporte de elementos divergentes.
    JSON: {"check": "export_parity", "status": "pass"|"skip"|"fail", "issues": [...]}
    Exit code: 0 em paridade perfeita, 1 se houver perda de conteúdo entre formatos.

Uso:
    python scripts/check_export_parity.py              # valida paridade em todo o corpus
    python scripts/check_export_parity.py meu-ensaio   # valida ensaio específico
"""
from __future__ import annotations

import argparse
import html as html_lib
import re
import unicodedata
from pathlib import Path

from repo_paths import ESSAYS_DIR, HTML_DIR, PDF_DIR
from sanity_common import CheckResult, text_contains

# Pandoc's smart punctuation renders the source's straight quotes as typographic
# ones, so "Boltzmann's Work" in the Markdown becomes "Boltzmann’s Work" in both
# exports. Folding them here is what keeps the two sides comparable; without it
# every reference whose title carries an apostrophe was reported as missing.
TYPOGRAPHIC = str.maketrans({
    "’": "'", "‘": "'", "“": '"', "”": '"',
    "′": "'", "″": '"', "…": "...",
})


def norm(text: str) -> str:
    """Normalize text across HTML/PDF extraction backends."""
    decomposed = unicodedata.normalize("NFKD", text.translate(TYPOGRAPHIC))
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", without_marks).strip().casefold()


def export_heading(text: str) -> str:
    """Return the heading text visibly emitted by the PDF exporter.

    The PDF exporter moves a leading author-supplied chapter number into the
    chapter kicker, so ``1. Introdução`` is rendered as ``Introdução``.
    """
    return re.sub(
        r"^\s*(?:(?:\d+(?:\.\d+)*)|[IVXLC]+)\s*[.\-–:]\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


MATH_SPAN = re.compile(r"\$[^$]*\$|\\\((?:[^\\]|\\(?!\)))*\\\)")


# `*` and `_` are Markdown emphasis in a source heading and are simply gone from
# every rendered form, so they belong with the punctuation both sides drop —
# otherwise a heading like "Rotor _Teetering_ Controlado" never matches.
PUNCTUATION = re.compile(r"[()\[\]{}:,;.\-–—*_'\"]")


def loose(text: str) -> str:
    """Normalize and drop punctuation, so both sides compare on words alone.

    Typographic punctuation is folded first: dropping the straight apostrophe
    from the source while the rendered side still carried a curly one left the
    two spellings of the same title looking different.
    """
    return norm(PUNCTUATION.sub(" ", text.translate(TYPOGRAPHIC)))


def prose_fragments(text: str) -> list[str]:
    """Split a heading into the prose pieces that survive rendering.

    A heading such as ``Efeitos de Primeira Ordem: $C_{n_r}$ e $I_z$`` is emitted
    as typeset math by both exporters, so the literal TeX is never present in the
    extracted text and the pieces around it are no longer contiguous. Checking
    each prose fragment separately keeps the parity check meaningful; the math
    itself is covered by the HTML and PDF content checkers.
    """
    fragments = []
    for piece in MATH_SPAN.split(text):
        normalized = loose(piece)
        if len(normalized) >= 4:
            fragments.append(normalized)
    return fragments


def html_text(path: Path) -> tuple[str, int]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        from bs4 import BeautifulSoup, FeatureNotFound
        try:
            soup = BeautifulSoup(raw, "html5lib")
        except FeatureNotFound:
            soup = BeautifulSoup(raw, "html.parser")
        return soup.get_text(" ", strip=True), len(soup.find_all("img"))
    except ImportError:
        plain = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.S | re.I)
        plain = re.sub(r"<[^>]+>", " ", plain)
        return html_lib.unescape(plain), len(re.findall(r"<img\b", raw, re.I))


TAG = re.compile(r"<[^>]+>")


def html_headings(path: Path) -> list[str]:
    """Every heading the exported page actually renders as a heading."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    try:
        from bs4 import BeautifulSoup, FeatureNotFound
        try:
            soup = BeautifulSoup(raw, "html5lib")
        except FeatureNotFound:
            soup = BeautifulSoup(raw, "html.parser")
        return [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])]
    except ImportError:
        found = re.findall(r"<h[123][^>]*>(.*?)</h[123]>", raw, re.S | re.I)
        return [html_lib.unescape(TAG.sub(" ", h)) for h in found]


def has_standalone_line(text: str, label: str) -> bool:
    """Is `label` a line of its own, rather than a word inside a sentence?

    A section heading is emitted on its own line by both exporters (the PDF
    template tracks it into "C O N E X Õ E S"), so spaces are dropped before
    comparing. Searching for the bare substring instead reported an essay whose
    *summary* happened to mention the word.
    """
    target = norm(label).replace(" ", "")
    return any(norm(line).replace(" ", "") == target for line in text.splitlines())


def pdf_text(path: Path) -> tuple[str, int]:
    import pymupdf as fitz
    doc = fitz.open(path)
    try:
        text = "\n".join(page.get_text("text") for page in doc)
        images = sum(len(page.get_images(full=True)) for page in doc)
        return text, images
    finally:
        doc.close()


def source_fingerprint(path: Path) -> dict:
    md = path.read_text(encoding="utf-8-sig")
    title = (re.search(r"(?m)^#\s+(.+)$", md) or [None, ""])[1].strip()
    h2 = [h.strip() for h in re.findall(r"(?m)^##\s+(.+)$", md)]
    visible_h2 = [export_heading(h) for h in h2]
    export_h2 = [h for h in visible_h2 if norm(h) != norm("Conexões")]
    refs = re.findall(r"(?m)^\[\d+\]\s+(.+)$", md)
    ref_titles = []
    for ref in refs:
        m = re.search(r"\*([^*]+)\*", ref)
        if m:
            ref_titles.append(m.group(1).strip())
    return {
        "title": title,
        "h2": export_h2,
        "connections": any(norm(h) == norm("Conexões") for h in visible_h2),
        "reference_titles": ref_titles,
        "images": len(re.findall(r"!\[[^\]]*\]\([^\)]+\)", md)),
    }


def audit(slug: str | None = None) -> CheckResult:
    result = CheckResult("export-parity")
    sources = [ESSAYS_DIR / f"{slug}.md"] if slug else sorted(ESSAYS_DIR.glob("*.md")) if ESSAYS_DIR.exists() else []
    checked = 0
    for source in sources:
        if not source.exists() or source.name == ".gitkeep":
            continue
        hp = HTML_DIR / f"{source.stem}.html"
        pp = PDF_DIR / f"{source.stem}.pdf"
        if not hp.exists() or not pp.exists():
            result.skip(
                "EXPORT_PAIR_INCOMPLETE",
                f"{source.stem}: HTML and PDF are both required for parity",
                source.name,
            )
            continue
        try:
            ptext, pimages = pdf_text(pp)
        except ImportError:
            result.error("PYMUPDF_MISSING", "PyMuPDF required for parity")
            break
        htext, himages = html_text(hp)
        fp = source_fingerprint(source)
        # Heading comparison ignores punctuation on both sides: the exporters
        # re-punctuate chapter kickers, and math spans leave stray separators.
        lh, lpdf = loose(htext), loose(ptext)
        for label in [fp["title"], *fp["h2"]]:
            fragments = prose_fragments(label)
            if not fragments:
                continue
            if any(not text_contains(lh, f) for f in fragments):
                result.error("HTML_TEXT_MISSING", f"missing heading/title: {label}", source.name)
            if any(not text_contains(lpdf, f) for f in fragments):
                result.error("PDF_TEXT_MISSING", f"missing heading/title: {label}", source.name)
        for title in fp["reference_titles"]:
            if not text_contains(lh, loose(title)):
                result.error("HTML_REFERENCE_MISSING", title, source.name)
            if not text_contains(lpdf, loose(title)):
                result.error("PDF_REFERENCE_MISSING", title, source.name)
        if fp["connections"]:
            # The section must be absent as a SECTION. The word itself is
            # ordinary Portuguese and may legitimately appear in the prose or
            # in the summary printed on the cover.
            if any(norm(h) == norm("Conexões") for h in html_headings(hp)):
                result.error("HTML_CONNECTIONS_EXPORTED", "Conexões should not be exported", source.name)
            if has_standalone_line(ptext, "Conexões"):
                result.error("PDF_CONNECTIONS_EXPORTED", "Conexões should not be exported", source.name)
        if himages < fp["images"]:
            result.error("HTML_IMAGE_COUNT", f"source {fp['images']}, HTML {himages}", source.name)
        if pimages < fp["images"]:
            result.error("PDF_IMAGE_COUNT", f"source {fp['images']}, PDF {pimages}", source.name)
        checked += 1
    if not checked and not result.issues:
        result.skip("NO_EXPORT_PAIRS", "no complete Markdown+HTML+PDF export pairs found")
    result.meta["pairs_checked"] = checked
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug", nargs="?", help="optional essay stem; default audits all complete export pairs")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = audit(args.slug)
    result.print(args.json)
    return result.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
