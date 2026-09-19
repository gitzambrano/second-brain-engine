import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import os
import re
import json
import time
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv("substack/.env")
cookie = os.getenv("SUBSTACK_COOKIE")
sid_match = re.search(r"substack\.sid=([^;]+)", cookie) if cookie else None
sid_val = sid_match.group(1) if sid_match else cookie

SCREENSHOT_DIR = Path("substack/screenshots")
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
ARTIFACT_DIR = Path(r"C:\Users\gusta\.gemini\antigravity\brain\b0f26ea5-e871-4fb6-a877-37f5bb7170b2")

DRAFTS = [
    (216380774, "lego-e-a-fisica-do-encaixe"),
    (216381367, "quem-e-voce-identidade-pessoal"),
    (216381714, "o-principio-antropico"),
    (216382120, "a-fenomenologia-do-tabuleiro"),
    (216382533, "engenharia-em-menos-de-um-metro-cubico"),
    (216383096, "o-que-e-vida"),
    (216383684, "ficcao-cientifica-como-incubadora-teorica"),
    (216384954, "campeoes-por-acaso"),
    (216386174, "rpg-de-mesa-e-a-teoria-da-informacao"),
]

print("Iniciando auditoria Playwright nos 9 drafts novos...")

results = {}

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    if sid_val:
        context.add_cookies([{
            "name": "substack.sid",
            "value": sid_val,
            "domain": ".substack.com",
            "path": "/",
        }])
    page = context.new_page()

    for pid, slug in DRAFTS:
        url = f"https://gzambrano.substack.com/publish/post/{pid}"
        print(f"\n--- Inspecionando Draft #{pid} ({slug}) ---")
        errors = []
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(3000)
            
            # Checar erros visíveis
            error_el = page.locator("text=Não foi possível carregar o post")
            has_load_error = error_el.count() > 0
            
            # Extrair contagem de elementos do editor
            code_boxes = page.locator("pre").count()
            blockquotes = page.locator("blockquote").count()
            images = page.locator("img").count()
            
            # Buscar texto de bylines visíveis
            body_text = page.locator(".post-content, .editor, .tiptap").inner_text() if page.locator(".post-content, .editor, .tiptap").count() > 0 else page.content()
            byline_matches = re.findall(r"Gustavo Zambrano", body_text)
            
            print(f"  Status: Carregou com sucesso (Load Error: {has_load_error})")
            print(f"  Elementos: {code_boxes} blocos de código pre, {blockquotes} citações/callouts, {images} imagens")
            print(f"  Ocorrências de 'Gustavo Zambrano' no corpo: {len(byline_matches)}")
            
            # Captura de tela do topo (onde ocorria a duplicata da byline)
            shot_name = f"draft_{slug}_head.png"
            dest = SCREENSHOT_DIR / shot_name
            page.screenshot(path=str(dest))
            (ARTIFACT_DIR / shot_name).write_bytes(dest.read_bytes())
            print(f"  Screenshot salva em: {dest.name}")
            
            results[pid] = {
                "slug": slug,
                "has_load_error": has_load_error,
                "code_boxes": code_boxes,
                "blockquotes": blockquotes,
                "byline_occurrences": len(byline_matches),
                "errors": errors[:3]
            }
        except Exception as e:
            print(f"  Erro ao abrir {url}: {e}")
            results[pid] = {"slug": slug, "error": str(e)}

    browser.close()

Path("scratch/browser_audit_summary.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
print("\nAuditoria Playwright concluída! Relatório salvo em scratch/browser_audit_summary.json")
