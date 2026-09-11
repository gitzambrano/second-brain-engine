#!/usr/bin/env python3
"""
build_sphere.py - Grafo ESFÉRICO da wiki: os mesmos nós e arestas do
build_graph.py distribuídos na superfície de uma esfera girável. Layout
pré-calculado (Fibonacci + relaxamento restrito à casca); o cliente não roda
simulação nenhuma - apenas rotação e projeção por frame.

Lê:
    idêntico ao build_graph.py (importa dele a extração de nós/arestas,
    tag gaps, fallback mermaid e leitor embutido):
    wiki/essays|concepts|entities|insights/*.md + wiki/references.json

Gera (em output/graph/, sem tocar nos artefatos canônicos do plano):
    MySecondBrain_sphere.html            globo interativo — versão LEVE (grafo + link .md), arquivo canônico
    MySecondBrain_sphere.reader.html     versão COMPLETA com os essays embutidos
    sphere.json                          grafo completo + ux/uy/uz por nó
    sphere.md                            fallback Mermaid

Uso:
    python scripts/build_sphere.py               # default: gera AS DUAS variantes (leve + reader)
    python scripts/build_sphere.py --reader      # gera só a completa (essays embutidos)
    python scripts/build_sphere.py --no-reader   # gera só a leve (globo + link .md)

Flags:
    --reader | --no-reader   gerar apenas uma das variantes. Sem flag, o
                             script gera as duas, cada uma com nome próprio:
                             leve → MySecondBrain_sphere.html; completa → MySecondBrain_sphere.reader.html
"""

import argparse
import json
import math
import random
import time
from collections import defaultdict

import console_encoding  # noqa: F401  (UTF-8 no console; ver o módulo)

# Reuso direto do build_graph: mesma extração de nós/arestas, mesmos gaps,
# mesmo leitor embutido, mesma compressão de payload. Qualquer correção ali
# vale automaticamente aqui.
from build_graph import (
    OUTPUT_DIR,
    PAKO_VENDORED,
    _deflate_b64,
    _json_for_script_tag,
    _reader_font_css,
    _scope_css_for_shadow,
    _template_base_css,
    build_graph,
    compute_tag_gaps,
    ensure_mathjax,
    render_mermaid,
    render_reader_fragments,
)

OUTPUT_HTML_NAME = "MySecondBrain_sphere.html"
# Versão completa com os essays renderizados embutidos. Sem flags o script
# gera esta E a leve.
READER_HTML_NAME = "MySecondBrain_sphere.reader.html"

# Aparência padrão do globo. Mesma filosofia do GRAPH_STYLE do plano: é o
# default "de fábrica"; o usuário ajusta ao vivo no painel de Estilo (salvo
# em localStorage por navegador) e este dict define o que quem nunca
# customizou recebe.
SPHERE_STYLE = {
    "colors": {
        "essay": "#4fa8ff",
        "concept": "#5fd3c4",
        "entity": "#e8b657",
        "insights": "#b48ce8",
        "reference": "#8a8f96",
        "edge": "#858b93",
        "background": "#1b1e21",
    },
    "edgeOpacity": 0.28,
    "edgeVisibility": "sempre",
    "radiusBase": 4,
    "radiusScale": 2.6,
    "labelSize": 10,
    "glow": "leve",
    "labels": "auto",
    "starfield": True,
    "gradient": True,
    "sphereShading": False,
    "tagTint": False,
    "sizeMode": "degree",
    # Esfera: opacidade dos nós do hemisfério de trás (0 = invisível).
    "backFade": 0.08,
    # Rotação automática até o primeiro arrasto do usuário.
    "autoRotate": True,
    "rotateSpeed": 1.0,
}

SPHERE_STYLE_MOBILE_OVERRIDES = {
    "glow": "leve",
    "starfield": False,
}


def compute_sphere_layout(nodes, edges, iterations=None, seed=42):
    """Espalha os nós pela superfície de uma esfera unitária.

    Duas fases, ambas determinísticas (seed fixa — builds repetíveis):

    1. Fibonacci sphere: sequência de ponto áureo dá cobertura uniforme da
       casca sem clusters nem polos densos (problema clássico de lat/long
       uniforme). Jitter minúsculo quebra coincidências exatas que travariam
       a repulsão. A ordem dos índices é embaralhada (mesma seed) antes da
       atribuição: os nós chegam em blocos contíguos por tipo (todos os
       essays primeiro, depois concepts, entities, references) e, sem o
       shuffle, pontos consecutivos da espiral formam uma faixa contínua —
       todas as bolinhas grandes de um tipo cairiam no mesmo gorro polar.

    2. Relaxamento local restrito à superfície: repulsão de curto alcance
       entre vizinhos (grade espacial 3D — só pares a menos de `cutoff`
       interagem, senão seria O(n²) por iteração) + atração ao longo das
       arestas quando elas estão mais compridas que a separação ideal +
       recentramento do centro de massa na origem a cada iteração. Todo
       deslocamento é renormalizado de volta ao raio 1 — é isso que mantém
       tudo NA superfície; as forças só escorregam pontos pela casca.

    O recentramento existe porque a atração das arestas, sozinha, contrai
    o grafo na direção dos hubs e derruba tudo num hemisfério só. Subtrair
    a média de todos os pontos é uma translação rígida: não altera distâncias
    entre pares (aglomerados temáticos intactos), apenas zera o viés global
    e devolve a cobertura 360°.

    Resultado: páginas conectadas se aglomeram em regiões temáticas da
    esfera, nós soltos ficam distribuídos uniformemente, e o globo inteiro
    mantém separação mínima razoável entre bolinhas. Grava ux/uy/uz em cada
    nó. Retorna a separação mínima final em graus (diagnóstico do main).
    """
    rng = random.Random(seed)
    n = len(nodes)
    if n == 0:
        return None

    ids = [nd["id"] for nd in nodes]
    px = [0.0] * n
    py = [0.0] * n
    pz = [0.0] * n

    golden_angle = math.pi * (3.0 - math.sqrt(5.0))
    # Shuffle determinístico: quebra os blocos contíguos por tipo antes da
    # espiral (ver docstring) — essays/concepts/entities/references passam a
    # se espalhar pelo globo inteiro em vez de ocupar faixas polares.
    order = list(range(n))
    rng.shuffle(order)
    for k, i in enumerate(order):
        if n == 1:
            px[0], py[0], pz[0] = 0.0, 0.0, 1.0
            break
        y = 1.0 - (k / (n - 1)) * 2.0
        r = math.sqrt(max(0.0, 1.0 - y * y))
        theta = golden_angle * k
        x, z = math.cos(theta) * r, math.sin(theta) * r
        x += rng.uniform(-1, 1) * 1e-4
        y += rng.uniform(-1, 1) * 1e-4
        z += rng.uniform(-1, 1) * 1e-4
        norm = math.sqrt(x * x + y * y + z * z) or 1.0
        px[i], py[i], pz[i] = x / norm, y / norm, z / norm

    # Âncoras: cópia das posições Fibonacci. A mola fraca para a âncora
    # (SPHERE_ANCHOR_GAIN) é o que GARANTE cobertura da superfície inteira:
    # sem ela, a atração das arestas contrai o componente gigante num lobo
    # contíguo e metade do globo fica vazia. Perto da âncora a mola é quase
    # nula — aglomerados temáticos locais seguem livres.
    sax = px[:]
    say = py[:]
    saz = pz[:]

    # Separação angular "ideal" entre vizinhos: área da esfera dividida por
    # nó (4π/n) virada em distância — mesmo papel do k de Fruchterman-Reingold.
    k = math.sqrt(4.0 * math.pi / n)
    # Alcance da repulsão em 2.0×k (calibrado na wiki real: dá NN mediano
    # ~5.3° contra ideal 5.9° para n≈1200, sem sufocar os aglomerados).
    cutoff = 2.0 * k
    # Calibração na wiki real (n≈1240): 6.0 equilibra as dezenas de arestas
    # dos hubs e mantém o peso visual (nó grande = alto grau) distribuído —
    # cones de 60° ficam entre 21–28% da massa contra ~25% do uniforme.
    # Ganho menor (<1.5) devolve o componente gigante a um lobo só.
    SPHERE_ANCHOR_GAIN = 6.0

    if iterations is None:
        iterations = 380 if n <= 300 else (240 if n <= 800 else 150)

    idx = {nid: i for i, nid in enumerate(ids)}
    disp = [[0.0, 0.0, 0.0] for _ in range(n)]
    cell = cutoff

    for it_num in range(iterations):
        # Resfriamento: passos largos no início, finos no fim (mesmo espírito
        # da temperatura do FR plano).
        temp = k * (0.55 * (1.0 - it_num / iterations) + 0.05)

        grid = defaultdict(list)
        for i in range(n):
            grid[(int(px[i] / cell), int(py[i] / cell), int(pz[i] / cell))].append(i)

        for dvec in disp:
            dvec[0] = dvec[1] = dvec[2] = 0.0

        # Repulsão de curto alcance — cada par visitado uma vez (j > i).
        # LINEAR no overlap (calibração empírica contra a wiki real: a versão
        # quadrática perdia da atração das arestas e comprimia o grafo todo
        # para 1/4 da separação ideal). Teto de passo no fim do loop controla
        # estabilidade; a força aqui só decide o equilíbrio.
        rep = 0.40 * k
        for i in range(n):
            xi, yi, zi = px[i], py[i], pz[i]
            gx, gy, gz = int(xi / cell), int(yi / cell), int(zi / cell)
            for ox in (-1, 0, 1):
                for oy in (-1, 0, 1):
                    for oz in (-1, 0, 1):
                        bucket = grid.get((gx + ox, gy + oy, gz + oz))
                        if not bucket:
                            continue
                        for j in bucket:
                            if j <= i:
                                continue
                            dx = xi - px[j]
                            dy = yi - py[j]
                            dz = zi - pz[j]
                            d2 = dx * dx + dy * dy + dz * dz
                            if d2 >= cutoff * cutoff or d2 == 0.0:
                                continue
                            d = math.sqrt(d2)
                            f = rep * ((cutoff - d) / cutoff) / d
                            disp[i][0] += dx * f
                            disp[i][1] += dy * f
                            disp[i][2] += dz * f
                            disp[j][0] -= dx * f
                            disp[j][1] -= dy * f
                            disp[j][2] -= dz * f

        # Atração geodésica fraca ao longo das arestas mais compridas que a
        # separação ideal — é o que forma os aglomerados temáticos. Teto por
        # passo evita que um hub muito conectado arraste metade da esfera.
        att = 0.06 * k
        ideal_edge = 0.85 * k
        for e in edges:
            a = idx.get(e["source"])
            b = idx.get(e["target"])
            if a is None or b is None:
                continue
            dx = px[a] - px[b]
            dy = py[a] - py[b]
            dz = pz[a] - pz[b]
            d = math.sqrt(dx * dx + dy * dy + dz * dz) or 1e-6
            if d <= ideal_edge:
                continue
            f = min(att, (d - ideal_edge) * 0.06) / d
            disp[a][0] -= dx * f
            disp[a][1] -= dy * f
            disp[a][2] -= dz * f
            disp[b][0] += dx * f
            disp[b][1] += dy * f
            disp[b][2] += dz * f

        # Mola à âncora Fibonacci: puxa cada nó de volta ao seu ponto semente
        # com força proporcional à distância (quase zero perto dela, forte
        # longe). É o contrapeso global da atração das arestas — impede que o
        # componente gigante contraia num lobo e garanta os 360°.
        ag = SPHERE_ANCHOR_GAIN * k
        for i in range(n):
            disp[i][0] += ag * (sax[i] - px[i])
            disp[i][1] += ag * (say[i] - py[i])
            disp[i][2] += ag * (saz[i] - pz[i])

        any_moved = False
        for i in range(n):
            dx, dy, dz = disp[i]
            mag = math.sqrt(dx * dx + dy * dy + dz * dz)
            if mag == 0.0:
                continue
            any_moved = True
            if mag > temp:
                s = temp / mag
                dx *= s
                dy *= s
                dz *= s
            nx_, ny_, nz_ = px[i] + dx, py[i] + dy, pz[i] + dz
            nm = math.sqrt(nx_ * nx_ + ny_ * ny_ + nz_ * nz_) or 1.0
            px[i], py[i], pz[i] = nx_ / nm, ny_ / nm, nz_ / nm

        # Recentra o centro de massa na origem antes da próxima iteração.
        # Sem isto, a atração das arestas contrai o grafo na direção dos hubs
        # e derruba a nuvem inteira num hemisfério só. Subtrair a média de
        # todos os pontos é uma translação rígida: não altera a distância
        # entre pares — aglomerados temáticos intactos —, apenas zera o viés
        # global e mantém a cobertura nos 360° da superfície. A reprojeção
        # abaixo devolve todo mundo ao raio 1.
        mx = sum(px) / n
        my = sum(py) / n
        mz = sum(pz) / n
        for i in range(n):
            nx_, ny_, nz_ = px[i] - mx, py[i] - my, pz[i] - mz
            nm = math.sqrt(nx_ * nx_ + ny_ * ny_ + nz_ * nz_)
            if nm > 1e-12:
                px[i], py[i], pz[i] = nx_ / nm, ny_ / nm, nz_ / nm

        if not any_moved:
            break

    # Diagnóstico: menor separação angular entre quaisquer dois nós. É O(n²)
    # mas roda UMA vez no build — barato e diz se o relaxamento funcionou
    # (esperado na casa de fração de k; se vier ~0°, tem par colado).
    min_chord = float("inf")
    for i in range(n):
        xi, yi, zi = px[i], py[i], pz[i]
        for j in range(i + 1, n):
            dx = xi - px[j]
            dy = yi - py[j]
            dz = zi - pz[j]
            d2 = dx * dx + dy * dy + dz * dz
            if d2 < min_chord:
                min_chord = d2
    min_sep_deg = math.degrees(2.0 * math.asin(min(math.sqrt(min_chord) / 2.0, 1.0)))

    for i, node in enumerate(nodes):
        node["ux"] = round(px[i], 5)
        node["uy"] = round(py[i], 5)
        node["uz"] = round(pz[i], 5)
    return min_sep_deg


