#!/usr/bin/env python3
"""
Abre cada página do site público construído num navegador real e a audita.

`check_html_browser.py` cobre o export HTML standalone. As páginas do site são
outro artefato — o mesmo template de essay mais a sobreposição do Atlas, o
cromo próprio e a folha de estilo própria — e ninguém estava olhando para elas.
Este script olha: sobe SITE_ROOT numa porta local, abre cada página, espera o
MathJax e reporta o que um leitor encontraria de fato.

Verificado num celular e num desktop:
    overflow horizontal, imagem quebrada, âncora interna morta, requisição que
    falhou, erro de console, Markdown vazando no texto renderizado e — num
    essay — a barra do site, um sumário com entradas e um título de capa sem
    marcadores de Markdown.

Default sem argumentos: auditar todas as páginas de SITE_ROOT.
"""
from __future__ import annotations

import argparse
import http.server
import socketserver
import threading
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from time import monotonic

import console_encoding  # noqa: F401  (UTF-8 no console; ver o módulo)
from repo_paths import SITE_ROOT
from sanity_common import (
    CHROMIUM_ABSENT,
    PLAYWRIGHT_ABSENT,
    CheckResult,
    resolve_chromium,
)

READER_STATES = (
    (390, 844, "mobile-light", "light"),
    (390, 844, "mobile-dark", "dark"),
    (1440, 900, "desktop-light", "light"),
    (1440, 900, "desktop-dark", "dark"),
)
# Kept for the map/index checks, which are not reading surfaces.
VIEWPORTS = ((390, 844, "mobile"), (1440, 900, "desktop"))

# A auditoria completa (prosa, âncoras, imagens, console) roda nos dois
# viewports acima, por página. Abrir 48 páginas em seis larguras triplicaria o
# gate sem achar três vezes mais.
#
# Só que o risco de geometria não está espalhado: ele mora na CAPA, onde a
# barra tem busca + temas + quatro botões de modo disputando a mesma linha, e
# 320 e 360px ficavam sem cobertura nenhuma — justamente as larguras em que
# essa barra tem menos espaço. Estas páginas, e só elas, passam por uma
# varredura barata de geometria na matriz inteira.
GEOMETRY_MATRIX = (320, 360, 390, 768, 1024, 1440)
GEOMETRY_PAGES = ("index.html", "404.html")


@dataclass
class AuditBudget:
    """Orçamento único compartilhado por toda a auditoria visual."""

    max_seconds: float
    now: callable = monotonic

    def __post_init__(self) -> None:
        self.deadline = self.now() + max(0, self.max_seconds)

    @property
    def expired(self) -> bool:
        return self.now() >= self.deadline

    def timeout_ms(self, requested_ms: int) -> int:
        remaining = int((self.deadline - self.now()) * 1000)
        if remaining <= 0:
            raise TimeoutError("orçamento total da auditoria esgotado")
        return min(requested_ms, remaining)

GEOMETRY_PROBE = r"""() => {
  const root = document.documentElement;
  const fora = [...document.querySelectorAll('body *')]
    .filter(el => {
      const r = el.getBoundingClientRect();
      return r.width > 0 && (r.right > window.innerWidth + 1 || r.left < -1);
    })
    .slice(0, 3)
    .map(el => el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : ''));
  return {docWidth: root.scrollWidth, innerWidth: window.innerWidth, fora};
}"""

# A capa do índice é `background-image` num <a> vazio, não um <img>. Por isso
# `document.images` não a enxerga: o retrato podia sumir do site inteiro sem o
# gate piscar. Aqui a URL é resolvida e baixada de verdade.
COVER_PROBE = r"""async () => {
  const el = document.querySelector('.cover-map');
  if (!el) return {presente: false};
  const bg = getComputedStyle(el).backgroundImage;
  const m = /url\(["']?([^"')]+)["']?\)/.exec(bg);
  if (!m) return {presente: true, url: null, bg};
  try {
    const r = await fetch(m[1], {cache: 'no-store'});
    const b = await r.blob();
    return {presente: true, url: m[1], status: r.status, bytes: b.size, tipo: b.type};
  } catch (e) {
    return {presente: true, url: m[1], erro: String(e)};
  }
}"""

