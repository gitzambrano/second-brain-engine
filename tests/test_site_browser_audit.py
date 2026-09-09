"""Auditoria visual do site num navegador de verdade.

Marcado `browser`: só roda no job de CI que instala Chromium, e é pulado em
qualquer máquina sem navegador. É o único teste que abre `graph.html` e
`sphere.html` — as duas superfícies mais pesadas em JavaScript do site, e as
únicas cujos defeitos ninguém via antes de chegarem ao celular do leitor.

O que ele prende, superfície por superfície:

- a página pinta o fundo do tema pedido (foi um fundo escuro preso no tema
  claro que chegou ao celular);
- nada de erro de console nem requisição falha;
- nada de rolagem horizontal;
- o mapa carrega dados, tem canvas com área e responde à legenda;
- o globo abre com a bibliografia DESLIGADA, que é a decisão de projeto: são
  centenas de nós de referência que escondem a malha de ideias.

As capturas das oito superfícies vão para `tmp_path` e, na CI, para os
artefatos do job — servem para olhar quando algo falha, não como baseline de
pixel: comparação por pixel entre sistemas operacionais reprova por
antialiasing de fonte, não por regressão.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import ROOT

pytestmark = pytest.mark.browser

sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

SURFACES = [
    ("home-light-desktop", "index.html", "light", (1440, 900)),
    ("home-dark-desktop", "index.html", "dark", (1440, 900)),
    ("home-mobile", "index.html", "light", (390, 844)),
    ("essay-light", "essays/dutch-roll.html", "light", (1440, 900)),
    ("essay-dark", "essays/dutch-roll.html", "dark", (1440, 900)),
    ("essay-mobile", "essays/dutch-roll.html", "light", (390, 844)),
    ("graph", "graph.html", "light", (1440, 900)),
    ("sphere", "sphere.html", "light", (1440, 900)),
]

THEME_BG = {"light": (255, 255, 255), "dark": (9, 9, 9)}


def _chromium():
    import sanity_common

    state, executable, detail = sanity_common.resolve_chromium()
    if state in (sanity_common.PLAYWRIGHT_ABSENT, sanity_common.CHROMIUM_ABSENT):
        pytest.skip(f"sem navegador: {detail}")
    return executable


def _essay(path, title, body):
    path.write_text(
        "---\ntags: [Teste]\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
        f"summary: resumo de {title} com tamanho suficiente para o catálogo "
        "mostrar uma frase inteira e não um fragmento cortado no meio.\n"
        "status: draft\nvisibility: public\n---\n"
        f"# {title}\n\n{body}\n",
        encoding="utf-8",
    )


@pytest.fixture(scope="module")
def built_site(tmp_path_factory):
    """Um site pequeno, mas com as mesmas páginas e o mesmo pipeline."""
    tmp = tmp_path_factory.mktemp("browser-site")
    data, site = tmp / "data", tmp / "site"
    essays = data / "wiki" / "essays"
    essays.mkdir(parents=True)
    site.mkdir()
    (site / ".second-brain-site").write_text("marker", encoding="utf-8")

    _essay(
        essays / "dutch-roll.md", "Dutch Roll",
        "## Sumário\n\n- [[#Um]]\n\n---\n\n## Um\n\nTexto público de teste, "
        "longo o bastante para a página ter corpo e o sumário ter destino.\n",
    )
    _essay(essays / "segundo.md", "Segundo Ensaio", "## Sumário\n\n- [[#Um]]\n\n---\n\n## Um\n\nOutro texto.\n")

    env = os.environ.copy()
    env["SECOND_BRAIN_DATA_ROOT"] = str(data)
    env["SECOND_BRAIN_SITE_ROOT"] = str(site)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_site.py")],
        cwd=ROOT, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return site


@pytest.fixture(scope="module")
def server(built_site):
    from check_site_pages import SiteServer

    with SiteServer(built_site) as base:
        yield base, built_site


def _open(browser, base, surface, shots: Path):
    name, page_path, theme, (width, height) = surface
    context = browser.new_context(viewport={"width": width, "height": height})
    context.route(
        "https://gustavo-jose-zambrano.kit.com/**",
        lambda route: route.fulfill(
            status=200, content_type="application/javascript", body=""
        ),
    )
    context.add_init_script(
        "try{localStorage.setItem('sb-theme',%r)}catch(e){}" % theme
    )
    page = context.new_page()
    errors: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("response", lambda r: errors.append(f"{r.status} {r.url}") if r.status >= 400 else None)
    page.goto(f"{base}/{page_path}", wait_until="load")
    page.wait_for_timeout(2500)
    shots.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(shots / f"{name}.png"), full_page=False)
    return page, context, [e for e in errors if "favicon" not in e.lower()]


@pytest.mark.parametrize("surface", SURFACES, ids=lambda s: s[0])
def test_every_surface_renders_clean(surface, server, tmp_path_factory):
    executable = _chromium()
    from playwright.sync_api import sync_playwright

    base, _site = server
    name, _page_path, theme, _viewport = surface
    shots = Path(tmp_path_factory.getbasetemp()) / "screenshots"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=executable)
        try:
            page, context, errors = _open(browser, base, surface, shots)
            try:
                assert not errors, f"{name}: console/rede sujos: {errors[:3]}"

                geometry = page.evaluate(
                    "() => ({doc: document.documentElement.scrollWidth,"
                    " win: window.innerWidth,"
                    " theme: document.documentElement.getAttribute('data-theme')})"
                )
                assert geometry["theme"] == theme, f"{name}: tema {geometry['theme']}"
                assert geometry["doc"] <= geometry["win"] + 1, (
                    f"{name}: rolagem horizontal ({geometry['doc']} > {geometry['win']})"
                )

                painted = page.evaluate(
                    "() => getComputedStyle(document.body).backgroundColor"
                )
                numbers = [int(n) for n in painted.replace("rgba", "rgb").strip("rgb() ").split(",")[:3]]
                expected = THEME_BG[theme]
                assert all(abs(a - b) <= 24 for a, b in zip(numbers, expected)), (
                    f"{name}: fundo {painted} não é o do tema {theme} ({expected})"
                )
            finally:
                context.close()
        finally:
            browser.close()

    assert (shots / f"{name}.png").stat().st_size > 2000, f"{name}: captura em branco"


def test_the_globe_opens_with_the_bibliography_off(server):
    """Decisão de projeto, não acaso: o globo abre sem os nós de referência."""
    executable = _chromium()
    from playwright.sync_api import sync_playwright

    base, _site = server
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=executable)
        try:
            page = browser.new_page()
            page.goto(f"{base}/sphere.html", wait_until="load")
            page.wait_for_timeout(2000)
            state = page.evaluate(
                "() => ({hidden: [...hiddenTypes],"
                " disabled: [...document.querySelectorAll('.legend-item.disabled')]"
                "   .map(e => e.getAttribute('data-type'))})"
            )
            assert "reference" in state["hidden"], "globo abriu com a bibliografia ligada"
            assert "reference" in state["disabled"], "legenda não mostra o tipo desligado"

            flat = browser.new_page()
            flat.goto(f"{base}/graph.html", wait_until="load")
            flat.wait_for_timeout(2000)
            plano = flat.evaluate(
                "() => ({hidden: [...hiddenTypes],"
                " disabled: [...document.querySelectorAll('.legend-item.disabled')]"
                "   .map(e => e.getAttribute('data-type'))})"
            )
            assert "reference" in plano["hidden"], "o grafo plano deve abrir com a bibliografia desligada"
            assert "reference" in plano["disabled"], "legenda do grafo plano não mostra o tipo desligado"
        finally:
            browser.close()


def test_the_maps_survive_a_resize(server):
    executable = _chromium()
    from playwright.sync_api import sync_playwright

    base, _site = server
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=executable)
        try:
            for page_name in ("graph.html", "sphere.html"):
                context = browser.new_context(viewport={"width": 1440, "height": 900})
                page = context.new_page()
                errors: list[str] = []
                page.on("pageerror", lambda e: errors.append(str(e)))
                page.goto(f"{base}/{page_name}", wait_until="load")
                page.wait_for_timeout(1500)
                page.set_viewport_size({"width": 390, "height": 844})
                page.wait_for_timeout(1200)
                size = page.evaluate(
                    "() => { const c = document.querySelector('canvas#graph');"
                    " const r = c.getBoundingClientRect();"
                    " return {w: Math.round(r.width), h: Math.round(r.height)}; }"
                )
                assert size["w"] <= 400, f"{page_name}: canvas não acompanhou o resize ({size})"
                assert size["h"] > 200, f"{page_name}: canvas colapsou ({size})"
                assert not errors, f"{page_name}: erro no resize: {errors[:2]}"
                context.close()
        finally:
            browser.close()
