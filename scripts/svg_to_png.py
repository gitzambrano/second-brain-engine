#!/usr/bin/env python3
"""svg_to_png.py - Converte diagramas e ilustrações SVG em imagens PNG de alta resolução.

Renderiza arquivos SVG em PNG de alta definição (Retina 2x por padrão) via Chromium/Playwright:
- Suporta renderização de arquivo único ou lote completo em wiki/assets/.
- Garante fidelidade geométrica total (suporte a polígonos, gradientes, CSS e marcadores).
- Produz os binários .png irmãos usados para exportações em PDF (LaTeX), HTML standalone e CDN.

Escopo:
    Compilador e renderizador de imagens SVG em DATA_ROOT/wiki/assets/.
    Padrão sem argumentos converte todos os SVGs da wiki desatualizados ou sem PNG correspondente.

Entradas (Inputs):
    Arquivos *.svg em wiki/assets/.
    Argumentos CLI opcionais:
        arquivo.svg    Arquivo específico a converter (caminho ou nome)
        --all          Força re-renderização de todos os SVGs da wiki
        --scale INT    Fator de escala de dispositivo (padrão: 2 para Retina)

Saídas (Outputs):
    Arquivos PNG gerados no mesmo diretório do arquivo .svg de origem.
    Stdout: Lista de conversões concluídas com tempo e dimensões.
    Exit code: 0 em sucesso, 1 em erro de renderização.

Uso:
    python scripts/svg_to_png.py                    # converte SVGs pendentes/desatualizados
    python scripts/svg_to_png.py arquivo.svg        # converte um arquivo específico
    python scripts/svg_to_png.py --all              # força conversão de todos os SVGs
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from pathlib import Path

from repo_paths import ASSETS_DIR

HTML_WRAPPER = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: #ffffff;
    display: inline-block;
    padding: 24px;
  }}
  svg {{
    display: block;
    background: #ffffff;
  }}
</style>
</head>
<body>
{svg_content}
</body>
</html>
"""


def prepare_svg(svg_raw: str, target_w: int = 1200) -> str:
    """Limpa e ajusta dimensões do nó SVG para renderização previsível."""
    clean = re.sub(r'<\?xml[^>]*\?>', '', svg_raw).strip()
    clean = re.sub(r'<(/?)svg:', r'<\1', clean)
    clean = re.sub(r'\ssvg:([a-zA-Z0-9_-]+)=', r' \1=', clean)

    if 'xmlns="http://www.w3.org/2000/svg"' not in clean:
        clean = re.sub(r'<svg\b', '<svg xmlns="http://www.w3.org/2000/svg"', clean, count=1)

    vb_match = re.search(r'viewBox=["\']([^"\']+)["\']', clean)
    w_match = re.search(r'<svg\b[^>]*\bwidth=["\']([^"\']+)["\']', clean)
    h_match = re.search(r'<svg\b[^>]*\bheight=["\']([^"\']+)["\']', clean)

    vb_w, vb_h = None, None
    if vb_match:
        try:
            parts = [float(x.strip()) for x in vb_match.group(1).replace(",", " ").split() if x.strip()]
            if len(parts) == 4:
                vb_w, vb_h = parts[2], parts[3]
        except Exception:
            pass

    if not vb_w or not vb_h:
        def parse_d(d):
            if not d: return None
            d = d.replace("px", "").replace("pt", "").replace("%", "").strip()
            try: return float(d)
            except Exception: return None
        vb_w = parse_d(w_match.group(1)) if w_match else None
        vb_h = parse_d(h_match.group(1)) if h_match else None

    if not vb_w or not vb_h or vb_w <= 0 or vb_h <= 0:
        vb_w, vb_h = 1200, 700

    aspect = vb_h / vb_w
    render_w = target_w
    render_h = max(int(target_w * aspect), 100)

    if re.search(r'<svg\b[^>]*\bwidth=', clean):
        clean = re.sub(r'(<svg\b[^>]*\bwidth=["\'])[^"\']*(["\'])', rf'\g<1>{render_w}\g<2>', clean)
    else:
        clean = re.sub(r'<svg\b', f'<svg width="{render_w}"', clean)

    if re.search(r'<svg\b[^>]*\bheight=', clean):
        clean = re.sub(r'(<svg\b[^>]*\bheight=["\'])[^"\']*(["\'])', rf'\g<1>{render_h}\g<2>', clean)
    else:
        clean = re.sub(r'<svg\b', f'<svg height="{render_h}"', clean)

    return clean


def render_svg_page(page, svg_path: Path, out_png: Path) -> None:
    """Renderiza um arquivo SVG para PNG usando uma página Playwright aberta."""
    svg_content = prepare_svg(svg_path.read_text(encoding="utf-8"))
    html = HTML_WRAPPER.format(svg_content=svg_content)
    page.set_content(html, wait_until="networkidle")
    page.locator("body").screenshot(path=str(out_png))


def render_svg_file(svg_path: Path, out_png: Path, scale: int = 2) -> bool:
    """Renderiza um arquivo SVG individual para PNG via Playwright/Chromium."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(device_scale_factor=scale)
            render_svg_page(page, svg_path, out_png)
            return True
        finally:
            browser.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Converte SVGs para PNG Retina 2x.")
    parser.add_argument("target", nargs="?", default="", help="Caminho do arquivo SVG ou slug")
    parser.add_argument("--all", action="store_true", help="Força re-renderização de todos os SVGs")
    parser.add_argument("--scale", type=int, default=2, help="Fator de escala Retina (padrão: 2)")
    args = parser.parse_args(argv)

    if not ASSETS_DIR.exists():
        print(f"[ERRO] Diretório de assets não encontrado: {ASSETS_DIR}")
        return 1

    targets: list[Path] = []
    if args.target:
        p = Path(args.target)
        if not p.is_absolute():
            candidate = ASSETS_DIR / args.target
            if candidate.exists():
                p = candidate
            elif not p.exists() and (ASSETS_DIR / f"{args.target}.svg").exists():
                p = ASSETS_DIR / f"{args.target}.svg"
        if not p.exists():
            print(f"[ERRO] Arquivo SVG não encontrado: {args.target}")
            return 1
        targets.append(p)
    else:
        all_svgs = sorted(ASSETS_DIR.glob("*.svg"))
        for s in all_svgs:
            png = s.with_suffix(".png")
            if args.all or not png.exists() or s.stat().st_mtime > png.stat().st_mtime or png.stat().st_size == 0:
                targets.append(s)

    if not targets:
        print("[OK] Todos os PNGs de SVGs estão atualizados.")
        return 0

    print(f"[*] Processando {len(targets)} arquivo(s) SVG com escala {args.scale}x...", flush=True)
    from playwright.sync_api import sync_playwright

    success = 0
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            page = browser.new_page(device_scale_factor=args.scale)
            for s in targets:
                png = s.with_suffix(".png")
                try:
                    render_svg_page(page, s, png)
                    print(f"  [OK] {s.name} -> {png.name} ({png.stat().st_size} bytes)", flush=True)
                    success += 1
                except Exception as e:
                    print(f"  [ERRO] Falha ao renderizar {s.name}: {e}", flush=True)
        finally:
            browser.close()

    print(f"[+] Concluído: {success}/{len(targets)} arquivos renderizados com sucesso.", flush=True)
    return 0 if success == len(targets) else 1


if __name__ == "__main__":
    sys.exit(main())