# The two maps are one 700 KB page each, with a force simulation that never
# settles inside a check's budget — so they get their own, lighter audit
# (`MAP_PROBE`) instead of the prose probe. Skipping them entirely left the two
# most JavaScript-heavy surfaces of the site unchecked by the only gate that
# opens a real browser.
MAPS = {"graph.html", "sphere.html"}

# The map's own JS pins `--bg` inline on <html>; the page background must end
# up matching the theme, which is exactly the defect that shipped to a phone.
MAP_PROBE = r"""() => {
  const canvas = document.querySelector('canvas#graph');
  const rect = canvas ? canvas.getBoundingClientRect() : {width: 0, height: 0};
  const root = document.documentElement;
  return {
    hasCanvas: !!canvas,
    canvasWidth: Math.round(rect.width),
    canvasHeight: Math.round(rect.height),
    docWidth: root.scrollWidth,
    innerWidth: window.innerWidth,
    nodes: (typeof data === 'object' && data && data.nodes) ? data.nodes.length : 0,
    theme: root.getAttribute('data-theme'),
    inlineBg: root.style.getPropertyValue('--bg').trim(),
    controls: {
      panel: !!document.getElementById('panel'),
      search: !!document.getElementById('search'),
      index: !!document.getElementById('btn-index'),
      legend: document.querySelectorAll('.legend-item[data-type]').length,
      back: !!document.getElementById('sb-back'),
      themeToggle: !!document.getElementById('sb-theme'),
    },
  };
}"""

PROBE = r"""() => {
  const content = document.querySelector('.content') || document.body;
  // ``[[...]]`` is an error in visible prose, but valid source code may use
  // it for nested arrays (e.g. ``np.array([[1.0]])``). Inspect a detached
  // copy with both fenced and inline code removed, so the auditor verifies
  // renderer leakage without asking code samples to avoid their own syntax.
  const prose = content.cloneNode(true);
  prose.querySelectorAll('pre,code').forEach(el => el.remove());
  const text = prose.innerText || '';
  return {
    docWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    badImages: [...document.images]
      .filter(i => !i.complete || i.naturalWidth === 0 || !i.getBoundingClientRect().width || !i.getBoundingClientRect().height)
      .map(i => i.getAttribute('src')),
    brokenAnchors: [...document.querySelectorAll('a[href^="#"]')]
      .map(a => a.getAttribute('href').slice(1))
      .filter(id => id && !document.getElementById(id)),
    rawWikilink: /\[\[[^\]\n]{1,80}\]\]/.test(text),
    rawFencedDiv: text.includes(':::{') || text.includes('::: {'),
    isEssay: !!document.querySelector('.sb-bar'),
    hasFab: !!document.querySelector('.sb-toc-fab'),
    tocLinks: document.querySelectorAll('#sbTocList a').length,
    headings: document.querySelectorAll('.content h2').length,
    coverTitle: (document.querySelector('.hero-title') || {}).textContent || '',
    editorialFonts: ['Playfair Display', 'Source Serif 4', 'JetBrains Mono']
      .filter(name => !(document.fonts && document.fonts.check('16px "' + name + '"'))),
    tocOverflow: (() => { const el=document.getElementById('sbToc'); return el && !el.hidden && el.scrollWidth > el.clientWidth + 1; })(),
    escaped: [...document.querySelectorAll('table,pre,mjx-container,.sb-toc')]
      .filter(el => {
        const r=el.getBoundingClientRect();
        if (!(r.width > 0 && (r.left < -1 || r.right > innerWidth + 1))) return false;
        const table=el.closest('table');
        if (table && el !== table) {
          const tr=table.getBoundingClientRect();
          const overflow=getComputedStyle(table).overflowX;
          if ((overflow === 'auto' || overflow === 'scroll') && tr.left >= -1 && tr.right <= innerWidth + 1) return false;
        }
        return true;
      })
      .map(el => el.tagName.toLowerCase() + (el.className ? '.' + String(el.className).split(' ')[0] : '')),
    controlsOutside: [...document.querySelectorAll('#sbTheme,#sbSubscribe,#sbTocFab,#sbTocClose')]
      .filter(el => { const r=el.getBoundingClientRect(); return r.width > 0 && (r.left < -1 || r.right > innerWidth + 1 || r.top < -1 || r.bottom > innerHeight + 1); })
      .map(el => el.id)
  };
}"""