SPHERE_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<title>Grafo Esférico — Second Brain</title>
<style>
  :root {
    --bg: #1b1e21;
    --panel: #24282c;
    --panel-border: #34393e;
    --ink: #e6e9ec;
    --ink-dim: #9aa3ab;
    --instrument-blue: #4fa8ff;
    --concept: #5fd3c4;
    --entity: #e8b657;
    --insight: #b48ce8;
    --reference: #8a8f96;
    --edge: #858b93;
    --edge-ref: #5a5f66;
    --edge-opacity: 0.28;
    --radius-base: 4;
    --radius-scale: 2.6;
    --label-size: 10px;
  }
  * { box-sizing: border-box; }
  /* `html` também precisa da trava de toque/scroll: no iPhone, sem isto, um
     arrasto que começa fora do <canvas> ainda faz o corpo da página fazer o
     "bounce" elástico do Safari. */
  html, body {
    margin: 0; height: 100%; overflow: hidden; overscroll-behavior: none;
    touch-action: none; -webkit-user-select: none; user-select: none;
    -webkit-touch-callout: none; -webkit-tap-highlight-color: transparent;
  }
  body { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; background: var(--bg); color: var(--ink); }
  #graph { width: 100vw; height: 100vh; height: 100dvh; display: block; touch-action: none; -webkit-user-select: none; }

  #panel-toggle {
    display: flex; position: fixed; z-index: 12; top: 10px; left: 10px;
    width: 40px; height: 40px; border-radius: 10px; cursor: pointer;
    border: 1px solid var(--panel-border); background: var(--panel); color: var(--ink);
    font-size: 17px; line-height: 1; align-items: center; justify-content: center;
    box-shadow: 0 4px 14px rgba(0,0,0,.4);
  }
  /* Painel colapsável em TODAS as telas (não só na pequena). */
  #panel.collapsed { display: none; }
  @media (min-width: 900px) {
    #panel-toggle { top: 26px; left: 288px; }
    body:has(#panel.collapsed) #panel-toggle { top: 16px; left: 16px; }
  }
  #panel {
    position: fixed; top: 16px; left: 16px; width: 320px; max-height: calc(100vh - 32px);
    overflow-y: auto; background: var(--panel); border: 1px solid var(--panel-border);
    border-radius: 10px; padding: 16px; box-shadow: 0 8px 24px rgba(0,0,0,.35);
  }
  #panel h1 { font-size: 13px; margin: 0 0 12px 0; letter-spacing: .08em; text-transform: uppercase;
    color: var(--ink-dim); font-weight: 600; }
  #search { width: 100%; padding: 8px 10px; border-radius: 6px; border: 1px solid var(--panel-border);
    background: #1b1e21; color: var(--ink); font-size: 13px; margin-bottom: 12px; }
  #search:focus { outline: none; border-color: var(--instrument-blue); }
  .legend-item { display: flex; align-items: center; gap: 8px; font-size: 12px; margin: 4px 0; color: var(--ink-dim);
    cursor: pointer; padding: 3px 6px; border-radius: 5px; user-select: none; }
  .legend-item:hover { background: rgba(255,255,255,.05); }
  .legend-item.disabled { opacity: 0.5; text-decoration: line-through; }
  /* Um ponto preto e chapado num fundo branco parece um tipo a mais, nao um
     tipo desligado. Vazio com contorno le como "apagado" nos dois temas. */
  .legend-item.disabled .dot { background: transparent !important; border: 1px solid var(--ink-dim); }
  .dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; }
  .btn { width: 100%; padding: 7px 10px; margin-top: 6px; border-radius: 6px; border: 1px solid var(--panel-border);
    background: #1b1e21; color: var(--ink); font-size: 12px; cursor: pointer; text-align: left; }
  .btn:hover { background: rgba(255,255,255,.06); border-color: var(--instrument-blue); }
  #detail { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--panel-border); }
  .detail-title { font-size: 13px; color: var(--ink); line-height: 1.35; }
  .detail-kind { display: flex; align-items: center; gap: 6px; margin-bottom: 7px;
    font-size: 10px; letter-spacing: .12em; text-transform: uppercase; color: var(--ink-dim); }
  .detail-kind i { width: 7px; height: 7px; border-radius: 50%; flex: none; }
  .detail-title.is-citation { font-size: 12px; color: var(--ink-dim); line-height: 1.5; }
  .detail-summary { margin: 8px 0 0; font-size: 11.5px; line-height: 1.5; color: var(--ink-dim); }
  .conn { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--panel-border); }
  .conn-tabs { display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 9px; }
  .conn-tab { display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px;
    border: 1px solid var(--panel-border); border-radius: 999px; background: transparent;
    color: var(--ink-dim); font: inherit; font-size: 10.5px; cursor: pointer;
    transition: color .12s ease, border-color .12s ease, background .12s ease; }
  .conn-tab:hover { color: var(--ink); border-color: var(--ink-dim); }
  .conn-tab b { font-weight: 700; font-variant-numeric: tabular-nums; opacity: .7; }
  .conn-tab.active { background: rgba(79,168,255,.14); border-color: var(--instrument-blue);
    color: var(--instrument-blue); }
  .conn-panes { max-height: 210px; overflow-y: auto; scrollbar-width: thin; }
  .conn-pane { display: flex; flex-direction: column; gap: 1px; }
  /* `display` declarado vence o padrao do atributo `hidden` no navegador:
     sem isto os paineis das outras abas continuavam desenhados embaixo do
     ativo e a aba nao trocava nada. */
  .conn-pane[hidden] { display: none !important; }
  .conn-item { display: flex; align-items: center; gap: 8px; width: 100%; padding: 5px 7px;
    border: 0; border-radius: 6px; background: transparent; color: var(--ink-dim);
    font: inherit; font-size: 11.5px; text-align: left; cursor: pointer; }
  .conn-item:hover { background: rgba(79,168,255,.10); color: var(--ink); }
  .conn-item i { flex: none; width: 6px; height: 6px; border-radius: 50%; }
  .conn-item span { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis;
    white-space: nowrap; }
  .conn-empty { margin: 12px 0 0; font-size: 11px; color: var(--ink-dim); }
  .idx-detail { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
    gap: 10px 32px; padding: 4px 2px 8px; }
  .idx-detail .conn { margin-top: 0; padding-top: 0; border-top: 0; }
  .idx-detail .conn-panes { max-height: 180px; }
  @media (max-width: 900px) {
    .idx-detail { grid-template-columns: minmax(0, 1fr); gap: 12px; }
  }
  .detail-tags { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 8px; }
  .detail-tags span, .idx-tagcell span {
    font-size: 10px; color: var(--ink-dim); background: rgba(255,255,255,.05);
    border-radius: 4px; padding: 2px 6px; white-space: nowrap; }
  .idx-tagcell span { display: inline-block; margin: 0 4px 2px 0; }
  /* Ações do cartão de detalhe: LER e .MD lado a lado, mesmo tamanho. */
  .detail-actions { display: flex; gap: 8px; margin-top: 12px; }
  .detail-actions > * { flex: 1; display: inline-flex; align-items: center;
    justify-content: center; gap: 6px; min-height: 34px; padding: 8px 10px;
    border-radius: 999px; font-size: 12px; font-weight: 600; cursor: pointer;
    text-decoration: none; font-family: inherit; }
  .detail-open { border: 1px solid var(--panel-border); background: transparent;
    color: var(--ink-dim); }
  .detail-open:hover { color: var(--ink); border-color: var(--instrument-blue); text-decoration: none; }

  #modal-overlay { display:none; position: fixed; inset: 0; background: rgba(9,11,13,.72);
    backdrop-filter: blur(3px); -webkit-backdrop-filter: blur(3px); z-index: 20; }
  #modal-overlay.open { display: flex; align-items: stretch; justify-content: stretch; }
  #modal { width: 100vw; height: 100dvh; max-height: 100dvh; overflow-y: auto;
    background: var(--panel); border: none; border-radius: 0; padding: 0; box-shadow: none; }
  /* Mesma medida do corpo: sem isto o "Fechar" fica na borda da tela enquanto o
     conteudo esta centrado, e os dois nao parecem a mesma pagina. */
  #modal-topbar { position: sticky; top: 0; z-index: 5; display: flex; justify-content: flex-end;
    width: 100%; max-width: 1280px; margin-inline: auto;
    padding: 20px clamp(20px, 4vw, 64px) 0; background: linear-gradient(var(--panel) 65%, transparent);
    pointer-events: none; }
  #modal-topbar .close { pointer-events: auto; }
  /* O modal ocupa a tela inteira de proposito, mas o CONTEUDO tem medida:
     sem isto a tabela do indice se estica a 1900px numa tela larga. */
  #modal-body { margin: -4px auto 0; padding: 4px clamp(20px, 4vw, 64px) 72px;
    width: 100%; max-width: 1280px; }
  #modal h2 { margin: 8px 0 20px 0; font-size: 20px; letter-spacing: -.01em;
    color: var(--ink); font-weight: 600; }
  #modal table { width: 100%; border-collapse: collapse; font-size: 13px; }
  #modal th { text-align: left; color: var(--ink-dim); cursor: pointer; padding: 10px 12px; border-bottom: 1px solid var(--panel-border); position: sticky; top:0; background: var(--panel); font-weight: 500;
    font-size: 11px; letter-spacing: .04em; text-transform: uppercase; }
  #modal th:hover { color: var(--ink); }
  #modal th.sorted { color: var(--instrument-blue); }
  #modal td { padding: 11px 12px; border-bottom: 1px solid var(--panel-border);
    vertical-align: middle; }
  /* Numa tela larga a tabela esticava ate a borda: o titulo ficava sozinho a
     esquerda, o botao de ler voava para o meio e os numeros para o canto —
     quatro colunas sem relacao visual entre si. Proporcoes fixas resolvem. */
  #modal table { table-layout: fixed; }
  #modal th:nth-child(1), #modal td:nth-child(1) { width: 46%; }
  #modal th:nth-child(2), #modal td:nth-child(2) { width: 36%; }
  #modal th:nth-child(3), #modal td:nth-child(3) { width: 9%; }
  #modal th:nth-child(4), #modal td:nth-child(4) { width: 9%; }
  #modal td:nth-child(1) > span { min-width: 0; }
  #modal tbody tr { cursor: pointer; transition: background .12s ease; }
  #modal tbody tr:hover td { background: rgba(79,168,255,.08); }

  .idx-summary-row { cursor: default; }
  .idx-summary-row:hover td { background: rgba(255,255,255,.02) !important; }
  .idx-summary-row td { padding-top: 2px; padding-bottom: 14px; background: rgba(255,255,255,.02); }
  .idx-summary { margin: 0; font-size: 12px; color: var(--ink-dim); line-height: 1.6; }
  .idx-expand { width: 28px; height: 28px; padding: 0; border-radius: 50%; flex: none;
    border: 1px solid var(--panel-border); background: #1b1e21; color: var(--ink-dim);
    cursor: pointer; font-family: inherit; font-size: 13px; line-height: 1;
    display: inline-flex; align-items: center; justify-content: center; }
  .idx-expand:hover { color: var(--instrument-blue); border-color: var(--instrument-blue);
    background: rgba(79,168,255,.12); }
  #modal .close { cursor: pointer; color: var(--ink-dim); font-size: 12px; font-family: inherit;
    background: rgba(255,255,255,.05); border: 1px solid var(--panel-border); border-radius: 999px;
    padding: 9px 18px; letter-spacing: .02em; }
  #modal .close:hover { color: var(--ink); border-color: var(--instrument-blue); background: rgba(79,168,255,.12); }

  .idx-tabs { display: flex; gap: 6px; margin-bottom: 16px; flex-wrap: wrap; }
  .idx-tab { padding: 7px 16px; border-radius: 999px; border: 1px solid var(--panel-border);
    background: transparent; color: var(--ink-dim); font-size: 12px; cursor: pointer; font-family: inherit;
    transition: background .12s ease, border-color .12s ease, color .12s ease; }
  .idx-tab:hover { color: var(--ink); border-color: var(--ink-dim); }
  .idx-tab.active { background: var(--instrument-blue); border-color: var(--instrument-blue); color: #0b1220;
    font-weight: 600; box-shadow: 0 2px 10px rgba(79,168,255,.35); }

  #idx-search { width: 100%; padding: 11px 14px; border-radius: 8px; border: 1px solid var(--panel-border);
    background: #1b1e21; color: var(--ink); font-size: 13px; font-family: inherit; margin-bottom: 14px;
    transition: border-color .12s ease, box-shadow .12s ease; }
  #idx-search:focus { outline: none; border-color: var(--instrument-blue);
    box-shadow: 0 0 0 3px rgba(79,168,255,.15); }

  .idx-more { margin-bottom: 14px; }
  .idx-more summary { cursor: pointer; font-size: 12px; color: var(--ink-dim); padding: 4px 0;
    list-style: none; user-select: none; }
  .idx-more summary::-webkit-details-marker { display: none; }
  .idx-more summary::before { content: "▸ "; }
  .idx-more[open] summary::before { content: "▾ "; }
  .idx-more summary:hover { color: var(--ink); }
  .idx-more[open] summary { margin-bottom: 10px; }

  .idx-filters { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; margin-bottom: 14px; }
  .idx-range { display: flex; align-items: center; gap: 6px; font-size: 12px; color: var(--ink-dim); }
  .idx-range input[type="number"] { width: 58px; padding: 7px 8px; border-radius: 7px; border: 1px solid var(--panel-border);
    background: #1b1e21; color: var(--ink); font-size: 12px; font-family: inherit; }
  .idx-range input[type="number"]:focus { outline: none; border-color: var(--instrument-blue); }
  #idx-maturidade { padding: 7px 10px; border-radius: 7px; border: 1px solid var(--panel-border);
    background: #1b1e21; color: var(--ink); font-size: 12px; font-family: inherit; cursor: pointer; }
  .idx-clear { margin-top: 0; padding: 7px 12px; font-size: 12px; width: auto; }

  .idx-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }
  .idx-chip { font-size: 11px; padding: 5px 12px; border-radius: 999px; cursor: pointer; font-family: inherit;
    border: 1px solid var(--panel-border); background: transparent; color: var(--ink-dim);
    transition: background .12s ease, border-color .12s ease, color .12s ease; }
  .idx-chip:hover { color: var(--ink); border-color: var(--ink-dim); }
  .idx-chip.on { background: rgba(79,168,255,.18); border-color: var(--instrument-blue); color: var(--instrument-blue); }
  /* `display:flex` tira o <td> do modelo de caixa da tabela: a celula passa a
     ter a altura do proprio conteudo e a borda de baixo dela desalinha das
     outras (11px acima), quebrando a regua da linha em tres pedacos soltos.
     As tags quebram linha do mesmo jeito como inline-block. */
  .idx-tagcell { line-height: 1.85; }
  .idx-empty { font-size: 13px; color: var(--ink-dim); padding: 40px 4px; text-align: center; }
  .idx-count { font-size: 12px; color: var(--ink-dim); margin-bottom: 10px; letter-spacing: .01em; }
  #modal mark { background: rgba(79,168,255,.35); color: var(--ink); border-radius: 2px; padding: 0 1px; }
  #modal th.sorted.asc::after { content: " ▲"; font-size: 9px; }
  #modal th.sorted.desc::after { content: " ▼"; font-size: 9px; }

  /* ---- Tela pequena ----------------------------------------------------
     Nada aqui altera o desktop: tudo mora dentro da media query. O painel
     lateral vira folha inferior recolhível e o modal ocupa a tela toda. */
  @media (max-width: 720px), (pointer: coarse) and (max-width: 900px) {
    #panel-toggle {
      display: flex;
      top: calc(10px + env(safe-area-inset-top));
      left: calc(10px + env(safe-area-inset-left));
    }
    #panel {
      top: auto; bottom: 0; left: 0; width: 100vw; border-radius: 14px 14px 0 0;
      max-height: 58dvh; padding: 14px 16px calc(16px + env(safe-area-inset-bottom));
      border-left: none; border-right: none; border-bottom: none;
    }
    #panel.collapsed { display: none; }
    #panel h1 { display: none; }
    /* 16px evita o zoom automático que o iOS aplica em campo de texto menor. */
    #search, #idx-search, .idx-range input, #idx-maturidade { font-size: 16px; padding: 10px 12px; }
    .idx-filters { flex-direction: column; align-items: stretch; }
    .idx-range { justify-content: space-between; }
    .idx-range input[type="number"] { flex: 1; width: auto; }
    .idx-clear { width: 100%; }
    .legend-item { font-size: 13px; padding: 7px 8px; }
    .dot { width: 12px; height: 12px; }
    .btn { padding: 10px 12px; font-size: 13px; }
    #modal-body { padding: 4px 14px calc(14px + env(safe-area-inset-bottom)); }
    #modal-topbar { padding: calc(10px + env(safe-area-inset-top)) 14px 0; }
    #modal .close { font-size: 12px; padding: 7px 14px; }
    .idx-tab { padding: 8px 14px; font-size: 12px; }
    .idx-chip { padding: 6px 11px; font-size: 11px; }
    .idx-tags { flex-wrap: nowrap; overflow-x: auto; max-height: none; padding-bottom: 4px; }
    .idx-chip { flex: none; }
    /* As proporcoes fixas do desktop (table-layout + width por coluna) nao
       valem aqui: com as celulas em `display: block` elas espremiam o titulo
       numa coluna de 46% da tela. */
    #modal table { table-layout: auto; }
    #modal th, #modal td,
    #modal th:nth-child(1), #modal td:nth-child(1),
    #modal th:nth-child(2), #modal td:nth-child(2),
    #modal th:nth-child(3), #modal td:nth-child(3),
    #modal th:nth-child(4), #modal td:nth-child(4) { width: auto; }
    #modal table, #modal tbody, #modal tbody tr, #modal td { display: block; width: 100%; }
    /* display:block vence o [hidden] do UA e impede de esconder a linha do
       resumo no mobile — restaura o comportamento do atributo. */
    #modal tbody tr[hidden] { display: none; }
    #modal thead { display: block; }
    #modal thead tr { display: flex; gap: 6px; }
    #modal th { flex: 1; text-align: center; font-size: 10px; padding: 9px 4px;
      border-radius: 6px; background: rgba(255,255,255,.05); border-bottom: none; position: static; }
    #modal tbody tr { border-bottom: 1px solid #2b2f33; padding: 10px 2px; }
    #modal td { border: none; padding: 2px; }
    #modal td[data-label]:not([data-label="Título"]):not([data-label="Temas"]) { color: var(--ink-dim); font-size: 11px; }
    #modal td[data-label]:not([data-label="Título"]):not([data-label="Temas"])::before { content: attr(data-label) ": "; }
  }
  .gap-item { font-size: 12px; margin: 4px 0; color: var(--ink-dim); }
  .gap-item b { color: var(--ink); }

  .style-section { margin-bottom: 0; padding: 18px 20px; background: rgba(255,255,255,.025);
    border: 1px solid var(--panel-border); border-radius: 12px; align-self: start; }
  .style-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(360px, 1fr)); gap: 18px; margin-bottom: 18px; }
  .style-span2 { grid-column: 1 / -1; }
  .style-row { display: flex; align-items: center; justify-content: space-between; gap: 12px;
    font-size: 13px; color: var(--ink-dim); padding: 10px 2px; border-bottom: 1px solid #2b2f33; }
  .style-row:last-child { border-bottom: none; }
  .style-row span { flex: 1; }
  .style-row input[type="color"] { width: 42px; height: 28px; padding: 0; border: 1px solid var(--panel-border);
    border-radius: 7px; background: none; cursor: pointer; }
  .style-slider input[type="range"] { flex: 1.4; accent-color: var(--instrument-blue); }
  .style-row input[type="checkbox"] { width: 17px; height: 17px; accent-color: var(--instrument-blue); cursor: pointer; }
  .style-actions { display: flex; gap: 10px; margin-top: 4px; position: sticky; bottom: 0;
    padding: 14px 0 4px; background: linear-gradient(transparent, var(--panel) 35%); }
  .style-actions .btn { margin-top: 0; text-align: center; }
  .style-primary { background: var(--instrument-blue) !important; color: #0b1220 !important; font-weight: 600;
    border-color: var(--instrument-blue) !important; box-shadow: 0 2px 10px rgba(79,168,255,.3); }
  .style-hint { font-size: 12px; color: var(--ink-dim); margin: -4px 0 12px 0; line-height: 1.5; }
  .theme-row { display: flex; gap: 10px; flex-wrap: wrap; }
  .theme-btn { flex: 1; min-width: 110px; margin-top: 0; text-align: center; padding: 10px 12px; }
  @media (max-width: 720px), (pointer: coarse) and (max-width: 900px) {
    .theme-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .theme-btn { min-width: 0; padding: 8px 6px; font-size: 12px; }
  }
  @media (min-width: 900px) {
    .style-grid { display: block; column-width: 380px; column-gap: 18px; }
    .style-section { break-inside: avoid; margin: 0 0 18px; display: inline-block; width: 100%; }
    .style-span2 { column-span: all; }
    .style-actions { justify-content: flex-end; }
    .style-actions .btn { width: auto; flex: 0 0 auto; padding: 10px 24px; }
  }

  #export-svg-popover { display: none; position: fixed; z-index: 30; flex-direction: column; gap: 8px;
    min-width: 240px; max-width: 280px; background: var(--panel); border: 1px solid var(--panel-border);
    border-radius: 10px; padding: 12px; box-shadow: 0 8px 24px rgba(0,0,0,.4); }
  #export-svg-popover.open { display: flex; }
  #export-svg-popover .btn { width: 100%; margin-top: 0; text-align: center; }
  #export-svg-popover p { font-size: 11px; color: var(--ink-dim); margin: 0 0 2px; line-height: 1.4; }

  /* ---- Leitor embutido (mesmo chrome do grafo plano) ------------------- */
  /* Botão primário do cartão de detalhe (LER): só a cor é dele — geometria
     vem de .detail-actions > *. */
  .read-btn { border: 1px solid var(--instrument-blue); background: var(--instrument-blue);
    color: #0b1220; }
  .read-btn:hover { filter: brightness(1.08); }
  @media (pointer: coarse) {
    .detail-actions > * { position: relative; }
    .detail-actions > *::after { content: ""; position: absolute; inset: -7px; }
    .idx-read { position: relative; }
    .idx-read::after { content: ""; position: absolute; inset: -8px; }
    .idx-expand { position: relative; }
    .idx-expand::after { content: ""; position: absolute; inset: -8px; }
  }
  .idx-read { width: 30px; height: 30px; margin-left: auto; padding: 0; border-radius: 50%;
    border: 1px solid var(--panel-border); background: #1b1e21; color: var(--ink-dim);
    cursor: pointer; font-size: 14px; line-height: 1; flex: none; vertical-align: middle; }
  a.idx-read { display: inline-flex; align-items: center; justify-content: center;
    text-decoration: none; }
  a.idx-read:hover { text-decoration: none; }
  .idx-draft { margin-left: 8px; font-size: 9px; letter-spacing: .14em;
    text-transform: uppercase; color: var(--ink-dim); opacity: .75;
    border: 1px solid var(--panel-border); border-radius: 3px;
    padding: 1px 5px; vertical-align: middle; white-space: nowrap; }
  /* Só a projeção pública usa: marca a página que aparece no mapa mas não abre. */
  .idx-review { margin-left: 8px; font-size: 9px; letter-spacing: .14em;
    text-transform: uppercase; color: var(--ink-dim); opacity: .7;
    border: 1px solid var(--panel-border); border-radius: 3px;
    padding: 1px 5px; vertical-align: middle; white-space: nowrap; }
  .idx-private { margin-left: 8px; font-size: 9px; letter-spacing: .14em;
    text-transform: uppercase; color: var(--ink-dim); opacity: .6;
    border: 1px dashed var(--panel-border); border-radius: 3px;
    padding: 1px 5px; vertical-align: middle; white-space: nowrap; }
  .idx-read:hover { color: var(--instrument-blue); border-color: var(--instrument-blue);
    background: rgba(79,168,255,.12); }
  #reader-overlay { display: none; position: fixed; inset: 0; z-index: 60; background: var(--bg); }
  #reader-overlay.open { display: block; }
  #reader-overlay .sb-progress { position: absolute; top: 0; left: 0; right: 0; height: 3px; z-index: 5; }
  #reader-overlay .sb-progress-fill { height: 100%; width: 0;
    background: linear-gradient(90deg, #A03C28, #C9922A); }
  #reader-scroll { height: 100dvh; overflow-y: auto; -webkit-overflow-scrolling: touch;
    touch-action: pan-y; }
  #reader-article { min-height: 100dvh; }
  #reader-fabs { position: fixed; top: calc(12px + env(safe-area-inset-top)); right: 14px;
    z-index: 70; display: flex; gap: 8px; }
  #reader-fabs button { cursor: pointer; font-family: inherit; border-radius: 999px;
    border: 1px solid #2A2A2A; background: rgba(17,17,17,.92); color: #8A857E;
    font-size: 12px; box-shadow: 0 4px 14px rgba(0,0,0,.35); }
  #reader-fabs button:hover { color: #EDE8DF; border-color: #C9922A; }
  #reader-theme { width: 38px; height: 38px; font-size: 1rem; }
  #reader-close { padding: 0 14px; height: 38px; }
  @media (pointer: coarse) {
    #reader-fabs button { position: relative; }
    #reader-fabs button::after { content: ""; position: absolute; inset: -6px; }
    #reader-close { padding: 0 16px; }
  }
