"""Geometria do player de podcast do essay num navegador de verdade.

Marcado `browser`: precisa de Chromium e é pulado sem ele. O site é o mesmo
pipeline do build real, com um essay sintético; o player entra pela mesma
função de produção (`insert_podcast_player`) com a duração fixada, porque o
teste não depende de nenhum áudio.

Prende, em cada largura e em claro e escuro:

- a caixa ocupa a coluna de texto do essay e cabe na viewport;
- todo controle fica dentro da caixa, com alvo de toque >= 32 px;
- nada transborda, nem a página nem o player;
- o rótulo nunca é cortado, a duração fica visível e a forma curta só
  aparece quando a completa não cabe;
- o player vem depois do resumo da capa; essay sem podcast não tem player.

`SB_PLAYER_SHOTS=<pasta>` grava as capturas de cada largura.
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

WIDTHS = [320, 360, 375, 390, 412, 430, 600, 768, 1024, 1440]
SCHEMES = ["light", "dark"]
FULL = "Ouça um podcast gerado por IA sobre este ensaio"
SHORT = "Ouça um podcast gerado por IA"

MEASURE = """
() => {
  const r = e => { const b = e.getBoundingClientRect();
    return {l: b.left, r: b.right, t: b.top, b: b.bottom, w: b.width, h: b.height}; };
  const p = document.querySelector('[data-sb-podcast]');
  const content = document.querySelector('main.content');
  const cs = getComputedStyle(content);
  const col = r(content);
  col.l += parseFloat(cs.paddingLeft); col.r -= parseFloat(cs.paddingRight);
  const label = p.querySelector('.sb-pc-label');
  const vis = e => e.offsetParent !== null && getComputedStyle(e).display !== 'none';
  const full = p.querySelector('.sb-pc-label-full'), short = p.querySelector('.sb-pc-label-short');
  const dur = p.querySelector('.sb-pc-label-dur');
  const controls = [...p.querySelectorAll('.sb-pc-play,.sb-pc-back,.sb-pc-seek,.sb-pc-fwd,.sb-pc-speed,.sb-pc-dl')]
    .map(e => ({cls: e.className.split(' ').pop(), shown: vis(e), ...r(e)}));
  const children = [...p.children].filter(vis).map(e => ({cls: e.className, ...r(e)}));
  // largura natural da forma completa, em uma linha, no espaço do rótulo
  label.classList.add('is-measuring');
  const fullFits = label.scrollWidth <= label.clientWidth + 1;
  label.classList.remove('is-measuring');
  const summary = document.querySelector('.cover-summary');
  return {
    box: r(p), col, vw: document.documentElement.clientWidth,
    docScroll: document.documentElement.scrollWidth,
    playerScroll: p.scrollWidth, playerClient: p.clientWidth,
    controls, children,
    label: {sw: label.scrollWidth, cw: label.clientWidth, sh: label.scrollHeight, ch: label.clientHeight,
            fullShown: vis(full), shortShown: vis(short), durShown: vis(dur), fullFits,
            text: label.innerText, durBox: r(dur), box: r(label)},
    afterSummary: !!(summary && (summary.compareDocumentPosition(p) & Node.DOCUMENT_POSITION_FOLLOWING)),
    summaryParent: summary && summary.parentElement === p.parentElement,
    directlyAfter: summary && summary.nextElementSibling === p,
  };
}
"""


def _chromium():
    import sanity_common

    state, executable, detail = sanity_common.resolve_chromium()
    if state in (sanity_common.PLAYWRIGHT_ABSENT, sanity_common.CHROMIUM_ABSENT):
        pytest.skip(f"sem navegador: {detail}")
    return executable


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("player-site")
    data, site = tmp / "data", tmp / "site"
    essays = data / "wiki" / "essays"
    essays.mkdir(parents=True)
    site.mkdir()
    (site / ".second-brain-site").write_text("marker", encoding="utf-8")
    (essays / "com-podcast.md").write_text(
        "---\ntags: [Teste]\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
        "summary: Um resumo descritivo com tamanho realista, longo o bastante para ocupar "
        "várias linhas na capa e provar que o player vem depois dele e não antes.\n"
        "status: draft\nvisibility: public\n---\n"
        "# Com Podcast\n\n## Sumário\n\n- [[#Um]]\n\n---\n\n## Um\n\nTexto público.\n",
        encoding="utf-8",
    )
    (essays / "sem-podcast.md").write_text(
        (essays / "com-podcast.md").read_text(encoding="utf-8").replace("Com Podcast", "Sem Podcast"),
        encoding="utf-8",
    )
    env = os.environ.copy()
    env["SECOND_BRAIN_DATA_ROOT"] = str(data)
    env["SECOND_BRAIN_SITE_ROOT"] = str(site)
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts/build_site.py")],
        cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr

    import podcast_common
    import render_public_essay

    original = podcast_common.published_minutes
    podcast_common.published_minutes = lambda slug, root=None: 23
    try:
        page = (site / "essays" / "com-podcast.html").read_text(encoding="utf-8")
        with_player = render_public_essay.insert_podcast_player(page, "com-podcast", "Com Podcast")
    finally:
        podcast_common.published_minutes = original
    assert "data-sb-podcast" in with_player
    (site / "essays" / "com-podcast.html").write_text(with_player, encoding="utf-8")

    from check_site_pages import SiteServer

    with SiteServer(site) as base:
        yield base


def _open(browser, base, slug, width, scheme):
    context = browser.new_context(
        viewport={"width": width, "height": 900}, color_scheme=scheme,
        device_scale_factor=2 if width < 500 else 1,
    )
    context.route("https://gustavo-jose-zambrano.kit.com/**",
                  lambda route: route.fulfill(status=200, content_type="application/javascript", body=""))
    context.add_init_script("try{localStorage.setItem('sb-theme',%r)}catch(e){}" % scheme)
    page = context.new_page()
    page.goto(f"{base}/essays/{slug}.html", wait_until="load")
    page.wait_for_timeout(600)
    return page, context


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("width", WIDTHS)
def test_player_geometry(width, scheme, server):
    executable = _chromium()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=executable)
        try:
            page, context = _open(browser, server, "com-podcast", width, scheme)
            try:
                m = page.evaluate(MEASURE)
                shots = os.environ.get("SB_PLAYER_SHOTS")
                if shots:
                    Path(shots).mkdir(parents=True, exist_ok=True)
                    page.locator("[data-sb-podcast]").scroll_into_view_if_needed()
                    page.screenshot(path=str(Path(shots) / f"player-{width}-{scheme}.png"))
                    page.locator("[data-sb-podcast]").screenshot(
                        path=str(Path(shots) / f"player-{width}-{scheme}-box.png"))
            finally:
                context.close()
        finally:
            browser.close()

    tag = f"{width}px/{scheme}"
    box, col = m["box"], m["col"]
    assert m["afterSummary"] and m["directlyAfter"], f"{tag}: player não vem logo após o resumo"
    assert m["summaryParent"], tag
    # coluna: a mesma do corpo (tolerância de subpixel) e dentro da viewport
    assert abs(box["l"] - col["l"]) <= 1.5 and abs(box["r"] - col["r"]) <= 1.5, (
        f"{tag}: caixa {box['l']:.1f}-{box['r']:.1f} difere da coluna {col['l']:.1f}-{col['r']:.1f}")
    assert box["l"] >= 0 and box["r"] <= m["vw"], f"{tag}: fora da viewport"
    # nada transborda
    assert m["docScroll"] <= m["vw"], f"{tag}: rolagem horizontal ({m['docScroll']} > {m['vw']})"
    assert m["playerScroll"] <= m["playerClient"], f"{tag}: player transborda"
    for child in m["children"]:
        assert child["l"] >= box["l"] - 0.5 and child["r"] <= box["r"] + 0.5, f"{tag}: {child['cls']} fora da caixa"
        assert child["t"] >= box["t"] - 0.5 and child["b"] <= box["b"] + 0.5, f"{tag}: {child['cls']} fora da caixa"
    for control in m["controls"]:
        assert control["shown"], f"{tag}: {control['cls']} escondido"
        assert control["l"] >= box["l"] - 0.5 and control["r"] <= box["r"] + 0.5, f"{tag}: {control['cls']} fora da caixa"
        assert control["w"] >= 32 and control["h"] >= 32, f"{tag}: {control['cls']} alvo {control['w']:.0f}x{control['h']:.0f}"
    seek = next(c for c in m["controls"] if c["cls"] == "sb-pc-seek")
    assert seek["w"] >= 40, f"{tag}: slider espremido ({seek['w']:.0f}px)"
    # rótulo
    lab = m["label"]
    assert lab["sw"] <= lab["cw"] + 1 and lab["sh"] <= lab["ch"] + 1, f"{tag}: rótulo cortado"
    assert lab["durShown"] and "23 min" in lab["text"], f"{tag}: duração sumiu: {lab['text']!r}"
    assert lab["durBox"]["r"] <= lab["box"]["r"] + 1, f"{tag}: duração cortada"
    assert lab["fullShown"] != lab["shortShown"], f"{tag}: deve mostrar exatamente uma forma"
    if lab["shortShown"]:
        assert not lab["fullFits"], f"{tag}: forma curta com espaço para a completa"
        assert lab["text"].startswith(SHORT) and "sobre este ensaio" not in lab["text"]
    else:
        assert lab["fullFits"] and lab["text"].startswith(FULL), f"{tag}: forma completa não cabe"
    if width >= 768:
        assert lab["fullShown"], f"{tag}: em tela larga o rótulo deve ser o completo"


def test_essay_without_podcast_has_no_player(server):
    executable = _chromium()
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=executable)
        try:
            page, context = _open(browser, server, "sem-podcast", 390, "light")
            try:
                assert page.locator("[data-sb-podcast]").count() == 0
                assert page.locator("audio").count() == 0
            finally:
                context.close()
        finally:
            browser.close()