# `_` and `*` in a rendered cover title mean the Markdown emphasis of the H1
# survived into text that no longer renders Markdown.
MARKDOWN_MARKERS = ("_", "*")


class SiteServer:
    """Serve SITE_ROOT on an ephemeral port for the duration of the audit.

    Loading the pages over `file://` is not equivalent: the browser blocks the
    index's own `fetch("graph.json")` as a cross-origin request, so the check
    would report a failure the deployed site never has.
    """

    def __init__(self, root: Path):
        handler = partial(QuietHandler, directory=str(root))
        self.server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> str:
        self.thread.start()
        return f"http://127.0.0.1:{self.port}"

    def __exit__(self, *exc) -> None:
        self.server.shutdown()
        self.server.server_close()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # noqa: D102 - keep the report clean
        pass


def audit_page(page, url: str, path: Path, label: str, result: CheckResult,
               console_errors: list[str], failed: list[str]) -> None:
    console_errors.clear()
    failed.clear()
    page.goto(url, wait_until="load", timeout=60000)
    try:
        page.wait_for_function(
            "() => !document.querySelector('script[src*=mathjax]')"
            " || !!(window.MathJax && window.MathJax.startup"
            " && window.MathJax.startup.promise)",
            timeout=20000,
        )
        # Bounded: an await on a promise that never settles has no timeout of
        # its own and would hang the audit instead of failing the page.
        page.evaluate(
            "async () => {"
            " const p = window.MathJax && window.MathJax.startup"
            " && window.MathJax.startup.promise;"
            " if (!p) return;"
            " await Promise.race([p, new Promise(r => setTimeout(r, 20000))]); }"
        )
    except Exception:  # noqa: BLE001 - measure anyway, never hang the check
        pass
    page.wait_for_timeout(300)

    data = page.evaluate(PROBE)
    name = path.name

    if data["docWidth"] > data["innerWidth"] + 2:
        result.error(
            "PAGE_HORIZONTAL_OVERFLOW",
            f"{label}: document {data['docWidth']}px > viewport {data['innerWidth']}px",
            name,
        )
    for src in data["badImages"]:
        result.error("IMAGE_NOT_LOADED", f"{label}: {src}", name)
    for anchor in data["brokenAnchors"]:
        result.error("BROKEN_ANCHOR", f"{label}: #{anchor}", name)
    if data["rawWikilink"]:
        result.error("RAW_WIKILINK", f"{label}: [[...]] visible in the page", name)
    if data["rawFencedDiv"]:
        result.error("RAW_FENCED_DIV", f"{label}: ::: block visible in the page", name)

    if data["isEssay"]:
        if data["editorialFonts"]:
            result.error(
                "EDITORIAL_FONT_UNAVAILABLE",
                f"{label}: {', '.join(data['editorialFonts'])}", name,
            )
        if data["tocOverflow"]:
            result.error("TOC_OVERFLOW", f"{label}: sumário excede sua largura", name)
        if data["escaped"]:
            result.error("READER_ELEMENT_OVERFLOW", f"{label}: {', '.join(data['escaped'][:4])}", name)
        if data["controlsOutside"]:
            result.error(
                "CONTROL_OUTSIDE_VIEWPORT",
                f"{label}: {', '.join(data['controlsOutside'])}", name,
            )
        if data["headings"] and not data["tocLinks"]:
            result.error("EMPTY_SUMMARY", f"{label}: essay has chapters but no summary", name)
        if not data["hasFab"]:
            result.error("NO_SUMMARY_CONTROL", f"{label}: summary cannot be opened", name)
        title = data["coverTitle"]
        if any(marker in title for marker in MARKDOWN_MARKERS):
            result.error("MARKDOWN_IN_COVER_TITLE", f"{label}: {title[:60]}", name)

    for message in console_errors:
        if "favicon" in message.lower():
            continue
        result.error("CONSOLE_ERROR", f"{label}: {message[:160]}", name)
    for url in dict.fromkeys(failed):
        if "favicon" in url:
            continue
        result.error("FAILED_REQUEST", f"{label}: {url}", name)