</style>
</head>
<body>
<canvas id="graph"></canvas>
<button id="panel-toggle" aria-label="Mostrar ou esconder o painel" aria-expanded="true">☰</button>
<div id="panel">
  <h1>Grafo Esférico da Wiki</h1>
  <input id="search" type="text" placeholder="Buscar por título ou tema…">

  <div class="legend-item" data-type="essay"><span class="dot" style="background:var(--instrument-blue)"></span> Ensaio</div>
  <div class="legend-item" data-type="concept"><span class="dot" style="background:var(--concept)"></span> Conceito</div>
  <div class="legend-item" data-type="entity"><span class="dot" style="background:var(--entity)"></span> Entidade</div>
  <div class="legend-item" data-type="insights"><span class="dot" style="background:var(--insight)"></span> Ideia</div>
  <div class="legend-item disabled" data-type="reference"><span class="dot" style="background:var(--reference)"></span> Referência</div>

  <button class="btn" id="btn-index">Índice</button>
  <button class="btn" id="btn-gaps">Lacunas entre temas</button>
  <button class="btn" id="btn-style">Estilo</button>
  <button class="btn" id="btn-export-png">Exportar PNG</button>
  <button class="btn" id="btn-export-svg">Exportar SVG</button>
  <button class="btn" id="btn-fit-screen">Recentralizar visão</button>

  <div id="detail" hidden></div>
</div>

<div id="export-svg-popover">
  <p>Completo tem glow e gradiente, mas alguns leitores de SVG simples (ex.: Xplore no Android) podem não abrir. Simples é sem os dois — teste se abre.</p>
  <button class="btn style-primary" id="btn-export-svg-completo">Completo (glow + gradiente)</button>
  <button class="btn" id="btn-export-svg-simples">Simples (sem glow/gradiente)</button>
</div>

<div id="modal-overlay">
  <div id="modal">
    <div id="modal-topbar"><span class="close" id="modal-close">✕ Fechar</span></div>
    <div id="modal-body"></div>
  </div>
</div>

<div id="reader-overlay" role="dialog" aria-modal="true" aria-label="Leitor de ensaio">
  <div class="sb-progress"><div class="sb-progress-fill" id="reader-progress-fill"></div></div>
  <div id="reader-fabs">
    <button id="reader-theme" title="Alternar tema" aria-label="Alternar tema">◐</button>
    <button id="reader-close" aria-label="Fechar leitor">✕ Fechar</button>
  </div>
  <div id="reader-scroll"><div id="reader-article"></div></div>
</div>

<script>__PAKO__</script>
<script type="application/json" id="sb-graph-data">__GRAPH_B64__</script>
<script type="application/json" id="sb-reader-data">__READER_B64__</script>
<script>
// ---- Payloads comprimidos (idêntico ao grafo plano) ---------------------
function b64ToU8(b64) {
  const bin = atob(b64.trim());
  const u = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) u[i] = bin.charCodeAt(i);
  return u;
}
function inflateJsonFromTag(id) {
  const el = document.getElementById(id);
  if (!el || !el.textContent.trim()) return null;
  return JSON.parse(pako.inflate(b64ToU8(el.textContent), { raw: true, to: "string" }));
}
const data = inflateJsonFromTag("sb-graph-data");
let READER_DATA = { essays: {}, mathjax: "", css: "" };
function ensureReaderData() {
  if (READER_DATA.__loaded) return;
  const d = inflateJsonFromTag("sb-reader-data");
  if (d) READER_DATA = d;
  READER_DATA.__loaded = true;
}

// Mesmo detector de aparelho fraco do grafo plano (decoração nasce mais
// leve no celular). Aqui não há física, mas o desenho por frame continua
// custando — a intuição "menos decoração no touch" segue valendo.
function isMobileDevice() {
  const coarse = window.matchMedia && window.matchMedia("(pointer: coarse)").matches;
  const small = Math.min(window.innerWidth, window.innerHeight) < 820;
  const fewCores = (navigator.hardwareConcurrency || 8) <= 4;
  return coarse || (small && fewCores);
}
const DEVICE_IS_MOBILE = isMobileDevice();

// ---- Estilo --------------------------------------------------------------
const STYLE_VARS = {
  essay: "--instrument-blue", concept: "--concept", entity: "--entity",
  insights: "--insight", reference: "--reference", edge: "--edge", background: "--bg",
};
// Chave PRÓPRIA da esfera: quem tem estilo salvo do grafo plano não deve
// ter essa preferência vazada pra cá (controles e defaults diferentes).
const STYLE_KEY = "sb-sphere-style-v1";
const FACTORY_STYLE = data.defaultStyle || {
  colors: { essay: "#4fa8ff", concept: "#5fd3c4", entity: "#e8b657", insights: "#b48ce8",
    reference: "#8a8f96", edge: "#858b93", background: "#1b1e21" },
  edgeOpacity: 0.28, edgeVisibility: "sempre", radiusBase: 4, radiusScale: 2.6,
  labelSize: 10, glow: "leve", labels: "auto", starfield: true, gradient: true,
  sphereShading: false, tagTint: false, sizeMode: "degree",
  backFade: 0.08, autoRotate: true, rotateSpeed: 1.0,
};
const MOBILE_OVERRIDES = data.defaultStyleMobileOverrides || { glow: "leve", starfield: false };
const defaultStyle = DEVICE_IS_MOBILE ? { ...FACTORY_STYLE, ...MOBILE_OVERRIDES } : FACTORY_STYLE;

