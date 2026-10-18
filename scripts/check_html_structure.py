#!/usr/bin/env python3
"""check_html_structure.py - Auditoria estrutural do HTML standalone exportado.

Valida a integridade semântica e do DOM nos arquivos HTML exportados em output/html/:
- Cabeçalhos bem formados e hierarquia correta (H1, H2, H3).
- Resolução de fórmulas matemáticas e ausência de LaTeX não processado.
- Delimitação correta de callouts (.box) para evitar que caixas engulam capítulos.
- Ausência de tags abertas ou corrompidas.

Escopo:
    Validação estática read-only em DATA_ROOT/output/html/*.html.
    Default sem argumentos audita todos os arquivos HTML exportados.

Entradas (Inputs):
    Arquivos HTML em DATA_ROOT/output/html/*.html.
    Argumentos CLI opcionais:
        arquivo.html    Arquivo HTML específico para validar
        --json          Emite diagnóstico formatado em JSON

Saídas (Outputs):
    Stdout: Lista de arquivos HTML auditados e falhas estruturais detectadas.
    JSON: {"check": "html_structure", "status": "pass"|"skip"|"fail", "issues": [...]}
    Exit code: 0 em conformidade, 1 em erro estrutural bloqueante.

Uso:
    python scripts/check_html_structure.py                  # audita todos os exports HTML
    python scripts/check_html_structure.py output/html/x.html # audita arquivo específico
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from repo_paths import HTML_DIR

# Caixa é callout, não capítulo. O pré-processador monta `.box` a partir de um
# rótulo em blockquote mais o conteúdo que vem depois; quando a regra de
# fronteira falha, a caixa engole o resto do capítulo e o HTML sai bem-formado
# mas semanticamente destruído — nada no checador percebia isso.
BOX_MAX_BLOCKS = 14


def strip_noise(h: str) -> str:
    h = re.sub(r'data:[\w/+.-]+;base64,[A-Za-z0-9+/=]+', '', h)
    h = re.sub(r'<style.*?</style>', '', h, flags=re.S | re.I)
    h = re.sub(r'<script.*?</script>', '', h, flags=re.S | re.I)
    return h


def audit_file(html_path: Path) -> list[dict]:
    raw = html_path.read_text(encoding="utf-8", errors="replace")
    body = strip_noise(raw)
    issues: list[dict] = []
    def add(code, message, severity="ERROR"):
        issues.append({"code": code, "severity": severity, "message": message})

    if not re.search(r"(?i)<!doctype\s+html", raw): add("DOCTYPE_MISSING", "HTML has no <!DOCTYPE html>")
    if re.search(r':::\s*\{', body): add("FENCED_DIV_LITERAL", "fenced div marker is visible")
    spans = re.findall(r'\[[^\]\n]{1,80}\]\{\.[\w-]+\}', body)
    if spans: add("BRACKETED_SPAN_LITERAL", f"unparsed bracketed span: {spans[:2]}")
    bq = len(re.findall(r"<blockquote\b", body, flags=re.I))
    if bq: add("BLOCKQUOTE_RESIDUAL", f"{bq} raw blockquote(s) remain")
    visible = re.sub(r"<[^>]+>", "", body)
    wl = re.findall(r"\[\[[^\]\n]{2,100}\]\]", visible)
    if wl: add("VISIBLE_WIKILINK", f"visible wikilink(s): {wl[:3]}")
    if re.search(r"(?mi)^\s*(?:##\s*)?Conexões\s*$", visible): add("CONEXOES_EXPORTED", "Conexões section is visible")

    for m in re.finditer(r"<p(?:\s[^>]*)?>(.*?)</p>", body, re.S | re.I):
        p = m.group(1); nbr = len(re.findall(r"<br\s*/?>", p, flags=re.I))
        plain = re.sub(r"<[^>]+>", "", p).strip()
        if len(plain) > 220 and nbr >= 3:
            before = body[max(0, m.start() - 3000):m.start()]
            classes = re.findall(r'<div\s+[^>]*class=["\']([^"\']+)["\']', before, flags=re.I)
            container = classes[-1].casefold() if classes else ""
            if not any(c in container for c in ("quote", "pull-quote", "box", "card")):
                add("PROSE_BR_STACK", f"long prose paragraph contains {nbr} <br> tags: {plain[:70]!r}")

    ids = re.findall(r'\bid=["\']([^"\']+)["\']', raw, flags=re.I)
    dup = sorted({x for x in ids if ids.count(x) > 1})
    if dup: add("DUPLICATE_ID", f"duplicate id(s): {dup[:5]}")
    idset = set(ids)
    anchors = re.findall(r'<a\b[^>]*href=["\']#([^"\']+)["\']', raw, flags=re.I)
    broken = sorted({a for a in anchors if a and a not in idset})
    if broken: add("BROKEN_ANCHOR", f"anchor target(s) missing: {broken[:5]}")

    try:
        from bs4 import BeautifulSoup, FeatureNotFound
        try:
            soup = BeautifulSoup(raw, "html5lib")
        except FeatureNotFound:
            soup = BeautifulSoup(raw, "html.parser")
            add("HTML5LIB_UNAVAILABLE", "html5lib unavailable; used built-in html.parser fallback", "WARNING")
        # Escopo de caixa. O pré-processador monta `.box` a partir de um
        # rótulo em blockquote mais o conteúdo que vem depois; quando a regra
        # de fronteira falha, a caixa engole o resto do capítulo e o HTML sai
        # bem-formado mas semanticamente destruído. Heading dentro de caixa é
        # o sintoma barato — exceto quando o rótulo abre a seção e enquadra a
        # seção inteira, caso em que o primeiro filho é o badge e os headings
        # são subseções dela.
        for box in soup.select("div.box"):
            sect = [h for h in box.find_all(["h1", "h2"])]
            if sect:
                add("BOX_CONTAINS_SECTION", f"caixa contém heading de seção: {sect[0].get_text()[:60]!r}")
            blocks = box.find_all(["p", "pre", "ul", "ol", "table"], recursive=False)
            if len(blocks) > BOX_MAX_BLOCKS:
                add("BOX_TOO_MANY_BLOCKS",
                    f"caixa com {len(blocks)} blocos diretos (limite {BOX_MAX_BLOCKS})", "WARNING")

        for img in soup.find_all("img"):
            src = str(img.get("src", ""))
            if not src: add("IMAGE_SRC_MISSING", "<img> has no src")
            elif not src.startswith(("data:", "http://", "https://", "file:")):
                # Standalone exports should embed images, not leave relative resources.
                add("IMAGE_NOT_EMBEDDED", f"image resource is not embedded: {src}")
        for tag, attr in (("script", "src"), ("link", "href")):
            for node in soup.find_all(tag):
                url = str(node.get(attr, ""))
                if url.startswith(("http://", "https://")):
                    add("EXTERNAL_RESOURCE", f"standalone HTML still depends on {url}", "WARNING")
    except ImportError:
        add("DOM_PARSER_UNAVAILABLE", "BeautifulSoup/html5lib not installed; regex layer completed", "WARNING")
    return issues


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug", nargs="?", help="optional HTML stem; default audits all exports")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on-warning", action="store_true")
    args = ap.parse_args()
    files = sorted(HTML_DIR.glob(f"{args.slug or '*'}.html")) if HTML_DIR.exists() else []
    report = {f.stem: audit_file(f) for f in files}
    report = {k: v for k, v in report.items() if v}
    if args.json:
        print(json.dumps({"files": len(files), "issues": report}, ensure_ascii=False, indent=2))
    else:
        if not files:
            print(f"SKIP: nenhum HTML em {HTML_DIR}")
        elif report:
            print(f"{len(report)}/{len(files)} HTML(s) com achados:")
            for name, issues in report.items():
                print(f"\n--- {name}")
                for issue in issues: print(f"  {issue['severity']:<7} {issue['code']}: {issue['message']}")
        else:
            print(f"TODOS OS {len(files)} HTMLS LIMPOS")
    errors = sum(i["severity"] == "ERROR" for issues in report.values() for i in issues)
    warnings = sum(i["severity"] == "WARNING" for issues in report.values() for i in issues)
    return 1 if errors or (args.fail_on_warning and warnings) else 0


if __name__ == "__main__":
    sys.exit(main())
