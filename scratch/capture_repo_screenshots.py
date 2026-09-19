import shutil
from pathlib import Path
from playwright.sync_api import sync_playwright

artifact_dir = Path(r"C:\Users\gusta\.gemini\antigravity\brain\b0f26ea5-e871-4fb6-a877-37f5bb7170b2")
ss_dir = Path("substack/screenshots")
ss_dir.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 900}, device_scale_factor=2)

    # 1. quando-a-distancia-colapsou: callout epidemiológico
    f1 = Path("data/output/html/quando-a-distancia-colapsou-por-que-a-aviacao-importa.html").resolve()
    page.goto(f1.as_uri())
    page.wait_for_timeout(1000)
    callout1 = page.locator("text=O Colapso das Barreiras Epidemiológicas")
    if callout1.count() > 0:
        callout1.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        p1 = ss_dir / "repo_quando_distancia_callout.png"
        box = callout1.bounding_box()
        if box:
            page.screenshot(path=str(p1), clip={"x": max(0, box["x"] - 40), "y": max(0, box["y"] - 30), "width": min(1100, box["width"] + 150), "height": 380})
        else:
            page.screenshot(path=str(p1))
        print("Saved:", p1)
        shutil.copy2(p1, artifact_dir / p1.name)

    # 2. a-historia-da-aviacao: mermaid diagram
    f2 = Path("data/output/html/a-historia-da-aviacao-como-um-jogo-estrategico.html").resolve()
    page.goto(f2.as_uri())
    page.wait_for_timeout(1500)
    loc2 = page.locator("text=Radar e Detecção Antecipada")
    if loc2.count() > 0:
        loc2.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        p2 = ss_dir / "repo_historia_aviacao_mermaid.png"
        box = loc2.bounding_box()
        if box:
            page.screenshot(path=str(p2), clip={"x": max(0, box["x"] - 80), "y": max(0, box["y"] - 50), "width": 800, "height": 650})
        else:
            page.screenshot(path=str(p2))
        print("Saved:", p2)
        shutil.copy2(p2, artifact_dir / p2.name)

    # 3. validacao-estocastica: TOST formula
    f3 = Path("data/output/html/validacao-estocastica-de-dinamica-de-voo-de-hume-ao-p-value.html").resolve()
    page.goto(f3.as_uri())
    page.wait_for_timeout(1500)
    loc3 = page.locator("text=Estrutura de Hipóteses do TOST").first
    if loc3.count() > 0:
        loc3.scroll_into_view_if_needed()
        page.wait_for_timeout(500)
        p3 = ss_dir / "repo_validacao_tost_latex.png"
        box = loc3.bounding_box()
        if box:
            page.screenshot(path=str(p3), clip={"x": max(0, box["x"] - 40), "y": max(0, box["y"] - 20), "width": 850, "height": 520})
        else:
            page.screenshot(path=str(p3))
        print("Saved:", p3)
        shutil.copy2(p3, artifact_dir / p3.name)

    browser.close()
print("Screenshots complete!")