function loadSavedStyle() {
  try {
    const raw = localStorage.getItem(STYLE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch { return null; }
}

function mergeWithDefaults(saved) {
  return {
    ...defaultStyle,
    ...(saved || {}),
    colors: { ...defaultStyle.colors, ...((saved || {}).colors || {}) },
  };
}

let styleConfig = mergeWithDefaults(loadSavedStyle());

// ---- Canvas base ---------------------------------------------------------
let width = window.innerWidth, height = window.innerHeight;
let dpr = window.devicePixelRatio || 1;
const canvas = document.getElementById("graph");
const ctx = canvas.getContext("2d");

// Loop de desenho com flag "dirty": igual ao plano — todo mundo que muda
// algo visível chama scheduleDraw(); quando ninguém mexe em nada (e a
// rotação automática está desligada), o loop para de ser reagendado.
let rafScheduled = false;
function scheduleDraw() {
  if (rafScheduled) return;
  rafScheduled = true;
  requestAnimationFrame(() => { rafScheduled = false; draw(); });
}

function resizeCanvas() {
  width = window.innerWidth;
  height = window.innerHeight;
  const oldDpr = dpr;
  dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  canvas.style.width = width + "px";
  canvas.style.height = height + "px";
  // Troca de monitor/zoom do SO muda dpr em runtime — sprites do dpr velho
  // sairiam borrados. Guarda `oldDpr !== undefined` porque a PRIMEIRA chamada
  // roda no topo do script, antes de `spriteCache` existir (TDZ estouraria).
  if (oldDpr !== undefined && dpr !== oldDpr) clearSpriteCache();
  scheduleDraw();
}
resizeCanvas();

window.addEventListener("resize", ajustarViewport);
window.addEventListener("orientationchange", ajustarViewport);

function ajustarViewport() {
  resizeCanvas();
  scheduleDraw();
}

function hexToRgb(hex) {
  hex = (hex || "#888888").replace("#", "");
  if (hex.length === 3) hex = hex.split("").map(c => c + c).join("");
  const num = parseInt(hex, 16) || 0x888888;
  return [(num >> 16) & 255, (num >> 8) & 255, num & 255];
}
function mixWhite(hex, amt) {
  const [r, g, b] = hexToRgb(hex);
  return `rgb(${Math.round(r + (255 - r) * amt)},${Math.round(g + (255 - g) * amt)},${Math.round(b + (255 - b) * amt)})`;
}
function hexToRgba(hex, alpha) {
  const [r, g, b] = hexToRgb(hex);
  return `rgba(${r},${g},${b},${alpha})`;
}

// Gradientes cacheados por tipo, definidos num círculo unitário — mesma
// técnica do plano: translate/scale por nó estica o gradiente pronto.
let nodeGradients = {};
let haloGradients = {};
function buildGradients() {
  nodeGradients = {};
  haloGradients = {};
  Object.keys(STYLE_VARS).forEach(type => {
    if (type === "background" || type === "edge") return;
    const color = (styleConfig.colors && styleConfig.colors[type]) || "#888";
    const g = ctx.createRadialGradient(-0.3, -0.35, 0, 0, 0, 1);
    g.addColorStop(0, mixWhite(color, 0.55));
    g.addColorStop(1, color);
    nodeGradients[type] = g;

    const h = ctx.createRadialGradient(0, 0, 0, 0, 0, 1);
    h.addColorStop(0, hexToRgba(color, 0.5));
    h.addColorStop(1, hexToRgba(color, 0));
    haloGradients[type] = h;
  });
}

// Céu estrelado decorativo — igual ao plano (coordenadas fracionárias da
// tela, baldes de opacidade pra baratear o fill por frame).
const STAR_COUNT = 140;
const stars = Array.from({ length: STAR_COUNT }, () => ({
  fx: Math.random(), fy: Math.random(),
  r: Math.random() * 1.1 + 0.2,
  o: Math.random() * 0.5 + 0.08,
}));
const STAR_BUCKETS = 6;
const STAR_O_MIN = 0.08, STAR_O_RANGE = 0.5;
const starBucketLists = Array.from({ length: STAR_BUCKETS }, () => []);
stars.forEach(s => {
  const idx = Math.min(
    STAR_BUCKETS - 1,
    Math.floor(((s.o - STAR_O_MIN) / STAR_O_RANGE) * STAR_BUCKETS)
  );
  starBucketLists[idx].push(s);
});
const starBucketOpacity = starBucketLists.map(
  (_, idx) => STAR_O_MIN + STAR_O_RANGE * ((idx + 0.5) / STAR_BUCKETS)
);

// ---- Estado da câmera esférica -------------------------------------------
// A esfera gira inteira (yaw/pitch); nós NUNCA mudam de lugar na casca —
// arrastar move o planeta, não a página. É a inversão deliberada do grafo
// plano (onde arrastava-se o nó): numa esfera, reposicionar um nó "pela
// superfície" exigiria projeção inversa e não acrescenta leitura nenhuma
// sobre a wiki.
let rotY = -0.6, rotX = 0.35; // radianos
let zoomK = 1;
// O primeiro ARRASTO mata a rotação automática ("Recentralizar visão"
// devolve o comportamento — e reaponta pro hub da wiki).
let userRotated = false;

function viewRadius() { return Math.min(width, height) * 0.40 * zoomK; }

// Ry(yaw) então Rx(pitch), aplicadas ao vetor unitário do nó. Uma passada
// linear por frame, sem trigonometria por nó (cos/sin calculados uma vez).
function projectAll() {
  const cy = Math.cos(rotY), sy = Math.sin(rotY);
  const cx = Math.cos(rotX), sx = Math.sin(rotX);
  const R = viewRadius();
  const hw = width / 2, hh = height / 2;
  for (let i = 0; i < data.nodes.length; i++) {
    const n = data.nodes[i];
    const x1 = n.ux * cy + n.uz * sy;
    const z1 = -n.ux * sy + n.uz * cy;
    const y2 = n.uy * cx - z1 * sx;
    const z2 = n.uy * sx + z1 * cx;
    n.sx = hw + x1 * R;
    n.sy = hh - y2 * R;
    n.sz = z2; // 1 = de frente pro observador, -1 = do outro lado
  }
}

// Fade suave na faixa do horizonte: sem ela, um nó que cruza o limiar dá um
// "pop" de opacidade feio a cada giro. backFade controla o platô de trás.
function depthAlpha(z) {
  const back = styleConfig.backFade ?? 0.08;
  if (z >= 0.12) return 1;
  if (z <= -0.12) return back;
  const t = (z + 0.12) / 0.24;
  return back + (1 - back) * t;
}

function rScreenOf(n) {
  // Profundidade também escala o raio (levemente): lê como volume, não como
  // discos colados num vidro.
  const depth = 0.85 + 0.25 * ((n.sz + 1) / 2);
  return radiusOf(n) * zoomK * depth;
}

// Aponta a câmera pro nó dado. Derivação: escolhe yaw que zera x' mantendo
// z' > 0, depois pitch que leva o resultado pro centro da face visível.
function aimAt(p) {
  rotY = Math.atan2(-p.ux, p.uz);
  rotX = Math.atan2(p.uy, Math.hypot(p.ux, p.uz));
}
function aimAtFocus() {
  let best = null;
  data.nodes.forEach(n => { if (!best || n.degree > best.degree) best = n; });
  if (best && typeof best.ux === "number") aimAt(best);
}

const nodeById = new Map(data.nodes.map(n => [n.id, n]));
const endpoint = (v) => (typeof v === "object" ? v : nodeById.get(v));

// A bibliografia começa DESLIGADA no globo: são centenas de nós de
// referência pendurados num essay só, e na esfera eles formam uma casca que
// esconde a malha de ideias que o mapa existe para mostrar. Ligar continua a
// um clique na legenda (o grafo plano, mais esparso, abre com tudo aceso).
const hiddenTypes = new Set(["reference"]);
function isNodeVisible(n) { return !hiddenTypes.has(n.type); }

function recomputeVisibleDegrees() {
  data.nodes.forEach(n => { n.visibleDegree = 0; });
  data.edges.forEach(e => {
    const s = endpoint(e.source), t = endpoint(e.target);
    if (!s || !t || !isNodeVisible(s) || !isNodeVisible(t)) return;
    s.visibleDegree++;
    t.visibleDegree++;
  });
}

const maxSizeBytes = Math.max(1, ...data.nodes.map(n => n.sizeBytes || 0));
const maxSizeLines = Math.max(1, ...data.nodes.map(n => n.sizeLines || 0));
const SIZE_NORM_K = 4;

function radiusOf(d) {
  const base = styleConfig.radiusBase, scale = styleConfig.radiusScale;
  if (styleConfig.sizeMode === "bytes") {
    return base + Math.sqrt((d.sizeBytes || 0) / maxSizeBytes) * scale * SIZE_NORM_K;
  }
  if (styleConfig.sizeMode === "lines") {
    return base + Math.sqrt((d.sizeLines || 0) / maxSizeLines) * scale * SIZE_NORM_K;
  }
  return base + Math.sqrt(d.visibleDegree ?? d.degree) * scale;
}

function typeColorRaw(n) {
  return (styleConfig.colors && styleConfig.colors[n.type]) || "#888";
}

// ---- Rótulos -------------------------------------------------------------
// "auto" aqui só olha zoom (não há tier de desempenho sem simulação):
// afastou demais, texto some — fillText continua sendo a coisa mais cara
// do frame.
let labelsShown = true;
function updateLabelVisibility() {
  const mode = styleConfig.labels || "sempre";
  const show = mode === "sempre" ? true
    : mode === "nunca" ? false
    : zoomK >= 0.8;
  if (show !== labelsShown) labelsShown = show;
  scheduleDraw();
}

// ---- Seleção/busca -------------------------------------------------------
let selectedNodeId = null;
let highlightSet = null;
let searchMatchIds = null;

function nodeDimmed(n) {
  if (searchMatchIds) return !searchMatchIds.has(n.id);
  if (highlightSet) return !highlightSet.has(n.id);
  return false;
}
function edgeDimmed(e) {
  if (styleConfig.edgeVisibility === "sempre") return false;
  if (searchMatchIds) return true;
  if (selectedNodeId) {
    const a = typeof e.source === "object" ? e.source.id : e.source;
    const b = typeof e.target === "object" ? e.target.id : e.target;
    return a !== selectedNodeId && b !== selectedNodeId;
  }
  return false;
}

// ---- Estilo aplicado ao vivo (painel de Estilo / init) --------------------
function applyStyle(cfg, opts) {
  styleConfig = cfg;
  const root = document.documentElement.style;
  Object.entries(STYLE_VARS).forEach(([key, cssVar]) => {
    if (cfg.colors[key]) root.setProperty(cssVar, cfg.colors[key]);
  });
  root.setProperty("--edge-opacity", cfg.edgeOpacity);
  root.setProperty("--radius-base", cfg.radiusBase);
  root.setProperty("--radius-scale", cfg.radiusScale);
  root.setProperty("--label-size", cfg.labelSize + "px");
  buildGradients();
  clearSpriteCache(); // cor/gradiente/glow/raio podem ter mudado
  updateLabelVisibility();
  scheduleDraw();
}

// ---- Sprites de nós (gradiente/glow/textura) ------------------------------
// Pré-rasterização por APARÊNCIA (tipo × raio em faixas × dpr), igual ao
// plano: um blit de bitmap pronto é ordens de magnitude mais barato que
// recriar gradiente/blur por nó por frame.
const RADIUS_STEP = 1;
const RADIUS_MAX = 48;
const STROKE_PAD = 1.5;
const GLOW_PAD = 8;
const spriteCache = new Map();

function radiusBucket(r) {
  return Math.min(RADIUS_MAX, Math.max(RADIUS_STEP, Math.round(r / RADIUS_STEP) * RADIUS_STEP));
}
function spriteHalfSize(bucket) {
  return bucket + STROKE_PAD + (styleConfig.glow === "alto" ? GLOW_PAD : 0);
}
function clearSpriteCache() {
  spriteCache.clear();
  tagTintSprites.clear();
}

function getNodeSprite(type, dim, r) {
  const bucket = radiusBucket(r);
  const key = type + "|" + dim + "|" + bucket + "|" + dpr + "|" + (styleConfig.sphereShading ? "s" : "");
  let sprite = spriteCache.get(key);
  if (sprite) return sprite;

  const color = (styleConfig.colors && styleConfig.colors[type]) || "#888";
  const half = spriteHalfSize(bucket);
  const size = half * 2;

  sprite = document.createElement("canvas");
  // HiDPI: o bitmap nasce na resolução FÍSICA do aparelho, senão fica
  // borrado em tela retina — mesma razão do resizeCanvas multiplicar dpr.
  const px = Math.max(2, Math.ceil(size * dpr));
  sprite.width = px;
  sprite.height = px;
  const sctx = sprite.getContext("2d");
  sctx.scale(px / size, px / size);
  const cx = half, cy = half;

  sctx.globalAlpha = dim ? 0.08 : 1;
  if (styleConfig.glow === "alto") {
    sctx.shadowColor = color;
    sctx.shadowBlur = 6;
  }
  sctx.beginPath();
  sctx.arc(cx, cy, bucket, 0, Math.PI * 2);
  if (styleConfig.gradient) {
    const g = sctx.createRadialGradient(cx - bucket * 0.3, cy - bucket * 0.35, 0, cx, cy, bucket);
    g.addColorStop(0, mixWhite(color, 0.55));
    g.addColorStop(1, color);
    sctx.fillStyle = g;
  } else {
    sctx.fillStyle = color;
  }
  sctx.fill();
  if (styleConfig.sphereShading) {
    // Brilho especular + sombra de contato: volume de bola de vidro.
    // "source-atop" restringe as camadas aos pixels já opacos do disco.
    sctx.globalCompositeOperation = "source-atop";
    const spec = sctx.createRadialGradient(
      cx - bucket * 0.38, cy - bucket * 0.42, 0,
      cx - bucket * 0.38, cy - bucket * 0.42, bucket * 0.9
    );
    spec.addColorStop(0, "rgba(255,255,255,0.75)");
    spec.addColorStop(0.35, "rgba(255,255,255,0.16)");
    spec.addColorStop(1, "rgba(255,255,255,0)");
    sctx.fillStyle = spec;
    sctx.fillRect(0, 0, size, size);
    const shade = sctx.createRadialGradient(
      cx + bucket * 0.45, cy + bucket * 0.5, 0,
      cx + bucket * 0.45, cy + bucket * 0.5, bucket * 1.15
    );
    shade.addColorStop(0, "rgba(0,0,0,0.4)");
    shade.addColorStop(0.6, "rgba(0,0,0,0.12)");
    shade.addColorStop(1, "rgba(0,0,0,0)");
    sctx.fillStyle = shade;
    sctx.fillRect(0, 0, size, size);
    sctx.globalCompositeOperation = "source-over";
  }
  sctx.shadowBlur = 0;
  sctx.lineWidth = 1;
  sctx.strokeStyle = "#0b1220";
  sctx.stroke();

  spriteCache.set(key, sprite);
  return sprite;
}

function drawNodeSpriteAt(n, r, alpha) {
  const dimmed = nodeDimmed(n);
  const sprite = getNodeSprite(n.type, dimmed, r);
  const bucket = radiusBucket(r);
  // Sprite rasterizado pro BALDE; estica aqui pro raio EXATO do nó — o
  // tamanho final na tela não tem degrau.
  const scale = r / bucket;
  const dw = spriteHalfSize(bucket) * 2 * scale;
  ctx.globalAlpha = alpha;
  ctx.drawImage(sprite, n.sx - dw / 2, n.sy - dw / 2, dw, dw);
}

// ---- Tingimento por tag (só hemisfério da frente) -------------------------
function tagHue(tag) {
  let h = 5381;
  for (let i = 0; i < tag.length; i++) h = ((h * 33) ^ tag.charCodeAt(i)) >>> 0;
  return h % 360;
}
const TAG_DAB_SIZE = 170;
const tagTintSprites = new Map();
function getTagTintSprite(tag) {
  let sprite = tagTintSprites.get(tag);
  if (sprite) return sprite;
  const hue = tagHue(tag);
  sprite = document.createElement("canvas");
  const px = Math.max(2, Math.ceil(TAG_DAB_SIZE * dpr));
  sprite.width = px;
  sprite.height = px;
  const sctx = sprite.getContext("2d");
  sctx.scale(px / TAG_DAB_SIZE, px / TAG_DAB_SIZE);
  const c = TAG_DAB_SIZE / 2;
  const g = sctx.createRadialGradient(c, c, 0, c, c, c);
  g.addColorStop(0, `hsla(${hue}, 60%, 11%, 0.9)`);
  g.addColorStop(1, `hsla(${hue}, 60%, 11%, 0)`);
  sctx.fillStyle = g;
  sctx.fillRect(0, 0, TAG_DAB_SIZE, TAG_DAB_SIZE);
  tagTintSprites.set(tag, sprite);
  return sprite;
}

function drawTagTint(inViewFn) {
  ctx.globalCompositeOperation = "lighter";
  const dabSize = TAG_DAB_SIZE * zoomK;
  const half = dabSize / 2;
  data.nodes.forEach(n => {
    // Dab é um disco de tela; pintar "atrás" da esfera mancharia a região
    // errada do globo — só a frente participa.
    if (!isNodeVisible(n) || n.sz < 0 || !n.tags || !n.tags.length || !inViewFn(n)) return;
    n.tags.forEach(tag => {
      ctx.drawImage(getTagTintSprite(tag), n.sx - half, n.sy - half, dabSize, dabSize);
    });
  });
  ctx.globalCompositeOperation = "source-over";
}

// O mapa publico segue o tema do Atlas (data-theme no <html>); no build da
// wiki o atributo nunca e "light", entao tudo aqui e no-op por la.
function isLightTheme() {
  return document.documentElement.getAttribute("data-theme") === "light";
}

function getLabelColor() {
  if (styleConfig.colors && styleConfig.colors.text) return styleConfig.colors.text;
  const isLight = isLightTheme();
  const bg = (styleConfig.colors && styleConfig.colors.background) || (isLight ? "#ffffff" : "#1b1e21");
  if (isLight) return "#3d4757";
  if (typeof bg === "string" && bg.startsWith("#") && bg.length >= 7) {
    const r = parseInt(bg.slice(1, 3), 16), g = parseInt(bg.slice(3, 5), 16), b = parseInt(bg.slice(5, 7), 16);
    if ((0.299 * r + 0.587 * g + 0.114 * b) / 255 > 0.55) return "#1e293b";
  }
  return "#e6e9ec";
}

// ---- Desenho ---------------------------------------------------------------
function drawHalo(n, r, alpha) {
  const hr = r * 2.4;
  ctx.save();
  ctx.globalAlpha = alpha * 0.9;
  ctx.translate(n.sx, n.sy);
  ctx.scale(hr, hr);
  ctx.beginPath();
  ctx.arc(0, 0, 1, 0, Math.PI * 2);
  ctx.fillStyle = haloGradients[n.type] || "transparent";
  ctx.fill();
  ctx.restore();
}

// Arestas agrupadas por (profundidade × tracejada × esmaecida): um stroke()
// por grupo em vez de um por aresta. Sem Path2D de propósito — a MESMA
// lógica precisa rodar dentro do mock do canvas2svg no export SVG, e lá
// Path2D não é confiável (ver drawSphereForSvgExport).
function collectEdgeGroups(inViewFn) {
  const groups = new Map();
  data.edges.forEach(e => {
    const s = endpoint(e.source), t = endpoint(e.target);
    if (!s || !t || !isNodeVisible(s) || !isNodeVisible(t)) return;
    if (!inViewFn(s) && !inViewFn(t)) return;
    const zf = Math.max(s.sz, t.sz), zb = Math.min(s.sz, t.sz);
    const grp = zb < -0.12 ? (zf > 0.12 ? "cross" : "back") : "front";
    const key = grp + "|" + (e.kind === "reference" ? "r" : "s") + "|" + (edgeDimmed(e) ? "d" : "n");
    let arr = groups.get(key);
    if (!arr) { arr = []; groups.set(key, arr); }
    arr.push(s.sx, s.sy, t.sx, t.sy);
  });
  return groups;
}

function strokeEdgeGroup(arr, grp, kind, dim) {
  ctx.beginPath();
  for (let i = 0; i < arr.length; i += 4) {
    ctx.moveTo(arr[i], arr[i + 1]);
    ctx.lineTo(arr[i + 2], arr[i + 3]);
  }
  ctx.setLineDash(kind === "r" ? [3, 3] : []);
  let alpha = styleConfig.edgeOpacity;
  if (dim) alpha = 0.08;
  else if (grp === "cross") alpha *= 0.45;
  else if (grp === "back") alpha *= Math.max(0.12, styleConfig.backFade ?? 0.08);
  ctx.globalAlpha = Math.min(1, alpha);
  ctx.strokeStyle = styleConfig.colors.edge;
  ctx.stroke();
}

function shouldSpin() {
  // Nada gira enquanto um modal/leitor está aberto ou a aba está oculta —
  // e nada reagenda frames à toa atrás de overlay opaco.
  return styleConfig.autoRotate !== false && !userRotated && !document.hidden
    && !modalOverlay.classList.contains("open") && !readerOpenState;
}

// Uma "passada" de profundidade: halo primeiro (por baixo), depois o corpo.
// Front=true desenha o hemisfério visível; front=false, o de trás. É a
// separação que dá leitura de casca sólida sem z-order por nó.
function nodePass(front, inViewFn) {
  const useSprites = styleConfig.glow === "alto" || styleConfig.gradient || styleConfig.sphereShading;
  // Em fundo claro o halo vira uma sombra colorida em volta de cada bolinha e
  // suja o mapa inteiro; no escuro ele e o que da profundidade. Some no claro.
  const drawHalosHere = styleConfig.glow === "leve" && !isLightTheme();
  if (drawHalosHere) {
    data.nodes.forEach(n => {
      if (!isNodeVisible(n) || !inViewFn(n)) return;
      if ((n.sz > -0.12) !== front) return;
      const dim = nodeDimmed(n);
      const a = depthAlpha(n.sz) * (dim ? 0.08 : 1);
      if (a <= 0.02) return;
      drawHalo(n, rScreenOf(n), a);
    });
  }
  if (useSprites) {
    data.nodes.forEach(n => {
      if (!isNodeVisible(n) || !inViewFn(n)) return;
      if ((n.sz > -0.12) !== front) return;
      const dim = nodeDimmed(n);
      const a = depthAlpha(n.sz) * (dim ? 0.08 : 1);
      if (a <= 0.02) return;
      drawNodeSpriteAt(n, rScreenOf(n), Math.min(1, a));
    });
    ctx.globalAlpha = 1;
  } else {
    // Cor chapada: batch por cor + nível QUANTIZADO de alpha. Profundidade
    // varia por nó, então o agrupamento clássico "uma cor = um path"
    // precisaria desse degrau — 12 níveis são invisíveis a olho nu e
    // limitam os strokes do frame a poucas dezenas.
    const nodeGroups = new Map();
    data.nodes.forEach(n => {
      if (!isNodeVisible(n) || !inViewFn(n)) return;
      if ((n.sz > -0.12) !== front) return;
      const dim = nodeDimmed(n);
      const a = depthAlpha(n.sz) * (dim ? 0.08 : 1);
      if (a <= 0.02) return;
      const aq = Math.min(11, (a * 12) | 0);
      const key = typeColorRaw(n) + "|" + aq + "|" + (dim ? "d" : "n");
      let path = nodeGroups.get(key);
      if (!path) { path = new Path2D(); nodeGroups.set(key, path); }
      const r = rScreenOf(n);
      path.moveTo(n.sx + r, n.sy);
      path.arc(n.sx, n.sy, r, 0, Math.PI * 2);
    });
    ctx.lineWidth = 1;
    ctx.strokeStyle = "#0b1220";
    nodeGroups.forEach((path, key) => {
      const parts = key.split("|");
      const aq = Number(parts[1]);
      ctx.globalAlpha = (aq + 0.5) / 12;
      ctx.fillStyle = parts[0];
      ctx.fill(path);
      ctx.stroke(path);
    });
    ctx.globalAlpha = 1;
  }
}

function draw() {
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);
  ctx.fillStyle = (styleConfig.colors && styleConfig.colors.background) || "#1b1e21";
  ctx.fillRect(0, 0, width, height);

  if (styleConfig.starfield) {
    for (let i = 0; i < STAR_BUCKETS; i++) {
      const bucket = starBucketLists[i];
      if (!bucket.length) continue;
      ctx.beginPath();
      for (let j = 0; j < bucket.length; j++) {
        const s = bucket[j];
        const x = s.fx * width, y = s.fy * height;
        ctx.moveTo(x + s.r, y);
        ctx.arc(x, y, s.r, 0, Math.PI * 2);
      }
      ctx.fillStyle = `rgba(255,255,255,${starBucketOpacity[i]})`;
      ctx.fill();
    }
  }

  // Rotação automática: incrementa ANTES de projetar, pra o frame exibido
  // já sair girado (sem trem de um frame de atraso).
  const spinning = shouldSpin();
  if (spinning) rotY += 0.0022 * (styleConfig.rotateSpeed ?? 1);

  projectAll();

  // Limbo da esfera: círculo-guia sutil que dá ao olho a referência "isso é
  // um globo" — sem ele, a borda entre frente e fundo parece um recorte.
  ctx.beginPath();
  ctx.arc(width / 2, height / 2, viewRadius(), 0, Math.PI * 2);
  ctx.lineWidth = 1;
  ctx.strokeStyle = hexToRgba((styleConfig.colors && styleConfig.colors.edge) || "#858b93", 0.16);
  ctx.stroke();

  const pad = 80;
  const inViewFn = (n) => n.sx >= -pad && n.sx <= width + pad && n.sy >= -pad && n.sy <= height + pad;

  if (styleConfig.tagTint) drawTagTint(inViewFn);

  // Ordem do pintor: arestas de trás -> nós de trás -> arestas da frente ->
  // nós da frente -> rótulos. É o que dá a leitura "casca sólida".
  if (styleConfig.edgeVisibility !== "off") {
    ctx.lineWidth = 1.2;
    const groups = collectEdgeGroups(inViewFn);
    groups.forEach((arr, key) => {
      const parts = key.split("|");
      if (parts[0] === "back") strokeEdgeGroup(arr, parts[0], parts[1], parts[2] === "d");
    });
    nodePass(false, inViewFn);
    ctx.lineWidth = 1.2;
    groups.forEach((arr, key) => {
      const parts = key.split("|");
      if (parts[0] !== "back") strokeEdgeGroup(arr, parts[0], parts[1], parts[2] === "d");
    });
  } else {
    nodePass(false, inViewFn);
  }
  nodePass(true, inViewFn);

  if (labelsShown) {
    ctx.font = `${styleConfig.labelSize}px -apple-system, "Segoe UI", Helvetica, Arial, sans-serif`;
    ctx.textAlign = "center";
    ctx.fillStyle = getLabelColor();
    const isLight = document.documentElement.getAttribute("data-theme") === "light";
    data.nodes.forEach(n => {
      // Rótulos só na frente: texto atravessando o globo vira sopa.
      if (n.type === "reference" || !isNodeVisible(n) || n.sz < 0.05 || !inViewFn(n)) return;
      const dim = nodeDimmed(n);
      ctx.globalAlpha = (dim ? 0.08 : (isLight ? 0.95 : 0.85)) * Math.min(1, depthAlpha(n.sz));
      ctx.fillText(n.title, n.sx, n.sy - (2 + rScreenOf(n)));
    });
    ctx.globalAlpha = 1;
  }

  // Enquanto houver giro próprio, o loop se mantém vivo sozinho; parou de
  // girar, volta a ser puramente event-driven (bateria poupada).
  if (spinning) scheduleDraw();
}

// ---- Gestos: girar o globo, pinça dá zoom, toque seleciona -----------------
const HIT_TOLERANCE_PX = DEVICE_IS_MOBILE ? 22 : 10;
function findNodeAtScreen(px, py) {
  // Varredura linear: roda só em eventos (nunca por frame). Só hemisfério
  // da frente é selecionável — clicar num ponto do outro lado do planeta e
  // selecionar o nó de lá seria surpresa, não descoberta.
  let found = null, best = Infinity;
  const tol = HIT_TOLERANCE_PX;
  for (let i = 0; i < data.nodes.length; i++) {
    const n = data.nodes[i];
    if (!isNodeVisible(n) || n.sz < -0.05) continue;
    const r = rScreenOf(n) + tol;
    const dx = n.sx - px, dy = n.sy - py;
    const d = dx * dx + dy * dy;
    if (d <= r * r && d < best) { best = d; found = n; }
  }
  return found;
}

const pointers = new Map();
let pinchDist = 0, downX = 0, downY = 0, downTime = 0, dragMoved = false;
// Nó agarrado pelo ponteiro: enquanto != null, mover o dedo/mouse arrasta A
// BOLINHA pela superfície em vez de girar o globo.
let dragNode = null;
const DOUBLE_TAP_MS = 350;
const DOUBLE_TAP_PX = 30;
let lastTap = null;

function ptrDist() {
  const v = [...pointers.values()];
  return Math.hypot(v[0].x - v[1].x, v[0].y - v[1].y);
}
function setZoom(k) {
  zoomK = Math.max(0.45, Math.min(5, k));
  updateLabelVisibility();
}

// Arrasta o nó pela superfície: inverte a projeção ortográfica do cursor
// (disco da esfera → frente do casco) e desfaz yaw/pitch para obter o vetor
// unitário no modelo. Cursor fora do disco gruda no horizonte.
function dragNodeTo(n, cx_, cy_) {
  const R = viewRadius();
  let x1 = (cx_ - width / 2) / R;
  let y2 = (height / 2 - cy_) / R;
  const d2 = x1 * x1 + y2 * y2;
  let z2 = 0;
  if (d2 >= 1) { const s = 1 / Math.sqrt(d2); x1 *= s; y2 *= s; }
  else z2 = Math.sqrt(1 - d2);
  const cy = Math.cos(rotY), sy = Math.sin(rotY);
  const cx = Math.cos(rotX), sx = Math.sin(rotX);
  const uy = y2 * cx + z2 * sx;   // desfaz Rx
  const z1 = -y2 * sx + z2 * cx;
  const ux = x1 * cy - z1 * sy;   // desfaz Ry
  const uz = x1 * sy + z1 * cy;
  n.ux = ux; n.uy = uy; n.uz = uz;
}

canvas.addEventListener("pointerdown", (e) => {
  canvas.setPointerCapture(e.pointerId);
  pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
  if (pointers.size === 1) {
    downX = e.clientX; downY = e.clientY;
    downTime = performance.now();
    dragMoved = false;
    // Acertou uma bolinha da frente: este ponteiro arrasta o nó, não o globo.
    dragNode = findNodeAtScreen(e.clientX, e.clientY);
    if (dragNode) userRotated = true;
  } else if (pointers.size === 2) {
    pinchDist = ptrDist();
    dragNode = null; // pinça é zoom: solta a bolinha
  }
});

canvas.addEventListener("pointermove", (e) => {
  const p = pointers.get(e.pointerId);
  if (!p) return;
  const dx = e.clientX - p.x, dy = e.clientY - p.y;
  p.x = e.clientX; p.y = e.clientY;
  if (pointers.size === 1) {
    if (Math.hypot(e.clientX - downX, e.clientY - downY) > 4) dragMoved = true;
    if (dragNode && dragMoved) {
      // Conteúdo segue o dedo: a bolinha gruda no cursor e desliza na casca.
      dragNodeTo(dragNode, e.clientX, e.clientY);
      scheduleDraw();
    } else if (dragMoved) {
      // Conteúdo segue o dedo: yaw com o horizontal, pitch com o vertical.
      userRotated = true;
      rotY += dx * 0.005;
      rotX += dy * 0.005;
      scheduleDraw();
    }
  } else if (pointers.size === 2) {
    dragNode = null;
    const d = ptrDist();
    if (pinchDist > 0 && d > 0) setZoom(zoomK * d / pinchDist);
    pinchDist = d;
  }
});

function handleTap(e) {
  const node = findNodeAtScreen(e.clientX, e.clientY);
  const doToque = e.pointerType !== "mouse";
  const agora = performance.now();
  if (node && doToque && lastTap
      && agora - lastTap.t < DOUBLE_TAP_MS
      && Math.hypot(e.clientX - lastTap.x, e.clientY - lastTap.y) < DOUBLE_TAP_PX) {
    lastTap = null;
    openNode(node);
    return;
  }
  lastTap = (doToque && node) ? { x: e.clientX, y: e.clientY, t: agora } : null;
  if (node) selectNode(node);
  else resetHighlight();
}

function endPointer(e) {
  const wasSingle = pointers.size === 1;
  pointers.delete(e.pointerId);
  if (wasSingle && !dragMoved && performance.now() - downTime < 600) handleTap(e);
  if (pointers.size < 2) pinchDist = 0;
  dragNode = null;
}
canvas.addEventListener("pointerup", endPointer);
canvas.addEventListener("pointercancel", (e) => { pointers.delete(e.pointerId); pinchDist = 0; dragNode = null; });

// Zoom NÃO conta como "usuário assumiu a visão": girar sozinho com o globo
// ampliado continua sendo agradável — só o ARRASTO desliga a rotação.
canvas.addEventListener("wheel", (e) => {
  e.preventDefault();
  setZoom(zoomK * Math.exp(-e.deltaY * 0.0015));
  scheduleDraw();
}, { passive: false });

canvas.addEventListener("dblclick", (e) => {
  const node = findNodeAtScreen(e.clientX, e.clientY);
  if (node) { e.stopPropagation(); openNode(node); }
});

document.addEventListener("visibilitychange", () => { if (!document.hidden) scheduleDraw(); });

// ---- Painel recolhível (tela pequena) --------------------------------------
const panelEl = document.getElementById("panel");
const toggleEl = document.getElementById("panel-toggle");
  const telaPequena = () => window.matchMedia("(max-width: 720px), (pointer: coarse) and (max-width: 900px)").matches;

  function definirPainel(aberto) {
    panelEl.classList.toggle("collapsed", !aberto);
    panelEl.style.display = aberto ? "" : "none";
    toggleEl.setAttribute("aria-expanded", String(aberto));
    toggleEl.textContent = aberto ? "✕" : "☰";
    if (aberto) revelarDetalhe();
  }

// Num celular o painel é uma folha de 58dvh e o cartão de detalhe mora DEPOIS
// da busca, da legenda e de seis botões — ou seja, fora da dobra. Selecionar um
// nó parecia não fazer nada. O painel rola; só faltava levá-lo até lá.
function revelarDetalhe() {
  if (!telaPequena() || detailEl.hidden || panelEl.classList.contains("collapsed")) return;
  requestAnimationFrame(() => {
    // `offsetParent` do cartao E o proprio painel, entao `offsetTop` ja e
    // relativo a ele: subtrair a posicao do painel na tela deixava a rolagem
    // curta exatamente essa distancia.
    panelEl.scrollTop = detailEl.offsetTop - 8;
  });
}
toggleEl.addEventListener("click", () => {
  definirPainel(panelEl.classList.contains("collapsed"));
});
if (telaPequena()) definirPainel(false);

const detailEl = document.getElementById("detail");

function resetHighlight() {
  highlightSet = null;
  selectedNodeId = null;
  searchMatchIds = null;
  detailEl.hidden = true;
  scheduleDraw();
}

// ---- Conexoes por tipo: abas -----------------------------------------------
// Mesmo componente do grafo plano (build_graph.py): os dois mapas mostram a
// mesma base e nao devem divergir no que oferecem ao clicar num no.
const CONN_ORDER = ["concept", "entity", "reference", "insights", "essay"];

function connectionsByType(id) {
  const buckets = new Map();
  neighborsOf(id).forEach(other => {
    if (other === id) return;
    const n = nodeById.get(other);
    if (!n) return;
    if (!buckets.has(n.type)) buckets.set(n.type, []);
    buckets.get(n.type).push(n);
  });
  buckets.forEach(list => list.sort((a, b) => a.title.localeCompare(b.title, "pt-BR")));
  return buckets;
}

function connectionsHtml(id) {
  const buckets = connectionsByType(id);
  const types = CONN_ORDER.filter(t => buckets.has(t));
  if (!types.length) return `<p class="conn-empty">Sem conexoes registradas.</p>`;
  const tabs = types.map((t, i) =>
    `<button type="button" class="conn-tab${i ? "" : " active"}" data-conn-tab="${t}">` +
    `${TYPE_LABELS[t]}<b>${buckets.get(t).length}</b></button>`).join("");
  const panes = types.map((t, i) =>
    `<div class="conn-pane" data-conn-pane="${t}"${i ? " hidden" : ""}>` +
    buckets.get(t).map(n =>
      `<button type="button" class="conn-item" data-conn-go="${escapeHtml(n.id)}" title="${escapeHtml(n.title)}">` +
      `<i style="background:${typeColorRaw(n)}"></i><span>${escapeHtml(n.title)}</span></button>`).join("") +
    `</div>`).join("");
  return `<div class="conn"><div class="conn-tabs">${tabs}</div><div class="conn-panes">${panes}</div></div>`;
}

function wireConnections(root, onGo) {
  root.querySelectorAll("[data-conn-tab]").forEach(tab => {
    tab.addEventListener("click", (e) => {
      e.stopPropagation();
      const key = tab.getAttribute("data-conn-tab");
      root.querySelectorAll("[data-conn-tab]").forEach(x => x.classList.toggle("active", x === tab));
      root.querySelectorAll("[data-conn-pane]").forEach(pane => {
        pane.hidden = pane.getAttribute("data-conn-pane") !== key;
      });
    });
  });
  root.querySelectorAll("[data-conn-go]").forEach(item => {
    item.addEventListener("click", (e) => {
      e.stopPropagation();
      const n = nodeById.get(item.getAttribute("data-conn-go"));
      if (n && onGo) onGo(n);
    });
  });
}

function selectNode(d) {
  // Vindo do índice, o nó pode ser de um tipo oculto na legenda — reexibir
  // é menos surpreendente que clicar e não ver nada acontecer.
  if (hiddenTypes.has(d.type)) {
    hiddenTypes.delete(d.type);
    const chip = document.querySelector(`.legend-item[data-type="${d.type}"]`);
    if (chip) chip.classList.remove("disabled");
    updateVisibility();
  }

  highlightSet = neighborsOf(d.id);
  selectedNodeId = d.id;
  searchMatchIds = null;
  scheduleDraw();

  const target = d.type === "reference" ? d.url : (d.file ? "../../" + d.file : null);
  const slug = essaySlugOf(d);
  const hasReader = slug && readerEssays()[slug];
  const readHref = !hasReader && d.type === "essay" ? d.htmlFile : null;
  detailEl.hidden = false;
  const actions =
    (hasReader ? `<button type="button" class="read-btn" data-read="${escapeHtml(slug)}">📖 Ler</button>` : "") +
    (readHref ? `<a class="read-btn" href="${escapeHtml(readHref)}" target="_blank">📖 Ler</a>` : "") +
    (target ? `<a class="detail-open" href="${escapeHtml(target)}" target="_blank">${d.type === "essay" ? ".MD" : "Abrir"}</a>` : "");
  // Uma referencia nao desenha rotulo no mapa (seria uma citacao inteira em
  // cima de cada ponto); e aqui, ao clicar, que ela se apresenta por extenso.
  const kind = TYPE_LABEL_ONE[d.type] || TYPE_LABELS[d.type] || "";
  detailEl.innerHTML =
    `<div class="detail-kind"><i style="background:${typeColorRaw(d)}"></i>${escapeHtml(kind)}</div>` +
    `<div class="detail-title${d.type === "reference" ? " is-citation" : ""}">${escapeHtml(d.title)}</div>` +
    (d.type === "essay" && d.summary
      ? `<p class="detail-summary">${escapeHtml(d.summary)}</p>` : "") +
    `<div class="detail-tags">${(d.tags || []).map(x => `<span>${escapeHtml(x)}</span>`).join("")}</div>` +
    (actions ? `<div class="detail-actions">${actions}</div>` : "") +
    connectionsHtml(d.id);
  wireConnections(detailEl, selectNode);
  const readBtn = detailEl.querySelector("button.read-btn");
  if (readBtn) readBtn.addEventListener("click", (ev) => {
    ev.stopPropagation();
    openReader(readBtn.getAttribute("data-read"));
  });
  revelarDetalhe();
}

function openNode(d) {
  if (!d) return;
  if (d.type === "reference") {
    if (d.url) window.open(d.url, "_blank");
    return;
  }
  if (d.type === "essay") {
    const slug = essaySlugOf(d);
    if (slug && readerEssays()[slug]) { openReader(slug); return; }
    // Build leve: sem leitor embutido, abre o HTML ja exportado.
    if (d.htmlFile) { window.open(d.htmlFile, "_blank"); return; }
  }
  if (d.file) {
    window.open("../../" + d.file, "_blank");
  }
}

const neighborsOf = (id) => {
  const s = new Set([id]);
  data.edges.forEach(e => {
    const a = typeof e.source === "object" ? e.source.id : e.source;
    const b = typeof e.target === "object" ? e.target.id : e.target;
    if (a === id) s.add(b);
    if (b === id) s.add(a);
  });
  return s;
};

document.getElementById("search").addEventListener("input", (e) => {
  const q = e.target.value.trim().toLowerCase();
  if (!q) { resetHighlight(); return; }
  searchMatchIds = new Set(data.nodes.filter(n =>
    n.title.toLowerCase().includes(q) || (n.tags || []).some(t => t.toLowerCase().includes(q))
  ).map(n => n.id));
  highlightSet = null;
  selectedNodeId = null;
  detailEl.hidden = true;
  scheduleDraw();
});

// ---- Legenda clicável ------------------------------------------------------
function updateVisibility() {
  // Sem simulação pra reacomodar: esconder um tipo só refaz os graus
  // visíveis (raio honesto na tela) e redesenha.
  recomputeVisibleDegrees();
  scheduleDraw();
}

document.querySelectorAll(".legend-item[data-type]").forEach(el => {
  el.addEventListener("click", () => {
    const type = el.getAttribute("data-type");
    if (hiddenTypes.has(type)) {
      hiddenTypes.delete(type);
      el.classList.remove("disabled");
    } else {
      hiddenTypes.add(type);
      el.classList.add("disabled");
    }
    updateVisibility();
  });
});

// ---- Recentralizar ---------------------------------------------------------
function resetView() {
  zoomK = 1;
  userRotated = false;
  aimAtFocus();
  updateLabelVisibility();
  scheduleDraw();
}
document.getElementById("btn-fit-screen").addEventListener("click", resetView);

// ---- Modal: Índice por tipo (idêntico ao plano) ----------------------------
const modalOverlay = document.getElementById("modal-overlay");
const modalBody = document.getElementById("modal-body");
document.getElementById("modal-close").addEventListener("click", () => modalOverlay.classList.remove("open"));
modalOverlay.addEventListener("click", (e) => { if (e.target === modalOverlay) modalOverlay.classList.remove("open"); });

const TYPE_LABELS = {
  essay: "Ensaios", concept: "Conceitos", entity: "Entidades",
  insights: "Ideias", reference: "Referências",
};

// O plural nomeia uma aba ("Concepts 22"); o singular nomeia o nó aberto no
// cartão de detalhe, onde "ESSAYS" para um único essay soaria errado.
const TYPE_LABEL_ONE = {
  essay: "Ensaio", concept: "Conceito", entity: "Entidade",
  insights: "Ideia", reference: "Referência",
};

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

const MATURIDADE_LABELS = { solta: "Solta", germinando: "Germinando", madura: "Madura", absorvida: "Absorvida" };

// ---- Leitor embutido -------------------------------------------------------
function readerEssays() { ensureReaderData(); return READER_DATA.essays || {}; }
const readerOverlay = document.getElementById("reader-overlay");
const readerArticle = document.getElementById("reader-article");
const readerScrollEl = document.getElementById("reader-scroll");
let readerOpenState = false;
let readerLastFocus = null;
let readerCurrentSlug = null;
let mathJaxInjected = false;
let readerShadow = null;
let readerRoot = null;

function essaySlugOf(node) {
  return node && node.type === "essay" ? node.id.slice("essay:".length) : null;
}

function ensureMathJaxInjected() {
  if (mathJaxInjected || !READER_DATA.mathjax) return;
  mathJaxInjected = true;
  const s = document.createElement("script");
  s.textContent = READER_DATA.mathjax;
  document.head.appendChild(s);
}

function typesetElement(el) {
  return new Promise((resolve) => {
    let tries = 0;
    (function attempt() {
      if (window.MathJax && window.MathJax.typesetPromise) {
        window.MathJax.typesetPromise([el]).catch(() => {}).finally(resolve);
      } else if (++tries > 40) {
        resolve();
      } else {
        setTimeout(attempt, 150);
      }
    })();
  });
}

function initReaderShadow() {
  if (readerShadow) return;
  ensureReaderData();
  readerShadow = readerArticle.attachShadow({ mode: "open" });
  // CSS lido AQUI, não no load: o payload é lazy — no load READER_DATA.css
  // ainda é "" e o shadow nasceria sem estilo nenhum.
  readerShadow.innerHTML = `<style>${READER_DATA.css || ""}</style><div class="rd-root"></div>`;
  readerRoot = readerShadow.querySelector(".rd-root");
  // Navegação por âncora DENTRO do shadow (o navegador não rola por #id que
  // só existe na árvore shadow). CSS.escape em vez de aspas escapadas à mão.
  readerRoot.addEventListener("click", (e) => {
    const a = e.target.closest && e.target.closest('a[href^="#"]');
    if (!a) return;
    const id = decodeURIComponent(a.getAttribute("href").slice(1));
    const t = readerRoot.querySelector('[id="' + (window.CSS && CSS.escape ? CSS.escape(id) : id) + '"]');
    if (t) { e.preventDefault(); t.scrollIntoView({ behavior: "smooth", block: "start" }); }
  });
}

function enhanceReaderDom() {
  const content = readerRoot.querySelector(".content");
  if (!content) return;
  content.querySelectorAll("h2[id]").forEach((h) => {
    const a = document.createElement("a");
    a.className = "hlink"; a.href = "#" + h.id; a.textContent = "§";
    a.setAttribute("aria-label", "Link para esta seção");
    a.addEventListener("click", (e) => {
      e.preventDefault();
      h.scrollIntoView({ behavior: "smooth", block: "start" });
      history.replaceState(history.state, "", "#read=" + encodeURIComponent(readerCurrentSlug));
    });
    h.appendChild(a);
  });
  // Rotulos dourados: <span class="sb-kicker"> no inicio de cada h2 (a CSS
  // desenha a regua elastica). Numeros vem do proprio titulo e sao ocultados
  // por stripSelfNumber; secoes semanticas recebem a palavra; essays sem
  // numeros usam contador local; subtitulos (h3) nunca recebem.
  const h2s = content.querySelectorAll("h2:not(#sumário):not(#referências)");
  const selfNum = Array.prototype.some.call(h2s,
    (h) => /^\\s*(?:(?:se[çc][aã]o|cap[íi]tulo|parte)\\s+)?(?:\\d+|[IVXLC]+)[.\\s—–:-]/i.test(h.textContent));
  if (selfNum) {
    content.classList.add("self-numbered");
    const toc = readerRoot.querySelector("#sumário + ul,#sumário + ol");
    if (toc) toc.classList.add("sb-toc-plain");
  }
  const SECTION_RE = /^\\s*(?:(?:se[çc][aã]o|cap[íi]tulo|parte)\\s*)?(?:\\d+|[IVXLC]+)?\\s*[.:\\-—–]?\\s*(introdu[çc][aã]o|conclus[aã]o|resumo(?:\\s+executivo)?|pref[áa]cio|pr[óo]logo|ep[íi]logo|posf[áa]cio|p[óo]s-?escrito|agradecimentos|ap[êe]ndice|anexos?)\\b/i;
  // Espelha o template: esconde o prefixo de numeração à esquerda do título
  // e devolve o número para o kicker. O prefixo pode ter rótulo ("Seção 9 —",
  // "Capítulo II:") — ele some inteiro. O lookahead (?!\\d) evita partir
  // número de subseção ("2.3 Título").
  function stripSelfNumber(h) {
    let n = h.firstChild;
    while (n && n.nodeType !== 3) n = n.nextSibling;
    if (!n) return null;
    const m = /^\\s*((?:(?:se[çc][aã]o|cap[íi]tulo|parte)\\s+)?((?:\\d+|[IVXLC]+))(?:[.\\s—–:-]+))(?!\\d)([\\s\\S]*)$/i.exec(n.data);
    if (!m) return null;
    const span = document.createElement("span");
    span.className = "sb-selfnum";
    span.setAttribute("aria-hidden", "true");
    span.textContent = m[1];
    n.data = m[3];
    h.insertBefore(span, n);
    return m[2].toUpperCase();
  }
  function makeKicker(text) {
    const k = document.createElement("span");
    k.className = "sb-kicker";
    k.textContent = text;
    return k;
  }
  let chapterNo = 0;
  Array.prototype.forEach.call(h2s, (h) => {
    const sem = SECTION_RE.exec(h.textContent);
    const num = selfNum ? stripSelfNumber(h) : null;
    let label = null;
    if (sem) {
      label = sem[1].toUpperCase();
    } else if (num) {
      const pad = /^[0-9]/.test(num) && num.length < 2 ? "0" + num : num;
      label = "CAPÍTULO " + pad;
    } else if (!selfNum) {
      chapterNo += 1;
      label = "CAPÍTULO " + (chapterNo < 10 ? "0" + chapterNo : "" + chapterNo);
    }
    if (label) h.insertBefore(makeKicker(label), h.firstChild);
  });
  const refs = content.querySelector("h2#referências");
  if (refs) refs.insertBefore(makeKicker("Referências"), refs.firstChild);
}

// Tema: mesma regra do template — mobile escuro, desktop claro; toggle
// persiste na MESMA chave 'sb-theme' usada pelos exports (consistência).
function applyReaderTheme() {
  let saved = null;
  try { saved = localStorage.getItem("sb-theme"); } catch (err) {}
  const def = window.matchMedia("(min-width:901px)").matches ? "light" : "dark";
  const theme = saved || def;
  readerArticle.setAttribute("data-theme", theme);
  return theme;
}

document.getElementById("reader-theme").addEventListener("click", () => {
  if (!readerOpenState) return;
  const cur = readerArticle.getAttribute("data-theme") || "dark";
  const next = cur === "dark" ? "light" : "dark";
  readerArticle.setAttribute("data-theme", next);
  try { localStorage.setItem("sb-theme", next); } catch (err) {}
});

async function openReader(slug) {
  ensureReaderData();
  const entry = readerEssays()[slug];
  if (!entry) return false;
  readerCurrentSlug = slug;
  initReaderShadow();
  // MathJax não enxerga dentro de shadow: tipografia num staging do
  // light-DOM antes da enxertia.
  const staging = document.createElement("div");
  staging.style.display = "none";
  staging.innerHTML = entry.html;
  document.body.appendChild(staging);
  ensureMathJaxInjected();
  await typesetElement(staging);
  applyReaderTheme();
  readerRoot.innerHTML = "";
  while (staging.firstChild) readerRoot.appendChild(staging.firstChild);
  staging.remove();
  enhanceReaderDom();
  readerScrollEl.scrollTop = 0;
  updateReaderProgress();
  readerOverlay.classList.add("open");
  if (!readerOpenState) {
    readerLastFocus = document.activeElement;
    history.pushState({ rd: slug }, "", "#read=" + encodeURIComponent(slug));
  } else {
    history.replaceState({ rd: slug }, "", "#read=" + encodeURIComponent(slug));
  }
  readerOpenState = true;
  document.getElementById("reader-close").focus({ preventScroll: true });
  return true;
}

function closeReader(fromPop) {
  if (!readerOpenState) return;
  readerOverlay.classList.remove("open");
  readerOpenState = false;
  if (readerLastFocus && readerLastFocus.focus) readerLastFocus.focus({ preventScroll: true });
  // Só volta no histórico se a entrada atual foi empilhada por nós; num
  // deep-link direto (#read= colado na URL) não há entry para estourar.
  if (!fromPop && history.state && history.state.rd) history.back();
}

function updateReaderProgress() {
  const el = readerScrollEl, max = el.scrollHeight - el.clientHeight;
  const fill = document.getElementById("reader-progress-fill");
  if (fill) fill.style.width = (max > 0 ? (el.scrollTop / max) * 100 : 0) + "%";
}
readerScrollEl.addEventListener("scroll", updateReaderProgress, { passive: true });

document.getElementById("reader-close").addEventListener("click", () => closeReader(false));
window.addEventListener("popstate", () => {
  if (!(history.state && history.state.rd)) closeReader(true);
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && readerOpenState) closeReader(false);
});

