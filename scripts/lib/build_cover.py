"""build_cover.py - Assa o retrato estático do mapa que ilustra a capa do Atlas.

Captura o retrato visual do mapa a partir de graph.html já compilado, em navegador
headless Playwright Chromium, com a mesma topologia, arestas e layout:
- Gera uma imagem PNG opaca por tema (light, sepia, dark).
- Elimina a necessidade de carregar grafos pesados em JavaScript na página inicial.

Escopo:
    Módulo de biblioteca para geração de imagens da capa em SITE_ROOT/assets/.
    Sem navegador headless, devolve resultado com status="skip" e preserva imagem existente.

Entradas (Inputs):
    Arquivo SITE_ROOT/graph.html e temas suportados.

Saídas (Outputs):
    Imagens cover-<tema>.png gravadas em SITE_ROOT/assets/brand/.
"""
from pathlib import Path

from sanity_common import (
    CHROMIUM_ABSENT,
    PLAYWRIGHT_ABSENT,
    resolve_chromium,
)

# Tem de bater com o fundo real das duas superfícies, senão a moldura opaca
# aparece. Verificado no navegador: body e canvas pintam a mesma cor.
FUNDOS = {"light": "#ffffff", "dark": "#090909"}

# O <canvas> some por baixo de tudo o que é interface: painel, botões, o
# seletor de mapa. A captura é só do desenho.
CHROME = "#panel, #panel-toggle, #export-svg-popover, #modal-overlay, #reader-overlay, #sb-back, #sb-map-switch"

# Captura num viewport de desktop e reduz: o mapa se enquadra sozinho ao
# viewport, então capturar direto na caixinha da capa engordaria os nós até
# virarem bolhas. Capturar grande e reduzir preserva a forma real e a malha
# inteira de arestas.
LARGURA, ALTURA = 2200, 1376  # 16:10, a proporção da caixa na capa
SAIDA = (1100, 688)           # 550x344 CSS em tela retina
CORES = 192                   # paleta indexada, generosa: o degradê dos nós
                              # e o cinza fino das arestas não fecham em 64
FOLGA = 0.03                  # respiro em volta do desenho, em fração do lado


class CoverResult:
    """Desfecho de uma tentativa de assar a capa.

    `status` é "ok" ou "skip"; `reason` é um código estável para quem programa
    em cima disto, e `detail` é a frase para o humano. `written` só tem
    conteúdo quando `status == "ok"`.
    """

    __slots__ = ("status", "reason", "detail", "written")

    def __init__(self, status, reason, detail, written=None):
        self.status = status
        self.reason = reason
        self.detail = detail
        self.written = written or []

    @property
    def ok(self):
        return self.status == "ok"

    def __iter__(self):
        """Compatibilidade: `for nome, kb in resultado` continua valendo."""
        return iter(self.written)

    def __len__(self):
        return len(self.written)

    def __repr__(self):
        return f"CoverResult({self.status!r}, {self.reason!r}, {self.detail!r})"


def render(site_root, largura=LARGURA, altura=ALTURA, saida=SAIDA, espera=6000):
    """Grava assets/cover-<tema>.png a partir de site/graph.html.

    Devolve sempre um `CoverResult`. Erro real de renderização levanta.
    """
    estado, executavel, texto = resolve_chromium()
    if estado in (PLAYWRIGHT_ABSENT, CHROMIUM_ABSENT):
        return CoverResult("skip", estado, texto)

    from playwright.sync_api import sync_playwright

    origem = Path(site_root) / "graph.html"
    if not origem.is_file():
        return CoverResult("skip", "graph-absent", f"{origem} não existe ainda")
    destino = Path(site_root) / "assets"
    destino.mkdir(parents=True, exist_ok=True)

    escritos = []
    # Falha de renderização NÃO derruba o build. O `clean()` do build já
    # esvaziou o site quando este passo roda, então uma exceção aqui — um
    # Chromium que morre no meio da captura, por exemplo — deixaria o site
    # publicado vazio, sem essay nenhum, por causa de um enfeite de capa. O
    # desfecho certo é o mesmo de não ter navegador: pular, dizer alto o motivo,
    # e deixar a capa anterior no lugar. Quem recusa publicar uma capa ausente
    # ou velha é o gate visual, que abre a página e confere a imagem.
    try:
        return _assar(sync_playwright, origem, destino, executavel, estado, texto,
                      escritos, largura, altura, saida, espera)
    except Exception as exc:  # noqa: BLE001 - ver acima: pular é melhor que abortar
        return CoverResult("skip", "render-failed", f"falha ao renderizar a capa: {exc}")


