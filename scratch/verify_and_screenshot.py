#!/usr/bin/env python3
"""
Auditoria visual com captura de screenshots e validação detalhada de Callboxes (.box),
MathJax SVGs, Figuras e Tipografia.
Salva screenshots no diretório de artefatos.
"""
import asyncio
import json
import os
from pathlib import Path
from playwright.async_api import async_playwright

ARTIFACTS_DIR = Path(r"C:\Users\gusta\.gemini\antigravity\brain\c201df52-4b4d-4620-aa4e-b8f33f77292b")
BASE_URL = "https://gitzambrano.github.io/second-brain-site"

PAGES = [
    ("home", f"{BASE_URL}/index.html"),
    ("kutta", f"{BASE_URL}/essays/a-fisica-da-sustentacao-kutta-que-pariu.html"),
    ("boltzmann", f"{BASE_URL}/essays/cerebros-de-boltzmann-epistemologia-e-o-limite-ontologico-da-fisica.html"),
    ("dutch_roll", f"{BASE_URL}/essays/dinamica-analitica-e-acoplamento-fisico-do-modo-dutch-roll.html"),
    ("zumbis", f"{BASE_URL}/essays/chatgpts-e-zumbis-filosoficos-uma-reflexao-sobre-consciencia-e-inteligencia-artificial.html"),
    ("graph", f"{BASE_URL}/graph.html"),
    ("sphere", f"{BASE_URL}/sphere.html"),
]

async def run_audit():
    details = {}
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 800})
        page = await context.new_page()

        for name, url in PAGES:
            print(f"Loading {name} ({url})...")
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Wait for MathJax if present
            await page.evaluate("""async () => {
                if (window.MathJax && window.MathJax.startup && window.MathJax.startup.promise) {
                    await window.MathJax.startup.promise;
                }
            }""")
            await page.wait_for_timeout(800)

            # Capture initial screenshot (light)
            shot_path_light = ARTIFACTS_DIR / f"screenshot_{name}_light.png"
            await page.screenshot(path=str(shot_path_light))

            # Audit elements
            info = await page.evaluate("""() => {
                // Callouts
                const boxes = Array.from(document.querySelectorAll('.box')).map(b => {
                    const cs = window.getComputedStyle(b);
                    return {
                        classes: b.className,
                        title: b.querySelector('.box-title')?.textContent?.trim() || '(sem título)',
                        borderLeft: cs.borderLeft,
                        bg: cs.backgroundColor,
                        color: cs.color
                    };
                });

                // MathJax
                const mathSvgs = Array.from(document.querySelectorAll('mjx-container svg, .MathJax svg')).map(svg => {
                    const r = svg.getBoundingClientRect();
                    return { w: r.width, h: r.height };
                });

                // Images
                const images = Array.from(document.querySelectorAll('img')).map(img => ({
                    src: img.src.split('/').pop(),
                    naturalWidth: img.naturalWidth,
                    naturalHeight: img.naturalHeight,
                    complete: img.complete
                }));

                // Fonts computed
                const bodyFont = window.getComputedStyle(document.body).fontFamily;
                const h1 = document.querySelector('h1');
                const h1Font = h1 ? window.getComputedStyle(h1).fontFamily : null;
                const aside = document.querySelector('aside, .box');
                const asideFont = aside ? window.getComputedStyle(aside).fontFamily : null;

                // Overflow
                const overflow = document.documentElement.scrollWidth > window.innerWidth + 2;

                return {
                    title: document.title,
                    boxes,
                    mathCount: mathSvgs.length,
                    images,
                    fonts: { body: bodyFont, h1: h1Font, aside: asideFont },
                    overflow
                };
            }""")

            # Toggle theme to dark and screenshot
            await page.evaluate("document.documentElement.setAttribute('data-theme', 'dark'); document.documentElement.dataset.theme = 'dark';")
            await page.wait_for_timeout(300)
            shot_path_dark = ARTIFACTS_DIR / f"screenshot_{name}_dark.png"
            await page.screenshot(path=str(shot_path_dark))

            details[name] = info

        await browser.close()

    out_file = ARTIFACTS_DIR / "visual_audit_details.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(details, f, indent=2, ensure_ascii=False)
    print("Audit completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_audit())