// Deep-link: MySecondBrain_sphere.html#read=<slug> abre direto no essay.
(function () {
  const m = location.hash.match(/^#read=([^\\s]+)$/);
  if (!m) return;
  requestAnimationFrame(() => openReader(decodeURIComponent(m[1])));
})();

// Navegação fragment-only (colar outro #read= na mesma aba, voltar/avançar)
// NÃO recarrega o documento — sem este listener, nada mudaria na tela.
window.addEventListener("hashchange", () => {
  const m = location.hash.match(/^#read=([^\\s]+)$/);
  if (m) openReader(decodeURIComponent(m[1]));
});

// ---- Índice ----------------------------------------------------------------
function highlightMatch(text, q) {
  const safe = escapeHtml(text);
  if (!q) return safe;
  const i = text.toLowerCase().indexOf(q.toLowerCase());
  if (i === -1) return safe;
  return escapeHtml(text.slice(0, i)) + "<mark>" + escapeHtml(text.slice(i, i + q.length)) + "</mark>" + escapeHtml(text.slice(i + q.length));
}

function renderTypeIndex() {
  const state = {
    type: "essay", tags: new Set(), query: "", col: "degree", dir: -1,
    minDegree: "", maxDegree: "", maturidade: "",
  };

  modalBody.innerHTML = `
    <h2>Índice</h2>
    <div class="idx-tabs"></div>
    <input id="idx-search" type="text" placeholder="Filtrar por título…">
    <details class="idx-more" ${telaPequena() ? "" : "open"}>
      <summary>Mais filtros</summary>
      <div class="idx-filters">
        <div class="idx-range">
          <span>Conexões</span>
          <input id="idx-min-degree" type="number" min="0" placeholder="mín">
          <span>–</span>
          <input id="idx-max-degree" type="number" min="0" placeholder="máx">
        </div>
        <select id="idx-maturidade" hidden></select>
        <button class="btn idx-clear" id="idx-clear">Limpar filtros</button>
      </div>
      <div class="idx-tags"></div>
    </details>
    <div class="idx-count"></div>
    <table id="idx-table">
      <thead><tr>
        <th data-col="title">Título</th><th data-col="tags">Temas</th>
        <th data-col="degree">Conexões</th><th data-col="size">Tamanho</th>
      </tr></thead>
      <tbody></tbody>
    </table>
    <div class="idx-empty" hidden>Nada corresponde a esse filtro.</div>`;

  const tabsEl = modalBody.querySelector(".idx-tabs");
  const tagsEl = modalBody.querySelector(".idx-tags");
  const tbody = modalBody.querySelector("tbody");
  const emptyEl = modalBody.querySelector(".idx-empty");
  const countEl = modalBody.querySelector(".idx-count");
  const maturidadeEl = modalBody.querySelector("#idx-maturidade");

  Object.keys(TYPE_LABELS).forEach(t => {
    const b = document.createElement("button");
    b.className = "idx-tab" + (t === state.type ? " active" : "");
    b.textContent = TYPE_LABELS[t];
    b.addEventListener("click", () => {
      state.type = t;
      state.tags.clear();
      state.maturidade = "";
      tabsEl.querySelectorAll(".idx-tab").forEach(x => x.classList.toggle("active", x === b));
      drawTags();
      drawMaturidadeFilter();
      draw();
    });
    tabsEl.appendChild(b);
  });

  // Filtro de maturidade só faz sentido pra Insights — os outros tipos nem
  // têm o campo. Reaproveita o mesmo <select> em vez de duplicar HTML.
  function drawMaturidadeFilter() {
    const show = state.type === "insights";
    maturidadeEl.hidden = !show;
    if (!show) return;
    maturidadeEl.innerHTML = `<option value="">Toda maturidade</option>` +
      Object.entries(MATURIDADE_LABELS).map(([k, label]) =>
        `<option value="${k}">${label}</option>`).join("");
  }

  // As tags oferecidas são só as que existem no tipo em exibição: filtro que
  // não pode dar resultado vazio é filtro que não precisa estar ali.
  function drawTags() {
    const counts = new Map();
    data.nodes.filter(n => n.type === state.type).forEach(n => {
      (n.tags || []).forEach(t => counts.set(t, (counts.get(t) || 0) + 1));
    });
    const ordered = [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
    tagsEl.innerHTML = "";
    ordered.forEach(([tag, count]) => {
      const chip = document.createElement("button");
      chip.className = "idx-chip";
      chip.textContent = `${tag} · ${count}`;
      chip.addEventListener("click", () => {
        state.tags.has(tag) ? state.tags.delete(tag) : state.tags.add(tag);
        chip.classList.toggle("on", state.tags.has(tag));
        draw();
      });
      tagsEl.appendChild(chip);
    });
    tagsEl.hidden = ordered.length === 0;
  }

  function draw() {
    const q = state.query.toLowerCase();
    const min = state.minDegree === "" ? -Infinity : Number(state.minDegree);
    const max = state.maxDegree === "" ? Infinity : Number(state.maxDegree);
    // Múltiplas tags combinam por E: cada clique estreita o resultado.
    const totalOfType = data.nodes.filter(n => n.type === state.type).length;
    let rows = data.nodes.filter(n =>
      n.type === state.type
      && (!q || n.title.toLowerCase().includes(q))
      && [...state.tags].every(t => (n.tags || []).includes(t))
      && n.degree >= min && n.degree <= max
      && (!state.maturidade || n.maturidade === state.maturidade)
    );

    const sizeOf = (n) => n.sizeLines || 0;
    const value = (n) => state.col === "title" ? n.title.toLowerCase()
      : state.col === "tags" ? (n.tags || []).join(",").toLowerCase()
      : state.col === "size" ? sizeOf(n)
      : n.degree;
    rows.sort((a, b) => {
      const av = value(a), bv = value(b);
      return av < bv ? -state.dir : av > bv ? state.dir : 0;
    });

    // Resumo expansível só pra essays (único tipo com corpo de verdade por
    // trás); sem `summary:` no arquivo, não mostra o botão de expandir.
    const showSummary = state.type === "essay";
    tbody.innerHTML = rows.map(n => {
      // A linha expande para um painel de detalhe: resumo (quando existe) e as
      // conexoes daquele no separadas por tipo.
      const hasSummary = showSummary && n.summary;
      const hasDetail = hasSummary || connectionsByType(n.id).size > 0;
      const rSlug = essaySlugOf(n);
      const readBtn = (rSlug && readerEssays()[rSlug])
        ? `<button type="button" class="idx-read" data-read="${escapeHtml(rSlug)}" aria-label="Ler ${escapeHtml(n.title)}" title="Ler">📖</button>`
        : (n.htmlFile
          ? `<a class="idx-read" href="${escapeHtml(n.htmlFile)}" target="_blank" aria-label="Ler ${escapeHtml(n.title)}" title="Ler">📖</a>`
          : "");
      const draft = n.status === "draft"
        ? `<span class="idx-draft" title="Rascunho">draft</span>`
        : n.status === "revisao"
          ? `<span class="idx-review" title="Em revisão">em revisão</span>`
          : "";
      // `public` só existe no build da projeção pública (build_public_map.py).
      // No build da wiki o campo não vem e nenhum selo é desenhado.
      const privateMark = (n.public === false)
        ? `<span class="idx-private" title="Não publicado: aparece no mapa, não abre">privado</span>`
        : "";
      const row = `<tr data-id="${escapeHtml(n.id)}">
      <td data-label="Título"><span style="display:flex;align-items:center;gap:8px;">${hasDetail
        ? `<button type="button" class="idx-expand" aria-label="Mostrar detalhe" aria-expanded="false">▸</button> `
        : ""}<span style="flex:0 1 auto;min-width:0;">${highlightMatch(n.title, state.query)}${draft}${privateMark}</span>${readBtn}</span></td>
      <td class="idx-tagcell" data-label="Temas">${(n.tags || []).map(t => `<span>${escapeHtml(t)}</span>`).join("")}</td>
      <td data-label="Conexões">${n.degree}</td>
      <td data-label="Tamanho">${sizeOf(n) ? sizeOf(n) + " linhas" : "—"}</td></tr>`;
      const summaryRow = hasDetail
        ? `<tr class="idx-summary-row" hidden><td colspan="4"><div class="idx-detail">`
          + (n.summary ? `<p class="idx-summary">${escapeHtml(n.summary)}</p>` : "")
          + connectionsHtml(n.id)
          + `</div></td></tr>`
        : "";
      return row + summaryRow;
    }).join("");
    emptyEl.hidden = rows.length > 0;
    countEl.textContent = rows.length === totalOfType
      ? `${rows.length} ${TYPE_LABELS[state.type].toLowerCase()}`
      : `${rows.length} de ${totalOfType} exibidos`;

    // stopPropagation(): abrir o resumo não pode também navegar pro nó.
    tbody.querySelectorAll(".idx-expand").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const summaryRow = btn.closest("tr").nextElementSibling;
        if (!summaryRow || !summaryRow.classList.contains("idx-summary-row")) return;
        const willOpen = summaryRow.hidden;
        summaryRow.hidden = !willOpen;
        if (willOpen && !summaryRow.dataset.wired) {
          summaryRow.dataset.wired = "1";
          wireConnections(summaryRow, (node) => {
            modalOverlay.classList.remove("open");
            selectNode(node);
          });
        }
        btn.textContent = willOpen ? "▾" : "▸";
        btn.setAttribute("aria-expanded", String(willOpen));
      });
    });

    // 📖 na linha abre o leitor sem fechar o índice nem navegar o grafo.
    // `button.idx-read` e nao `.idx-read`: no build leve o mesmo lugar tem um
    // <a> que navega sozinho — um seletor solto chamaria openReader(null).
    tbody.querySelectorAll("button.idx-read").forEach(b => {
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        openReader(b.getAttribute("data-read"));
      });
    });
    tbody.querySelectorAll("a.idx-read").forEach(a => {
      a.addEventListener("click", (e) => e.stopPropagation());
    });

    tbody.querySelectorAll("tr").forEach(tr => {
      tr.addEventListener("click", () => {
        const node = nodeById.get(tr.getAttribute("data-id"));
        if (!node) return;
        modalOverlay.classList.remove("open");
        selectNode(node);
      });
    });
  }

  modalBody.querySelector("#idx-search").addEventListener("input", (e) => {
    state.query = e.target.value.trim();
    draw();
  });
  modalBody.querySelector("#idx-min-degree").addEventListener("input", (e) => { state.minDegree = e.target.value; draw(); });
  modalBody.querySelector("#idx-max-degree").addEventListener("input", (e) => { state.maxDegree = e.target.value; draw(); });
  maturidadeEl.addEventListener("change", (e) => { state.maturidade = e.target.value; draw(); });
  modalBody.querySelector("#idx-clear").addEventListener("click", () => {
    state.tags.clear(); state.query = ""; state.minDegree = ""; state.maxDegree = ""; state.maturidade = "";
    modalBody.querySelector("#idx-search").value = "";
    modalBody.querySelector("#idx-min-degree").value = "";
    modalBody.querySelector("#idx-max-degree").value = "";
    maturidadeEl.value = "";
    tagsEl.querySelectorAll(".idx-chip.on").forEach(c => c.classList.remove("on"));
    draw();
  });
  modalBody.querySelectorAll("th[data-col]").forEach(th => {
    th.addEventListener("click", () => {
      const col = th.getAttribute("data-col");
      state.dir = (state.col === col) ? -state.dir : -1;
      state.col = col;
      modalBody.querySelectorAll("th").forEach(x => { x.classList.remove("sorted", "asc", "desc"); });
      th.classList.add("sorted", state.dir === 1 ? "asc" : "desc");
      draw();
    });
  });

  drawTags();
  drawMaturidadeFilter();
  draw();
}