def audit_map(page, url, path, label, result, console_errors, failed):
    """Auditoria leve dos dois mapas: sobe, desenha, responde e troca de tema.

    Não espera a simulação assentar — o que interessa é que a página
    inicializa, tem canvas com área, tem os controles, não solta erro de
    console e responde a interação e a resize. A dívida que isto paga: um
    fundo escuro preso no tema claro chegou ao celular do leitor sem que
    nenhum gate tivesse aberto `graph.html` uma vez sequer.
    """
    name = path.name
    console_errors.clear()
    failed.clear()
    page.goto(url, wait_until="load")
    page.wait_for_timeout(2500)

    probe = page.evaluate(MAP_PROBE)

    if not probe["hasCanvas"]:
        result.error("MAP_NO_CANVAS", f"{label}: sem canvas#graph", name)
        return
    if probe["canvasWidth"] < 200 or probe["canvasHeight"] < 200:
        result.error(
            "MAP_CANVAS_COLLAPSED",
            f"{label}: canvas {probe['canvasWidth']}x{probe['canvasHeight']}",
            name,
        )
    if probe["nodes"] < 1:
        result.error("MAP_NO_DATA", f"{label}: nenhum nó carregado", name)
    if probe["docWidth"] > probe["innerWidth"] + 1:
        result.error(
            "HORIZONTAL_OVERFLOW",
            f"{label}: {probe['docWidth']}px > {probe['innerWidth']}px",
            name,
        )

    missing = [k for k, v in probe["controls"].items() if not v]
    if missing:
        result.error("MAP_CONTROL_MISSING", f"{label}: {', '.join(missing)}", name)

    # O tema tem que mandar no fundo — e mandar mesmo quando existe um estilo
    # salvo pelo painel Estilo. Esse era o defeito real: `applyStyle` grava
    # `--bg` inline no <html>, inline vence a folha, e o mapa abria com fundo
    # escuro e painéis claros. Sem semear o estilo fixado aqui, o gate passa
    # num navegador limpo e o leitor com histórico continua vendo o bug.
    chave = "sb-sphere-style-v1" if name.startswith("sphere") else "sb-graph-style-v1"
    page.evaluate(
        """k => {
          try {
            localStorage.setItem(k, JSON.stringify({colors: {background: '#1b1e21', edge: '#9aa0a8'}}));
          } catch (e) {}
        }""",
        chave,
    )
    for theme, esperado in (("light", "#ffffff"), ("dark", "#090909")):
        page.evaluate("t => { try { localStorage.setItem('sb-theme', t); } catch (e) {} }", theme)
        page.reload(wait_until="load")
        page.wait_for_timeout(1500)
        depois = page.evaluate(MAP_PROBE)
        if depois["theme"] != theme:
            result.error("MAP_THEME_IGNORED", f"{label}: pediu {theme}, veio {depois['theme']}", name)
        elif depois["inlineBg"].lower() != esperado:
            result.error(
                "MAP_BACKGROUND_STUCK",
                f"{label}: tema {theme} com --bg {depois['inlineBg'] or '(vazio)'}",
                name,
            )

    # Interação básica: um clique na legenda tem que desligar aquele tipo. O
    # clique é despachado pelo DOM, não pelo mouse: no celular o painel abre
    # recolhido e o Playwright recusaria o alvo por invisibilidade, o que
    # testaria o painel em vez do handler.
    alternou = page.evaluate(
        """() => {
          const el = document.querySelector('.legend-item[data-type="essay"]');
          if (!el) return null;
          const antes = el.classList.contains('disabled');
          el.click();
          return antes !== el.classList.contains('disabled');
        }"""
    )
    if alternou is False:
        result.error("MAP_LEGEND_INERT", f"{label}: clique na legenda não alternou", name)
    elif alternou is None:
        result.error("MAP_CONTROL_MISSING", f"{label}: legenda sem item de essay", name)

    for message in console_errors:
        if "favicon" in message.lower():
            continue
        result.error("CONSOLE_ERROR", f"{label}: {message[:160]}", name)
    for url_falho in dict.fromkeys(failed):
        if "favicon" in url_falho:
            continue
        result.error("FAILED_REQUEST", f"{label}: {url_falho}", name)


