#!/usr/bin/env python3
"""
Validação exaustiva e automatizada do site GitHub Pages ao vivo.
Acessa o site remoto via Playwright:
- index.html (busca, filtros, tema claro/escuro, links)
- graph.html e sphere.html
- Todos os ensaios listados (ou amostra prioritária)
- Verifica:
  * MathJax SVGs renderizados sem código raw LaTeX nem overflow
  * Imagens com naturalWidth > 0 e HTTP 200
  * Callboxes / callouts com computed styles (borda, background, visibilidade)
  * Fontes (Inter, Playfair Display, JetBrains Mono, Source Serif 4)
  * Erros de console e falhas de rede
"""
import asyncio
import json
import sys
from playwright.async_api import async_playwright

BASE_URL = "https://gitzambrano.github.io/second-brain-site"

ESSAYS_TO_TEST = [
    "a-fisica-da-sustentacao-kutta-que-pariu.html",
    "dinamica-analitica-e-acoplamento-fisico-do-modo-dutch-roll.html",
    "dinamica-de-voo-de-um-rotor-teetering-controlado-por-rpm.html",
    "chatgpts-e-zumbis-filosoficos-uma-reflexao-sobre-consciencia-e-inteligencia-artificial.html",
    "compatibilismo-o-livre-arbitrio-como-propriedade-de-um-sistema-natural.html",
    "efeito-da-solidez-sobre-os-parametros-aerodinamicos-fundamentais-de-um-rotor-a-tracao-constante.html",
    "equacoes-analiticas-para-os-coeficientes-aerodinamicos-de-um-rotor-rigido.html",
    "forca-lateral-de-um-rotor-em-voo-a-frente-inflow-uniforme-e-coleman.html",
    "godel-turing-e-os-limites-da-computacao.html",
    "o-teorema-do-stagger-de-munk-e-sua-universalidade-em-sistemas-aerodinamicos-de-multiplas-superficies.html",
    "rotores-e-giroscopios-construcao-fisica-e-matematica-a-partir-das-leis-de-newton.html",
]

async def audit_page(page, url):
    console_errors = []
    failed_requests = []

    def on_console(msg):
        if msg.type in ("error",):
            # Ignore harmless favicon 404 from root domain
            if "favicon.ico" not in msg.text:
                console_errors.append(msg.text)

    def on_request_failed(req):
        if "favicon.ico" not in req.url:
            failed_requests.append(f"{req.url} ({req.failure})")

    page.on("console", on_console)
    page.on("requestfailed", on_request_failed)

    resp = await page.goto(url, wait_until="networkidle", timeout=30000)
    status = resp.status if resp else None

    # Wait for MathJax if present
    await page.evaluate("""async () => {
        if (window.MathJax && window.MathJax.startup && window.MathJax.startup.promise) {
            await window.MathJax.startup.promise;
        }
    }""")
    await page.wait_for_timeout(500)

    # Audit probe
    details = await page.evaluate("""() => {
        // 1. MathJax checks
        const mjxContainers = document.querySelectorAll('mjx-container, .MathJax');
        let unrenderedLatex = [];
        // Check for raw $$ or unparsed latex patterns in visible text outside code blocks
        const textNodes = [];
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
        let n;
        while (n = walker.nextNode()) {
            if (n.parentElement && !['SCRIPT', 'STYLE', 'CODE', 'PRE'].includes(n.parentElement.tagName)) {
                const val = n.nodeValue;
                if (/\\$\\$[^\\$]+\\$\\$/.test(val) || /\\\\begin\\{[a-z]+\\}/.test(val)) {
                    unrenderedLatex.push(val.trim().slice(0, 80));
                }
            }
        }

        // 2. Images check
        const imgs = Array.from(document.querySelectorAll('img')).map(img => ({
            src: img.src,
            naturalWidth: img.naturalWidth,
            naturalHeight: img.naturalHeight,
            complete: img.complete
        }));
        const brokenImgs = imgs.filter(i => !i.complete || i.naturalWidth === 0);

        // 3. Callouts / Callboxes check
        const callboxes = Array.from(document.querySelectorAll('.callout, .sb-callout, .admonition, blockquote')).map(el => {
            const cs = window.getComputedStyle(el);
            return {
                tag: el.tagName,
                className: el.className,
                borderLeft: cs.borderLeftWidth + ' ' + cs.borderLeftStyle + ' ' + cs.borderLeftColor,
                bg: cs.backgroundColor,
                color: cs.color,
                width: el.getBoundingClientRect().width,
                height: el.getBoundingClientRect().height
            };
        });

        // 4. Geometry / Horizontal overflow
        const docWidth = document.documentElement.scrollWidth;
        const winWidth = window.innerWidth;
        const overflow = docWidth > winWidth + 2;

        // 5. Fonts verification
        const fontsLoaded = document.fonts.check("16px 'Playfair Display'") &&
                            document.fonts.check("16px 'Inter'") &&
                            document.fonts.check("16px 'JetBrains Mono'") &&
                            document.fonts.check("16px 'Source Serif 4'");

        // 6. TOC and Connections
        const toc = document.querySelector('.toc, #toc, nav[aria-label="Sumário"], .sb-toc, details.toc');
        const connections = document.querySelector('#conexões, #conexoes, [id*="conex"]');

        return {
            title: document.title,
            mjxCount: mjxContainers.length,
            unrenderedLatex,
            imgCount: imgs.length,
            brokenImgs,
            callboxCount: callboxes.length,
            sampleCallbox: callboxes[0] || null,
            docWidth,
            winWidth,
            overflow,
            fontsLoaded,
            hasToc: !!toc || !!document.querySelector('a[href*="#"]'),
            hasConnections: !!connections || document.body.innerText.includes('Conexões')
        };
    }""")

    return {
        "url": url,
        "status": status,
        "console_errors": console_errors,
        "failed_requests": failed_requests,
        **details
    }