def _assar(sync_playwright, origem, destino, executavel, estado, texto,
           escritos, largura, altura, saida, espera):
    with sync_playwright() as p:
        navegador = p.chromium.launch(headless=True, executable_path=executavel)
        try:
            for tema, fundo in FUNDOS.items():
                ctx = navegador.new_context(
                    viewport={"width": largura, "height": altura},
                )
                ctx.add_init_script(
                    "try{localStorage.setItem('sb-theme',%r)}catch(e){}" % tema
                )
                # A interface é escondida ANTES da carga, e não depois: o
                # `fitToScreen` do mapa enquadra contando com o painel lateral
                # ocupando a tela, e capturar com ele oculto depois do
                # enquadramento jogava o desenho para a direita.
                ctx.add_init_script(
                    "document.addEventListener('DOMContentLoaded',function(){"
                    "var e=document.createElement('style');"
                    "e.textContent=%r+'{display:none!important}';"
                    "document.head.appendChild(e)})" % CHROME
                )
                pagina = ctx.new_page()
                pagina.goto(origem.resolve().as_uri(), wait_until="load")
                # O layout chega pronto do Python (compute_layout, seed fixa),
                # mas o enquadramento é feito por ticks da simulação: a espera
                # é para capturar o mapa já assentado, que é o que o leitor vê
                # ao abrir a página.
                pagina.wait_for_timeout(espera)
                alvo = destino / f"cover-{tema}.png"
                pagina.locator("canvas#graph").screenshot(path=str(alvo))
                ctx.close()
                _enxugar(alvo, saida, fundo)
                escritos.append((alvo.name, alvo.stat().st_size / 1024))
        finally:
            navegador.close()
    return CoverResult("ok", estado, texto, escritos)


def _enxugar(caminho, saida, fundo):
    """Recorta no desenho, recentraliza no quadro e indexa a paleta.

    O recorte pelo conteúdo é o que garante o centro: não depende de o
    enquadramento do mapa ter acertado a margem, e de quebra devolve ao desenho
    o espaço que sobrava nas bordas.

    Sem dithering de propósito — num mapa, que é fundo chapado com pontos, o
    ruído do dithering destrói a compressão do PNG sem ganho visível.
    """
    from PIL import Image, ImageChops

    imagem = Image.open(caminho).convert("RGB")
    cor = tuple(int(fundo[i:i + 2], 16) for i in (1, 3, 5))
    caixa = ImageChops.difference(imagem, Image.new("RGB", imagem.size, cor)).getbbox()
    if caixa:
        imagem = imagem.crop(caixa)

    largura, altura = saida
    folga = 1 - 2 * FOLGA
    escala = min(largura * folga / imagem.width, altura * folga / imagem.height)
    desenho = imagem.resize(
        (max(1, round(imagem.width * escala)), max(1, round(imagem.height * escala))),
        Image.LANCZOS,
    )
    quadro = Image.new("RGB", saida, cor)
    quadro.paste(desenho, ((largura - desenho.width) // 2,
                           (altura - desenho.height) // 2))
    quadro.quantize(colors=CORES, method=Image.MEDIANCUT, dither=Image.NONE).save(
        caminho, optimize=True
    )


def main():
    from repo_paths import SITE_ROOT

    resultado = render(SITE_ROOT)
    if not resultado.ok:
        print(f"cover: SKIP ({resultado.reason}) — {resultado.detail}")
        return 0
    print(f"cover: {resultado.detail}")
    for nome, kb in resultado.written:
        print(f"  assets/{nome} ({kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