let styleModalOpen = false;

document.getElementById("btn-index").addEventListener("click", () => {
  styleModalOpen = false;
  renderTypeIndex();
  modalOverlay.classList.add("open");
});

// ---- Gaps (calculado no Python, embutido nos dados) ------------------------
document.getElementById("btn-gaps").addEventListener("click", () => {
  styleModalOpen = false;
  const gaps = data.tag_gaps || [];
  let html = `<h2>Lacunas entre temas</h2>`;
  if (!gaps.length) {
    html += `<div class="gap-item">Nenhum par de tags isolado — todo o grafo conectado por tags está num único componente (ou não há tags suficientes ainda).</div>`;
  } else {
    gaps.forEach(([a, b]) => {
      html += `<div class="gap-item"><b>${a}</b> nunca se conecta com <b>${b}</b></div>`;
    });
  }
  modalBody.innerHTML = html;
  modalOverlay.classList.add("open");
});

// ---- Painel de Estilo do globo ---------------------------------------------
const STYLE_LABELS = {
  essay: "Ensaio", concept: "Conceito", entity: "Entidade", insights: "Ideia",
  reference: "Referência", edge: "Arestas", background: "Fundo",
};

const GRAPH_THEMES = {
  cosmico: { label: "Cósmico", glow: "alto", starfield: true, gradient: true },
  padrao: { label: "Padrão", glow: "leve", starfield: true, gradient: true },
  minimalista: { label: "Minimalista", glow: "off", starfield: false, gradient: false },
  aqua: {
    label: "Aqua", glow: "leve", starfield: false, gradient: true,
    colors: { essay: "#22d3ee", concept: "#0ea5a2", entity: "#38bdf8",
      insights: "#67e8f9", reference: "#5f8f96", edge: "#3fa6c2", background: "#062026" },
  },
  noite: {
    label: "Céu Noturno", glow: "alto", starfield: true, gradient: true,
    colors: { essay: "#8ab4ff", concept: "#a78bfa", entity: "#fbbf24",
      insights: "#f472b6", reference: "#64748b", edge: "#3d4a63", background: "#0a0e1f" },
  },
  inferno: {
    label: "Inferno", glow: "alto", starfield: false, gradient: true,
    colors: { essay: "#ff6b35", concept: "#ff3b3b", entity: "#ffb703",
      insights: "#c1121f", reference: "#7f1d1d", edge: "#a11d1d", background: "#170404" },
  },
  synthwave: {
    label: "Synthwave", glow: "alto", starfield: true, gradient: true,
    colors: { essay: "#ff2bd6", concept: "#00e5ff", entity: "#ffe400",
      insights: "#a78bfa", reference: "#7c3aed", edge: "#ff2bd6", background: "#170426" },
  },
};