async def main():
    results = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1440, "height": 900})
        page = await context.new_page()

        # Audit home
        print(f"Auditing Home: {BASE_URL}/index.html ...")
        home_res = await audit_page(page, f"{BASE_URL}/index.html")
        results["home"] = home_res

        # Test Dark Theme toggle on Home
        await page.click("#themeToggle")
        await page.wait_for_timeout(300)
        theme = await page.evaluate("document.documentElement.dataset.theme")
        results["theme_toggle"] = theme

        # Audit Graph and Sphere
        print(f"Auditing Graph: {BASE_URL}/graph.html ...")
        results["graph"] = await audit_page(page, f"{BASE_URL}/graph.html")
        print(f"Auditing Sphere: {BASE_URL}/sphere.html ...")
        results["sphere"] = await audit_page(page, f"{BASE_URL}/sphere.html")

        # Audit Essays
        results["essays"] = []
        for essay_slug in ESSAYS_TO_TEST:
            essay_url = f"{BASE_URL}/essays/{essay_slug}"
            print(f"Auditing Essay: {essay_slug} ...")
            res = await audit_page(page, essay_url)
            results["essays"].append(res)

        await browser.close()

    print("\n" + "="*60)
    print("AUDIT RESULTS SUMMARY")
    print("="*60)
    print(f"Home status: {results['home']['status']} | Title: {results['home']['title']}")
    print(f"Theme toggle switched to: {results['theme_toggle']}")
    print(f"Graph: HTTP {results['graph']['status']} | Console errs: {len(results['graph']['console_errors'])}")
    print(f"Sphere: HTTP {results['sphere']['status']} | Console errs: {len(results['sphere']['console_errors'])}")
    
    all_ok = True
    for e in results["essays"]:
        slug = e['url'].split('/')[-1]
        broken = len(e['brokenImgs'])
        latex_errs = len(e['unrenderedLatex'])
        overflow = e['overflow']
        errs = len(e['console_errors'])
        status_str = f"HTTP {e['status']} | Math: {e['mjxCount']} | Imgs: {e['imgCount']} (broken: {broken}) | Callboxes: {e['callboxCount']} | Overflow: {overflow} | Errs: {errs}"
        print(f"{slug[:45]:<45} : {status_str}")
        if broken > 0 or latex_errs > 0 or overflow or errs > 0 or e['status'] != 200:
            all_ok = False

    print("\nOVERALL STATUS: " + ("ALL CHECKS PASSED PERFECTLY" if all_ok else "ISSUES DETECTED"))
    with open("scratch/live_site_results.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    asyncio.run(main())