def audit_geometry(page, base: str, result: CheckResult) -> int:
    """Varre a capa e o 404 na matriz de larguras, só medindo geometria.

    Barato de propósito: não espera MathJax, não lê prosa, não abre essay. O que
    procura é a barra de ferramentas transbordando numa tela estreita — o único
    defeito de layout que 320 e 360px produzem e 390 não.
    """
    conferidas = 0
    for nome in GEOMETRY_PAGES:
        if not (SITE_ROOT / nome).is_file():
            continue
        for largura in GEOMETRY_MATRIX:
            page.set_viewport_size({"width": largura, "height": 800})
            page.goto(f"{base}/{nome}", wait_until="load")
            page.wait_for_timeout(350)
            m = page.evaluate(GEOMETRY_PROBE)
            conferidas += 1
            if m["docWidth"] > m["innerWidth"] + 1:
                culpados = ", ".join(m["fora"]) or "(elemento não identificado)"
                result.error(
                    "HORIZONTAL_OVERFLOW",
                    f"{largura}px: {m['docWidth']}px > {m['innerWidth']}px — {culpados}",
                    nome,
                )
    return conferidas


def audit_cover(page, base: str, result: CheckResult) -> None:
    """A capa do índice tem de existir e carregar de verdade."""
    if not (SITE_ROOT / "index.html").is_file():
        return
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(f"{base}/index.html", wait_until="load")
    page.wait_for_timeout(600)
    capa = page.evaluate(COVER_PROBE)

    if not capa.get("presente"):
        result.error("COVER_MISSING", "index.html não tem .cover-map", "index.html")
        return
    if not capa.get("url"):
        result.error("COVER_NO_IMAGE", f"sem background-image: {capa.get('bg')}", "index.html")
        return
    if capa.get("erro"):
        result.error("COVER_UNREACHABLE", f"{capa['url']}: {capa['erro']}", "index.html")
        return
    if capa.get("status") != 200:
        result.error("COVER_HTTP", f"{capa['url']} respondeu {capa.get('status')}", "index.html")
        return
    # Um PNG de capa real tem dezenas de KB. Um arquivo minúsculo aqui é
    # placeholder, erro de escrita ou uma página de erro servida como imagem.
    if capa.get("bytes", 0) < 8192:
        result.error(
            "COVER_TOO_SMALL",
            f"{capa['url']}: {capa.get('bytes')} bytes — capa ausente ou truncada",
            "index.html",
        )


