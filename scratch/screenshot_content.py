#!/usr/bin/env python3
import asyncio
from pathlib import Path
from playwright.async_api import async_playwright

ARTIFACTS_DIR = Path(r"C:\Users\gusta\.gemini\antigravity\brain\c201df52-4b4d-4620-aa4e-b8f33f77292b")
BASE_URL = "https://gitzambrano.github.io/second-brain-site"

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1280, "height": 900})
        page = await context.new_page()

        # 1. Kutta scrolled to figure and math
        await page.goto(f"{BASE_URL}/essays/a-fisica-da-sustentacao-kutta-que-pariu.html", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        # Scroll to section with figure
        await page.evaluate("window.scrollBy(0, 1800)")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(ARTIFACTS_DIR / "screenshot_kutta_body_fig.png"))

        # Scroll to section with math equations
        await page.evaluate("window.scrollBy(0, 1800)")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(ARTIFACTS_DIR / "screenshot_kutta_body_math.png"))

        # 2. Boltzmann scrolled to callouts (.box)
        await page.goto(f"{BASE_URL}/essays/cerebros-de-boltzmann-epistemologia-e-o-limite-ontologico-da-fisica.html", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        await page.evaluate("document.querySelector('.box').scrollIntoView({block: 'center'})")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(ARTIFACTS_DIR / "screenshot_boltzmann_callout.png"))

        # In dark mode
        await page.evaluate("document.documentElement.setAttribute('data-theme', 'dark'); document.documentElement.dataset.theme = 'dark';")
        await page.wait_for_timeout(300)
        await page.screenshot(path=str(ARTIFACTS_DIR / "screenshot_boltzmann_callout_dark.png"))

        # 3. Dutch roll scrolled to complex math equations
        await page.goto(f"{BASE_URL}/essays/dinamica-analitica-e-acoplamento-fisico-do-modo-dutch-roll.html", wait_until="networkidle")
        await page.wait_for_timeout(1000)
        await page.evaluate("document.querySelector('mjx-container, svg.mjx-svg, .MathJax').scrollIntoView({block: 'center'})")
        await page.wait_for_timeout(500)
        await page.screenshot(path=str(ARTIFACTS_DIR / "screenshot_dutch_roll_math.png"))

        await browser.close()
    print("Screenshots taken successfully!")

if __name__ == "__main__":
    asyncio.run(main())
