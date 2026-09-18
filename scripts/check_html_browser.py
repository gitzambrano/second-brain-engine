#!/usr/bin/env python3
"""
Validação em navegador dos arquivos HTML standalone exportados.

Default sem argumentos: auditar cada ``output/html/*.html`` nos viewports de
celular e de desktop. Se não existir HTML (modo esqueleto, normal), reportar
SKIP.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from repo_paths import HTML_DIR
from sanity_common import (
    CHROMIUM_ABSENT,
    PLAYWRIGHT_ABSENT,
    CheckResult,
    resolve_chromium,
)

VIEWPORTS = ((390, 844, "mobile"), (1440, 900, "desktop"))

# Fórmula dentro de célula pode ser um pouco menor que a da prosa — `td` herda
# um corpo menor que o do texto corrido. Abaixo desta fração da escala da prosa
# não é hierarquia tipográfica, é a fórmula sendo esmagada pela largura da
# célula: a `max-width:100%` do MathJax já reduziu equação de 35ex a 4px de
# altura, ilegível, e sem disparar nenhuma checagem de overflow.
MATH_CELL_MIN_RATIO = 0.75


def audit_file(browser, path: Path, result: CheckResult) -> None:
    for width, height, label in VIEWPORTS:
        page = browser.new_page(viewport={"width": width, "height": height})
        console_errors: list[str] = []
        failed: list[str] = []
        page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        page.on("requestfailed", lambda req: failed.append(req.url))
        raw = path.read_text(encoding="utf-8", errors="replace")
        page.set_content(raw, wait_until="load")
        # Wait for MathJax before measuring. A page caught mid-typeset
        # still has raw TeX laid out as running text, which reports a
        # width the finished page does not have — and the naive
        # "MathJax is absent" guard passed instantly, because at that
        # moment its script had simply not run yet.
        if "MathJax" in raw:
            try:
                # Await MathJax's own startup promise. A state() >= N
                # guard is not enough: the early states are reached
                # almost immediately, so the page was still measured
                # mid-typeset, with raw TeX laid out as running text.
                page.wait_for_function(
                    "() => !!(window.MathJax && window.MathJax.startup"
                    " && window.MathJax.startup.promise)",
                    timeout=30000,
                )
                # Bounded: a document whose typeset never settles would
                # otherwise hang the whole audit on an await with no timeout.
                page.evaluate(
                    "async () => {"
                    " const p = window.MathJax && window.MathJax.startup"
                    " && window.MathJax.startup.promise;"
                    " if (!p) return;"
                    " await Promise.race([p, new Promise(r => setTimeout(r, 20000))]); }"
                )
            except Exception:  # noqa: BLE001 - measure anyway, never hang
                pass
        page.wait_for_timeout(400)
        data = page.evaluate("""() => ({
          docWidth: document.documentElement.scrollWidth,
          innerWidth: window.innerWidth,
          badImages: [...document.images].filter(i => !i.complete || i.naturalWidth === 0).map(i => i.src),
          brokenAnchors: [...document.querySelectorAll('a[href^="#"]')]
            .map(a => a.getAttribute('href').slice(1)).filter(id => id && !document.getElementById(id)),
          rawWikilinks: (() => {
          const clean = document.body.cloneNode(true);
          clean.querySelectorAll('pre, code, script, style').forEach(el => el.remove());
          const text = clean.textContent || '';
          return text.includes('[[') && text.includes(']]');
          })(),
          rawFencedDiv: document.body.innerText.includes(':::{') || document.body.innerText.includes('::: {'),
          // Escala real do MathJax: altura renderizada dividida pela altura
          // declarada em `ex`. Numa fórmula espremida por `max-width` a razão
          // despenca e a equação vira um risco de 4px — a checagem de overflow
          // não pega, porque encolher é justamente o que evita o overflow.
          mathScale: (() => {
            const px = el => {
              const svg = el.querySelector('svg');
              if (!svg) return null;
              const ex = parseFloat(svg.getAttribute('height'));
              if (!ex) return null;
              return svg.getBoundingClientRect().height / ex;
            };
            const all = [...document.querySelectorAll('mjx-container:not([display="true"])')];
            const cell = all.filter(e => e.closest('td,th')).map(px).filter(Boolean);
            const prose = all.filter(e => !e.closest('td,th')).map(px).filter(Boolean);
            if (!cell.length || !prose.length) return null;
            const med = a => [...a].sort((x, y) => x - y)[Math.floor(a.length / 2)];
            return {minCell: Math.min(...cell), medProse: med(prose), n: cell.length};
          })()
        })""")
        if data["docWidth"] > data["innerWidth"] + 2:
            result.error(
                "PAGE_HORIZONTAL_OVERFLOW",
                f"{label}: document {data['docWidth']}px > viewport {data['innerWidth']}px",
                path.name,
            )
        if data["badImages"]:
            result.error(
                "BROKEN_IMAGE",
                f"{label}: {len(data['badImages'])} image(s) failed",
                path.name,
                details=data["badImages"][:5],
            )
        if data["brokenAnchors"]:
            result.error(
                "BROKEN_TOC_NAVIGATION",
                f"{label}: broken anchors {data['brokenAnchors'][:5]}",
                path.name,
            )
        if data["rawWikilinks"]:
            result.error("VISIBLE_WIKILINK", f"{label}: raw [[wikilink]] visible", path.name)
        if data["rawFencedDiv"]:
            result.error("VISIBLE_FENCED_DIV", f"{label}: fenced div marker visible", path.name)
        scale = data["mathScale"]
        if scale and scale["minCell"] < MATH_CELL_MIN_RATIO * scale["medProse"]:
            result.error(
                "MATH_SHRUNK_IN_CELL",
                f"{label}: fórmula em célula a {scale['minCell']:.2f}px/ex contra "
                f"{scale['medProse']:.2f}px/ex na prosa ({scale['n']} fórmulas em tabela)",
                path.name,
            )

        ref_check = page.evaluate("""() => {
          const anchor = document.querySelector('a.ref-cite');
          if (!anchor) return { present: false };
          anchor.click();
          const popup = document.querySelector('#ref-popup.is-active');
          if (!popup) return { present: true, opened: false };
          const popRect = popup.getBoundingClientRect();
          const overflow = popRect.right > window.innerWidth + 2 || popRect.left < -2;
          return {
            present: true,
            opened: true,
            hasContent: (popup.innerText || '').length > 10,
            overflow: overflow
          };
        }""")
        if ref_check.get("present") and not ref_check.get("opened"):
            result.error("REF_POPUP_FAILED", f"{label}: footnote popup did not open on click", path.name)
        if ref_check.get("present") and ref_check.get("overflow"):
            result.error("REF_POPUP_OVERFLOW", f"{label}: footnote popup overflows viewport", path.name)

        for message in console_errors[:5]:
            result.error("CONSOLE_ERROR", f"{label}: {message}", path.name)
        for url in failed[:5]:
            # file:// requests for intentionally absent local links are not page resources.
            if not url.startswith("file://"):
                result.error("FAILED_REQUEST", f"{label}: {url}", path.name)
        page.close()


def audit(slug: str | None = None) -> CheckResult:
    result = CheckResult("html-render")
    files = sorted(HTML_DIR.glob(f"{slug or '*'}.html")) if HTML_DIR.exists() else []
    if not files:
        result.skip("NO_HTML", f"no HTML exports in {HTML_DIR}")
        return result
    estado, executable, detalhe = resolve_chromium()
    if estado == PLAYWRIGHT_ABSENT:
        result.skip("PLAYWRIGHT_MISSING", f"browser validation unavailable; {detalhe}")
        return result
    if estado == CHROMIUM_ABSENT:
        result.skip("CHROMIUM_MISSING", detalhe)
        return result

    from playwright.sync_api import sync_playwright

    # One browser for the whole audit. Launching Chromium per file cost more
    # than the checking did: 47 exports meant 47 cold starts.
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=executable)
        try:
            for path in files:
                audit_file(browser, path, result)
        finally:
            browser.close()

    result.meta["files"] = len(files)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug", nargs="?", help="optional export stem; default audits all HTML")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on-warning", action="store_true")
    args = ap.parse_args()
    result = audit(args.slug)
    result.print(args.json)
    return result.exit_code(args.fail_on_warning)


if __name__ == "__main__":
    raise SystemExit(main())
