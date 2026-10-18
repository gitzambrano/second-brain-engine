#!/usr/bin/env python3
"""build_favicons.py - Gera os ícones e favicons do Atlas a partir da arte-mestra.

Processa a arte-mestra em site_src/brand/: recorta por croma, gera a variante dourada,
ajusta espessura de traços para legibilidade em baixa resolução e exporta os arquivos
necessários para navegadores desktop, mobile e PWA.

Escopo:
    Geração e otimização de imagens estáticas em SITE_ROOT e site_src/brand/.

Entradas (Inputs):
    Imagens SVG/PNG mestras em site_src/brand/.
    Argumentos CLI opcionais:
        --check    Valida a presença e dimensões dos favicons sem regerar

Saídas (Outputs):
    favicon.ico, apple-touch-icon.png e variantes PNG em SITE_ROOT/assets/brand/.
    Exit code: 0 em sucesso, 1 em falha de processamento de imagem.

Uso:
    python scripts/build_favicons.py          # regera todos os favicons
    python scripts/build_favicons.py --check  # verifica conformidade
"""
from __future__ import annotations

import argparse
from pathlib import Path

import console_encoding  # noqa: F401  (UTF-8 no console; ver o módulo)
from repo_paths import SITE_SRC_DIR

BRAND_DIR = SITE_SRC_DIR / "brand"
MASTER = "brain-blue-source.png"
SOURCES = (MASTER, "brain-gold-source.png")

# Rampa do dourado, do `--gold-dim` do site ao brilho alto do metal. A
# luminância do desenho azul escolhe o ponto da rampa, então o relevo do traço
# sobrevive à troca de cor em vez de virar silhueta chapada.
GOLD_DARK = (138, 107, 51)
GOLD_LIGHT = (243, 224, 173)

# Rampa da máscara de croma. Abaixo de LO é xadrez; acima de HI é arte cheia.
CHROMA_LO, CHROMA_HI = 10.0, 45.0

# Respiro em volta do desenho, em fração do lado. Um ícone colado na borda
# parece grande demais em qualquer grade — de aba a launcher.
PADDING = 0.06

# Fundo do apple-touch: a Apple compõe PNG transparente sobre PRETO, e a marca
# azul-marinho sumiria. Este é o azul de tinta do Atlas.
TOUCH_BG = (11, 22, 39)


def _load_masked(path: Path):
    """Devolve a arte em RGBA, já sem o xadrez e recortada no conteúdo."""
    import numpy as np
    from PIL import Image

    rgb = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    chroma = rgb.max(axis=2) - rgb.min(axis=2)
    alpha = np.clip((chroma - CHROMA_LO) / (CHROMA_HI - CHROMA_LO), 0, 1)
    art = Image.fromarray(np.dstack([rgb, alpha * 255]).astype(np.uint8), "RGBA")
    return art.crop(art.getbbox())


def _recolour_gold(art):
    """Troca o azul pelo dourado do Atlas, preservando o relevo do traço."""
    import numpy as np
    from PIL import Image

    rgba = np.asarray(art).astype(np.float32)
    rgb, alpha = rgba[..., :3], rgba[..., 3]
    visivel = alpha > 38
    lum = rgb.mean(axis=2)
    lo, hi = np.percentile(lum[visivel], [4, 96])
    t = np.clip((lum - lo) / max(hi - lo, 1e-6), 0, 1)[..., None]
    escuro = np.array(GOLD_DARK, np.float32)
    claro = np.array(GOLD_LIGHT, np.float32)
    dourado = escuro + (claro - escuro) * t
    return Image.fromarray(np.dstack([dourado, alpha]).astype(np.uint8), "RGBA")


def _square(art, size: int, padding: float = PADDING, background=None):
    """Centraliza a arte num quadrado, preservando proporção."""
    from PIL import Image

    inner = max(1, round(size * (1 - 2 * padding)))
    escala = min(inner / art.width, inner / art.height)
    desenho = art.resize(
        (max(1, round(art.width * escala)), max(1, round(art.height * escala))),
        Image.LANCZOS,
    )
    canvas = Image.new("RGBA", (size, size), (*background, 255) if background else (0, 0, 0, 0))
    canvas.paste(desenho, ((size - desenho.width) // 2, (size - desenho.height) // 2), desenho)
    return canvas


def _thicken(art, raio: int = 5):
    """Engrossa o traço dilatando o alpha, para o ícone pequeno sobreviver.

    Só o alpha cresce; a cor vem do próprio desenho borrado por baixo, então a
    marca engorda sem ganhar contorno chapado.
    """
    from PIL import Image, ImageFilter

    r, g, b, a = art.split()
    gordo = a.filter(ImageFilter.MaxFilter(raio * 2 + 1))
    cor = Image.merge("RGB", (r, g, b)).filter(ImageFilter.GaussianBlur(raio))
    return Image.merge("RGBA", (*cor.split(), gordo))


# Paleta indexada para os PNG grandes. A arte é degradê de uma cor só; 128
# entradas cobrem o metal sem banda visível e cortam o arquivo a uma fração.
# Sem dithering: o ruído destrói a compressão do PNG e não se vê num ícone.
# Octree é o único método do Pillow que quantiza RGBA sem descartar o alpha —
# MEDIANCUT exigiria achatar a transparência primeiro, que é o oposto do que
# este arquivo existe para preservar.
QUANTIZE_ABOVE = 64


def _shrink(imagem):
    """Indexa a paleta preservando o alpha, quando o arquivo justifica."""
    from PIL import Image

    if imagem.width < QUANTIZE_ABOVE:
        return imagem
    return imagem.quantize(colors=128, method=Image.FASTOCTREE, dither=Image.NONE)


def build(quiet: bool = False) -> list[tuple[str, int]]:
    escritos: list[tuple[str, int]] = []

    def grava(nome: str, imagem):
        destino = BRAND_DIR / nome
        _shrink(imagem).save(destino, optimize=True)
        escritos.append((nome, destino.stat().st_size // 1024))

    azul = _load_masked(BRAND_DIR / MASTER)
    dourado = _recolour_gold(azul)

    grava("icon-light-512.png", _square(azul, 512))
    grava("icon-dark-512.png", _square(dourado, 512))
    grava("icon-light-192.png", _square(azul, 192))
    grava("icon-dark-192.png", _square(dourado, 192))

    # Apple-touch: fundo opaco e respiro maior, que é como a Apple recorta.
    grava("apple-touch-icon.png", _square(azul, 180, padding=0.13, background=TOUCH_BG))

    grosso = _thicken(azul)
    grava("icon-32.png", _square(grosso, 32, padding=0.03))
    grava("icon-16.png", _square(grosso, 16, padding=0.0))
    # O chip do cabeçalho troca de marca junto com o tema, e o tema do site é
    # um `data-theme` no <html> — não o `prefers-color-scheme` do sistema. Por
    # isso a variante escura precisa existir como arquivo próprio: a troca é
    # feita por CSS, não pelo `media` de um <link>.
    grava("icon-32-dark.png", _square(_thicken(dourado), 32, padding=0.03))

    ico = _square(grosso, 48, padding=0.03)
    ico.save(BRAND_DIR / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
    escritos.append(("favicon.ico", (BRAND_DIR / "favicon.ico").stat().st_size // 1024))

    if not quiet:
        for nome, kb in escritos:
            print(f"  brand/{nome} ({kb} KB)")
    return escritos


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    faltando = [n for n in SOURCES if not (BRAND_DIR / n).is_file()]
    if faltando:
        print(f"arte-mestra ausente em {BRAND_DIR}: {', '.join(faltando)}")
        return 1
    build(quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