def audit(name: str | None = None, allow_skip_browser: bool = False,
          max_seconds: float = 900) -> CheckResult:
    result = CheckResult("site-pages")
    budget = AuditBudget(max_seconds=max_seconds)
    result.meta["max_seconds"] = max_seconds
    if budget.expired:
        result.error("AUDIT_TIME_BUDGET_EXCEEDED", "orçamento visual esgotado antes de iniciar")
        return result

    if not (SITE_ROOT / ".second-brain-site").exists():
        result.skip("NO_SITE", f"site checkout not initialized: {SITE_ROOT}")
        return result

    pages = [p for p in sorted(SITE_ROOT.glob("*.html")) if p.name not in MAPS]
    pages += sorted((SITE_ROOT / "essays").glob("*.html"))
    maps = [SITE_ROOT / m for m in sorted(MAPS) if (SITE_ROOT / m).is_file()]
    if name:
        pages = [p for p in pages if p.name == name or p.stem == name]
        maps = [p for p in maps if p.name == name or p.stem == name]
    if not pages and not maps:
        result.skip("NO_PAGES", f"no pages to audit in {SITE_ROOT}")
        return result

    # Este é o gate visual obrigatório de `/publish`. Ausência de navegador
    # significa que a auditoria não aconteceu, e "não aconteceu" não pode
    # passar por "passou": sem `--allow-skip-browser` isso é erro. A flag
    # existe para diagnóstico local, onde pular é uma escolha consciente.
    estado, executable, detalhe = resolve_chromium()
    if estado in (PLAYWRIGHT_ABSENT, CHROMIUM_ABSENT):
        code = "PLAYWRIGHT_MISSING" if estado == PLAYWRIGHT_ABSENT else "CHROMIUM_MISSING"
        if allow_skip_browser:
            result.skip(code, f"{detalhe} (pulado por --allow-skip-browser)")
        else:
            result.error(
                code,
                f"auditoria visual não executada: {detalhe}. "
                f"Use --allow-skip-browser para pular conscientemente.",
            )
        return result

    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=True, executable_path=executable)
        try:
            with SiteServer(SITE_ROOT) as base:
                for width, height, label, theme in READER_STATES:
                    context = browser.new_context(viewport={"width": width, "height": height})
                    context.add_init_script(
                        "try{if(!localStorage.getItem('sb-theme'))"
                        "localStorage.setItem('sb-theme',%r)}catch(e){}" % theme
                    )
                    page = context.new_page()
                    console_errors: list[str] = []
                    failed: list[str] = []
                    page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
                    page.on("pageerror", lambda e: console_errors.append(str(e)))
                    page.on("requestfailed", lambda r: failed.append(r.url))
                    # A 404 is a *successful* response as far as Playwright is
                    # concerned, so `requestfailed` never sees it — and the console
                    # only says "404", never which file. Name it here.
                    page.on("response", lambda r: failed.append(f"{r.status} {r.url}")
                            if r.status >= 400 else None)
                    for path in pages:
                        if budget.expired:
                            result.error("AUDIT_TIME_BUDGET_EXCEEDED", "orçamento visual esgotado durante as páginas")
                            break
                        page.set_default_timeout(budget.timeout_ms(20_000))
                        relative = path.relative_to(SITE_ROOT).as_posix()
                        try:
                            audit_page(page, f"{base}/{relative}", path, label,
                                       result, console_errors, failed)
                        except Exception as exc:  # a página falhou, não o processo inteiro
                            result.error("PAGE_TIMEOUT", f"{label}: {exc}", path.name)
                    # Maps have their own light/dark interaction audit below; opening
                    # them for every essay-reader state only spends the corpus budget.
                    for path in (maps if label == "desktop-light" else ()):
                        if budget.expired:
                            result.error("AUDIT_TIME_BUDGET_EXCEEDED", "orçamento visual esgotado durante os mapas")
                            break
                        page.set_default_timeout(budget.timeout_ms(20_000))
                        relative = path.relative_to(SITE_ROOT).as_posix()
                        try:
                            audit_map(page, f"{base}/{relative}", path, label,
                                      result, console_errors, failed)
                        except Exception as exc:
                            result.error("PAGE_TIMEOUT", f"{label}: {exc}", path.name)
                    context.close()

                # Passadas de escopo próprio, uma vez cada — não por viewport.
                # Rodam na auditoria completa e também quando o alvo nomeado é a
                # própria capa: sem isso, `check_site_pages.py index.html` — a
                # forma mais natural de investigar a capa — era justamente a que
                # não a conferia.
                if not budget.expired and (not name or name in ("index.html", "index")):
                    contexto = browser.new_context(viewport={"width": 1440, "height": 900})
                    pagina = contexto.new_page()
                    try:
                        result.meta["geometry_checks"] = audit_geometry(pagina, base, result)
                        audit_cover(pagina, base, result)
                    finally:
                        contexto.close()
        finally:
            browser.close()

    result.meta["pages"] = len(pages)
    result.meta["maps"] = len(maps)
    result.meta["reader_states"] = [state[2] for state in READER_STATES]
    result.meta["geometry_matrix"] = list(GEOMETRY_MATRIX)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("page", nargs="?", help="optional page name or stem; default audits all")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on-warning", action="store_true")
    ap.add_argument("--max-seconds", type=float, default=900,
                    help="orçamento total da auditoria visual (padrão: 900)")
    ap.add_argument(
        "--allow-skip-browser",
        action="store_true",
        help="sem Chromium, reportar SKIP em vez de erro (diagnóstico local)",
    )
    args = ap.parse_args()
    result = audit(args.page, allow_skip_browser=args.allow_skip_browser,
                   max_seconds=args.max_seconds)
    result.print(args.json)
    return result.exit_code(args.fail_on_warning)


if __name__ == "__main__":
    raise SystemExit(main())