function renderStylePanel(seed) {
  const draft = JSON.parse(JSON.stringify(seed || styleConfig)); // rascunho — só grava no "Salvar"

  const colorRow = (key) => `
    <label class="style-row">
      <span>${STYLE_LABELS[key]}</span>
      <input type="color" data-color="${key}" value="${draft.colors[key]}">
    </label>`;

  const themeBtn = (key, t) => `<button class="btn theme-btn" data-theme="${key}">${t.label}</button>`;

  modalBody.innerHTML = `
    <h2>Estilo do globo</h2>
    <div class="style-grid">
    <div class="style-section style-span2">
      <p class="style-hint">Temas ajustam vários controles de uma vez — os itens abaixo continuam ajustáveis um a um depois.</p>
      <div class="theme-row">${Object.entries(GRAPH_THEMES).map(([k, t]) => themeBtn(k, t)).join("")}</div>
    </div>
    <div class="style-section">
      ${Object.keys(STYLE_LABELS).map(colorRow).join("")}
      <label class="style-row style-slider">
        <span>Raio base da bolinha</span>
        <input type="range" id="st-radius-base" min="2" max="14" step="1" value="${draft.radiusBase}">
      </label>
      <label class="style-row style-slider">
        <span>Escala do tamanho</span>
        <input type="range" id="st-radius-scale" min="0" max="8" step="0.5" value="${draft.radiusScale}">
      </label>
    </div>
    <div class="style-section">
      <label class="style-row">
        <span>Tamanho da bolinha representa</span>
        <select id="st-size-mode">
          <option value="degree" ${draft.sizeMode === "degree" ? "selected" : ""}>Nº de conexões</option>
          <option value="bytes" ${draft.sizeMode === "bytes" ? "selected" : ""}>Tamanho do essay (bytes)</option>
          <option value="lines" ${draft.sizeMode === "lines" ? "selected" : ""}>Tamanho do essay (linhas)</option>
        </select>
      </label>
      <p class="style-hint">Referências não têm arquivo — nos modos de tamanho de essay elas ficam sempre no raio base.</p>
    </div>
    <div class="style-section">
      <label class="style-row">
        <span>Conexões (arestas) entre os nós</span>
        <select id="st-edges">
          <option value="sempre" ${(draft.edgeVisibility ?? "sempre") === "sempre" ? "selected" : ""}>Sempre visível</option>
          <option value="auto" ${draft.edgeVisibility === "auto" ? "selected" : ""}>Automático (esmaece ao selecionar/buscar)</option>
          <option value="off" ${draft.edgeVisibility === "off" ? "selected" : ""}>Desligado</option>
        </select>
      </label>
      <label class="style-row style-slider">
        <span>Opacidade das arestas</span>
        <input type="range" id="st-edge-opacity" min="0.1" max="1" step="0.05" value="${draft.edgeOpacity}">
      </label>
      <label class="style-row style-slider">
        <span>Tamanho do rótulo</span>
        <input type="range" id="st-label-size" min="8" max="18" step="1" value="${draft.labelSize}">
      </label>
    </div>
    <div class="style-section">
      <label class="style-row">
        <span>Rotação automática</span>
        <input type="checkbox" id="st-autorotate" ${draft.autoRotate !== false ? "checked" : ""}>
      </label>
      <p class="style-hint">O globo gira devagar até o primeiro arrasto seu; o botão "Recentralizar visão" religa.</p>
      <label class="style-row style-slider">
        <span>Velocidade da rotação</span>
        <input type="range" id="st-rotate-speed" min="0.2" max="3" step="0.2" value="${draft.rotateSpeed ?? 1}">
      </label>
      <label class="style-row style-slider">
        <span>Nós do lado de trás</span>
        <input type="range" id="st-back-fade" min="0" max="0.35" step="0.01" value="${draft.backFade ?? 0.08}">
      </label>
      <p class="style-hint">Opacidade do hemisfério oculto. 0 = invisível (só a face da frente); subir demais vira bagunça de profundidade.</p>
    </div>
    <div class="style-section">
      <p class="style-hint">Extras puramente decorativos — desligue os que não quiser, principalmente em wikis grandes ou no celular.</p>
      <label class="style-row">
        <span>Brilho (glow) nos nós</span>
        <select id="st-glow">
          <option value="off" ${draft.glow === "off" ? "selected" : ""}>Desligado</option>
          <option value="leve" ${draft.glow === "leve" ? "selected" : ""}>Leve (leve no processamento)</option>
          <option value="alto" ${draft.glow === "alto" ? "selected" : ""}>Alto (mais bonito, mais pesado)</option>
        </select>
      </label>
      <label class="style-row">
        <span>Rótulo (nome) dos nós</span>
        <select id="st-labels">
          <option value="sempre" ${(draft.labels ?? "sempre") === "sempre" ? "selected" : ""}>Sempre visível</option>
          <option value="auto" ${draft.labels === "auto" ? "selected" : ""}>Automático (some ao afastar o zoom)</option>
          <option value="nunca" ${draft.labels === "nunca" ? "selected" : ""}>Sempre oculto</option>
        </select>
      </label>
      <label class="style-row">
        <span>Gradiente nas bolinhas</span>
        <input type="checkbox" id="st-gradient" ${draft.gradient ? "checked" : ""}>
      </label>
      <label class="style-row">
        <span>Textura esférica nas bolinhas</span>
        <input type="checkbox" id="st-sphere-shading" ${draft.sphereShading ? "checked" : ""}>
      </label>
      <label class="style-row">
        <span>Céu estrelado no fundo</span>
        <input type="checkbox" id="st-starfield" ${draft.starfield ? "checked" : ""}>
      </label>
      <label class="style-row">
        <span>Tingir o fundo pelas tags</span>
        <input type="checkbox" id="st-tag-tint" ${draft.tagTint ? "checked" : ""}>
      </label>
      <p class="style-hint">Textura esférica: brilho e sombra por cima da bolinha, pra parecer uma esfera 3D em vez de um disco chapado. Tingir por tag: manchas escuras onde cada tag se concentra na face visível do globo.</p>
    </div>
    </div>
    <div class="style-actions">
      <button class="btn" id="st-reset">Restaurar padrão</button>
      <button class="btn style-primary" id="st-save">Salvar</button>
    </div>`;

  const preview = () => applyStyle(draft); // aplica ao vivo, sem salvar

  modalBody.querySelectorAll(".theme-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      Object.assign(draft, GRAPH_THEMES[btn.getAttribute("data-theme")]);
      preview();
      renderStylePanel(draft); // reflete o tema nos controles, sem perder o resto do rascunho
    });
  });
  modalBody.querySelectorAll("input[data-color]").forEach(inp => {
    inp.addEventListener("input", () => { draft.colors[inp.getAttribute("data-color")] = inp.value; preview(); });
  });
  modalBody.querySelector("#st-size-mode").addEventListener("change", (e) => { draft.sizeMode = e.target.value; preview(); });
  modalBody.querySelector("#st-edges").addEventListener("change", (e) => { draft.edgeVisibility = e.target.value; preview(); });
  modalBody.querySelector("#st-edge-opacity").addEventListener("input", (e) => { draft.edgeOpacity = +e.target.value; preview(); });
  modalBody.querySelector("#st-radius-base").addEventListener("input", (e) => { draft.radiusBase = +e.target.value; preview(); });
  modalBody.querySelector("#st-radius-scale").addEventListener("input", (e) => { draft.radiusScale = +e.target.value; preview(); });
  modalBody.querySelector("#st-label-size").addEventListener("input", (e) => { draft.labelSize = +e.target.value; preview(); });
  modalBody.querySelector("#st-autorotate").addEventListener("change", (e) => { draft.autoRotate = e.target.checked; preview(); });
  modalBody.querySelector("#st-rotate-speed").addEventListener("input", (e) => { draft.rotateSpeed = +e.target.value; preview(); });
  modalBody.querySelector("#st-back-fade").addEventListener("input", (e) => { draft.backFade = +e.target.value; preview(); });
  modalBody.querySelector("#st-glow").addEventListener("change", (e) => { draft.glow = e.target.value; preview(); });
  modalBody.querySelector("#st-labels").addEventListener("change", (e) => { draft.labels = e.target.value; preview(); });
  modalBody.querySelector("#st-gradient").addEventListener("change", (e) => { draft.gradient = e.target.checked; preview(); });
  modalBody.querySelector("#st-sphere-shading").addEventListener("change", (e) => { draft.sphereShading = e.target.checked; preview(); });
  modalBody.querySelector("#st-starfield").addEventListener("change", (e) => { draft.starfield = e.target.checked; preview(); });
  modalBody.querySelector("#st-tag-tint").addEventListener("change", (e) => { draft.tagTint = e.target.checked; preview(); });

  modalBody.querySelector("#st-save").addEventListener("click", () => {
    try { localStorage.setItem(STYLE_KEY, JSON.stringify(draft)); } catch {}
    styleModalOpen = false;
    modalOverlay.classList.remove("open");
  });
  modalBody.querySelector("#st-reset").addEventListener("click", () => {
    try { localStorage.removeItem(STYLE_KEY); } catch {}
    applyStyle(JSON.parse(JSON.stringify(defaultStyle)));
    renderStylePanel(); // redesenha o modal já com os controles no padrão
  });
}

document.getElementById("btn-style").addEventListener("click", () => {
  styleModalOpen = true;
  renderStylePanel();
  modalOverlay.classList.add("open");
});

// ---- Exportar PNG ----------------------------------------------------------
// O canvas já é a imagem inteira exatamente como está na tela — exportar é
// pedir um blob e disparar o download. "Supersampling": o buffer físico nasce
// EXPORT_SCALE× maior só na hora do export, draw() respeita `dpr` em tudo
// sem tocar numa linha, e o PNG final sai nítido com bastante zoom.
const EXPORT_SCALE = 3;

