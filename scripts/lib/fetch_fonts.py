#!/usr/bin/env python3
"""fetch_fonts.py - Baixa fontes do Google Fonts (só subset latino) e as
auto-hospeda em cache local para o export HTML - mantém apenas o subset
`latin`, cortando ~85% do peso das fontes embutidas.

Lê:
    CSS e woff2 do Google Fonts (rede)

Gera:
    output/html/_fonts/fonts.css + woff2 referenciados
    (cache: nada é rebaixado se já existirem; falha de rede -> None e o
    export segue com fontes do sistema)

Uso:
    from fetch_fonts import ensure_local_fonts
    css_path = ensure_local_fonts(output_dir)   # caminho do fonts.css ou None

(Chamado pelo export HTML e pelo leitor embutido dos grafos; sem CLI.)
"""

import re
import urllib.request
from pathlib import Path

CSS_URL = (
    "https://fonts.googleapis.com/css2"
    "?family=Playfair+Display:ital,wght@0,700;0,900;1,400;1,700"
    "&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400"
    "&family=JetBrains+Mono&display=swap"
)
# UA de navegador moderno -> Google devolve woff2 com unicode-range.
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

KEEP_SUBSETS = {"latin"}
# pt-BR inteiro (acentos U+00xx) e pontuacao tipografica (U+2000-206F: aspas
# curvas, travessoes, reticencias) mora no subset "latin" do Google; latin-ext
# so adicionaria chars que o corpus nao usa. Menos arquivos, menos KB.

BLOCK_RE = re.compile(r"/\*\s*([\w-]+)\s*\*/\s*(@font-face\s*\{[^}]*\})", re.S)


def _download(url, dest):
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = r.read()
    dest.write_bytes(data)


# O site tem outra necessidade: `--sans` começa em Inter, mas nada nunca a
# servia, então a página inteira caía em Segoe UI/Roboto. O sintoma visível era
# que pesos intermediários não existiam — 500, 550 e 600 renderizavam o mesmo
# Semibold, e não havia como pedir um negrito mais leve. A Inter variável
# resolve as duas coisas: a fonte que o desenho pressupõe, com o eixo de peso
# contínuo que ele usa.
SITE_CSS_URL = (
    "https://fonts.googleapis.com/css2"
    "?family=Inter:wght@100..900"
    "&family=Playfair+Display:ital,wght@0,700;0,900;1,400;1,700"
    "&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400"
    "&family=JetBrains+Mono:wght@400;500;600&display=swap"
)
SITE_FONT_FAMILIES = ("Inter", "Playfair Display", "Source Serif 4", "JetBrains Mono")


def ensure_local_fonts(output_dir, css_url=None, dirname="_fonts", required_families=()):
    """Retorna Path do fonts.css local (ou None se offline/falhou)."""
    output_dir = Path(output_dir)
    css_url = css_url or CSS_URL
    font_dir = output_dir / dirname
    css_path = font_dir / "fonts.css"

    # Cache valido? css existe e todo woff2 referenciado existe (refs sao
    # relativas ao PROPRIO diretorio _fonts, nao ao output_dir).
    if css_path.exists():
        css_text = css_path.read_text(encoding="utf-8", errors="replace")
        refs = re.findall(r"url\(([^)]+)\)", css_text)
        if (all((font_dir / u).exists() for u in refs)
                and all(f'font-family: "{family}"' in css_text for family in required_families)):
            return css_path

    try:
        req = urllib.request.Request(css_url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=30) as r:
            css = r.read().decode("utf-8")
    except Exception as e:
        print(f"  WARNING: nao foi possivel baixar CSS das fontes ({e}); "
              f"serao usadas serifas do sistema.")
        return None

    blocks_out, n_fonts = [], 0
    # Garante o diretorio ANTES de qualquer download.
    font_dir.mkdir(parents=True, exist_ok=True)
    for subset, block in BLOCK_RE.findall(css):
        if subset not in KEEP_SUBSETS:
            continue
        m_url = re.search(r"url\((https://[^)]+)\)", block)
        if not m_url:
            continue
        remote = m_url.group(1)
        # nome determinista: ultimo segmento do caminho remoto
        last_seg = re.sub(r"[?#].*$", "", remote.rsplit("/", 1)[-1])
        fname = re.sub(r"[^A-Za-z0-9._-]", "", last_seg) or f"f{n_fonts}.woff2"
        if not fname.endswith(".woff2"):
            fname += ".woff2"
        local_rel = fname
        local_abs = font_dir / fname
        if not local_abs.exists():
            try:
                _download(remote, local_abs)
            except Exception as e:
                print(f"  WARNING: falha ao baixar fonte {fname} ({e}); "
                      f"serao usadas serifas do sistema.")
                return None
        blocks_out.append(block.replace(m_url.group(0), f"url({local_rel})"))
        n_fonts += 1

    if n_fonts == 0:
        print("  WARNING: nenhum bloco latin encontrado no CSS das fontes.")
        return None

    font_dir.mkdir(parents=True, exist_ok=True)
    css_path.write_text("\n".join(blocks_out), encoding="utf-8")
    print(f"  Fontes locais prontas: {n_fonts} woff2 (latin/latin-ext) em {font_dir}")
    return css_path


if __name__ == "__main__":
    from repo_paths import HTML_DIR

    out = ensure_local_fonts(HTML_DIR)
    print(out or "sem fontes locais")
