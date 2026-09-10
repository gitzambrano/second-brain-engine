#!/usr/bin/env python3
"""
Checador semântico e de integridade dos PDFs exportados, via PyMuPDF.

Default sem argumentos: auditar cada ``output/pdf/*.pdf``. Um repositório
esqueleto sem PDF nenhum é um SKIP válido, não uma falha.
"""
from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

from repo_paths import ESSAYS_DIR, PDF_DIR
from sanity_common import CheckResult, text_contains
from site_common import title_plain

A4 = (595.28, 841.89)
SIZE_TOLERANCE_PT = 4.0


def norm(text: str) -> str:
    """Normalize text extracted from PDFs for semantic comparisons."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", without_marks).strip().casefold()


def strip_md_inline(text: str) -> str:
    """Remove Markdown inline markers (*bold*, _italic_, **bold**) before text comparison.

    PDF renderers output the rendered text without the markup delimiters, so
    '_Teetering_' in the source becomes 'Teetering' in the PDF. Comparing
    against the raw Markdown title produces spurious TITLE_MISSING failures.
    """
    return title_plain(text).strip()


def _source_for(pdf: Path) -> Path | None:
    candidate = ESSAYS_DIR / f"{pdf.stem}.md"
    return candidate if candidate.exists() else None


def audit_file(path: Path, result: CheckResult) -> None:
    try:
        import pymupdf as fitz
    except ImportError:
        result.error("PYMUPDF_MISSING", "PyMuPDF is required for PDF checks", path.name)
        return
    try:
        doc = fitz.open(path)
    except Exception as exc:
        result.error("PDF_OPEN_FAILED", str(exc), path.name)
        return
    try:
        if doc.page_count == 0:
            result.error("EMPTY_DOCUMENT", "PDF has zero pages", path.name)
            return
        all_text: list[str] = []
        image_total = 0
        for index, page in enumerate(doc):
            rect = page.rect
            if abs(rect.width - A4[0]) > SIZE_TOLERANCE_PT or abs(rect.height - A4[1]) > SIZE_TOLERANCE_PT:
                result.error(
                    "PAGE_SIZE_INVALID",
                    f"page {index + 1}: {rect.width:.1f}x{rect.height:.1f}pt, expected A4",
                    path.name,
                )
            text = page.get_text("text")
            images = page.get_images(full=True)
            image_total += len(images)
            if not text.strip() and not images and not page.get_drawings():
                result.error("EMPTY_PAGE", f"page {index + 1} has no text, images or drawings", path.name)
            if "\ufffd" in text:
                result.error("REPLACEMENT_CHARACTER", f"page {index + 1} contains U+FFFD", path.name)
            for link in page.get_links():
                kind = link.get("kind")
                if kind == fitz.LINK_URI and not str(link.get("uri", "")).startswith(
                    ("http://", "https://", "mailto:")
                ):
                    result.error("BROKEN_EXTERNAL_LINK", f"page {index + 1}: {link.get('uri')!r}", path.name)
                if kind == fitz.LINK_GOTO:
                    target = link.get("page", -1)
                    if not isinstance(target, int) or target < 0 or target >= doc.page_count:
                        result.error("BROKEN_INTERNAL_LINK", f"page {index + 1}: invalid target {target}", path.name)
            all_text.append(text)

        joined = "\n".join(all_text)
        joined_norm = norm(joined)
        normalized_lines = [norm(line) for line in joined.splitlines()]
        if any(re.fullmatch(r"(?:##\s*)?conexoes", line) for line in normalized_lines):
            result.error("CONEXOES_EXPORTED", "internal Conexões section is visible in PDF", path.name)

        source = _source_for(path)
        if source:
            md = source.read_text(encoding="utf-8-sig")
            h1 = re.search(r"(?m)^#\s+(.+)$", md)
            if h1:
                raw_title = h1.group(1).strip()
                plain_title = strip_md_inline(raw_title)
                if not text_contains(joined_norm, norm(plain_title)):
                    result.error("TITLE_MISSING", f"source title not found in PDF: {raw_title}", path.name)
            if "Gustavo Zambrano" in md and not text_contains(joined_norm, norm("Gustavo Zambrano")):
                result.error("AUTHOR_MISSING", "author missing from rendered PDF", path.name)
            if "## Sumário" in md and not text_contains(joined_norm, norm("Sumário")):
                result.error("SUMARIO_MISSING", "source has Sumário but PDF text does not", path.name)
            if "## Referências" in md and not text_contains(joined_norm, norm("Referências")):
                result.error("REFERENCES_MISSING", "source has Referências but PDF text does not", path.name)
            source_images = len(re.findall(r"!\[[^\]]*\]\([^\)]+\)", md))
            if source_images and image_total < source_images:
                result.error(
                    "IMAGE_MISSING",
                    f"source has {source_images} image(s), PDF exposes {image_total}",
                    path.name,
                )
    finally:
        doc.close()


def audit(slug: str | None = None) -> CheckResult:
    result = CheckResult("pdf-content")
    files = sorted(PDF_DIR.glob(f"{slug or '*'}.pdf")) if PDF_DIR.exists() else []
    if not files:
        result.skip("NO_PDF", f"no PDFs in {PDF_DIR}")
        return result
    for path in files:
        audit_file(path, result)
    result.meta["files"] = len(files)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug", nargs="?", help="optional PDF stem; default audits all PDFs")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on-warning", action="store_true")
    args = ap.parse_args()
    result = audit(args.slug)
    result.print(args.json)
    return result.exit_code(args.fail_on_warning)


if __name__ == "__main__":
    raise SystemExit(main())