document.getElementById("btn-export-png").addEventListener("click", () => {
  const originalDpr = dpr;
  const originalCanvasWidth = canvas.width;
  const originalCanvasHeight = canvas.height;
  dpr = originalDpr * EXPORT_SCALE;
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  clearSpriteCache(); // sprites no dpr antigo ficariam borrados no buffer novo

  draw();

  canvas.toBlob((blob) => {
    // Restaura o buffer ANTES de qualquer outra coisa: o blob já leu os
    // pixels, e canvas gigante sobrando em memória é desperdício.
    dpr = originalDpr;
    canvas.width = originalCanvasWidth;
    canvas.height = originalCanvasHeight;
    clearSpriteCache();
    draw(); // repinta no dpr normal — sem isto ficaria em branco até o próximo evento

    if (!blob) return;
    const url = URL.createObjectURL(blob);
    const stamp = new Date().toISOString().slice(0, 10);
    const a = document.createElement("a");
    a.href = url;
    a.download = `grafo-esferico-second-brain-${stamp}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }, "image/png");
});

// ---- Exportar SVG (vetorial) ------------------------------------------------
// Mesma arquitetura do plano: drawSphereForSvgExport() redesenha contra o
// mock do canvas2svg (global C2S, carregado sob demanda da CDN), acumulando
// um grafo de cena que serializa como <svg>. Gradientes SAEM no export
// (<radialGradient> de verdade); o que fica fora é o shadowBlur do glow
// "alto" — "alto" e "leve" desenham o mesmo halo em gradiente aqui.
// Círculo fechado como dois semicírculos: startAngle===endAngle (depois do
// módulo 2π) é tratado como "nada a desenhar" pelo canvas2svg.
function unitCircle(c) {
  c.beginPath();
  c.arc(0, 0, 1, 0, Math.PI);
  c.arc(0, 0, 1, Math.PI, Math.PI * 2);
}

function svgNodesPass(c, svgStyle, front, grads, inViewFn) {
  data.nodes.forEach(n => {
    if (!isNodeVisible(n) || !inViewFn(n)) return;
    if ((n.sz > -0.12) !== front) return;
    const dim = nodeDimmed(n);
    const a = depthAlpha(n.sz) * (dim ? 0.08 : 1);
    if (a <= 0.02) return;
    const r = rScreenOf(n);
    const type = n.type;

    if (svgStyle.glow !== "off") {
      c.save();
      c.globalAlpha = a * 0.9;
      c.translate(n.sx, n.sy);
      c.scale(r * 2.4, r * 2.4);
      unitCircle(c);
      c.fillStyle = grads.halo[type] || "transparent";
      c.fill();
      c.restore();
    }

    c.save();
    c.globalAlpha = Math.min(1, a);
    c.translate(n.sx, n.sy);
    c.scale(r, r);
    unitCircle(c);
    c.fillStyle = svgStyle.gradient ? (grads.node[type] || typeColorRaw(n)) : typeColorRaw(n);
    c.fill();
    // lineWidth compensado pelo scale(r,r): devolve a espessura real de 1px.
    c.lineWidth = 1 / r;
    c.strokeStyle = "#0b1220";
    c.stroke();
    c.restore();
  });
  c.globalAlpha = 1;
}

function svgEdgePass(c, svgStyle, wantGrps, inViewFn) {
  c.lineWidth = 1.2;
  data.edges.forEach(e => {
    const s = endpoint(e.source), t = endpoint(e.target);
    if (!s || !t || !isNodeVisible(s) || !isNodeVisible(t)) return;
    if (!inViewFn(s) && !inViewFn(t)) return;
    const zf = Math.max(s.sz, t.sz), zb = Math.min(s.sz, t.sz);
    const grp = zb < -0.12 ? (zf > 0.12 ? "cross" : "back") : "front";
    if (!wantGrps.includes(grp)) return;
    const dim = edgeDimmed(e);
    let alpha = svgStyle.edgeOpacity;
    if (dim) alpha = 0.08;
    else if (grp === "cross") alpha *= 0.45;
    else if (grp === "back") alpha *= Math.max(0.12, svgStyle.backFade ?? 0.08);
    c.globalAlpha = Math.min(1, alpha);
    // setLineDash pode não existir no mock — checar antes evita estourar a
    // exportação inteira por causa de um detalhe cosmético.
    if (typeof c.setLineDash === "function") {
      c.setLineDash(e.kind === "reference" ? [3, 3] : []);
    }
    c.beginPath();
    c.moveTo(s.sx, s.sy);
    c.lineTo(t.sx, t.sy);
    c.stroke();
  });
  c.globalAlpha = 1;
}

function drawSphereForSvgExport(simple) {
  const svgStyle = simple ? Object.assign({}, styleConfig, { glow: "off", gradient: false }) : styleConfig;
  const c = new C2S(width, height); // px CSS — vetor não precisa de dpr/supersampling

  c.fillStyle = (svgStyle.colors && svgStyle.colors.background) || "#1b1e21";
  c.fillRect(0, 0, width, height);

  // Reprojeta com a rotação ATUAL: o último frame desenhado pode estar um
  // gesto atrás (ver comentário do export PNG no grafo plano).
  projectAll();

  if (svgStyle.starfield) {
    for (let i = 0; i < STAR_BUCKETS; i++) {
      const bucket = starBucketLists[i];
      if (!bucket.length) continue;
      c.beginPath();
      for (let j = 0; j < bucket.length; j++) {
        const s = bucket[j];
        const x = s.fx * width, y = s.fy * height;
        c.moveTo(x + s.r, y);
        c.arc(x, y, s.r, 0, Math.PI * 2);
      }
      c.fillStyle = `rgba(255,255,255,${starBucketOpacity[i]})`;
      c.fill();
    }
  }

  c.beginPath();
  c.arc(width / 2, height / 2, viewRadius(), 0, Math.PI * 2);
  c.lineWidth = 1;
  c.strokeStyle = hexToRgba((svgStyle.colors && svgStyle.colors.edge) || "#858b93", 0.16);
  c.stroke();

  // Gradientes construídos uma vez no espaço unitário, reaproveitados por
  // tipo via translate/scale por nó (mesma técnica de buildGradients()).
  const grads = { node: {}, halo: {} };
  if (svgStyle.gradient || svgStyle.glow !== "off") {
    Object.keys(svgStyle.colors || {}).forEach(type => {
      if (type === "background" || type === "edge") return;
      const color = svgStyle.colors[type] || "#888";
      if (svgStyle.gradient) {
        const g = c.createRadialGradient(-0.3, -0.35, 0, 0, 0, 1);
        g.addColorStop(0, mixWhite(color, 0.55));
        g.addColorStop(1, color);
        grads.node[type] = g;
      }
      if (svgStyle.glow !== "off") {
        const h = c.createRadialGradient(0, 0, 0, 0, 0, 1);
        h.addColorStop(0, hexToRgba(color, 0.5));
        h.addColorStop(1, hexToRgba(color, 0));
        grads.halo[type] = h;
      }
    });
  }

  const pad = 80;
  const inViewFn = (n) => n.sx >= -pad && n.sx <= width + pad && n.sy >= -pad && n.sy <= height + pad;

  // Mesma ordem do pintor da tela.
  svgEdgePass(c, svgStyle, ["back"], inViewFn);
  svgNodesPass(c, svgStyle, false, grads, inViewFn);
  svgEdgePass(c, svgStyle, ["cross", "front"], inViewFn);
  svgNodesPass(c, svgStyle, true, grads, inViewFn);

  if (labelsShown) {
    c.font = `${svgStyle.labelSize}px -apple-system, "Segoe UI", Helvetica, Arial, sans-serif`;
    c.textAlign = "center";
    c.fillStyle = getLabelColor();
    data.nodes.forEach(n => {
      if (n.type === "reference" || !isNodeVisible(n) || n.sz < 0.05 || !inViewFn(n)) return;
      c.globalAlpha = (nodeDimmed(n) ? 0.08 : 0.85) * Math.min(1, depthAlpha(n.sz));
      c.fillText(n.title, n.sx, n.sy - (2 + rScreenOf(n)));
    });
    c.globalAlpha = 1;
  }

  let svgString = c.getSerializedSvg(true); // entidades nomeadas -> numéricas (SVG standalone)

  // Dedupe de atributos na tag <svg>: o serializer do canvas2svg sai com
  // xmlns:xlink DUPLICADO; atributo repetido viola XML e parsers enxutos
  // (ex.: visualizador do Xplore) rejeitam o arquivo inteiro.
  svgString = svgString.replace(/<svg([^>]*)>/, (match, attrs) => {
    const seen = new Set();
    const dedupedAttrs = attrs.replace(/\\s+([a-zA-Z_:][-a-zA-Z0-9_:.]*)="[^"]*"/g, (attrMatch, name) => {
      if (seen.has(name)) return "";
      seen.add(name);
      return attrMatch;
    });
    return `<svg${dedupedAttrs} viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" style="width:100%;height:100%">`;
  });

  // Notação científica residual (erros de 1e-16 de IEEE 754 nos arcos) é
  // válida em SVG mas derruba parsers simples — arredonda pra 6 casas.
  svgString = svgString.replace(/-?\\d*\\.?\\d+e[+-]\\d+/gi, (numStr) => {
    const rounded = Number(numStr).toFixed(6).replace(/\\.?0+$/, "");
    return rounded === "" || rounded === "-" ? "0" : rounded;
  });

  // Prólogo XML + encoding explícito: títulos em português têm acentos gravados
  // como UTF-8 cru; parser legado que caia pro charset da plataforma corrompe.
  svgString = '<?xml version="1.0" encoding="UTF-8"?>\\n' + svgString;

  // Raios de <radialGradient> com sufixo "px" são <length> válido, mas parsers
  // enxutos preferem número puro — userSpaceOnUse não muda nada sem unidade.
  svgString = svgString.replace(/([a-zA-Z]+)="(-?[\\d.]+)px"/g, '$1="$2"');
  // paint-order é SVG2; a ordem default já é a seguida pela lib.
  svgString = svgString.replace(/ paint-order="[^"]*"/g, "");

  return svgString;
}

function exportSvgFile(simple) {
  const svgString = drawSphereForSvgExport(simple);
  const blob = new Blob([svgString], { type: "image/svg+xml" });
  const url = URL.createObjectURL(blob);
  const stamp = new Date().toISOString().slice(0, 10);
  const a = document.createElement("a");
  a.href = url;
  a.download = `grafo-esferico-second-brain-${stamp}${simple ? "-simples" : ""}.svg`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const exportSvgBtn = document.getElementById("btn-export-svg");
const exportSvgPopover = document.getElementById("export-svg-popover");

function closeExportSvgPopover() { exportSvgPopover.classList.remove("open"); }

function openExportSvgPopover() {
  // Ancorado no botão, clamped na viewport — nunca sai da tela no painel
  // estreito do mobile.
  exportSvgPopover.classList.add("open");
  const btnRect = exportSvgBtn.getBoundingClientRect();
  const popRect = exportSvgPopover.getBoundingClientRect();
  let left = btnRect.left;
  left = Math.min(left, window.innerWidth - popRect.width - 10);
  left = Math.max(left, 10);
  let top = btnRect.bottom + 8;
  if (top + popRect.height > window.innerHeight - 10) {
    top = btnRect.top - popRect.height - 8;
  }
  exportSvgPopover.style.left = `${left}px`;
  exportSvgPopover.style.top = `${top}px`;
}

exportSvgBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  if (exportSvgPopover.classList.contains("open")) { closeExportSvgPopover(); return; }
  openExportSvgPopover();
});
// canvas2svg (~50 KB) só existe para o export vetorial: carrega sob demanda.
// Único recurso dependente de rede — o resto funciona offline.
let c2sPromise = null;
function ensureC2S() {
  if (window.C2S) return Promise.resolve();
  if (!c2sPromise) {
    c2sPromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/canvas2svg@1.0.16/canvas2svg.min.js";
      s.onload = () => resolve();
      s.onerror = () => { c2sPromise = null; reject(new Error("sem rede para carregar o canvas2svg")); };
      document.head.appendChild(s);
    });
  }
  return c2sPromise;
}
document.getElementById("btn-export-svg-completo").addEventListener("click", () => { closeExportSvgPopover(); ensureC2S().then(() => exportSvgFile(false)).catch(err => alert("Exportar SVG requer conexão: " + err.message)); });
document.getElementById("btn-export-svg-simples").addEventListener("click", () => { closeExportSvgPopover(); ensureC2S().then(() => exportSvgFile(true)).catch(err => alert("Exportar SVG requer conexão: " + err.message)); });
document.addEventListener("click", (e) => {
  if (exportSvgPopover.classList.contains("open") && !exportSvgPopover.contains(e.target)) closeExportSvgPopover();
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeExportSvgPopover(); });

// Fechar o modal de Estilo sem clicar "Salvar" descarta o rascunho e volta
// ao estilo realmente salvo — sem isto, preview cancelado ficaria grudado.
// Só quando era o modal de Estilo: fechar Índice/Gaps não redesenha à toa.
function revertUnsavedStylePreview() {
  if (!styleModalOpen) return;
  applyStyle(mergeWithDefaults(loadSavedStyle()));
}
document.getElementById("modal-close").addEventListener("click", revertUnsavedStylePreview);
modalOverlay.addEventListener("click", (e) => { if (e.target === modalOverlay) revertUnsavedStylePreview(); });

// ---- Endurecimento para iPhone/Safari --------------------------------------
// Safari tem pinça PRÓPRIA de página (`gesturestart` etc.) que compete com
// os gestos do globo; neutralizar os três eventos é rede de segurança pra
// versões de iOS que disparam mesmo com touch-action: none.
["gesturestart", "gesturechange", "gestureend"].forEach(evt => {
  document.addEventListener(evt, (e) => e.preventDefault());
});

// Safari esconde/mostra a barra de endereço sem sempre disparar `resize` —
// o evento confiável é o do visualViewport.
if (window.visualViewport) {
  window.visualViewport.addEventListener("resize", ajustarViewport);
}

// ---- Init -------------------------------------------------------------------
applyStyle(styleConfig, { silent: true });
recomputeVisibleDegrees();
aimAtFocus();       // abre o globo mostrando o nó mais conectado da wiki
updateVisibility(); // graus visíveis + primeiro desenho agendado
scheduleDraw();
</script>
</body>
</html>
"""


def render_sphere_html(nodes, edges, tag_gaps, reader_payload):
    graph_b64 = _deflate_b64(_json_for_script_tag(
        {
            "nodes": nodes,
            "edges": edges,
            "tag_gaps": tag_gaps,
            "defaultStyle": SPHERE_STYLE,
            "defaultStyleMobileOverrides": SPHERE_STYLE_MOBILE_OVERRIDES,
        }
    ))
    reader_b64 = ""
    if reader_payload.get("essays"):
        reader_b64 = _deflate_b64(_json_for_script_tag(reader_payload))

    pako_src = PAKO_VENDORED.read_text(encoding="utf-8")
    # Injeção é como <script> inline: '</script' dentro do vendor fecharia a
    # tag no meio do arquivo.
    if "</script" in pako_src.lower():
        raise RuntimeError("vendor pako contém '</script' — não pode ir inline")

    html = SPHERE_HTML_TEMPLATE
    html = html.replace("__GRAPH_B64__", graph_b64)
    html = html.replace("__READER_B64__", reader_b64)
    html = html.replace("__PAKO__", pako_src)
    return html


def main():
    parser = argparse.ArgumentParser(
        description="Gera o grafo ESFÉRICO da wiki. Por padrão gera as DUAS "
                    "variantes (MySecondBrain_sphere.html leve + "
                    "MySecondBrain_sphere.reader.html com essays embutidos); "
                    "--reader gera só a completa e --no-reader só a leve.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--reader", dest="reader", action="store_true", default=None,
                       help="gera só a versão completa (essays embutidos em "
                            f"{READER_HTML_NAME})")
    group.add_argument("--no-reader", dest="reader", action="store_false",
                       help=f"gera só a versão leve (globo + link .md em {OUTPUT_HTML_NAME})")
    args = parser.parse_args()
    embed = args.reader  # True (só completa) | False (só leve) | None (default → ambas)

    nodes, edges, isolated = build_graph()
    tag_gaps = compute_tag_gaps(nodes, edges)

    layout_start = time.perf_counter()
    min_sep_deg = compute_sphere_layout(nodes, edges)
    layout_ms = (time.perf_counter() - layout_start) * 1000

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Variantes a gerar: por padrão (None) as duas; os flags restringem a uma.
    want_light = (embed is not True)
    want_reader = (embed is not False)

    # Payload do leitor é caro (renderiza todos os essays) — calcula só se for usar.
    reader_payload = None
    if want_reader:
        frag_start = time.perf_counter()
        essay_nodes = [n for n in nodes if n["type"] == "essay"]
        print(f"Leitor embutido: renderizando {len(essay_nodes)} essays…")
        essays = render_reader_fragments(essay_nodes)
        mathjax = ensure_mathjax() or ""
        font_css = _reader_font_css()
        base_css = _template_base_css()
        reader_css = _scope_css_for_shadow(base_css + "\n" + font_css)
        reader_payload = {"essays": essays, "mathjax": mathjax, "css": reader_css}
        print(f"  leitor pronto em {(time.perf_counter()-frag_start):.0f}s "
              f"({len(essays)} fragmentos, mathjax={'sim' if mathjax else 'não'}, "
              f"css={len(reader_css)//1024} KB)")

    (OUTPUT_DIR / "sphere.json").write_text(
        json.dumps({"nodes": nodes, "edges": edges, "tag_gaps": tag_gaps, "isolated": isolated},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "sphere.md").write_text(
        f"# Grafo Esférico da Wiki\n\n{len(nodes)} páginas, {len(edges)} conexões.\n\n"
        + render_mermaid(nodes, edges) + "\n",
        encoding="utf-8",
    )

    def _escreve(filename, payload):
        p = OUTPUT_DIR / filename
        p.write_text(render_sphere_html(nodes, edges, tag_gaps, payload), encoding="utf-8")
        return p.stat().st_size / (1024 * 1024)

    vazio = {"essays": {}, "mathjax": "", "css": ""}
    gerados = []
    if want_light:
        gerados.append(("leve", OUTPUT_HTML_NAME, _escreve(OUTPUT_HTML_NAME, vazio)))
    if want_reader:
        gerados.append(("completa", READER_HTML_NAME, _escreve(READER_HTML_NAME, reader_payload)))

    print(f"Globo gerado: {len(nodes)} nós, {len(edges)} conexões.")
    sep_txt = f"{min_sep_deg:.2f}°" if min_sep_deg is not None else "n/a"
    print(f"  layout esférico em {layout_ms:.0f}ms (separação mínima entre nós: {sep_txt})")
    for nome, fname, mb in gerados:
        print(f"  {fname} ({nome}, {mb:.1f} MB)")
    print(f"  {OUTPUT_DIR / 'sphere.md'} (mermaid)")
    print(f"  {OUTPUT_DIR / 'sphere.json'} (dados)")
    if isolated:
        print(f"\n⚠ {len(isolated)} página(s) sem nenhuma conexão:")
        for title in isolated:
            print(f"  - {title}")
    if tag_gaps:
        print(f"\n⚠ {len(tag_gaps)} par(es) de tags que nunca se conectam (ver painel de Gaps no HTML):")
        for a, b in tag_gaps:
            print(f"  - {a} / {b}")


if __name__ == "__main__":
    main()
