#!/usr/bin/env python3
"""
build_graph.py - Grafo PLANO canônico da wiki: nós e conexões em 2D
(força-dirigida), HTML interativo com índice, gaps, painel de estilo e
leitor de essays embutido.

Lê:
    wiki/essays|concepts|entities|insights/*.md   títulos, wikilinks, frontmatter
    wiki/references.json                          referências citadas por essay

Gera (em output/graph/):
    MySecondBrain.html            grafo interativo — versão LEVE (grafo + link .md), arquivo canônico
    MySecondBrain.reader.html     versão COMPLETA com os essays embutidos (leitura premium offline, ~6 MB)
    graph.md                      fallback Mermaid
    graph.json                    nós/arestas/tag_gaps/isolated (lido por /organize)
    graph.html                    redirect para MySecondBrain.html

Uso:
    python scripts/build_graph.py               # default: gera AS DUAS variantes (leve + reader)
    python scripts/build_graph.py --reader      # gera só a completa (essays embutidos)
    python scripts/build_graph.py --no-reader   # gera só a leve (grafo + link .md)

Flags:
    --reader | --no-reader   gerar apenas uma das variantes. Sem flag, o
                             script gera as duas, cada uma com nome próprio:
                             leve → MySecondBrain.html; completa → MySecondBrain.reader.html

Variante esférica: scripts/build_sphere.py (importa deste arquivo).
"""

import argparse
import base64
import json
import math
import random
import re
import subprocess
import tempfile
import time
import urllib.request
import zlib
from collections import defaultdict
from pathlib import Path

import console_encoding  # noqa: F401  (UTF-8 no console; ver o módulo)
import visibility
import yaml
from repo_paths import CODE_ROOT, DATA_ROOT, GRAPH_DIR, WIKI_ROOT
from site_common import title_plain

ROOT_DIR = CODE_ROOT
ESSAYS_DIR = WIKI_ROOT / "essays"
CONCEPTS_DIR = WIKI_ROOT / "concepts"
ENTITIES_DIR = WIKI_ROOT / "entities"
INSIGHTS_DIR = WIKI_ROOT / "insights"
REFERENCES_JSON_PATH = WIKI_ROOT / "references.json"
OUTPUT_DIR = GRAPH_DIR

# Arquivo único compartilhável: grafo + leitor de essays com o MESMO
# template do export HTML. Sem flags, o script gera AS DUAS variantes, cada
# uma com nome próprio:
#   leve (grafo + link .md)  → OUTPUT_HTML_NAME   (arquivo canônico)
#   completa (essays embutidos) → READER_HTML_NAME
# graph.json/graph.md mantêm os nomes canônicos — outras ferramentas
# (/organize, gaps) leem o JSON e não sabem deste nome aqui.
OUTPUT_HTML_NAME = "MySecondBrain.html"
# Versão completa com os essays renderizados embutidos (leitura premium
# offline, ~5,5 MB). Sem flags o script gera esta E a leve.
READER_HTML_NAME = "MySecondBrain.reader.html"

# >>> DEFAULT DO BUILD <<<
# Sem flag de linha de comando, o script gera AS DUAS variantes:
#   leve (grafo + botão apontando para o .md local)         → MySecondBrain.html
#   completa (essays renderizados embutidos, ~5,5 MB)       → MySecondBrain.reader.html
# --reader gera só a completa; --no-reader gera só a leve.
DEFAULT_MODE = "both"  # "both" | "reader" | "no-reader"

# Legado: valor do antigo default quando só existia uma variante. Mantida
# por compatibilidade do import em build_sphere.py e de mensagens que a
# referenciam — já não é usada como default do argparse.
DEFAULT_EMBED_READER = False

# Preenchimento 360° do grafo PLANO (centra a nuvem no centróide e estica a
# bounding box até as bordas do canvas). DESLIGADO por padrão — ligue apenas
# sob pedido explícito do Usuário.
ENABLE_FILL_360 = False

MATHJAX_URL = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg-full.js"
MATHJAX_CACHE = OUTPUT_DIR / "_mathjax_cache.js"

# JS vendorado (scripts/vendor/, versionado no git): builds e visualização
# funcionam 100% offline — nada de CDN no caminho crítico do grafo.
VENDOR_DIR = Path(__file__).resolve().parent / "vendor"
D3_VENDORED = VENDOR_DIR / "d3.v7.min.js"
PAKO_VENDORED = VENDOR_DIR / "pako.min.js"

# Payloads (grafo, leitor) vão comprimidos (deflate-raw + base64) em tags
# <script type="application/json">: o navegador NÃO parseia nada até o
# bootstrap pedir — primeira pintura não espera os MB de dados. Pako embutido
# infla de forma síncrona, sem reestruturar o script principal.
def _deflate_b64(text):
    """Comprime o texto em deflate cru e devolve em base64, para embutir no HTML."""
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    data = comp.compress(text.encode("utf-8")) + comp.flush()
    return base64.b64encode(data).decode("ascii")


def _json_for_script_tag(obj):
    """Serializa para dentro de <script type="application/json">. O escape
    \\u002f é válido em JSON e impede que um '</script' vindo de conteúdo
    feche a tag cedo."""
    s = json.dumps(obj, ensure_ascii=False)
    return s.replace("</", "<\\u002f")

DIRS = {
    "essay": ESSAYS_DIR,
    "concept": CONCEPTS_DIR,
    "entity": ENTITIES_DIR,
    "insights": INSIGHTS_DIR,
}

# Aparência padrão do grafo. Editável aqui para um novo padrão permanente
# (todo mundo que abrir o HTML do zero recebe estas cores/tamanhos), ou
# ajustável ao vivo no navegador via o modal "Estilo" — nesse caso a escolha
# fica salva em localStorage e sobrescreve este padrão só naquele navegador.
GRAPH_STYLE = {
    "colors": {
        "essay": "#4fa8ff",
        "concept": "#5fd3c4",
        "entity": "#e8b657",
        "insights": "#b48ce8",
        "reference": "#8a8f96",
        # Puxada para o branco (mais clara que cinza médio) — dá uma sensação
        # de "fio de luz" sutil entre os nós, visível no toque sem chamar
        # atenção pra si.
        "edge": "#858b93",
        "background": "#1b1e21",
    },
    "edgeOpacity": 0.28,
    # "sempre" (arestas sempre na opacidade cheia de `edgeOpacity`, mesmo
    # durante o destaque de um nó selecionado — nada nunca esmaece) | "auto"
    # (comportamento clássico: opacidade normal em repouso, mas esmaece as
    # arestas irrelevantes ao selecionar um nó ou buscar) | "off" (arestas
    # completamente ocultas). "auto" é o padrão — ao selecionar um nó, só as
    # arestas que tocam ele continuam visíveis; o resto esmaece para não virar
    # ruído visual num grafo com milhares de conexões.
    "edgeVisibility": "auto",
    "radiusBase": 5,
    "radiusScale": 3,
    "labelSize": 10,
    # "off" | "leve" (halo sem blur, barato) | "alto" (drop-shadow com blur,
    # mais bonito porém pesado em SVG — cada nó vira uma rasterização à
    # parte; em grafos grandes ou no Chrome mobile isso é o maior vilão de
    # FPS que existe aqui). "leve" é o padrão por ser barato E ainda dar
    # uma sensação de brilho.
    "glow": "leve",
    # "sempre" (rótulo sempre visível) | "auto" (esconde ao afastar o zoom
    # se o tier de desempenho pedir) | "nunca" (rótulo sempre oculto).
    # No automático, os rótulos aparecem apenas quando o zoom já os torna
    # legíveis. "sempre" e "nunca" continuam escolhas explícitas no painel.
    "labels": "auto",
    "starfield": True,
    "gradient": True,
    # Camada extra de luz especular + sombra de contato por cima do
    # preenchimento normal da bolinha, dando volume de esfera 3D (tipo bola
    # de vidro/plástico) em vez do disco chapado ou do gradiente simples de
    # `gradient`. Mais caro que os dois (mais um par de gradientes por
    # sprite, uma vez só — cacheado igual ao resto), então fica desligado
    # por padrão; quem quiser o efeito ativa no painel de Estilo.
    "sphereShading": False,
    # "Tingimento" do fundo por tag: pinta uma mancha bem escura (quase a
    # cor de fundo, só com um matiz sutil) em torno do centro de massa de
    # cada tag, do tamanho da dispersão dos nós que a carregam — dá pra
    # perceber "regiões temáticas" no grafo sem que a cor chame mais atenção
    # que os próprios nós/arestas. Desligado por padrão (custo extra por
    # frame e é só decorativo); ver drawTagTint() no HTML gerado.
    "tagTint": False,
    # "degree" (nº de conexões visíveis), "bytes" ou "lines" (tamanho do
    # corpo do arquivo). Só afeta essay/concept/entity/insights — reference
    # não tem arquivo e sempre usa o raio base.
    "sizeMode": "degree",
    # Multiplicador de distância entre bolinhas (colisão + arestas + carga).
    # 1 = padrão; acima disso, o grafo "respira" mais quando fica denso
    # demais pra ler.
    "spacing": 1.8,
    # Multiplicador da força elástica das arestas (d3 forceLink.strength).
    # 1 = padrão (a heurística de grau já embutida na fórmula, ver
    # applyForces() no HTML gerado); acima disso as conexões puxam os nós
    # com mais força, deixando o grafo mais "rígido" e compacto; abaixo,
    # mais "solto", com arestas mais folgadas.
    "linkStrength": 3.5,
    # Multiplicador da força de repulsão entre nós (d3 forceManyBody).
    # 1 = padrão; acima disso os nós se afastam mais uns dos outros.
    # Complementa `spacing` (que mexe em distância/colisão/arestas juntos):
    # este controla só a repulsão, isolado.
    "chargeStrength": 2.5,
    # Atrito da simulação (d3 forceSimulation.velocityDecay). Quanto maior,
    # mais rápido os nós perdem velocidade e assentam; quanto menor, mais
    # eles carregam momento entre ticks e podem oscilar antes de parar.
    # 0.5 é o padrão atual (ver comentário junto de `.velocityDecay` no
    # HTML gerado) — reduzido de 0.55 pra deixar as bolinhas um pouco mais
    # nervosas/flutuantes por padrão, sem exagerar (um degrau do slider).
    "friction": 0.70,
    # Elasticidade de retorno: puxa cada nó de volta pra sua posição no
    # layout calculado (n.x0/n.y0, ver compute_layout() no Python) sempre
    # que ele se afasta dali — na prática, é o que faz uma bolinha arrastada
    # voltar pra onde ela "mora" ao ser solta, em vez de simplesmente
    # assentar onde as forças de link/carga a deixarem depois do arrasto
    # (que raramente é o mesmo lugar: link/carga só resolvem a forma
    # relativa entre vizinhos, não têm noção de posição absoluta nenhuma).
    # É um d3.forceX/forceY por trás (ver applyForces() no HTML gerado), com
    # este valor como strength — 0 desliga completamente (nó fica onde for
    # solto, comportamento de antes desta opção existir); valores de
    # forceX/Y acima de ~0.6 já ficam bem rígidos (quase trava o nó no
    # lugar), por isso o slider vai só até ali.
    "homeStrength": 0.25,
    # "alta" | "media" | "baixa" — ver PERFORMANCE_TIERS no HTML
    # gerado. "alta" é o padrão tanto no Desktop quanto no Mobile.
    "performance": "alta",
    # Força de colisão do d3 (evita nós sobrepostos). Ligada por padrão —
    # pedido explícito do Usuário — mas o usuário pode desligar no painel de
    # Estilo em aparelhos fracos: é uma das forças mais caras por tick em
    # grafos com centenas/milhares de nós.
    "collision": True,
}

# Aplicado por cima de GRAPH_STYLE no navegador, só quando o próprio
# navegador se identifica como celular/tablet (toque ou tela pequena) — e só
# se o usuário nunca salvou uma preferência própria naquele aparelho. Glow e
# céu estrelado são os itens puramente decorativos mais caros de render;
# desligá-los por padrão no celular evita que a maioria dos usuários mobile
# precise descobrir o painel de Estilo só pra destravar performance.
GRAPH_STYLE_MOBILE_OVERRIDES = {
    # "on" não é um valor válido (as opções são "off"/"leve"/"alto" — ver
    # <select id="st-glow"> no HTML gerado); ficava sem corresponder a
    # nenhuma delas, então o halo nunca desenhava na tela mesmo assim.
    # Trocado para "leve", a opção decorativa mais barata, já que a intenção
    # aqui parece ter sido ligar glow no celular em vez de desligar.
    "glow": "leve",
    "starfield": False,
    # Física um passo mais calma no celular. A tela é pequena e o dedo é um
    # ponteiro grosso: o mesmo grafo que no desktop assenta rápido, aqui fica
    # escorregando debaixo do toque. Mais atrito e menos força fazem a malha
    # parar antes e mexer menos quando o leitor arrasta.
    #
    # Os três são o valor de GRAPH_STYLE acima, deslocado 10%:
    #   atrito     0.70 → 0.77   (mais alto = perde velocidade mais rápido)
    #   elástica   3.5  → 3.15   (arestas puxam menos)
    #   repulsão   2.5  → 2.25   (nós se empurram menos)
    "friction": 0.77,
    "linkStrength": 3.15,
    "chargeStrength": 2.25,
}


def load(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def get_h1(content):
    m = re.search(r"(?m)^# (.+)", content)
    return m.group(1).strip() if m else None


def get_frontmatter(content):
    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        return {}
    try:
        return yaml.safe_load(m.group(1)) or {}
    except Exception:
        return {}


def strip_frontmatter(content):
    return re.sub(r"^---\n.*?\n---\n?", "", content, count=1, flags=re.DOTALL)


def strip_fences(body):
    """Remove blocos de código cercados, para wikilink de exemplo em documentação
    não virar aresta.
    """
    return re.sub(r"```.*?```", "", body, flags=re.DOTALL)


def load_references():
    """Lê wiki/references.json; devolve lista vazia se o arquivo faltar ou não
    for JSON válido — o grafo é gerado sem as referências, não falha.
    """
    if not REFERENCES_JSON_PATH.exists():
        return []
    try:
        data = json.loads(REFERENCES_JSON_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data.get("references", [])


def build_graph():
    nodes = {}          # id -> node dict
    title_to_id = {}     # H1 title -> node id
    bodies = {}          # id -> body text (for edge extraction)
    slug_to_id = {}       # essay slug (filename stem) -> node id

    hidden_ids = set()
    for node_type, dir_path in DIRS.items():
        if not dir_path.exists():
            continue
        for file in sorted(dir_path.glob("*.md")):
            if file.name == ".gitkeep":
                continue
            content = load(file)
            title = get_h1(content)
            if not title:
                continue
            # Um rótulo do mapa é texto puro desenhado no canvas: a ênfase
            # inline do título viraria "_Teetering_" literal em cima do nó.
            title = title_plain(title)
            fm = get_frontmatter(content)
            node_id = f"{node_type}:{file.stem}"
            subtype = None
            if node_type == "insights":
                subtype = f"maturidade:{fm.get('maturidade', 'desconhecida')}"
            nodes[node_id] = {
                "id": node_id,
                "title": title,
                "type": node_type,
                "subtype": subtype,
                "maturidade": fm.get("maturidade") if node_type == "insights" else None,
                "tags": fm.get("tags", []) if isinstance(fm.get("tags"), list) else [],
                # Resumo de uma linha (campo `summary:` do frontmatter, já
                # validado/obrigatório pelo check_wiki.py em toda a wiki — ver
                # SUMMARY_MAX_CHARS lá). Usado no modal de Índice para um
                # resumo expansível por essay, sem precisar reabrir o arquivo.
                "summary": str(fm.get("summary") or "").strip(),
                # POSIX sempre: `file` vira href no HTML (`../../` + file) e no
                # Windows `relative_to` devolve `wiki\essays\x.md`, montando
                # `../../wiki\essays\x.md`. Funciona no file:// do Windows e
                # em mais nenhum lugar.
                "file": file.relative_to(DATA_ROOT).as_posix(),
                # HTML exportado do essay, quando existe. Resolvido no BUILD e
                # não no navegador: sem isso o modo leve teria de adivinhar se
                # `/html` já rodou, e quem nunca rodou ganharia link quebrado.
                # Caminho relativo a output/graph/, onde o arquivo é gravado.
                "htmlFile": (
                    f"../html/{file.stem}.html"
                    if node_type == "essay"
                    and (OUTPUT_DIR.parent / "html" / f"{file.stem}.html").exists()
                    else None
                ),
                # Rascunho vs. finalizado: o `status:` do frontmatter só era
                # lido pelo build_index e morria ali. O grafo usa para marcar
                # draft no painel Índice e na capa do leitor.
                "status": str(fm.get("status") or "").strip().lower() or None,
                "url": None,
                "degree": 0,
            }
            # `visibility: hidden` tira a página do grafo inteiro — build da
            # wiki e projeção pública. O nó não é descartado AQUI, e sim depois
            # de as arestas existirem: `prune_hidden` precisa saber o que ele
            # sustentava para levar junto o que só existia por causa dele.
            if visibility.is_hidden(fm):
                hidden_ids.add(node_id)
            title_to_id[title] = node_id
            # O slug do arquivo também indexa o nó. A forma canônica de wikilink
            # na wiki é `[[slug|Título]]`, porque é a única que o Obsidian
            # resolve, então o alvo que aparece no texto é o SLUG. Indexar só
            # pelo H1 derrubava o grafo de ~2500 para ~780 arestas, e nós sem
            # aresta somem da tela.
            title_to_id.setdefault(file.stem, node_id)
            body_text = strip_fences(strip_frontmatter(content))
            bodies[node_id] = body_text
            # Tamanho do essay como proxy de "densidade" — alternativa ao grau
            # como métrica de raio da bolinha no grafo (ver GRAPH_STYLE/sizeMode
            # e o painel "Estilo" no HTML: nem todo nó denso é bem conectado
            # ainda, e vice-versa; o usuário escolhe qual conta mais para ele).
            nodes[node_id]["sizeBytes"] = len(body_text.encode("utf-8"))
            nodes[node_id]["sizeLines"] = len([ln for ln in body_text.splitlines() if ln.strip()])
            if node_type == "essay":
                slug_to_id[file.stem] = node_id

    edges = []
    seen_pairs = set()
    for node_id, body in bodies.items():
        links = re.findall(r"\[\[([^\]]+)\]\]", body)
        for raw in links:
            target_title = raw.split("|")[0].strip()
            if target_title.startswith("#"):
                continue
            target_id = title_to_id.get(target_title)
            if not target_id or target_id == node_id:
                continue
            pair = tuple(sorted((node_id, target_id)))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            edges.append({"source": node_id, "target": target_id, "kind": "wikilink"})
            nodes[node_id]["degree"] += 1
            nodes[target_id]["degree"] += 1

    # Nós de referência (a partir de wiki/references.json) + arestas essay -> referência
    for i, ref in enumerate(load_references()):
        ref_id = f"reference:{i}"
        domain_group = ref.get("domain_group", "institucional")
        nodes[ref_id] = {
            "id": ref_id,
            "title": ref.get("citation_aiaa", ref_id),
            "type": "reference",
            "subtype": f"domain_group:{domain_group}",
            "tags": [],
            "file": None,
            "url": ref.get("url"),
            "degree": 0,
            "sizeBytes": 0,
            "sizeLines": 0,
        }
        for slug in ref.get("cited_by", []):
            essay_id = slug_to_id.get(slug)
            if not essay_id:
                continue
            edges.append({"source": essay_id, "target": ref_id, "kind": "reference"})
            nodes[essay_id]["degree"] += 1
            nodes[ref_id]["degree"] += 1

    nodes, edges = prune_hidden(nodes, edges, hidden_ids)

    isolated = [n["title"] for n in nodes.values() if n["degree"] == 0]
    return list(nodes.values()), edges, isolated


def prune_hidden(nodes, edges, hidden_ids):
    """Remove as páginas ocultas e o que só existia para sustentá-las.

    Esconder um essay não pode deixar para trás o concept, a entity ou a
    referência que só ele citava: o nó ficaria na tela sem nada que o
    sustente, denunciando por omissão que existe algo ali. A regra é a que o
    Usuário pediu — conexão exclusiva do essay oculto some junto; conexão que
    outro essay também alcança permanece.

    O critério é ALCANCE, não grau. Um concept citado só pelo essay oculto
    costuma ter arestas próprias (para uma referência, para outro concept), e
    contar grau o deixaria de pé com todo o rastro pendurado nele. O que
    decide é se ainda existe caminho até algum essay visível.

    Um nó que já não era alcançável por essay nenhum ANTES da poda é
    preservado: isso não é consequência de ocultar nada, é um buraco real da
    wiki, e `isolated` existe para denunciá-lo em vez de escondê-lo.
    """
    if not hidden_ids:
        return nodes, edges

    def alcancaveis(a_partir_de, proibidos):
        vizinhos = {}
        for e in edges:
            a, b = e["source"], e["target"]
            if a in proibidos or b in proibidos:
                continue
            vizinhos.setdefault(a, []).append(b)
            vizinhos.setdefault(b, []).append(a)
        vistos, fila = set(a_partir_de), list(a_partir_de)
        while fila:
            for viz in vizinhos.get(fila.pop(), ()):
                if viz not in vistos:
                    vistos.add(viz)
                    fila.append(viz)
        return vistos

    todos_essays = {nid for nid in nodes if nid.startswith("essay:")}
    sustentado_antes = alcancaveis(todos_essays, set())
    sustentado_depois = alcancaveis(todos_essays - hidden_ids, hidden_ids)

    removidos = set(hidden_ids) | {
        nid for nid in nodes
        if nid not in hidden_ids
        and nid in sustentado_antes          # era sustentado por algum essay
        and nid not in sustentado_depois     # e deixou de ser ao ocultar
    }

    nodes = {nid: n for nid, n in nodes.items() if nid not in removidos}
    edges = [e for e in edges if e["source"] in nodes and e["target"] in nodes]
    for n in nodes.values():
        n["degree"] = 0
    for e in edges:
        nodes[e["source"]]["degree"] += 1
        nodes[e["target"]]["degree"] += 1
    return nodes, edges


def compute_layout(nodes, edges, width=1600, height=1000, iterations=None, seed=42):
    """Layout força-dirigida (Fruchterman-Reingold simplificado), em Python
    puro, sem dependências novas.

    Por quê fazer isto no build em vez de deixar o navegador calcular: o
    d3.forceSimulation no cliente começa de posições aleatórias e precisa de
    ~300 ticks (cada um recalculando repulsão de todo par de nós) até
    "assentar" — e cada tick redesenha o SVG inteiro. Isso roda toda vez que
    alguém abre o HTML, inclusive no celular, onde é sensivelmente mais
    lento que no desktop. Pré-calcular aqui, uma vez, no build, e embutir
    x/y prontos no JSON faz o navegador abrir quase já assentado — o
    d3.forceSimulation no cliente só precisa de umas dezenas de ticks pra
    resolver sobreposição fina, não o layout inteiro do zero.

    O algoritmo é O(nós² × iterações) — aceitável em build time (roda uma
    vez quando o Usuário chama o script, não a cada carregamento de página).
    `iterations=None` escala automaticamente pelo tamanho do grafo (menos
    iterações em wikis grandes) pra manter o build na casa de segundos;
    passe um número explícito pra forçar mais precisão.
    """
    rng = random.Random(seed)
    n = len(nodes)
    if n == 0:
        return
    if n == 1:
        nodes[0]["x0"] = width / 2
        nodes[0]["y0"] = height / 2
        return

    if iterations is None:
        if n <= 300:
            iterations = 250
        elif n <= 800:
            iterations = 120
        else:
            iterations = 60

    area = width * height
    k = math.sqrt(area / n)  # distância "ideal" de equilíbrio entre nós

    pos = {node["id"]: [rng.uniform(0, width), rng.uniform(0, height)] for node in nodes}
    node_ids = [node["id"] for node in nodes]

    for it in range(iterations):
        temp = (1 - it / iterations) * (width / 10)  # esfria: passos grandes no início, finos no fim
        disp = {nid: [0.0, 0.0] for nid in node_ids}

        # Repulsão entre todos os pares — o termo O(n²) do algoritmo.
        for i in range(n):
            xi, yi = pos[node_ids[i]]
            for j in range(i + 1, n):
                xj, yj = pos[node_ids[j]]
                dx, dy = xi - xj, yi - yj
                dist = math.hypot(dx, dy) or 0.01
                force = (k * k) / dist
                fx, fy = (dx / dist) * force, (dy / dist) * force
                disp[node_ids[i]][0] += fx
                disp[node_ids[i]][1] += fy
                disp[node_ids[j]][0] -= fx
                disp[node_ids[j]][1] -= fy

        # Atração ao longo das arestas.
        for e in edges:
            a, b = e["source"], e["target"]
            if a not in pos or b not in pos:
                continue
            xa, ya = pos[a]
            xb, yb = pos[b]
            dx, dy = xa - xb, ya - yb
            dist = math.hypot(dx, dy) or 0.01
            force = (dist * dist) / k
            fx, fy = (dx / dist) * force, (dy / dist) * force
            disp[a][0] -= fx
            disp[a][1] -= fy
            disp[b][0] += fx
            disp[b][1] += fy

        for nid in node_ids:
            dx, dy = disp[nid]
            dist = math.hypot(dx, dy) or 0.01
            step = min(dist, temp)
            pos[nid][0] += (dx / dist) * step
            pos[nid][1] += (dy / dist) * step
            # Mantém dentro da área — evita que outliers fujam pro infinito
            # em grafos muito assimétricos (um nó com grau 1 isolado longe
            # do resto), o que faria o fit-to-screen do cliente zoom out
            # demais no primeiro carregamento.
            pos[nid][0] = min(width, max(0, pos[nid][0]))
            pos[nid][1] = min(height, max(0, pos[nid][1]))

    # Preenchimento 360° (ENABLE_FILL_360, desligado por padrão): centra a
    # nuvem no centróide e estica a bounding box para o canvas inteiro (com
    # margem de respiro). Sem isto, o FR deixa a nuvem assimétrica — densa
    # num quadrante, vazia no oposto — e o grafo abre ocupando "só uma parte"
    # da tela em vez de se distribuir nos 360°. A topologia do grafo é
    # preservada (é uma transformação afim de escala/translate, não um
    # re-layout).
    if ENABLE_FILL_360:
        xs = [pos[nid][0] for nid in node_ids]
        ys = [pos[nid][1] for nid in node_ids]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        span_x = max(max_x - min_x, 1e-6)
        span_y = max(max_y - min_y, 1e-6)
        fill_margin = 0.04  # 4% de respiro em cada borda
        sx = width * (1 - 2 * fill_margin) / span_x
        sy = height * (1 - 2 * fill_margin) / span_y
        for nid in node_ids:
            pos[nid][0] = width * fill_margin + (pos[nid][0] - min_x) * sx
            pos[nid][1] = height * fill_margin + (pos[nid][1] - min_y) * sy

    for node in nodes:
        x, y = pos[node["id"]]
        node["x0"] = round(x, 1)
        node["y0"] = round(y, 1)


def union_find_components(nodes, edges):
    """Union-find simples sobre ids de nó. Retorna dict id -> component_id."""
    parent = {n["id"]: n["id"] for n in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for e in edges:
        union(e["source"], e["target"])

    return {node_id: find(node_id) for node_id in parent}


def compute_tag_gaps(nodes, edges):
    """Pares de tags cujos essays nunca caem no mesmo componente conectado
    (nem transitivamente) — sinal de silo temático (ver plano de
    implementação, seção 3.4). Só considera nós com `tags` (essays hoje).
    """
    components = union_find_components(nodes, edges)
    tag_components = defaultdict(set)
    for n in nodes:
        for tag in n.get("tags") or []:
            tag_components[tag].add(components[n["id"]])

    tags = sorted(tag_components.keys())
    gaps = []
    for i in range(len(tags)):
        for j in range(i + 1, len(tags)):
            a, b = tags[i], tags[j]
            if tag_components[a].isdisjoint(tag_components[b]):
                gaps.append((a, b))
    return gaps


MERMAID_CLASS = {
    "essay": "essay",
    "concept": "concept",
    "entity": "entity",
    "insights": "insights",
    "reference": "reference",
}


def render_mermaid(nodes, edges):
    """Gera o fallback Mermaid do grafo, para quem abre o .md sem navegador."""
    lines = ["```mermaid", "graph TD"]
    for n in nodes:
        safe_id = n["id"].replace(":", "_").replace("-", "_").replace(".", "_").replace(" ", "_")
        label = n["title"].replace('"', "'")
        lines.append(f'    {safe_id}["{label}"]:::{MERMAID_CLASS[n["type"]]}')
    for e in edges:
        s = e["source"].replace(":", "_").replace("-", "_").replace(".", "_").replace(" ", "_")
        t = e["target"].replace(":", "_").replace("-", "_").replace(".", "_").replace(" ", "_")
        style = "-.-" if e.get("kind") == "reference" else "---"
        lines.append(f"    {s} {style} {t}")
    lines += [
        "    classDef essay fill:#4fa8ff,stroke:#1c3f66,color:#0b1220;",
        "    classDef concept fill:#5fd3c4,stroke:#1c4f47,color:#0b1220;",
        "    classDef entity fill:#e8b657,stroke:#6b4f16,color:#0b1220;",
        "    classDef insights fill:#b48ce8,stroke:#4a2f66,color:#0b1220;",
        "    classDef reference fill:#8a8f96,stroke:#3a3d40,color:#0b1220;",
        "```",
    ]
    return "\n".join(lines)


# ---- Leitor embutido (MySecondBrain) ------------------------------------

def ensure_mathjax():
    """Retorna o fonte do MathJax tex-svg-full (uma única cópia compartilhada
    por todos os essays no arquivo único). Cache local em output/graph/ —
    builds offline reutilizam; sem cache e sem rede, devolve None e o leitor
    mostra LaTeX cru (mesmo comportamento tolerado pelo export de HTML)."""
    if MATHJAX_CACHE.exists() and MATHJAX_CACHE.stat().st_size > 100_000:
        return MATHJAX_CACHE.read_text(encoding="utf-8", errors="replace")
    try:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(MATHJAX_URL, timeout=60) as resp:
            src = resp.read().decode("utf-8", errors="replace")
        MATHJAX_CACHE.write_text(src, encoding="utf-8")
        return src
    except Exception as e:  # noqa: BLE001 - qualquer falha de rede degrada
        print(f"  aviso: MathJax indisponível ({e}); fórmulas ficarão como LaTeX cru no leitor.")
        return None


_IMG_SRC_RE = re.compile(r'(<img\b[^>]*?\bsrc=")([^"]+)(")')
_MIME_BY_EXT = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp"}

# Compressão de imagens embutidas: o arquivo único circula por e-mail/WhatsApp
# e é re-parseado pelo navegador a cada abertura — plots originais de 300-600 KB
# viram dezenas de KB sem perda relevante em tela (qualidade/limiar rebaixados
# a pedido do Usuário: carregar leve > fidelidade de zoom).
_READER_IMG_MAX_WIDTH = 820
_READER_JPEG_QUALITY = 64

# Conjuntos de figuras que pesam desproporcionalmente no arquivo único levam
# tratamento mais agressivo. O essay de dinâmica de voo sozinho traz 60 plots,
# quase metade do payload do leitor; em tela eles continuam legíveis a 560 px,
# e quem precisa de zoom abre o PDF.
_READER_IMG_HEAVY_PREFIXES = ("dinlon-",)
_READER_IMG_HEAVY_MAX_WIDTH = 560
_READER_IMG_HEAVY_QUALITY = 52


def _reader_img_budget(nome):
    """Largura máxima e qualidade JPEG para a imagem, por nome de arquivo."""
    if nome.startswith(_READER_IMG_HEAVY_PREFIXES):
        return _READER_IMG_HEAVY_MAX_WIDTH, _READER_IMG_HEAVY_QUALITY
    return _READER_IMG_MAX_WIDTH, _READER_JPEG_QUALITY


def _compress_image(p):
    """Retorna (bytes, mime) na menor codificação disponível.

    Plot fotográfico e superfície contínua comprimem melhor em JPEG. Diagrama
    de traço, esquema e mapa de área chapada comprimem melhor em PNG de paleta,
    e forçar JPEG neles chega a *inflar* o arquivo: um mapa de 59 KB virava 187
    KB. Codificar nos dois formatos e ficar com o menor elimina esse caso sem
    precisar classificar a imagem por heurística.
    """
    if p.suffix.lower() == ".svg":
        return p.read_bytes(), _MIME_BY_EXT[".svg"]
    try:
        from io import BytesIO

        from PIL import Image
        img = Image.open(p)
        needs_alpha = False
        if img.mode in ("RGBA", "LA", "PA") or (
                img.mode == "P" and "transparency" in img.info):
            rgba = img.convert("RGBA")
            lo, _hi = rgba.getchannel("A").getextrema()
            # Alfa totalmente opaco é artefato de export (matplotlib): não
            # precisa de PNG — fundo branco é idêntico na tela.
            needs_alpha = lo < 255
            img = rgba
        max_w, jpeg_q = _reader_img_budget(p.name)
        if img.width > max_w:
            ratio = max_w / img.width
            img = img.resize((max_w, max(1, round(img.height * ratio))),
                             Image.LANCZOS)
        if needs_alpha:
            buf = BytesIO()
            img.save(buf, format="PNG", optimize=True)
            return buf.getvalue(), "image/png"
        rgb = img if img.mode == "RGB" else img.convert("RGB")
        jpg = BytesIO()
        rgb.save(jpg, format="JPEG", quality=jpeg_q, optimize=True)
        png = BytesIO()
        rgb.convert("P", palette=Image.ADAPTIVE, colors=256).save(
            png, format="PNG", optimize=True)
        if len(png.getvalue()) < len(jpg.getvalue()):
            return png.getvalue(), "image/png"
        return jpg.getvalue(), "image/jpeg"
    except Exception:  # noqa: BLE001 - sem Pillow/imagem exótica: manda cru
        return p.read_bytes(), _MIME_BY_EXT.get(p.suffix.lower(), "application/octet-stream")


def _embed_images(fragment):
    """Converte <img src="caminho-local"> em data URI — pré-requisito para o
    arquivo único circular por e-mail/WhatsApp sem carregar a pasta assets."""
    def repl(m):
        import urllib.parse
        src = m.group(2)
        if src.startswith(("http://", "https://", "data:", "#")):
            return m.group(0)
        # Pandoc percent-encode espaços/acentos no src; decodifica antes de
        # resolver no disco.
        p = Path(urllib.parse.unquote(src))
        if not p.exists():
            p = Path(str(p).replace("\\", "/"))
        if not p.exists() or not p.is_file():
            print(f"    aviso: imagem não encontrada para embutir: {src}")
            return m.group(0)
        data, mime = _compress_image(p)
        b64 = base64.b64encode(data).decode("ascii")
        return f'{m.group(1)}data:{mime};base64,{b64}{m.group(3)}'
    return _IMG_SRC_RE.sub(repl, fragment)


_PANDOC_READER_FMT = ("markdown+smart+tex_math_dollars+pipe_tables+strikeout"
                      "+superscript+subscript+implicit_figures+gfm_auto_identifiers")


def _reader_font_css():
    """CSS de @font-face com os woff2 embutidos como data URI — uma única
    vez para o arquivo todo. Sem fontes em cache/disponíveis, devolve ''
    e o template cai nas serifas do sistema (comportamento do export)."""
    try:
        from fetch_fonts import ensure_local_fonts
        css_path = ensure_local_fonts(OUTPUT_DIR)
        if not css_path:
            return ""
        css = Path(css_path).read_text(encoding="utf-8", errors="replace")
        base = Path(css_path).parent

        def inline(m):
            url = m.group(2)
            if url.startswith("data:"):
                return m.group(0)
            f = base / url
            if not f.exists():
                return m.group(0)
            mime = "font/woff2" if url.endswith("woff2") else "font/woff"
            b64 = base64.b64encode(f.read_bytes()).decode("ascii")
            return f"url({m.group(1)}data:{mime};base64,{b64}{m.group(1)})"

        return re.sub(r"url\((['\"]?)([^)'\"]+)\1\)", inline, css)
    except Exception as e:  # noqa: BLE001
        print(f"  aviso: fontes do leitor indisponíveis ({e}); usando fontes do sistema.")
        return ""


def _template_base_css():
    """Extrai o <style> real do template (tokens, masthead, caixas, tabelas,
    highlighting) gerando uma página dummy via pandoc — garante que o leitor
    use EXATAMENTE o mesmo CSS do export HTML, inclusive o bloco de
    highlighting que só existe quando há código."""
    try:
        from export_essay_html import TEMPLATE_PATH
    except Exception as e:  # noqa: BLE001
        print(f"  aviso: template do export indisponível ({e}); leitor sem estilo premium.")
        return ""
    dummy = OUTPUT_DIR / "_reader_dummy.md"
    dummy.parent.mkdir(parents=True, exist_ok=True)
    dummy.write_text(
        "# Dummy\n\n```python\nx = 1\n```\n\n$C_L$ e $$x^2$$\n",
        encoding="utf-8",
    )
    out_html = OUTPUT_DIR / "_reader_dummy.html"
    try:
        r = subprocess.run(
            ["pandoc", str(dummy), "--standalone", f"--template={TEMPLATE_PATH}",
             "--mathjax", "-f", _PANDOC_READER_FMT, "-t", "html",
             "-o", str(out_html)],
            capture_output=True, timeout=120, encoding="utf-8", errors="replace",
        )
        if r.returncode != 0:
            print(f"  aviso: pandoc falhou no CSS base do leitor: {r.stderr[:200]}")
            return ""
        html = out_html.read_text(encoding="utf-8", errors="replace")
        styles = re.findall(r"<style>(.*?)</style>", html, re.DOTALL)
        return "\n".join(styles)
    except FileNotFoundError:
        print("  aviso: pandoc não encontrado para o CSS base do leitor.")
        return ""
    finally:
        dummy.unlink(missing_ok=True)
        out_html.unlink(missing_ok=True)


def _scope_css_for_shadow(css):
    """Adapta o CSS do template para viver num Shadow Root enxertado no
    overlay do grafo: :root/body viram :host (o host é o elemento que carrega
    o atributo data-theme), html somem, e nada vaza para a página do grafo."""
    css = re.sub(r":root:not\(\[data-theme=\"dark\"\]\)", ":host(:not([data-theme=\"dark\"]))", css)
    css = re.sub(r"\[data-theme=\"light\"\]", ":host([data-theme=\"light\"])", css)
    css = re.sub(r":root(?![\w-])", ":host", css)
    css = re.sub(r"(?<![}\w])html\b[^{]*\{", ":host{", css)
    css = re.sub(r"(?<![}\w])body(?=\s*[,{])", ":host", css)
    # position:fixed do chrome do template não existe no shadow (sem nós
    # correspondentes); o leitor tem seus próprios botões flutuantes.
    # O MathJax esconde a cópia MathML assistiva de cada fórmula via CSS que
    # ele mesmo injeta no <head> do documento principal — e que NÃO atravessa
    # a fronteira do shadow onde o conteúdo tipografado é enxertado. Sem esta
    # réplica (mesmo padrão sr-only do assistive-mml do MathJax), toda
    # equação do leitor aparece duplicada: o SVG visível + a cópia MathML
    # solta, renderizada pelo navegador com outra fonte. A réplica preserva a
    # cópia no DOM (leitores de tela continuam atendidos) só a esconde.
    css += (
        "\nmjx-assistive-mml {"
        " position: absolute !important;"
        " clip: rect(1px, 1px, 1px, 1px);"
        " padding: 1px 0 0 0 !important;"
        " border: 0 !important;"
        " margin: 0 !important;"
        " width: 1px !important;"
        " height: 1px !important;"
        " overflow: hidden !important;"
        " display: block !important;"
        " user-select: none;"
        " }"
    )
    return css


def render_reader_fragments(essay_nodes):
    """Gera {slug: {t, tags, html}} com o MESMO visual do export HTML:
    pandoc --standalone --template=essay_template.html por essay, extraindo
    masthead + content + footer (o chrome fixo e o JS do template ficam de
    fora; o leitor reimplementa o essencial no Shadow Root)."""
    from export_essay_html import TEMPLATE_PATH, prepare_for_pandoc

    payload = {}
    total = len(essay_nodes)
    for i, node in enumerate(essay_nodes, 1):
        # node["file"] is stored relative to DATA_ROOT, not to the engine.
        path = DATA_ROOT / node["file"]
        try:
            body, title, subtitle, author_date, summary, _status = prepare_for_pandoc(path)
        except Exception as e:  # noqa: BLE001 - essay problemático não derruba o build
            print(f"  aviso: falha ao preparar leitor de {path.name}: {e}")
            continue
        safe_subtitle = str(subtitle).replace('"', '\\"')
        safe_author = str(author_date).replace('"', '\\"')
        safe_summary = str(summary).replace('"', "'").replace("\n", " ")
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                         encoding="utf-8", dir=str(OUTPUT_DIR)) as tmp:
            tmp.write(body)
            tmp_path = Path(tmp.name)
        try:
            result = subprocess.run(
                ["pandoc", str(tmp_path),
                 "--standalone", f"--template={TEMPLATE_PATH}",
                 # --mathjax muda o formato de saída da matemática para
                 # delimitadores \(..\) que o MathJax compartilhado processa;
                 # não embute nada (sem --embed-resources).
                 "--mathjax",
                 "-f", _PANDOC_READER_FMT, "-t", "html",
                 "-V", f"title={title}",
                 "-V", f"subtitle={safe_subtitle}",
                 "-V", f"author={safe_author}",
                 "-V", f"summary={safe_summary}",
                 f"--resource-path={path.parent}"],
                capture_output=True, timeout=180, encoding="utf-8", errors="replace",
            )
            if result.returncode != 0:
                print(f"  aviso: pandoc falhou para {path.name}: {result.stderr[:200]}")
                continue
            page = result.stdout
        except FileNotFoundError:
            print("  ERRO: pandoc não encontrado — leitor embutido desabilitado neste build.")
            return {}
        finally:
            tmp_path.unlink(missing_ok=True)

        m = re.search(r"<body[^>]*>(.*)</body>", page, re.DOTALL)
        if not m:
            print(f"  aviso: body não encontrado no pandoc de {path.name}")
            continue
        frag = m.group(1)
        # Chrome fixo do template não existe no leitor (overlay tem os seus).
        frag = re.sub(r'<div class="sb-progress">.*?</div>', "", frag, flags=re.DOTALL)
        frag = re.sub(r'<button id="sbThemeToggle".*?</button>', "", frag, flags=re.DOTALL)
        frag = re.sub(r'<button id="sbToTop".*?</button>', "", frag, flags=re.DOTALL)
        frag = re.sub(r"<script>.*?</script>", "", frag, flags=re.DOTALL)
        frag = _embed_images(frag)
        payload[node["id"].removeprefix("essay:")] = {
            "t": node["title"],
            "tags": node.get("tags") or [],
            # Só `draft` viaja: o leitor usa para trocar a meta-row da capa
            # pela marca de rascunho. `finalizado` não precisa de campo.
            "status": node.get("status") if node.get("status") == "draft" else None,
            "html": frag,
        }
        if i % 10 == 0 or i == total:
            print(f"  leitor: {i}/{total} essays renderizados")
    return payload


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no, viewport-fit=cover">
<title>Grafo — Second Brain</title>
<!-- d3 vendorado (inline): o arquivo único funciona sem rede — CDN aqui
     quebraria o caso "mandei o arquivo pra alguém abrir offline". -->
<script>__D3__</script>
<!-- canvas2svg (mock de CanvasRenderingContext2D que serializa SVG) é
     carregado SOB DEMANDA, só quando o usuário exporta SVG (ensureC2S()
     abaixo): são ~50 KB que 99% das sessões nunca usam, e é o único
     recurso que ainda depende de CDN — exportar SVG offline não funciona,
     o resto da página sim. -->
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
    --radius-base: 5;
    --radius-scale: 3;
    --label-size: 10px;
    --node-glow: drop-shadow(0 0 0 transparent);
  }
  * { box-sizing: border-box; }
  /* `html` também precisa da trava de toque/scroll: no iPhone, sem isto, um
     arrasto que começa fora do <svg> (ex.: numa fração de pixel da borda)
     ainda faz o corpo da página fazer o "bounce" elástico do Safari, o que
     no Android nunca acontece — Chrome não tem esse gesto de página. */
  html, body {
    margin: 0; height: 100%; overflow: hidden; overscroll-behavior: none;
    touch-action: none; -webkit-user-select: none; user-select: none;
    -webkit-touch-callout: none; -webkit-tap-highlight-color: transparent;
  }
  body { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; background: var(--bg); color: var(--ink); }
  /* `dvh` acompanha a barra de endereço do navegador móvel, que muda de altura
     ao rolar; `vh` deixaria o grafo cortado atrás dela. */
  #graph { width: 100vw; height: 100vh; height: 100dvh; display: block; touch-action: none; -webkit-user-select: none; }

  /* Botão de recolher o painel. Aparece em qualquer tela — no desktop ele
     fica estacionado sobre a quina do painel (ver @media min-width abaixo) e
     permite colapsar o painel pra usar a tela inteira do grafo; em tela
     pequena, onde o painel compete com o grafo pelo espaço todo, flutua no
     canto e o painel vira folha inferior. */
  #panel-toggle {
    display: flex; position: fixed; z-index: 12; top: 10px; left: 10px;
    width: 40px; height: 40px; border-radius: 10px; cursor: pointer;
    border: 1px solid var(--panel-border); background: var(--panel); color: var(--ink);
    font-size: 17px; line-height: 1; align-items: center; justify-content: center;
    box-shadow: 0 4px 14px rgba(0,0,0,.4);
  }
  /* Painel colapsável em TODAS as telas (não só na pequena): a classe some
     com o painel de vez — sem isso o desktop não tinha como recolhê-lo e o
     grafo inteiro ficava escondido atrás dele. */
  #panel.collapsed { display: none; }
  /* Desktop: com o painel aberto, o botão estaciona na quina superior direita
     do painel (✕ de fechar); com o painel recolhido, vira o botão flutuante
     ☰ no canto do grafo. `:has` é suportado pelos navegadores atuais. */
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
  .legend-item.active { background: rgba(79,168,255,.15); color: var(--ink); }
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
  .detail-kind { display: flex; align-items: center; gap: 6px; margin-bottom: 7px;
    font-size: 10px; letter-spacing: .12em; text-transform: uppercase; color: var(--ink-dim); }
  .detail-kind i { width: 7px; height: 7px; border-radius: 50%; flex: none; }
  /* Uma referencia nao tem rotulo no mapa: e aqui que a citacao aparece por
     extenso, entao ela ganha a medida e o corpo de um texto, nao de um titulo. */
  .detail-title.is-citation { font-size: 12px; color: var(--ink-dim); line-height: 1.5; }
  .detail-summary { margin: 8px 0 0; font-size: 11.5px; line-height: 1.5; color: var(--ink-dim); }

  /* ---- Conexoes por tipo (cartao de detalhe e linha do indice) ---- */
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

  /* A linha expandida do indice tem a largura toda da tabela: o resumo ganha
     medida de leitura e as conexoes ficam ao lado dele, nao embaixo. */
  .idx-detail { display: grid; grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
    gap: 10px 32px; padding: 4px 2px 8px; }
  .idx-detail .conn { margin-top: 0; padding-top: 0; border-top: 0; }
  .idx-detail .conn-panes { max-height: 180px; }
  @media (max-width: 900px) {
    .idx-detail { grid-template-columns: minmax(0, 1fr); gap: 12px; }
  }

  .node-title { font-size: var(--label-size); fill: var(--ink); pointer-events: none; opacity: .85; }
  .link { stroke: var(--edge); stroke-width: 1.2px; opacity: var(--edge-opacity); }
  .link.reference { stroke: var(--edge-ref); stroke-dasharray: 3,3; }
  /* Vinheta sutil atrás do grafo — puramente decorativa, custa zero em JS/perf
     porque é só um gradiente de fundo do body, não redesenha por nó. */
  #graph { background: radial-gradient(ellipse at center, color-mix(in srgb, var(--bg) 92%, white) 0%, var(--bg) 72%); }
  circle.node-glow { filter: var(--node-glow); }
  /* Halo do glow "leve" — opacidade por classe, não por estilo inline, de
     propósito: estilo inline sempre venceria `.dim` abaixo (ao selecionar
     um nó ou buscar) e o halo nunca esmaeceria. Sem a classe, opacidade
     0 (escondido); ver applyStyle() no HTML gerado. */
  .node-halo { opacity: 0; }
  .node-halo.glow-leve { opacity: 1; }
  .dim { opacity: .08; }
  /* As três classes somadas (mais específico que `.dim` sozinho) garantem
     que o halo realmente esmaeça com o resto do nó ao deselecionar/buscar,
     em vez de ficar "grudado" por cima. */
  .node-halo.glow-leve.dim { opacity: .08; }
  /* Modo "sempre visível" das conexões: nunca esmaece, nem por seleção nem
     por busca — vence `.dim` pelo mesmo motivo acima (mais classes = mais
     específico). Modo "off": oculta de vez, independente de tudo o mais. */
  .link.link-always, .link.link-always.dim { opacity: var(--edge-opacity); }
  .link.link-off { display: none; }
  circle { transition: opacity .25s ease, filter .2s ease, stroke-width .15s ease; }
  circle:hover { stroke-width: 2px; }
  /* Escala no hover só quando parado (sem `.dragging`) — durante o arrasto
     o d3.drag já reposiciona `cx`/`cy` a cada frame; empilhar uma transform
     de escala por cima brigaria com isso e o nó "tremeria" ao ser puxado. */
  g.node:not(.dragging) circle:hover { transform: scale(1.12); transform-box: fill-box; transform-origin: center; }
  .link { transition: opacity .25s ease; }
  .hidden-node { display: none; }
  /* Índice e Estilo usam a tela inteira, no desktop tanto quanto no
     celular — uma tabela de centenas de linhas ou um painel de dezenas de
     controles não cabem bem numa janelinha de 760px cheia de scroll
     interno. #modal-body ocupa 100% da largura do modal, que por sua vez
     é 100vw/100dvh (ver #modal abaixo): nada aqui limita a largura do
     conteúdo, só o padding lateral (clamp abaixo) dá a margem de leitura. */
  #modal-overlay { display:none; position: fixed; inset: 0; background: rgba(9,11,13,.72);
    backdrop-filter: blur(3px); -webkit-backdrop-filter: blur(3px); z-index: 20; }
  #modal-overlay.open { display: flex; align-items: stretch; justify-content: stretch; }
  #modal { width: 100vw; height: 100dvh; max-height: 100dvh; overflow-y: auto;
    background: var(--panel); border: none; border-radius: 0; padding: 0;
    box-shadow: none; }
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

  /* Linha de resumo expansível (só essays, ver renderTypeIndex): não é
     clicável pra navegar como as outras — só existe pra mostrar o texto do
     `summary:` do frontmatter sem abrir o arquivo. Sobrescreve o hover azul
     genérico de tr acima (mais específico por causa da classe), senão o
     parágrafo de resumo pareceria clicável igual às linhas de verdade. */
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

  /* `<details>` nativo — some sozinho a lógica de abrir/fechar, sem estado
     em JS. Fecha por padrão no celular (o JS decide o atributo `open` na
     hora de montar o HTML, olhando o mesmo sinal de "tela pequena" que o
     resto do layout responsivo usa) e some com o filtro fino até o usuário
     pedir por ele — é o que sobra pra lista de verdade quando a tela é
     estreita. No desktop, tudo continua visível por padrão, como antes. */
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
  /* Setinha de direção no cabeçalho ordenado — sinal visual rápido de qual
     coluna manda e em que sentido, sem precisar clicar de novo pra saber. */
  #modal th.sorted.asc::after { content: " ▲"; font-size: 9px; }
  #modal th.sorted.desc::after { content: " ▼"; font-size: 9px; }

  /* ---- Tela pequena ----------------------------------------------------
     Nada aqui altera o desktop: tudo mora dentro da media query. O painel
     lateral vira folha inferior recolhível, porque numa tela de celular ele
     cobriria metade do grafo; e o modal do índice passa a ocupar a tela
     inteira, já que uma tabela em 92vw de largura fica ilegível. */
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
    /* Esconder é `display: none`, não `transform` nem `visibility`: o painel
       precisa sumir de fato, inclusive parar de receber toque, e é a única
       forma que não depende de o renderizador resolver porcentagem de
       transform. O JS também aplica isto inline, para não ficar refém da
       cascata. Sem animação de deslizar, de propósito. */
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
    /* #modal já é 100vw/100dvh no desktop também — aqui só sobra o respiro
       de área segura do iPhone (notch/home indicator) e um pouco menos de
       padding lateral, já que a tela é estreita. */
    #modal-body { padding: 4px 14px calc(14px + env(safe-area-inset-bottom)); }
    #modal-topbar { padding: calc(10px + env(safe-area-inset-top)) 14px 0; }
    #modal .close { font-size: 12px; padding: 7px 14px; }
    .idx-tab { padding: 8px 14px; font-size: 12px; }
    .idx-chip { padding: 6px 11px; font-size: 11px; }
    /* Linha única, rolando na horizontal — bem mais compacto na vertical do
       que deixar as tags quebrarem linha e empilharem. Isto já mora dentro
       do <details> fechado por padrão, então some da vista até o usuário
       pedir "Mais filtros" mesmo. */
    .idx-tags { flex-wrap: nowrap; overflow-x: auto; max-height: none; padding-bottom: 4px; }
    .idx-chip { flex: none; }
    /* Tabela em coluna: cabeçalho de tabela não cabe em tela estreita. */
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
    /* O cabeçalho vira barra de ordenação em vez de sumir: sem ele o índice
       perderia a ordenação por coluna justamente onde a lista é mais longa. */
    #modal thead { display: block; }
    #modal thead tr { display: flex; gap: 6px; }
    #modal th { flex: 1; text-align: center; font-size: 10px; padding: 9px 4px;
      border-radius: 6px; background: rgba(255,255,255,.05); border-bottom: none; position: static; }
    #modal tbody tr { border-bottom: 1px solid #2b2f33; padding: 10px 2px; }
    #modal td { border: none; padding: 2px; }
    #modal td[data-label]:not([data-label="Título"]):not([data-label="Tags"]) { color: var(--ink-dim); font-size: 11px; }
    #modal td[data-label]:not([data-label="Título"]):not([data-label="Tags"])::before { content: attr(data-label) ": "; }
    .node-title { font-size: 12px; }
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
  .style-row select { background: var(--panel); color: var(--ink); border: 1px solid var(--panel-border);
    border-radius: 7px; padding: 7px 10px; font-size: 12px; font-family: inherit; cursor: pointer; }
  .style-hint { font-size: 12px; color: var(--ink-dim); margin: -4px 0 12px 0; line-height: 1.5; }
  .theme-row { display: flex; gap: 10px; flex-wrap: wrap; }
  .theme-btn { flex: 1; min-width: 110px; margin-top: 0; text-align: center; padding: 10px 12px; }
  /* Precisa vir DEPOIS da regra acima (mesma especificidade — quem vem
     depois no arquivo vence a cascata, media query ou não): um bloco igual
     a este, mas colado dentro da media query grande lá em cima, ficava
     sobrescrito pela regra desktop acima, que roda incondicionalmente. Os 4
     botões de tema em flex-wrap/min-width 110px cabiam só 2 por linha numa
     tela estreita, e cada botão mantinha o padding de desktop — juntos isso
     empilhava 2 linhas altas e "engolia" boa parte da folha do Estilo. Grid
     fixo de 2 colunas com padding/fonte menores encaixa as 4 opções
     (Aqua/Céu Noturno/Inferno/Synthwave) em bem menos altura. */
  @media (max-width: 720px), (pointer: coarse) and (max-width: 900px) {
    .theme-row { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .theme-btn { min-width: 0; padding: 8px 6px; font-size: 12px; }
  }

  /* Acima de 900px: os 6 cartões de .style-section (alturas bem diferentes —
     um tem 9 linhas de cor, outro tem 4 sliders de física) numa grid comum
     deixam buraco embaixo dos cartões curtos que dividem linha com um
     cartão alto, porque grid não é masonry: a altura da linha é dada pelo
     maior item dela, e cada linha não sabe da anterior. Numa tela larga
     isso lê como "cartões jogados sem ordem". Column layout resolve: cada
     cartão flui pro topo da PRÓXIMA coluna assim que a atual enche, então o
     espaço usado acompanha a altura real do conteúdo, sem sobra — e a
     largura toda da tela é ocupada porque column-width define uma largura
     mínima e o navegador decide quantas colunas cabem, esticando-as pra
     preencher o contêiner (igual ao auto-fit da grid, só que sem as linhas
     fantasmas). Mobile não entra aqui: fica com a grid de coluna única de
     sempre. */
  @media (min-width: 900px) {
    .style-grid { display: block; column-width: 380px; column-gap: 18px; }
    .style-section { break-inside: avoid; margin: 0 0 18px; display: inline-block; width: 100%; }
    .style-span2 { column-span: all; }
    /* .btn é width:100% por padrão (bom no mobile, onde a barra de ações
       deve preencher a largura toda). Em desktop, dentro do .style-actions
       flex, isso vira flex-basis:100% pros dois botões, que dividem a
       largura inteira do modal entre si e ficam enormes. Aqui eles voltam a
       ter largura pelo conteúdo, alinhados à direita como uma barra de
       ação comum. */
    .style-actions { justify-content: flex-end; }
    .style-actions .btn { width: auto; flex: 0 0 auto; padding: 10px 24px; }
  }

  /* ---- Popover de escolha ao exportar SVG -------------------------------
     Um clique em "Exportar SVG" tem duas saídas bem diferentes (arquivo com
     glow/gradiente, que o Xplore do Android historicamente recusa a abrir,
     vs. um sem nenhum dos dois, pra testar se é isso). Um <select> ou
     confirm() nativo esconderia essa escolha atrás de mais um clique sem
     explicar o porquê; um popover ancorado no botão deixa as duas opções
     visíveis de cara, com a explicação ao lado. */
  #export-svg-popover { display: none; position: fixed; z-index: 30; flex-direction: column; gap: 8px;
    min-width: 240px; max-width: 280px; background: var(--panel); border: 1px solid var(--panel-border);
    border-radius: 10px; padding: 12px; box-shadow: 0 8px 24px rgba(0,0,0,.4); }
  #export-svg-popover.open { display: flex; }
  #export-svg-popover .btn { width: 100%; margin-top: 0; text-align: center; }
  #export-svg-popover p { font-size: 11px; color: var(--ink-dim); margin: 0 0 2px; line-height: 1.4; }

  /* ---- Leitor embutido (MySecondBrain) --------------------------------
     O visual dos essays é EXATAMENTE o do export HTML: o CSS do template
     (tokens, masthead, caixas, fontes, highlighting) é gerado pelo build a
     partir do próprio essay_template.html e vive DENTRO do Shadow Root
     (READER_DATA.css). Aqui só existe o chrome do overlay. */
  /* Botão primário do cartão de detalhe (LER): só a cor é dele — geometria
     vem de .detail-actions > *. */
  .read-btn { border: 1px solid var(--instrument-blue); background: var(--instrument-blue);
    color: #0b1220; }
  .read-btn:hover { filter: brightness(1.08); }
  /* Área de toque real ≥44px no toque grosso sem inflar o desenho: pseudo-
     elemento invisível expande o alvo ao redor de cada botão da linha. */
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
  .idx-read:hover { color: var(--instrument-blue); border-color: var(--instrument-blue);
    background: rgba(79,168,255,.12); }
  /* No build leve o 📖 é um <a>: precisa do mesmo desenho do <button>, que
     não herda (âncora não é flex item centrado nem perde o sublinhado). */
  a.idx-read { display: inline-flex; align-items: center; justify-content: center;
    text-decoration: none; }
  a.idx-read:hover { text-decoration: none; }
  /* Marca de rascunho ao lado do título no Índice. Versalete pequeno, sem
     fundo: mesmo peso das tags, para sinalizar sem competir com o título. */
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
  <h1>Grafo da Wiki</h1>
  <input id="search" type="text" placeholder="Buscar por título ou tag…">

  <div class="legend-item" data-type="essay"><span class="dot" style="background:var(--instrument-blue)"></span> Essay</div>
  <div class="legend-item" data-type="concept"><span class="dot" style="background:var(--concept)"></span> Concept</div>
  <div class="legend-item" data-type="entity"><span class="dot" style="background:var(--entity)"></span> Entity</div>
  <div class="legend-item" data-type="insights"><span class="dot" style="background:var(--insight)"></span> Insight</div>
  <div class="legend-item disabled" data-type="reference"><span class="dot" style="background:var(--reference)"></span> Reference</div>

  <button class="btn" id="btn-index">Índice</button>
  <button class="btn" id="btn-gaps">Gaps entre tags</button>
  <button class="btn" id="btn-style">Estilo</button>
  <button class="btn" id="btn-export-png">Exportar PNG</button>
  <button class="btn" id="btn-export-svg">Exportar SVG</button>
  <button class="btn" id="btn-fit-screen">Ajustar à tela</button>

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
<script type="application/json" id="sb-mathjax-data">__MATHJAX_B64__</script>
<script>
// Payloads chegam comprimidos (deflate-raw + base64) em tags JSON: o parser
// de JS não vê os MB de dados na inicialização — cada payload é inflado
// sincronamente (pako) só quando quem o consome precisa.
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

// Toque grosso (dedo, não mouse) OU tela pequena — cobre tablet/celular
// mesmo quando `matchMedia("pointer: coarse")` falha (alguns Android
// antigos). É intencionalmente mais amplo que `telaPequena()` (que só olha
// largura de tela pra decidir layout do painel): aqui a pergunta é "este
// aparelho tem menos fôlego de CPU/GPU pra física e SVG", não "a tela é
// estreita" — as duas coisas costumam andar juntas mas não são a mesma.
function isMobileDevice() {
  const coarse = window.matchMedia && window.matchMedia("(pointer: coarse)").matches;
  const small = Math.min(window.innerWidth, window.innerHeight) < 820;
  // Toque grosso já basta sozinho. Sem ele, tela pequena isolada não é sinal
  // suficiente — uma janela de desktop redimensionada fica estreita sem virar
  // um aparelho fraco — então some com `hardwareConcurrency` (poucos núcleos
  // lógicos) como segundo sinal antes de aceitar "pequena" como "fraca".
  // Nenhum dos três é confiável sozinho (coarse falha em Android antigo,
  // innerWidth mente em janela redimensionada, hardwareConcurrency pode vir
  // limitado/ausente do navegador) — combinados, cobrem a maioria dos casos.
  const fewCores = (navigator.hardwareConcurrency || 8) <= 4;
  return coarse || (small && fewCores);
}
const DEVICE_IS_MOBILE = isMobileDevice();

// ---- Estilo (cores, raio, rótulo) --------------------------------------
// `defaultStyle` vem do Python (GRAPH_STYLE) — é o padrão "de fábrica" da
// wiki. `localStorage` guarda só o que o usuário mudou neste navegador; se
// o Python mudar o padrão depois, quem nunca customizou nada recebe o novo
// padrão automaticamente (não fica preso a uma cópia congelada). No celular,
// por cima do padrão do Python ainda entram os `mobileOverrides` — glow e
// cenário custam mais no Chrome mobile do que no desktop, então o ponto de
// partida já nasce mais leve lá, sem o usuário precisar descobrir isso
// sozinho abrindo o painel de Estilo.
const STYLE_VARS = {
  essay: "--instrument-blue", concept: "--concept", entity: "--entity",
  insights: "--insight", reference: "--reference", edge: "--edge", background: "--bg",
};
const STYLE_KEY = "sb-graph-style-v1";
const FACTORY_STYLE = data.defaultStyle || {
  colors: { essay: "#4fa8ff", concept: "#5fd3c4", entity: "#e8b657", insights: "#b48ce8",
    reference: "#8a8f96", edge: "#858b93", background: "#1b1e21" },
  edgeOpacity: 0.28, edgeVisibility: "auto", radiusBase: 5, radiusScale: 3, labelSize: 10,
  glow: "leve", labels: "auto", starfield: true, gradient: true, sizeMode: "degree",
  spacing: 1.8, performance: "alta", collision: true,
  linkStrength: 3.5, chargeStrength: 2.5, friction: 0.65, homeStrength: 0.25,
  sphereShading: false, tagTint: false,
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

// ---- Nível de desempenho da simulação/renderização ---------------------
// "auto" decide sozinho a partir de aparelho + tamanho do grafo. Os outros
// três (alta/média/baixa) são escolha explícita do usuário, sobrepondo o
// automático. `theta` é o parâmetro de aproximação Barnes-Hut do
// forceManyBody do d3 (quanto maior, mais aproximado e mais rápido, com
// leve perda de precisão no layout); `distanceMax` limita o alcance da
// repulsão entre nós distantes, que em grafos grandes é boa parte do custo
// por tick mesmo com a árvore já aproximando; `collideIterations` é quantas
// vezes o d3 relaxa colisões por tick (mais = menos sobreposição, mais CPU).
const PERFORMANCE_TIERS = {
  // Menos precisão nos modos baratos, mas sem mudar demais a física.
  alta: { theta: 0.65, distanceMax: 1300, collideIterations: 4, labelsAlways: true, damping: 0.68, collisionScale: 1.16 },
  media: { theta: 0.90, distanceMax: 900, collideIterations: 3, labelsAlways: true, damping: 0.76, collisionScale: 1.18 },
  baixa: { theta: 1.15, distanceMax: 700, collideIterations: 4, labelsAlways: false, damping: 0.80, collisionScale: 1.24 },
};
function resolvePerformanceTier(cfg) {
  if (cfg.performance && cfg.performance !== "auto") return cfg.performance;
  // Tanto Desktop quanto Mobile iniciam em "alta" por padrão.
  // O usuário ainda pode escolher "média" ou "baixa" manualmente no painel de Estilo se necessário.
  return "alta";
}

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
  // "alto" usa filter: drop-shadow (bonito, caro — rasteriza cada nó à
  // parte). "leve" usa um halo desenhado como círculo comum, sem filter —
  // visualmente mais simples mas praticamente de graça em qualquer
  // aparelho. "off" desliga os dois.
  root.setProperty("--node-glow", cfg.glow === "alto" ? "drop-shadow(0 0 4px currentColor)" : "none");

  // Em Canvas não há atributos DOM pra reaplicar: os gradientes são
  // recriados (baratos — só stops, não pixels) e o resto (raio, halo,
  // glow, arestas) é lido direto de `styleConfig` a cada frame por
  // draw(), então só precisamos agendar um redesenho.
  buildGradients();
  clearSpriteCache(); // cor/gradiente/glow/raio podem ter mudado: sprite velho não pode ficar em tela
  updateLabelVisibility(zoomTransform.k);

  if (!opts || !opts.silent) {
    applyForces(cfg);
    simulation.alpha(0.3).restart();
  }
  scheduleDraw();
}

function typeColorRaw(n) {
  return (styleConfig.colors && styleConfig.colors[n.type]) || "#888";
}

let width = window.innerWidth, height = window.innerHeight;
let dpr = window.devicePixelRatio || 1;
const canvas = document.getElementById("graph");
const ctx = canvas.getContext("2d");

// ---- Loop de desenho (rAF com flag "dirty") ----------------------------
// Nada aqui redesenha por conta própria: todo mundo que muda algo visível
// (tick da simulação, zoom/pan, arrasto, seleção, busca, mudança de estilo)
// chama scheduleDraw(), que só agenda UM requestAnimationFrame por vez —
// múltiplas chamadas na mesma volta do event loop colapsam num único
// desenho. Quando a simulação esfria e ninguém mais mexe em nada, o loop
// simplesmente para de ser reagendado: sem isso o Chrome mobile continuaria
// desenhando a 60fps pra sempre, gastando bateria à toa.
let rafScheduled = false;
function scheduleDraw() {
  if (rafScheduled) return;
  rafScheduled = true;
  requestAnimationFrame(() => { rafScheduled = false; draw(); });
}

// HiDPI: o canvas físico é maior que o CSS (devicePixelRatio), e o contexto
// escala de volta — sem isto o grafo fica borrado em qualquer tela retina,
// que é a maioria dos celulares hoje.
function resizeCanvas() {
  width = window.innerWidth;
  height = window.innerHeight;
  const oldDpr = dpr;
  dpr = window.devicePixelRatio || 1;
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  canvas.style.width = width + "px";
  canvas.style.height = height + "px";
  // Trocar de monitor (ou zoom do SO) muda o devicePixelRatio em runtime —
  // sprites já cacheados no dpr antigo ficariam borrados/nítidos demais no
  // novo, então descarta e deixa regenerar sob demanda (a chave já inclui
  // dpr, então isto só evita acumular as duas gerações à toa).
  // `oldDpr !== undefined` guarda a PRIMEIRA chamada, que acontece no topo do
  // script, antes de `const spriteCache` ser inicializado lá embaixo: limpar
  // ali dentro estouraria em ReferenceError (temporal dead zone) e mataria o
  // script inteiro, deixando o grafo em branco. No primeiro run o cache nasce
  // vazio de qualquer jeito, então não há o que limpar.
  if (oldDpr !== undefined && dpr !== oldDpr) clearSpriteCache();
  scheduleDraw();
}
resizeCanvas();

// Campo de estrelas decorativo, em coordenadas fracionárias da tela (0..1)
// para se adaptar sozinho a qualquer resize sem recalcular nada — fica fora
// do transform de zoom/pan (é cenário, não conteúdo) e é gerado uma vez só.
const STAR_COUNT = 140;
const stars = Array.from({ length: STAR_COUNT }, () => ({
  fx: Math.random(), fy: Math.random(),
  r: Math.random() * 1.1 + 0.2,
  o: Math.random() * 0.5 + 0.08,
}));

// Agrupa as estrelas por opacidade em poucos "baldes", uma vez só na carga
// (não a cada frame): cada estrela tem sua própria opacidade aleatória, e
// fillStyle vale para o path inteiro, então um fill() só serviria apenas se
// todas as estrelas tivessem a mesma opacidade. Com poucos baldes (a
// diferença de opacidade dentro de um balde é imperceptível num ponto de
// 1-2px) trocamos 140 pares beginPath/fill por frame por só 6, mantendo o
// aspecto "cintilante" do céu quase idêntico ao original contínuo.
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
// Opacidade representativa do balde: o ponto médio do seu intervalo.
const starBucketOpacity = starBucketLists.map(
  (_, idx) => STAR_O_MIN + STAR_O_RANGE * ((idx + 0.5) / STAR_BUCKETS)
);

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

// Gradientes cacheados por tipo, definidos num círculo unitário (raio 1,
// centro 0,0) — na hora de desenhar cada nó fazemos ctx.translate/scale até
// o raio de fato, e o CanvasGradient (que guarda só os stops, não pixels)
// se estica sozinho para o tamanho certo. Isso evita recriar o gradiente a
// cada nó/frame: é criado uma vez por chamada de applyStyle().
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

// Fica marcado assim que o próprio usuário mexe no zoom/pan (toque, roda ou
// arrasto), para nunca mais sobrescrever o enquadramento que ele escolheu —
// nem no fit-to-screen inicial do mobile, nem numa rotação de tela depois.
let userAdjustedView = false;
let zoomTransform = d3.zoomIdentity;

const nodeById = new Map(data.nodes.map(n => [n.id, n]));
const endpoint = (v) => (typeof v === "object" ? v : nodeById.get(v));

// Quadtree para hit-testing barato: em vez de testar distância contra os
// ~1100 nós a cada clique/arrasto/hover, a árvore descarta ramos inteiros
// fora do raio de busca. Reconstruída a cada tick (a simulação move os nós),
// mas isso é O(n log n) e desprezível perto do custo de desenhar.
// A bibliografia começa oculta por padrão (o mesmo comportamento do modo globo)
// para não sobrecarregar a malha com centenas de nós-folha de referência.
// Declarado AQUI, e não junto da legenda lá embaixo, porque rebuildQuadtree()
// e draw() leem `hiddenTypes` durante a inicialização no topo do script — um
// `const` mais abaixo estouraria em ReferenceError (temporal dead zone) e
// mataria o script inteiro, deixando o grafo em branco.
const hiddenTypes = new Set(["reference"]);

function isNodeVisible(n) {
  return !hiddenTypes.has(n.type);
}

let quadtree = d3.quadtree().x(d => d.x).y(d => d.y);
function rebuildQuadtree() {
  quadtree = d3.quadtree(data.nodes.filter(isNodeVisible), d => d.x, d => d.y);
}

// Tolerância de toque maior que a de mouse: um dedo cobre bem mais área de
// tela que a ponta de um cursor, e com só 10px um toque levemente descentrado
// do nó simplesmente não achava nada — sensação de "preciso mirar/segurar
// bastante pro arrasto pegar". 22px (~ metade de um alvo de toque confortável)
// resolve isso sem prejudicar a precisão no desktop, que continua em 10px.
const HIT_TOLERANCE_PX = DEVICE_IS_MOBILE ? 22 : 10;
function findNodeAt(wx, wy) {
  const tolerance = HIT_TOLERANCE_PX / zoomTransform.k; // tolerância em pixels de tela
  let found = null;
  let bestDist = Infinity;
  quadtree.visit((node, x0, y0, x1, y1) => {
    if (!node.length) {
      let q = node;
      do {
        const d = q.data;
        const dx = d.x - wx, dy = d.y - wy;
        const r = radiusOf(d) + tolerance;
        const dist = dx * dx + dy * dy;
        if (dist <= r * r && dist < bestDist) { found = d; bestDist = dist; }
      } while ((q = q.next));
    }
    return x0 > wx + tolerance || x1 < wx - tolerance || y0 > wy + tolerance || y1 < wy - tolerance;
  });
  return found;
}

const zoom = d3.zoom()
  .scaleExtent([0.1, 6])
  .filter((event) => {
    // Se o ponteiro/toque começa em cima de um nó, este evento não deve
    // virar pan: o d3.drag (abaixo) assume o gesto para arrastar o nó. Sem
    // este filtro, zoom e drag brigariam pelo mesmo mousedown/touchstart.
    if (event.type === "mousedown") {
      const pt = d3.pointer(event, canvas);
      const [wx, wy] = zoomTransform.invert(pt);
      if (findNodeAt(wx, wy)) return false;
    }
    if (event.type === "touchstart") {
      // Pinça (2+ dedos) é sempre gesto de zoom, sem hit-test. Com 1 dedo só,
      // `d3.pointer(event, canvas)` desembrulharia o TouchEvent inteiro, que
      // não tem clientX/clientY (ficam em event.touches[]) — passar o próprio
      // Touch de touches[0] é o que d3.pointer sabe interpretar.
      if (event.touches.length > 1) return true;
      const pt = d3.pointer(event.touches[0], canvas);
      const [wx, wy] = zoomTransform.invert(pt);
      if (findNodeAt(wx, wy)) return false;
    }
    if (event.type.startsWith("touch")) return true;
    // O filtro padrão do d3 aceita só o botão esquerdo (`!event.button`).
    // Liberar o botão do meio dá o pan por clique-na-rodinha sem tirar o
    // arrastar de nó, que continua no esquerdo.
    if (event.type === "wheel") return !event.ctrlKey;
    return event.button === 0 || event.button === 1;
  })
  .on("zoom", (event) => {
    zoomTransform = event.transform;
    updateLabelVisibility(zoomTransform.k);
    // `sourceEvent` só existe quando a transformação veio de uma interação
    // real (toque, roda, arrasto) — chamadas programáticas como o
    // fitToScreen() não têm, então não acionam esta marca.
    if (event.sourceEvent) userAdjustedView = true;
    scheduleDraw();
  });

const canvasSel = d3.select(canvas);
canvasSel.call(zoom);

// Sem isto o navegador entra em auto-scroll (aquele ícone de setas) no
// clique do meio, e o pan nunca chega a acontecer.
canvas.addEventListener("mousedown", (event) => { if (event.button === 1) event.preventDefault(); });
canvas.addEventListener("auxclick", (event) => { if (event.button === 1) event.preventDefault(); });

// Rotação de tela e troca de janela: sem isto o canvas fica com a dimensão
// de carregamento e o grafo aparece cortado ou centralizado fora da tela.
function ajustarViewport() {
  resizeCanvas();
  simulation.force("center", d3.forceCenter(width / 2, height / 2));
  simulation.alpha(0.15).restart();
  // Ao voltar para tela grande o painel reaparece: `collapsed` é inerte fora
  // da media query, mas deixar a classe pendurada faria o botão reaparecer
  // com o rótulo errado se a janela encolhesse de novo.
  if (!telaPequena()) definirPainel(true);
  // Girar o celular ou redimensionar a janela muda o que cabe na tela;
  // reencaixa o grafo, a menos que o leitor já tenha escolhido o próprio
  // enquadramento (fitToScreen respeita `userAdjustedView`).
  fitToScreen(true);
}
window.addEventListener("resize", ajustarViewport);
window.addEventListener("orientationchange", ajustarViewport);

function recomputeVisibleDegrees() {
  data.nodes.forEach(n => { n.visibleDegree = 0; });
  data.edges.forEach(e => {
    const s = endpoint(e.source), t = endpoint(e.target);
    if (!s || !t || !isNodeVisible(s) || !isNodeVisible(t)) return;
    s.visibleDegree++;
    t.visibleDegree++;
  });
}

// Bytes/linhas variam muito mais que grau (um essay grande pode ter 15000
// bytes vs. um insight solto com 200) — por isso os modos "bytes"/"lines"
// normalizam pelo máximo do dataset (0 a 1) antes de aplicar a escala,
// senão o slider "Escala por conexões" precisaria de valores completamente
// diferentes dependendo do modo escolhido. O modo "degree" fica como estava
// (sem normalizar), pra não mudar o visual de quem já usa o padrão.
const maxSizeBytes = Math.max(1, ...data.nodes.map(n => n.sizeBytes || 0));
const maxSizeLines = Math.max(1, ...data.nodes.map(n => n.sizeLines || 0));
const SIZE_NORM_K = 4; // calibrado pra "bytes"/"lines" ocuparem faixa visual parecida com "degree"

const radiusOf = (d) => {
  const base = styleConfig.radiusBase, scale = styleConfig.radiusScale;
  if (styleConfig.sizeMode === "bytes") {
    return base + Math.sqrt((d.sizeBytes || 0) / maxSizeBytes) * scale * SIZE_NORM_K;
  }
  if (styleConfig.sizeMode === "lines") {
    return base + Math.sqrt((d.sizeLines || 0) / maxSizeLines) * scale * SIZE_NORM_K;
  }
  return base + Math.sqrt(d.visibleDegree ?? d.degree) * scale;
};

// Semeia com o layout já calculado no build (ver compute_layout() no
// Python) em vez de deixar o d3 começar de posições aleatórias. Isso é o
// que faz o celular não precisar rodar a simulação inteira do zero — só
// uma passada curta de ajuste fino (colisão) por cima de um layout que já
// está quase certo.
// ...mas semeando COMPRIMIDO em direção ao centro, não na posição final.
// Semear exato deixava a simulação sem nada a resolver: ela rodava, e o
// grafo aparecia congelado, sem movimento nem colisão visível. Começando
// contraído, os nós se abrem até o lugar certo em ~2s, o que devolve a
// animação orgânica sem pagar o custo de descobrir o layout do zero — a
// topologia já está certa, só a escala é que se resolve na tela.
const BLOOM = 0.55;          // 1 = já na posição final (estático)
const JITTER = 18;           // quebra simetria, senão nós coincidentes travam
data.nodes.forEach(n => {
  const bx = n.x0 ?? width / 2;
  const by = n.y0 ?? height / 2;
  n.x = width / 2 + (bx - width / 2) * BLOOM + (Math.random() - 0.5) * JITTER;
  n.y = height / 2 + (by - height / 2) * BLOOM + (Math.random() - 0.5) * JITTER;
});

// Estado do nível de desempenho atual — lido pela visibilidade de rótulos
// no zoom (abaixo) e recalculado toda vez que spacing/performance mudam.
let currentTier = PERFORMANCE_TIERS[resolvePerformanceTier(styleConfig)];
let labelsShown = false;
const LABEL_SHOW_AT = 0.96;
const LABEL_HIDE_AT = 0.90;

// Some com os rótulos quando o tier não é "sempre mostrar" e o zoom está
// afastado — em wikis de centenas de nós, texto é de longe a coisa mais
// cara de desenhar em Canvas (fillText é ordens de magnitude mais lento que
// um arc()); ilegível de longe mesmo, então não custa nada pular de vez o
// fillText em vez de só escondê-lo via CSS como no SVG.
function updateLabelVisibility(k) {
  // "sempre"/"nunca" são escolha explícita do usuário e vencem o tier de
  // desempenho; só em "auto" (o padrão) é que baixo zoom + tier "baixa"
  // ainda escondem rótulo sozinhos, como antes.
  const mode = styleConfig.labels || "auto";
  const show = mode === "sempre" ? true
    : mode === "nunca" ? false
    // Histerese evita piscada quando o zoom repousa no limiar.
    : (labelsShown ? k > LABEL_HIDE_AT : k >= LABEL_SHOW_AT);
  if (show !== labelsShown) {
    labelsShown = show;
  }
  scheduleDraw();
}

// Recria link/charge/collide a partir de spacing + tier de desempenho —
// chamada na criação e de novo sempre que o usuário mexe nesses controles
// no painel de Estilo. `collision` desliga a força inteira quando o usuário
// pede mais velocidade num aparelho fraco, ao custo de nós podendo se
// sobrepor visualmente.
// Grau do nó para calibrar a força do link. `function` (não `const`) porque
// applyForces() roda na inicialização, no topo do script, e uma const aqui
// entraria em temporal dead zone. O piso de 1 evita divisão por zero num nó
// isolado; aceita id ou objeto porque o d3 resolve source/target em momentos
// diferentes do ciclo de vida do forceLink.
function degreeOf(node) {
  if (node == null) return 1;
  const n = typeof node === "object" ? node : null;
  if (!n) return 1;
  return Math.max(1, n.visibleDegree ?? n.degree ?? 1);
}

function applyForces(cfg) {
  currentTier = PERFORMANCE_TIERS[resolvePerformanceTier(cfg)];
  const spacing = cfg.spacing || 1;
  // Multiplicadores do painel de Estilo — `?? 1`/`?? 0.55` cobrem tanto
  // estilos salvos antigos (de antes destes controles existirem) quanto o
  // padrão de fábrica, então ninguém herda um valor `undefined` na fórmula.
  const linkStrengthMult = cfg.linkStrength ?? 3.5;
  const chargeMult = cfg.chargeStrength ?? 2.5;
  const homeMult = cfg.homeStrength ?? 0.25;
  simulation
    // A força do link NÃO é fixa de propósito. Um `.strength(0.5)` igual para
    // toda aresta era a causa da agitação: um nó-hub com 40 arestas recebia 40
    // puxões de 0.5 por tick, entrava em oscilação e sacudia a vizinhança
    // inteira junto. A fórmula abaixo é a heurística padrão do d3 (dividir pelo
    // grau do extremo menos conectado), que enfraquece automaticamente o link
    // conforme o nó acumula conexões — é exatamente o caso desta wiki, onde
    // alguns essays concentram dezenas de links e a maioria das páginas tem 2 ou 3.
    // `linkStrengthMult` (slider "Força elástica das conexões") multiplica o
    // resultado inteiro sem mudar a heurística de grau em si.
    .force("link", d3.forceLink(data.edges).id(d => d.id)
      .distance(70 * spacing)
      .strength(l => linkStrengthMult / Math.min(degreeOf(l.source), degreeOf(l.target))))
    // `chargeMult` (slider "Força de repulsão entre nós") é independente de
    // `spacing`: spacing mexe em distância/colisão/arestas juntos, este só
    // na intensidade da repulsão.
    .force("charge", d3.forceManyBody().strength(-110 * spacing * chargeMult)
      .theta(currentTier.theta).distanceMax(currentTier.distanceMax))
    // Elasticidade de retorno (slider "Elasticidade de retorno"): âncora cada
    // nó na sua posição de layout (x0/y0, calculada no Python — ver BLOOM
    // acima, que semeia daqui) via forceX/forceY. Link e charge só resolvem
    // FORMA relativa entre vizinhos; nenhum dos dois tem noção de posição
    // absoluta, então nada nesta simulação puxava um nó arrastado de volta
    // pro lugar de onde ele saiu — essa é a força que faz isso. Fallback
    // pra `d.x`/`d.y` cobre o caso raro de nó sem x0/y0 (não travado por
    // compute_layout): sem home definido, a força vira strength*0 = no-op
    // pra ele, em vez de NaN se propagando pela simulação inteira.
    .force("homeX", d3.forceX(d => d.x0 ?? d.x).strength(homeMult))
    .force("homeY", d3.forceY(d => d.y0 ?? d.y).strength(homeMult));
  if (cfg.collision === false) {
    simulation.force("collide", null);
  } else {
    simulation.force("collide", d3.forceCollide().radius(d => (7.8 + radiusOf(d)) * spacing * currentTier.collisionScale)
      .strength(1.25)
      .iterations(currentTier.collideIterations));
  }
  // Atrito: o valor do usuário continua prevalecendo; quando não há valor
  // explícito, cada tier usa um damping um pouco diferente.
  const requestedDamping = cfg.friction ?? 0.70;
  // Cada tier tem um piso de damping. Assim BAIXA continua barata e estável
  // mesmo quando um estilo antigo salvou um atrito menor.
  simulation.velocityDecay(Math.max(requestedDamping, currentTier.damping));
  updateLabelVisibility(zoomTransform.k);
}

const simulation = d3.forceSimulation(data.nodes)
  // Padrão do d3 é alpha=1 decaindo a 0.0228 (~300 ticks até parar) —
  // pensado pra layout começando do zero. Como já chegamos quase prontos,
  // um alpha inicial baixo + decaimento mais rápido faz a simulação gastar
  // só uns 40-60 ticks resolvendo sobreposição fina, não o layout inteiro.
  .force("center", d3.forceCenter(width / 2, height / 2))
  // Alpha cheio com decaimento suave: são ~180 ticks (uns 3s) de assentamento
  // VISÍVEL, que é o ponto — com 0.5/0.06 o grafo assentava antes de o olho
  // pegar e parecia estático. O custo continua baixo porque a semente já traz
  // a topologia certa (ver BLOOM acima); o que roda aqui é expansão e
  // colisão, não descoberta de layout.
  // alpha 0.7, não 1: a semente do Python já traz a topologia certa, então o
  // que roda aqui é acomodação, não descoberta de layout. Em alpha cheio o
  // arranque saía com velocidade mediana ~11px/tick, e num aparelho que
  // renderiza a 15fps cada frame vira um salto visível — daí a impressão de
  // agitação. Continua havendo expansão visível, só que sem o esticão inicial.
  .alpha(0.65)
  .alphaDecay(0.035)
  // Parar em 0.005 em vez do padrão 0.001 corta as últimas dezenas de ticks,
  // que só produzem tremor sub-pixel invisível mas mantêm o rAF girando (e o
  // celular acordado) sem nada acontecer na tela.
  .alphaMin(0.002)
  // velocityDecay é atrito: quanto menor, mais o nó carrega a velocidade do
  // tick anterior. Em 0.35 (abaixo até do padrão 0.4 do d3) os nós guardavam
  // momento demais, passavam do ponto de equilíbrio e voltavam, ficando
  // tremendo no lugar em vez de assentar. 0.55 preserva a expansão inicial
  // visível, mas mata a oscilação residual bem mais cedo. Só o valor inicial
  // fica fixo aqui — applyForces() (chamado logo abaixo) já reaplica a partir
  // de cfg.friction, então o slider "Atrito" do painel de Estilo sobrescreve
  // isto no mesmo tick, sem período em que o valor fixo esteja realmente em vigor.
  .velocityDecay(0.70);

applyForces(styleConfig);

// ---- Desenho -------------------------------------------------------------
// Estado de destaque/seleção/busca, lido por nodeDimmed()/edgeDimmed() a
// cada frame — evita recalcular o Set de vizinhos por nó (isso seria O(n²)
// se chamado dentro do loop de desenho; aqui é calculado uma vez por seleção
// e reaproveitado por todos os nós/arestas do frame).
let selectedNodeId = null;
let highlightSet = null;   // Set<id> dos vizinhos do nó selecionado, ou null
let searchMatchIds = null; // Set<id> do resultado da busca, ou null

function nodeDimmed(n) {
  if (searchMatchIds) return !searchMatchIds.has(n.id);
  if (highlightSet) return !highlightSet.has(n.id);
  return false;
}
function edgeDimmed(e) {
  const a = typeof e.source === "object" ? e.source.id : e.source;
  const b = typeof e.target === "object" ? e.target.id : e.target;
  // A busca vence a politica de visibilidade das arestas, e vem ANTES do
  // atalho "sempre". Com "sempre" (o default) a busca escurecia os nos e
  // deixava as ~2900 arestas em opacidade cheia: a tela virava uma teia
  // branca MAIS forte que antes da busca, e o resultado sumia embaixo dela.
  // "Sempre visivel" continua significando que aresta nunca some — mas numa
  // busca explicita o usuario pediu para isolar algo.
  //
  // Sobrevivem as arestas que TOCAM um resultado: elas sao a informacao util
  // (com quem o no encontrado se conecta), nao ruido.
  if (searchMatchIds) return !(searchMatchIds.has(a) || searchMatchIds.has(b));
  if (styleConfig.edgeVisibility === "sempre") return false;
  if (selectedNodeId) {
    return a !== selectedNodeId && b !== selectedNodeId;
  }
  return false;
}

function drawHalo(n) {
  const r = radiusOf(n) * 2.4;
  ctx.save();
  ctx.globalAlpha = nodeDimmed(n) ? 0.08 : 1;
  ctx.translate(n.x, n.y);
  ctx.scale(r, r);
  ctx.beginPath();
  ctx.arc(0, 0, 1, 0, Math.PI * 2);
  ctx.fillStyle = haloGradients[n.type] || "transparent";
  ctx.fill();
  ctx.restore();
}

// ---- Cache de sprites para nós com gradiente / glow "alto" --------------
// O agrupamento em Path2D (arestas, e nós quando são cor chapada sem glow
// "alto") só funciona porque um único fill()/stroke() serve pro grupo
// inteiro. Gradiente e shadowBlur não têm essa saída: um CanvasGradient é
// definido no espaço do usuário no momento do fill, então mesmo reaproveitando
// o MESMO objeto de gradiente (como nodeGradients já fazia) o navegador ainda
// precisa rasterizá-lo de novo a cada nó, porque translate/scale muda o
// espaço de destino a cada chamada — e shadowBlur é rasterização à parte,
// nó a nó, por definição. Ou seja: no default de fábrica (gradient: true,
// glow: "leve") e em glow "alto", esse é o custo que sobra depois de
// bateladar as arestas.
//
// A saída é pré-rasterizar cada APARÊNCIA (não cada nó) uma única vez num
// <canvas> offscreen e, depois, só ctx.drawImage() esse bitmap pronto por nó
// — um blit de pixels já prontos é ordens de magnitude mais barato que
// recriar gradiente/blur e rasterizar o arco a cada frame.
//
// O raio de um nó é contínuo (grau, bytes ou linhas, dependendo de
// sizeMode), então "um sprite por raio exato" nunca teria cache hit. Como a
// diferença visual entre um sprite desenhado a 12.0px e um a 12.4px é
// sub-pixel — imperceptível num círculo de poucos pixels — arredondamos o
// raio em faixas de RADIUS_STEP px pra escolher/gerar o sprite, e na hora de
// desenhar ainda esticamos (drawImage com dw/dh proporcionais) pro raio
// EXATO do nó. O tamanho final na tela continua fiel até a fração de pixel;
// só a "textura" do gradiente/blur é compartilhada entre nós de raio parecido.
const RADIUS_STEP = 1;   // faixas de 1px: degrau pequeno o bastante pra não notar
const RADIUS_MAX = 48;   // cobre o maior raio plausível (radiusBase + radiusScale*escala); acima disso reusa o maior sprite
const STROKE_PAD = 1.5;  // folga pra borda escura não ser cortada na margem do sprite
const GLOW_PAD = 8;      // folga extra só em glow "alto": o shadowBlur "vaza" além do arco
const spriteCache = new Map(); // chave "tipo|dim|bucket|dpr" -> HTMLCanvasElement

function radiusBucket(r) {
  return Math.min(RADIUS_MAX, Math.max(RADIUS_STEP, Math.round(r / RADIUS_STEP) * RADIUS_STEP));
}

// Meio-lado do sprite em coordenadas de MUNDO (antes do dpr) pro raio de um
// balde — inclui a folga de borda/blur, calculada em cima do bucket (não do
// raio real) porque o sprite inteiro é escalado depois no drawImage.
function spriteHalfSize(bucket) {
  return bucket + STROKE_PAD + (styleConfig.glow === "alto" ? GLOW_PAD : 0);
}

// Invalida o cache inteiro sempre que algo que afete a aparência do sprite
// muda (cor, gradiente, glow, raio, dpr) — chamado por applyStyle() e por
// resizeCanvas(). Não há por que reciclar sprites individualmente: o cache
// inteiro é barato de reconstruir (algumas centenas de bitmaps pequenos, sob
// demanda, não de uma vez), e "meio-invalidar" arriscaria deixar sprite
// velho em tela depois do usuário mexer no painel de Estilo.
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
  const size = half * 2; // lado do sprite em px "de mundo" (CSS), antes do dpr

  sprite = document.createElement("canvas");
  // HiDPI: o bitmap do sprite precisa nascer na resolução FÍSICA do
  // aparelho, senão fica borrado em tela retina/mobile mesmo com o
  // drawImage depois escalando "certo" — exatamente o mesmo motivo de
  // resizeCanvas() multiplicar por dpr no canvas principal. Aqui é feito
  // uma vez na criação do sprite, não a cada frame.
  const px = Math.max(2, Math.ceil(size * dpr));
  sprite.width = px;
  sprite.height = px;
  const sctx = sprite.getContext("2d");
  sctx.scale(px / size, px / size); // desenha em coordenadas de mundo (0..size)
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
  // Textura esférica: opcional, desligada por padrão (custa mais um par de
  // gradientes por sprite — barato porque é uma vez só, cacheado, mas não
  // é grátis). "source-atop" restringe as duas camadas abaixo aos pixels
  // já opacos do disco que acabou de ser pintado, sem precisar refazer o
  // path de recorte — mais simples e mais barato que clip().
  if (styleConfig.sphereShading) {
    sctx.globalCompositeOperation = "source-atop";
    // Brilho especular: ponto de luz deslocado pro canto superior-esquerdo,
    // como um reflexo de estúdio numa bola de vidro/plástico.
    const spec = sctx.createRadialGradient(
      cx - bucket * 0.38, cy - bucket * 0.42, 0,
      cx - bucket * 0.38, cy - bucket * 0.42, bucket * 0.9
    );
    spec.addColorStop(0, "rgba(255,255,255,0.75)");
    spec.addColorStop(0.35, "rgba(255,255,255,0.16)");
    spec.addColorStop(1, "rgba(255,255,255,0)");
    sctx.fillStyle = spec;
    sctx.fillRect(0, 0, size, size);
    // Sombra de contato no quadrante oposto (inferior-direito) — sem ela o
    // brilho sozinho lê como uma mancha clara, não como volume 3D; os dois
    // juntos simulam luz vindo de um único lado, como numa esfera de verdade.
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

function drawNodeSprite(n) {
  const r = radiusOf(n);
  if (r <= 0) return;
  const dimmed = nodeDimmed(n);
  const sprite = getNodeSprite(n.type, dimmed, r);
  const bucket = radiusBucket(r);
  // O sprite foi rasterizado pro raio do BALDE; escalamos aqui pro raio
  // EXATO do nó (desvio no máximo RADIUS_STEP/2, imperceptível) em vez de
  // usar o bucket puro — assim o tamanho final na tela não tem degrau.
  const scale = r / bucket;
  const dw = spriteHalfSize(bucket) * 2 * scale;
  ctx.drawImage(sprite, n.x - dw / 2, n.y - dw / 2, dw, dw);
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

function drawLabel(n) {
  // font/fillStyle/textAlign já vêm setados uma vez só pelo chamador (draw())
  // antes do loop — não mudam de rótulo pra rótulo, só a posição e o alpha
  // de esmaecimento mudam aqui. Reatribuir `ctx.font` por rótulo forçaria o
  // Canvas a reparsear a string de fonte a cada um dos ~1100 nós.
  const dimmed = nodeDimmed(n);
  const r = radiusOf(n);
  ctx.globalAlpha = dimmed ? 0.08 : (isLightTheme() ? 0.78 : 0.85);
  ctx.fillText(n.title, n.x, n.y - (2 + r));
}

// ---- Tingimento de fundo por tag ------------------------------------------
// Hash determinístico (djb2) de string pra matiz 0-360: a mesma tag sempre
// cai na mesma cor entre recarregamentos, sem precisar guardar um mapa em
// lugar nenhum.
function tagHue(tag) {
  let h = 5381;
  for (let i = 0; i < tag.length; i++) h = ((h * 33) ^ tag.charCodeAt(i)) >>> 0;
  return h % 360;
}

// Um blob GLOBAL por tag (centro de massa + raio de dispersão de TODOS os
// nós daquela tag) foi a primeira tentativa aqui, e não funcionava: tag não
// entra na física do layout (só wikilink entra), então a maioria das tags
// está espalhada pelo grafo inteiro — o "blob" saía do tamanho do grafo
// inteiro, com opacidade quase uniforme em qualquer ponto da tela.
// Efetivamente invisível.
//
// A solução é local, não global: um "dab" pequeno e bem fraco em cima de
// CADA nó, pra cada tag que ele carrega, com blend ADITIVO
// (globalCompositeOperation "lighter"). Um dab sozinho quase não muda nada;
// mas onde vários nós da MESMA tag caem perto uns dos outros no layout (o
// que tende a acontecer de verdade — essays da mesma tag costumam se citar
// e o wikilink os aproxima), os dabs se empilham e a região acumula cor,
// revelando a densidade real da tag naquele ponto do grafo. "Pinta mais ou
// menos" literalmente: mais onde a tag está concentrada, quase nada onde
// está isolada ou espalhada.
//
// Sprite cacheado por tag (não por nó): mesma ideia de getNodeSprite() —
// sem isso seriam milhares de createRadialGradient()+fill() por frame (um
// por par nó×tag), caro demais até pra uma opção já opt-in.
const TAG_DAB_SIZE = 170; // diâmetro do dab em px "de mundo", antes do dpr — raio de ação maior que o original (110)
const tagTintSprites = new Map(); // tag -> HTMLCanvasElement
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
  // Saturação e luminosidade um pouco acima do fundo (que já é bem escuro,
  // ~12% de luminosidade no padrão de fábrica): perto DEMAIS do preto de
  // fundo e o "lighter" não tem o que somar — o efeito também sumiria,
  // igual ao blob antigo. Ainda assim continua escuro (11%), só o
  // suficiente pra ler como matiz, não como cor chapada.
  g.addColorStop(0, `hsla(${hue}, 60%, 11%, 0.9)`);
  g.addColorStop(1, `hsla(${hue}, 60%, 11%, 0)`);
  sctx.fillStyle = g;
  sctx.fillRect(0, 0, TAG_DAB_SIZE, TAG_DAB_SIZE);
  tagTintSprites.set(tag, sprite);
  return sprite;
}

// Desenhado ANTES de arestas/nós, ainda dentro do bloco de transform de
// mundo (mesmo pan/zoom) — funciona como camada de fundo. `inView` (já
// calculado pelo chamador pra cull de nó/aresta) também limita o custo aqui:
// não pinta o que está fora da tela.
function drawTagTint(inView) {
  ctx.globalCompositeOperation = "lighter";
  const half = TAG_DAB_SIZE / 2;
  data.nodes.forEach(n => {
    if (!isNodeVisible(n) || n.x == null || !n.tags || !n.tags.length || !inView(n)) return;
    n.tags.forEach(tag => {
      ctx.drawImage(getTagTintSprite(tag), n.x - half, n.y - half, TAG_DAB_SIZE, TAG_DAB_SIZE);
    });
  });
  ctx.globalCompositeOperation = "source-over";
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
        // moveTo antes do arc: sem isto o primeiro arco do balde ficaria
        // ligado ao ponto anterior do path por uma linha reta invisível
        // (fillStyle não desenha contorno, mas o subpath ainda "gruda").
        ctx.moveTo(x + s.r, y);
        ctx.arc(x, y, s.r, 0, Math.PI * 2);
      }
      ctx.fillStyle = `rgba(255,255,255,${starBucketOpacity[i]})`;
      ctx.fill();
    }
  }

  ctx.save();
  ctx.translate(zoomTransform.x, zoomTransform.y);
  ctx.scale(zoomTransform.k, zoomTransform.k);

  // Culling: só desenha o que cai dentro do viewport (+ margem), em
  // coordenadas de mundo — evita gastar tempo com milhares de nós fora da
  // tela quando o usuário dá zoom in numa região pequena do grafo.
  const [wx0, wy0] = zoomTransform.invert([0, 0]);
  const [wx1, wy1] = zoomTransform.invert([width, height]);
  const pad = 80;
  const inView = (n) => n.x >= wx0 - pad && n.x <= wx1 + pad && n.y >= wy0 - pad && n.y <= wy1 + pad;

  if (styleConfig.tagTint) drawTagTint(inView);

  if (styleConfig.edgeVisibility !== "off") {
    // Batelada de arestas — o maior ganho do arquivo inteiro. Antes: um
    // beginPath/moveTo/lineTo/stroke POR aresta (2547 chamadas de stroke()
    // por frame); cada stroke() é uma rasterização própria da GPU/CPU, então
    // o custo por frame crescia linear com o nº de arestas, não com o nº de
    // pixels desenhados. Como toda aresta de um mesmo grupo visual (normal
    // vs. esmaecida × sólida vs. tracejada) compartilha cor/alpha/dash,
    // acumulamos todos os segmentos do grupo num único Path2D e chamamos
    // stroke() uma vez por grupo — 4 chamadas fixas por frame, não 2547.
    // Path2D (em vez de ctx.beginPath()) porque os 4 grupos são intercalados
    // durante a única passada pelas arestas: só um path pode estar "aberto"
    // no ctx por vez, mas 4 objetos Path2D podem acumular em paralelo.
    const edgeColor = styleConfig.colors.edge;
    const edgeAlphaNormal = styleConfig.edgeOpacity;
    const pathSolidNormal = new Path2D();
    const pathSolidDim = new Path2D();
    const pathDashNormal = new Path2D();
    const pathDashDim = new Path2D();
    data.edges.forEach(e => {
      const s = endpoint(e.source), t = endpoint(e.target);
      if (!s || !t || !isNodeVisible(s) || !isNodeVisible(t)) return;
      if (!inView(s) && !inView(t)) return;
      const dim = edgeDimmed(e);
      const isRef = e.kind === "reference";
      const path = isRef
        ? (dim ? pathDashDim : pathDashNormal)
        : (dim ? pathSolidDim : pathSolidNormal);
      path.moveTo(s.x, s.y);
      path.lineTo(t.x, t.y);
    });
    ctx.lineWidth = 1.2 / zoomTransform.k;
    ctx.strokeStyle = edgeColor;
    ctx.setLineDash([]);
    ctx.globalAlpha = edgeAlphaNormal;
    ctx.stroke(pathSolidNormal);
    ctx.globalAlpha = 0.08;
    ctx.stroke(pathSolidDim);
    ctx.setLineDash([3, 3]);
    ctx.globalAlpha = edgeAlphaNormal;
    ctx.stroke(pathDashNormal);
    ctx.globalAlpha = 0.08;
    ctx.stroke(pathDashDim);
    ctx.setLineDash([]);
    ctx.globalAlpha = 1;
  }

  // Halo pulado inteiro no tier "baixa" — é o item decorativo mais caro
  // depois do rótulo, e o tier baixo já existe justamente pra aparelhos sem
  // fôlego de sobra.
  // Em fundo claro o halo vira uma sombra colorida em volta de cada bolinha e
  // suja o mapa inteiro; no escuro ele e o que da profundidade. Some no claro.
  const drawHalos = styleConfig.glow === "leve" && currentTier !== PERFORMANCE_TIERS.baixa
    && !isLightTheme();
  if (drawHalos) {
    // Halo usa gradiente radial recentrado por nó (translate/scale
    // individual) — não dá pra bater em lote sem trocar o visual, porque um
    // único CanvasGradient não se "reposiciona" por arco dentro do mesmo
    // path. Fica no caminho por-nó de propósito.
    data.nodes.forEach(n => {
      if (!isNodeVisible(n) || !inView(n)) return;
      drawHalo(n);
    });
  }

  // Batelada de nós por cor sólida — mesma lógica das arestas. Só é possível
  // quando o preenchimento é cor chapada: gradiente (padrão) recentra um
  // CanvasGradient por nó, e glow "alto" usa shadowBlur, que precisa
  // desenhar/rasterizar nó a nó pra não borrar o halo dos vizinhos. Com os
  // dois desligados, agrupamos por cor+esmaecimento (poucas combinações) e
  // fazemos um fill()+stroke() por grupo em vez de um par por nó — de
  // ~1122 pares fill/stroke para menos de uma dezena.
  const canBatchNodes = styleConfig.glow !== "alto" && !styleConfig.gradient;
  if (canBatchNodes) {
    const nodeGroups = new Map(); // "cor|esmaecido" -> Path2D
    data.nodes.forEach(n => {
      if (!isNodeVisible(n) || !inView(n)) return;
      const color = typeColorRaw(n);
      const dim = nodeDimmed(n);
      const key = color + "|" + dim;
      let path = nodeGroups.get(key);
      if (!path) {
        path = new Path2D();
        nodeGroups.set(key, path);
      }
      const r = radiusOf(n);
      path.moveTo(n.x + r, n.y);
      path.arc(n.x, n.y, r, 0, Math.PI * 2);
    });
    // Contorno escuro é idêntico pra todo mundo (cor e espessura fixas,
    // independente do raio do nó — igual ao caminho individual, que
    // compensava o raio com translate/scale + lineWidth=1/r; aqui os arcos
    // já estão em coordenadas de mundo sem esse scale por nó, então
    // lineWidth=1 reproduz a mesma espessura final).
    ctx.lineWidth = 1;
    ctx.strokeStyle = "#0b1220";
    nodeGroups.forEach((path, key) => {
      const sep = key.lastIndexOf("|");
      const color = key.slice(0, sep);
      const dim = key.slice(sep + 1) === "true";
      ctx.globalAlpha = dim ? 0.08 : 1;
      ctx.fillStyle = color;
      ctx.fill(path);
      ctx.stroke(path);
    });
    ctx.globalAlpha = 1;
  } else {
    // gradient ligado e/ou glow "alto": nenhum dos dois bateria num Path2D
    // em grupo (ver comentário acima de getNodeSprite), então o caminho aqui
    // é o cache de sprites — drawImage por nó em vez de fill/stroke com
    // gradiente ou shadowBlur recalculados a cada um.
    data.nodes.forEach(n => {
      if (!isNodeVisible(n) || !inView(n)) return;
      drawNodeSprite(n);
    });
  }

  if (labelsShown) {
    // Lê o estilo uma vez fora do loop apertado: font/fillStyle não mudam
    // por nó, só a posição — evitar reatribuir a mesma string de fonte a
    // cada rótulo economiza reparse de `ctx.font` (não é grátis no Canvas).
    ctx.font = `${styleConfig.labelSize}px -apple-system, "Segoe UI", Helvetica, Arial, sans-serif`;
    ctx.textAlign = "center";
    ctx.fillStyle = getLabelColor();
    data.nodes.forEach(n => {
      if (n.type === "reference" || !isNodeVisible(n) || !inView(n)) return;
      drawLabel(n);
    });
  }

  ctx.restore();
}

// Damping adaptativo simples: só atua quando há pouco movimento e muitos
// nós estão invertendo a velocidade ao mesmo tempo — padrão típico de
// oscilação residual. Não interfere no movimento normal do layout.
let adaptiveDampingTicks = 0;
let autoFitTicks = 0;
let previousVx = data.nodes.map(n => n.vx || 0);
let previousVy = data.nodes.map(n => n.vy || 0);

simulation.on("tick", () => {
  let moving = 0;
  let reversals = 0;
  data.nodes.forEach((n, i) => {
    const vx = n.vx || 0, vy = n.vy || 0;
    const speed = Math.hypot(vx, vy);
    if (speed > 0.15) moving++;
    if (speed > 0.15 && Math.hypot(previousVx[i], previousVy[i]) > 0.15 &&
        vx * previousVx[i] + vy * previousVy[i] < 0) reversals++;
    previousVx[i] = vx;
    previousVy[i] = vy;
  });

  const reversalRatio = moving ? reversals / moving : 0;
  if (adaptiveDampingTicks > 0) {
    adaptiveDampingTicks--;
    if (adaptiveDampingTicks === 0) simulation.velocityDecay(
      Math.max(styleConfig.friction ?? 0.70, currentTier.damping)
    );
  } else if (moving > 0 && reversalRatio > 0.30) {
    adaptiveDampingTicks = 8;
    simulation.velocityDecay(Math.min(0.88,
      Math.max(styleConfig.friction ?? 0.70, currentTier.damping) + 0.14));
  }

  rebuildQuadtree();
  // Enquanto o leitor não escolheu o próprio enquadramento, a moldura segue o
  // layout. Amarrar isso ao tick e não ao relógio é o que faz funcionar em
  // qualquer ritmo: numa aba em segundo plano o rAF é estrangulado e um
  // agendamento por tempo acabava enquadrando a versão ainda apertada do
  // grafo. Um reencaixe a cada 4 ticks custa um passe O(n) sobre posições que
  // o tick já percorreu.
  if (!userAdjustedView && ++autoFitTicks % 4 === 0) fitToScreen(true);
  scheduleDraw();
});

// Aplica cores/raio/rótulo/halo salvos (ou o padrão vindo do Python) agora
// que styleConfig/simulation existem — silencioso porque redesenhar já
// basta pra ficar certo visualmente, sem precisar reiniciar a simulação que
// acabou de nascer quase assentada.
applyStyle(styleConfig, { silent: true });
rebuildQuadtree();
scheduleDraw();

// Reaquecer a simulação inteira a alphaTarget 0.3 é o padrão de livro-texto
// do d3, pensado pra grafos pequenos — com centenas/milhares de nós e carga
// repulsiva entre todos eles, esse alpha alto durante o arrasto faz a
// colisão inteira ser recalculada a cada tick, e ao soltar o nó o grafo
// "explode" num pulo generalizado em vez de só reacomodar a vizinhança do
// nó largado. Grafos grandes usam um alvo bem mais baixo: o suficiente pra
// arestas/colisão do próprio nó arrastado acompanharem o mouse, sem jogar
// energia extra no resto do sistema.
const DRAG_ALPHA_TARGET = data.nodes.length > 300 ? 0.025 : 0.12;
let dragMoved = false;

// Em Canvas não há elemento por nó pra prender um d3.drag — o "subject" faz
// hit-testing via quadtree em coordenadas de mundo (invertendo o transform
// de zoom atual), e start/drag/end trabalham com esse mesmo nó encontrado.
// event.x/event.y do d3.drag continuam em pixels de TELA (o drag não sabe
// nada sobre zoom), então cada handler inverte o transform de novo.
function dragsubject(event) {
  // Diferente de dragged(), aqui NÃO usamos d3.pointer(event, canvas): o
  // `event` recebido pelo accessor `subject` é o DragEvent do d3-drag, e
  // d3.pointer desembrulharia `.sourceEvent` até o evento nativo — que no
  // toque é um TouchEvent sem clientX/clientY (isso mora em event.touches[]).
  // O próprio d3-drag já calculou event.x/event.y certos em pixels do
  // container (inclusive para toque, chamando pointer() com o Touch, não com
  // o TouchEvent), então usamos esses valores prontos e só invertemos o zoom.
  const [wx, wy] = zoomTransform.invert([event.x, event.y]);
  return findNodeAt(wx, wy);
}
// `dragOffsetX/Y` guarda a distância entre o CENTRO do nó e o ponto exato do
// dedo/cursor no instante do toque. Sem isso, dragged() faria fx/fy = posição
// absoluta do ponteiro invertida pelo zoom, o que recentraliza o nó embaixo
// do dedo de golpe assim que o gesto começa — visto como "pula pro lado" por
// quem não tocou bem no centro do círculo (comum em toque: o dedo cobre uma
// área bem maior que o nó de poucos pixels, e o ponto de contato reportado
// raramente cai exatamente no centro). Guardando o deslocamento inicial e
// somando ele de novo em todo dragged(), o nó acompanha o dedo pelo mesmo
// delta que ele percorre, preservando onde exatamente ele foi pego — e
// qualquer viés sistemático residual de coordenada (toque vs. mouse, DPR)
// cancela na subtração em vez de aparecer como um salto constante.
let dragOffsetX = 0, dragOffsetY = 0;
function dragstarted(event) {
  if (!event.active) simulation.alphaTarget(DRAG_ALPHA_TARGET).restart();
  const [wx, wy] = zoomTransform.invert([event.x, event.y]);
  dragOffsetX = event.subject.x - wx;
  dragOffsetY = event.subject.y - wy;
  event.subject.fx = event.subject.x;
  event.subject.fy = event.subject.y;
  dragMoved = false;
}
function dragged(event) {
  const [wx, wy] = zoomTransform.invert([event.x, event.y]);
  event.subject.fx = wx + dragOffsetX;
  event.subject.fy = wy + dragOffsetY;
  dragMoved = true;
  scheduleDraw();
}
// Double-tap é detectado AQUI dentro, e não num listener de "touchend" no
// canvas, porque o touchended do próprio d3-drag chama stopImmediatePropagation()
// sempre que há um gesto ativo — isto é, exatamente quando o toque caiu em cima
// de um nó. Um listener registrado depois do d3.drag nunca rodaria no único caso
// que interessa. Aqui já estamos dentro do gesto, então nada pode nos calar.
const DOUBLE_TAP_MS = 350;
const DOUBLE_TAP_PX = 30;
let lastTap = null; // { x, y, t } em pixels do container

function dragended(event) {
  if (!event.active) simulation.alphaTarget(0);
  event.subject.fx = null;
  event.subject.fy = null;
  // Sem movimento perceptível = clique, não arrasto: seleciona o nó (a
  // versão SVG tinha um listener de "click" próprio; em Canvas o mesmo
  // mousedown/touchstart já foi capturado pelo d3.drag, então tratamos o
  // "clique parado" aqui mesmo).
  if (!dragMoved) {
    // No desktop o duplo-clique já é tratado pelo listener de "dblclick"; só
    // o toque precisa da detecção manual, senão um duplo-clique de mouse
    // abriria o nó duas vezes.
    const doToque = event.sourceEvent && String(event.sourceEvent.type).startsWith("touch");
    const agora = performance.now();
    if (doToque && lastTap
        && agora - lastTap.t < DOUBLE_TAP_MS
        && Math.hypot(event.x - lastTap.x, event.y - lastTap.y) < DOUBLE_TAP_PX) {
      lastTap = null;
      openNode(event.subject);
    } else {
      lastTap = doToque ? { x: event.x, y: event.y, t: agora } : null;
      selectNode(event.subject);
    }
  }
  scheduleDraw();
}
canvasSel.call(d3.drag()
  .subject(dragsubject)
  .on("start", dragstarted)
  .on("drag", dragged)
  .on("end", dragended));

// Ação compartilhada entre dblclick (desktop) e double-tap (mobile), para não
// duplicar a lógica de abrir o nó em dois listeners.
function openNodeAt(wx, wy, event) {
  const node = findNodeAt(wx, wy);
  if (node) { event.stopPropagation(); openNode(node); }
  return node;
}

canvas.addEventListener("dblclick", (event) => {
  const pt = d3.pointer(event, canvas);
  const [wx, wy] = zoomTransform.invert(pt);
  openNodeAt(wx, wy, event);
});

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

// ---- Painel recolhível (tela pequena) ----
const panelEl = document.getElementById("panel");
const toggleEl = document.getElementById("panel-toggle");
// "Tela pequena" agora é decidido pela própria media query que re-layoutiza o
// painel (não pelo display do botão: o botão existe em toda tela agora, então
// `display !== "none"` seria sempre verdadeiro e quebraria fitToScreen etc.).
const telaPequena = () => window.matchMedia("(max-width: 720px), (pointer: coarse) and (max-width: 900px)").matches;

function definirPainel(aberto) {
  panelEl.classList.toggle("collapsed", !aberto);
  // O inline vence a cascata e não depende de a media query ser reavaliada —
  // recolhe o painel em qualquer tela, desktop inclusive.
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
  // Espera o layout assentar antes de medir (o cartão acabou de ser escrito).
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

// Em tela pequena o painel começa fechado: quem abre o grafo no celular quer
// ver o grafo, não a legenda. No desktop a media query esconde o botão e a
// classe `collapsed` não tem efeito nenhum, então nada muda.
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
// Um essay toca dezenas de conceitos, entidades e referencias. Listadas juntas
// viram parede; separadas por tipo em abas, a mesma informacao fica legivel e
// navegavel em dois cliques. O mesmo componente serve ao cartao de detalhe e a
// linha expandida do indice, para os dois nunca divergirem.
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
  // Vindo do índice, o nó pode ser de um tipo que está oculto na legenda.
  // Reexibir é menos surpreendente do que clicar e não ver nada acontecer.
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
  // No build leve não há leitor embutido, mas há o HTML exportado — o botão
  // "Ler" continua existindo, só que abre numa aba em vez do overlay.
  const readHref = !hasReader && d.type === "essay" ? d.htmlFile : null;
  // O cartão de detalhe mora dentro do painel, mas o painel só deve abrir
  // por ação explícita no botão ☰ — nunca sozinho por causa de um toque no
  // grafo. Num celular com o painel recolhido, o destaque no próprio grafo
  // (nós vizinhos) já é o feedback da seleção; o cartão de detalhe fica
  // pronto e some ao abrir o painel manualmente.
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
  // `button.read-btn` e não `.read-btn`: no build leve o botão de ler é um
  // <a> com a MESMA classe (mesmo desenho, destino diferente). Um seletor
  // solto pegaria a âncora, que não tem data-read, e chamaria openReader(null).
  const readBtn = detailEl.querySelector("button.read-btn");
  if (readBtn) readBtn.addEventListener("click", (e) => {
    e.stopPropagation();
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
  // Ordem de preferência para abrir um essay:
  //   1. leitor embutido  (build com --reader: o overlay abre sem sair da página)
  //   2. HTML exportado   (build leve: output/html/<slug>.html, já com todo o
  //                        design do essay e cacheado pelo navegador)
  //   3. markdown cru     (nem um nem outro disponível — nunca deixa sem ação)
  // Checagem sincrona no mapa: openReader é async e sempre devolve Promise.
  if (d.type === "essay") {
    const slug = essaySlugOf(d);
    if (slug && readerEssays()[slug]) { openReader(slug); return; }
    if (d.htmlFile) { window.open(d.htmlFile, "_blank"); return; }
  }
  if (d.file) {
    window.open("../../" + d.file, "_blank");
  }
}

// Clique num nó já é resolvido em dragended() (mousedown/touchstart parado
// sem movimento = clique). Aqui só sobra o clique no fundo, pra resetar o
// destaque — dispara depois do dragend, então checar "achou nó aqui?" evita
// desfazer por engano a seleção que acabou de acontecer no mesmo gesto.
canvas.addEventListener("click", (event) => {
  const pt = d3.pointer(event, canvas);
  const [wx, wy] = zoomTransform.invert(pt);
  if (!findNodeAt(wx, wy)) resetHighlight();
});

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

// ---- Legenda clicável com visibilidade independente para cada tipo ----
// (`hiddenTypes` e `isNodeVisible` moram lá em cima, junto do quadtree: são
// lidos por rebuildQuadtree()/draw(), que rodam bem antes daqui.)

function updateVisibility() {
  recomputeVisibleDegrees();
  rebuildQuadtree(); // hit-test não deve mais achar nós de um tipo oculto

  // Reacomoda o layout: bolinhas menores pedem menos espaço entre si.
  // Respeita o mesmo toggle de colisão do painel de Estilo.
  if (styleConfig.collision === false) {
    simulation.force("collide", null);
  } else {
    simulation.force("collide", d3.forceCollide().radius(d => (7.8 + radiusOf(d)) * (styleConfig.spacing || 1) * currentTier.collisionScale)
      .strength(1.25)
      .iterations(currentTier.collideIterations));
  }
  simulation.alpha(0.35).restart();
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

updateVisibility();

// ---- Fit-to-screen inicial (mobile) ------------------------------------
// No desktop o grafo nasce em torno do centro e cabe razoavelmente numa
// tela grande. No celular a viewport é estreita e a simulação de forças
// espalha os nós livremente pelo espaço "de mundo" (que não tem relação
// nenhuma com o tamanho da tela) — sem isto, quem abre o grafo no celular
// vê só um pedaço cortado e precisa dar zoom out à mão antes de enxergar
// qualquer estrutura.
function fitToScreen(instant, force) {
  // `force` (botão "Ajustar à tela") ignora as duas condições que existem só
  // para o auto-fit silencioso de carga em celular: aqui é um clique
  // explícito do usuário, então deve funcionar em qualquer tamanho de tela e
  // mesmo depois de o usuário já ter mexido no zoom manualmente.
  // O mapa abre mostrando a base inteira em qualquer tela: um mapa que comeca
  // cortado esconde justamente o que ele existe para mostrar. So nao reencaixa
  // depois que o leitor mexeu no enquadramento por conta propria.
  if (!force && userAdjustedView) return;
  const visible = data.nodes.filter(n => n.x != null && n.y != null && isNodeVisible(n));
  if (!visible.length) return;

  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
  visible.forEach(n => {
    minX = Math.min(minX, n.x); maxX = Math.max(maxX, n.x);
    minY = Math.min(minY, n.y); maxY = Math.max(maxY, n.y);
  });
  const bboxW = Math.max(1, maxX - minX);
  const bboxH = Math.max(1, maxY - minY);
  const padding = 48;
  const [minScale, maxScale] = zoom.scaleExtent();
  const scale = Math.max(minScale, Math.min(
    maxScale,
    0.92 / Math.max(bboxW / (width - padding * 2), bboxH / (height - padding * 2))
  ));
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
  const transform = d3.zoomIdentity.translate(width / 2, height / 2).scale(scale).translate(-cx, -cy);

  (instant ? canvasSel : canvasSel.transition().duration(280)).call(zoom.transform, transform);
  return scale;
}

// A simulação esfria e emite "end" sozinha (alphaDecay padrão) — nesse ponto
// os nós pararam de se mexer e o bounding box é definitivo, então este é o
// último reencaixe. O acompanhamento durante a abertura vive no "tick".
simulation.on("end.fit", () => fitToScreen(false));

// Aba aberta em segundo plano: o navegador estrangula o requestAnimationFrame,
// a simulação quase não avança e o mapa fica parado num enquadramento antigo.
// Quando a aba finalmente aparece, reencaixa — a menos que o leitor já tenha
// escolhido o próprio enquadramento.
document.addEventListener("visibilitychange", () => {
  if (!document.hidden && !userAdjustedView) fitToScreen(false);
});

// ---- Modal: Índice por tipo ----
const modalOverlay = document.getElementById("modal-overlay");
const modalBody = document.getElementById("modal-body");
document.getElementById("modal-close").addEventListener("click", () => modalOverlay.classList.remove("open"));
modalOverlay.addEventListener("click", (e) => { if (e.target === modalOverlay) modalOverlay.classList.remove("open"); });

const TYPE_LABELS = {
  essay: "Essays", concept: "Concepts", entity: "Entities",
  insights: "Insights", reference: "Referências",
};

// O plural nomeia uma aba ("Concepts 22"); o singular nomeia o nó aberto no
// cartão de detalhe, onde "ESSAYS" para um único essay soaria errado.
const TYPE_LABEL_ONE = {
  essay: "Essay", concept: "Concept", entity: "Entity",
  insights: "Insight", reference: "Referência",
};

function escapeHtml(s) {
  return String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
}

const MATURIDADE_LABELS = { solta: "Solta", germinando: "Germinando", madura: "Madura", absorvida: "Absorvida" };

// ---- Leitor embutido -----------------------------------------------------
// READER_DATA.essays[slug] = { t, tags, html } — html com masthead+content+
// footer EXATOS do export (mesmo template pandoc). READER_DATA.css = CSS do
// template (tokens/masthead/caixas/fontes) já adaptado para Shadow Root.
// MathJax não enxerga dentro de shadow: o fragmento é tipografado num
// staging no light-DOM e só então enxertado.
const READER_BY_SLUG = null; // legado — usar readerEssays() (payload é lazy)
function readerEssays() { ensureReaderData(); return READER_DATA.essays || {}; }
const READER_CSS = READER_DATA.css || "";
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

// Inflado da PROPRIA tag, so na primeira vez que um essay com matematica
// abre. Um ensaio de filosofia nunca descomprime os 2,3 MB do bundle.
function ensureMathJaxInjected() {
  if (mathJaxInjected) return;
  const src = READER_DATA.mathjax || inflateJsonFromTag("sb-mathjax-data");
  if (!src) return;
  mathJaxInjected = true;
  const s = document.createElement("script");
  s.textContent = src;
  document.head.appendChild(s); // executa inline, sincrono ao inserir
}

// Pandoc emite matematica como \\(..\\) / \\[..\\] envolvidos em
// <span class="math">. Sem nenhum, nao ha o que tipografar e o MathJax nem
// precisa entrar na pagina.
function fragmentHasMath(html) {
  return typeof html === "string" && html.indexOf('class="math') !== -1;
}

// O startup do MathJax v3 é async; resolve assim que typesetPromise existir.
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
  // ainda é "" (placeholder), e o shadow nasceria sem estilo nenhum.
  readerShadow.innerHTML = `<style>${READER_DATA.css || ""}</style><div class="rd-root"></div>`;
  readerRoot = readerShadow.querySelector(".rd-root");
  // Navegação por âncora DENTRO do shadow: o navegador não rola por #id que
  // só existe na árvore shadow — intercepta e rola aqui. Fallback normalizado
  // (sem acentos/pontuação): slugs do Sumário escrito à mão podem divergir
  // do id que o gfm_auto_identifiers gerou para o heading.
  function normSlug(s) {
    return s.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")
            .replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  }
  readerRoot.addEventListener("click", (e) => {
    const a = e.target.closest && e.target.closest('a[href^="#"]');
    if (!a) return;
    const id = decodeURIComponent(a.getAttribute("href").slice(1));
    let t = null;
    try { t = readerRoot.querySelector('[id="' + id.replace(/"/g, '\\"') + '"]'); } catch (_) {}
    if (!t) {
      const nid = normSlug(id);
      for (const el of readerRoot.querySelectorAll("[id]")) {
        if (normSlug(el.id) === nid) { t = el; break; }
      }
    }
    if (t) { e.preventDefault(); t.scrollIntoView({ behavior: "smooth", block: "start" }); }
  });
}

// Porta do JS do template (essay_template.html): âncoras §, capítulos
// auto-numerados e rótulos semânticos (Introdução/Conclusão...).
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
  const SECTION_RE = /^\\s*(?:(?:se[çc][aã]o|cap[íi]tulo|parte)\\s*)?(?:\\d+|[IVXLC]+)?\\s*[.:\\-—–]?\\s*(introdu[çc][aã]o|conclus[aã]o|resumo(?:\\s+executivo)?|pref[áa]cio|pr[óo]logo|ep[íi]logo|posf[áa]cio|p[óo]s-?escrito|agradecimentos|ap[êe]ndice|anexos?)\b/i;
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
  // Meta-row da capa: tempo de leitura (~200 palavras/min) e capítulos —
  // ou a marca de rascunho, que ocupa o LUGAR dela. Num draft a duração
  // ainda não significa nada, e o que o leitor precisa saber é o estado.
  if (h2s.length) {
    // `readerRoot` e nao `readerArticle`: o conteudo do leitor vive DENTRO
    // do shadow root, e querySelector no host nao atravessa a fronteira —
    // `by` vinha null e a meta-row nunca era inserida. O leitor ficou sem
    // tempo de leitura desde que o shadow foi introduzido.
    const by = readerRoot.querySelector(".byline");
    if (by) {
      const entry = readerEssays()[readerCurrentSlug] || {};
      const meta = document.createElement("p");
      meta.className = "cover-meta";
      if (entry.status === "draft") {
        meta.classList.add("cover-draft");
        meta.textContent = "Rascunho";
      } else {
        const words = (content.innerText || "").trim().split(/\\s+/).length;
        const mins = Math.max(1, Math.round(words / 200));
        meta.textContent = "~" + mins + " min de leitura · " + h2s.length + " capítulos";
      }
      by.parentNode.insertBefore(meta, by.nextSibling);
    }
  }
}

// Tema: mesma regra do template — mobile escuro, desktop claro; toggle
// persiste na MESMA chave 'sb-theme' usada pelos exports (consistência).
function applyReaderTheme() {
  let saved = null;
  try { saved = localStorage.getItem("sb-theme"); } catch (e) {}
  const def = window.matchMedia("(min-width:901px)").matches ? "light" : "dark";
  const theme = saved || def;
  readerArticle.setAttribute("data-theme", theme); // :host([data-theme]) no shadow
  return theme;
}

document.getElementById("reader-theme").addEventListener("click", () => {
  if (!readerOpenState) return;
  const cur = readerArticle.getAttribute("data-theme") || "dark";
  const next = cur === "dark" ? "light" : "dark";
  readerArticle.setAttribute("data-theme", next);
  try { localStorage.setItem("sb-theme", next); } catch (e) {}
});

async function openReader(slug) {
  ensureReaderData();
  const entry = readerEssays()[slug];
  if (!entry) return false;
  readerCurrentSlug = slug;
  initReaderShadow();
  const staging = document.createElement("div");
  staging.style.display = "none";
  staging.innerHTML = entry.html;
  document.body.appendChild(staging);
  if (fragmentHasMath(entry.html)) {
    ensureMathJaxInjected();
    await typesetElement(staging);
  }
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
  // deep-link direto (#read=... colado na URL) não há entry para estourar.
  if (!fromPop && history.state && history.state.rd) history.back();
}

// Progresso de leitura — mesma barra do template, presa ao scroll do overlay.
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

// Deep-link: MySecondBrain.html#read=<slug> abre direto no essay.
(function () {
  const m = location.hash.match(/^#read=([^\\s]+)$/);
  if (!m) return;
  requestAnimationFrame(() => openReader(decodeURIComponent(m[1])));
})();

// Navegação fragment-only (colar outro #read= na mesma aba, voltar/avançar
// entre deep-links) NÃO recarrega o documento — sem este listener, colar um
// link novo num hash diferente de nada mudaria a tela.
window.addEventListener("hashchange", () => {
  const m = location.hash.match(/^#read=([^\\s]+)$/);
  if (m) openReader(decodeURIComponent(m[1]));
});

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
        <th data-col="title">Título</th><th data-col="tags">Tags</th>
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
  // têm o campo. Reaproveita o mesmo <select> em vez de um bloco de HTML
  // condicional separado, pra não duplicar o vocabulário em dois lugares.
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
    // Múltiplas tags selecionadas combinam por E: cada clique estreita o
    // resultado, que é como se procura o cruzamento entre dois assuntos.
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

    // Resumo expansível só faz sentido pra essays (é o único tipo com corpo
    // de texto de verdade por trás — concept/entity/insight/reference não
    // têm `summary:` de arquivo, ou têm um campo curto sem tanto valor extra
    // aqui). `n.summary` pode vir vazio (arquivo sem o campo no frontmatter,
    // ou frontmatter que não passou no check_wiki.py ainda) — nesse caso não
    // mostra o botão de expandir, pra não prometer um resumo que não existe.
    const showSummary = state.type === "essay";
    tbody.innerHTML = rows.map(n => {
      // A linha expande para um painel de detalhe: resumo (quando existe) e as
      // conexoes daquele no separadas por tipo. Vale para qualquer tipo que
      // tenha ao menos uma das duas coisas a mostrar.
      const hasSummary = showSummary && n.summary;
      const hasDetail = hasSummary || connectionsByType(n.id).size > 0;
      const rSlug = essaySlugOf(n);
      // Com leitor embutido, <button> abre o overlay; no build leve, <a> abre
      // o HTML exportado numa aba. Mesma classe, mesmo desenho.
      const readBtn = (rSlug && readerEssays()[rSlug])
        ? `<button type="button" class="idx-read" data-read="${escapeHtml(rSlug)}" aria-label="Ler ${escapeHtml(n.title)}" title="Ler">📖</button>`
        : (n.htmlFile
          ? `<a class="idx-read" href="${escapeHtml(n.htmlFile)}" target="_blank" aria-label="Ler ${escapeHtml(n.title)}" title="Ler">📖</a>`
          : "");
      // Só rascunho é marcado. `finalizado` não recebe nada: a marca serve
      // para dizer "ainda em obra", e 45 selos repetidos não diriam nada.
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
      <td class="idx-tagcell" data-label="Tags">${(n.tags || []).map(t => `<span>${escapeHtml(t)}</span>`).join("")}</td>
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

    // `stopPropagation()` é o que faz o botão de expandir não também disparar
    // o clique da linha (que fecha o modal e navega até o nó) — sem isto,
    // abrir o resumo já saía navegando pro nó junto, o oposto do que
    // "expansível pra não ficar clutered" pede.
    tbody.querySelectorAll(".idx-expand").forEach(btn => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const summaryRow = btn.closest("tr").nextElementSibling;
        if (!summaryRow || !summaryRow.classList.contains("idx-summary-row")) return;
        const willOpen = summaryRow.hidden;
        summaryRow.hidden = !willOpen;
        btn.textContent = willOpen ? "▾" : "▸";
        btn.setAttribute("aria-expanded", String(willOpen));
        if (willOpen && !summaryRow.dataset.wired) {
          summaryRow.dataset.wired = "1";
          wireConnections(summaryRow, (node) => {
            modalOverlay.classList.remove("open");
            selectNode(node);
          });
        }
      });
    });

    // 📖 na linha abre o leitor sem fechar o índice nem navegar o grafo.
    // `button.idx-read` e não `.idx-read`: no build leve o mesmo lugar tem um
    // <a> que já navega sozinho — se ele caísse aqui, chamaria
    // openReader(null) antes de abrir a aba.
    tbody.querySelectorAll("button.idx-read").forEach(b => {
      b.addEventListener("click", (e) => {
        e.stopPropagation();
        openReader(b.getAttribute("data-read"));
      });
    });
    // A âncora navega por conta própria; só precisa não disparar o clique da
    // linha (que fecharia o índice e navegaria o grafo por baixo).
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

// ---- Painel de Gaps (calculado no Python, embutido nos dados) ----
document.getElementById("btn-gaps").addEventListener("click", () => {
  styleModalOpen = false;
  const gaps = data.tag_gaps || [];
  let html = `<h2>Gaps entre tags</h2>`;
  if (!gaps.length) {
    html += "<div class=\\"gap-item\\">Nenhum par de tags isolado — todo o grafo conectado por tags está num único componente (ou não há tags suficientes ainda).</div>";
  } else {
    gaps.forEach(([a, b]) => {
      html += `<div class="gap-item"><b>${a}</b> nunca se conecta com <b>${b}</b></div>`;
    });
  }
  modalBody.innerHTML = html;
  modalOverlay.classList.add("open");
});

// ---- Painel de Estilo (cores, raio, rótulo — ao vivo + salvo por navegador) ----
const STYLE_LABELS = {
  essay: "Essay", concept: "Concept", entity: "Entity", insights: "Insight",
  reference: "Reference", edge: "Arestas", background: "Fundo",
};

const GRAPH_THEMES = {
  cosmico: { label: "Cósmico", glow: "alto", starfield: true, gradient: true },
  padrao: { label: "Padrão", glow: "leve", starfield: true, gradient: true },
  minimalista: { label: "Minimalista", glow: "off", starfield: false, gradient: false },
  // Os quatro abaixo, diferente dos três de cima, também trocam as cores
  // (`colors` completo, um valor pra cada chave de STYLE_LABELS) — um reskin
  // inteiro num clique, não só glow/fundo estrelado/gradiente. Aplicado via
  // Object.assign(draft, tema) no clique do botão: como cada um define os 7
  // tipos, a troca substitui o objeto de cores inteiro sem deixar sobra do
  // tema anterior.
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
  const draft = JSON.parse(JSON.stringify(seed || styleConfig)); // rascunho — só grava de fato no "Salvar"

  const colorRow = (key) => `
    <label class="style-row">
      <span>${STYLE_LABELS[key]}</span>
      <input type="color" data-color="${key}" value="${draft.colors[key]}">
    </label>`;

  const themeBtn = (key, t) => `<button class="btn theme-btn" data-theme="${key}">${t.label}</button>`;

  modalBody.innerHTML = `
    <h2>Estilo do grafo</h2>
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
      <p class="style-hint">Referências não têm arquivo — nos modos de tamanho de essay elas ficam sempre no raio base. O raio base e a escala do tamanho agora ficam ao lado das cores, acima.</p>
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
      <label class="style-row style-slider">
        <span>Espaçamento entre bolinhas</span>
        <input type="range" id="st-spacing" min="0.6" max="3" step="0.2" value="${draft.spacing ?? 1.8}">
      </label>
      <p class="style-hint">Sobe a distância mínima entre nós, a força que os empurra pra longe e o comprimento das arestas — útil quando o grafo fica denso demais pra ler.</p>
      <label class="style-row style-slider">
        <span>Força elástica das conexões</span>
        <input type="range" id="st-link-strength" min="0.2" max="7" step="0.4" value="${draft.linkStrength ?? 3.5}">
      </label>
      <label class="style-row style-slider">
        <span>Força de repulsão entre nós</span>
        <input type="range" id="st-charge-strength" min="0.2" max="6" step="0.4" value="${draft.chargeStrength ?? 2}">
      </label>
      <label class="style-row style-slider">
        <span>Atrito</span>
        <input type="range" id="st-friction" min="0.05" max="1.25" step="0.1" value="${draft.friction ?? 0.65}">
      </label>
      <p class="style-hint">Elástica: quanto maior, mais as arestas puxam os nós conectados com força. Repulsão: quanto maior, mais os nós se afastam uns dos outros. Atrito: quanto maior, mais rápido o grafo assenta e para de balançar.</p>
      <label class="style-row style-slider">
        <span>Elasticidade de retorno</span>
        <input type="range" id="st-home-strength" min="0" max="0.6" step="0.02" value="${draft.homeStrength ?? 0.25}">
      </label>
      <p class="style-hint">Puxa cada bolinha de volta pro lugar dela no layout quando ela é arrastada e solta — diferente da força elástica das conexões, que só rege a distância entre vizinhos, sem noção de posição absoluta. 0 desliga (a bolinha fica onde for solta).</p>
    </div>
    <div class="style-section">
      <label class="style-row">
        <span>Nível de desempenho</span>
        <select id="st-performance">
          <option value="alta" ${(draft.performance ?? "alta") === "alta" ? "selected" : ""}>Alta (recomendado)</option>
          <option value="auto" ${draft.performance === "auto" ? "selected" : ""}>Automático</option>
          <option value="media" ${draft.performance === "media" ? "selected" : ""}>Média</option>
          <option value="baixa" ${draft.performance === "baixa" ? "selected" : ""}>Baixa</option>
        </select>
      </label>
      <p class="style-hint">
        Controla a física da simulação e quando os rótulos somem ao afastar o zoom — não mexe em cor/glow.
        No automático, este navegador/grafo está usando: <b>${resolvePerformanceTier(draft)}</b>
        (${data.nodes.length} nós${DEVICE_IS_MOBILE ? ", aparelho móvel" : ""}).
      </p>
      <label class="style-row">
        <span>Colisão entre nós</span>
        <select id="st-collision">
          <option value="true" ${(draft.collision ?? true) !== false ? "selected" : ""}>Ligada (padrão)</option>
          <option value="false" ${draft.collision === false ? "selected" : ""}>Desligada (mais rápido)</option>
        </select>
      </label>
      <p class="style-hint">Desligar evita que o simulador gaste tempo resolvendo sobreposição entre bolinhas — mais rápido em aparelhos fracos, ao custo de nós podendo se sobrepor na tela.</p>
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
          <option value="auto" ${(draft.labels ?? "auto") === "auto" ? "selected" : ""}>Automático (some ao afastar o zoom)</option>
          <option value="sempre" ${draft.labels === "sempre" ? "selected" : ""}>Sempre visível</option>
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
      <p class="style-hint">Textura esférica: brilho e sombra por cima da bolinha, pra parecer uma esfera 3D em vez de um disco chapado. Tingir por tag: manchas bem escuras (quase a cor de fundo) em torno de onde cada tag se concentra no grafo — um indício visual de "regiões temáticas", sutil de propósito.</p>
    </div>
    </div>
    <div class="style-actions">
      <button class="btn" id="st-reset">Restaurar padrão</button>
      <button class="btn style-primary" id="st-save">Salvar</button>
    </div>`;

  const preview = () => applyStyle(draft); // aplica ao vivo no grafo por trás do modal, sem salvar ainda

  modalBody.querySelectorAll(".theme-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      Object.assign(draft, GRAPH_THEMES[btn.getAttribute("data-theme")]);
      preview();
      renderStylePanel(draft); // redesenha os controles pra refletir o tema, sem perder o resto do rascunho
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
  modalBody.querySelector("#st-spacing").addEventListener("input", (e) => { draft.spacing = +e.target.value; preview(); });
  modalBody.querySelector("#st-link-strength").addEventListener("input", (e) => { draft.linkStrength = +e.target.value; preview(); });
  modalBody.querySelector("#st-charge-strength").addEventListener("input", (e) => { draft.chargeStrength = +e.target.value; preview(); });
  modalBody.querySelector("#st-friction").addEventListener("input", (e) => { draft.friction = +e.target.value; preview(); });
  modalBody.querySelector("#st-home-strength").addEventListener("input", (e) => { draft.homeStrength = +e.target.value; preview(); });
  modalBody.querySelector("#st-performance").addEventListener("change", (e) => {
    draft.performance = e.target.value;
    preview();
    renderStylePanel(draft); // atualiza o texto "está usando: X" com o novo valor
  });
  modalBody.querySelector("#st-collision").addEventListener("change", (e) => { draft.collision = e.target.value === "true"; preview(); });
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

// ---- Ajustar à tela --------------------------------------------------------
// Reenquadra o grafo inteiro (nós visíveis) no viewport atual, com a mesma
// lógica do auto-fit de celular, mas forçado: funciona em qualquer tamanho
// de tela e mesmo depois de o usuário já ter dado zoom/pan manualmente.
document.getElementById("btn-fit-screen").addEventListener("click", () => {
  fitToScreen(false, true);
});

// ---- Exportar PNG --------------------------------------------------------
// O canvas já é a imagem inteira (fundo, céu estrelado, arestas, nós, halos)
// exatamente como está na tela — inclusive zoom/pan e seleção/busca ativos —
// então exportar é só pedir um blob do canvas e disparar o download; nada
// precisa ser redesenhado num canvas separado.
// Exportar no dpr da tela (1x em monitor comum, 2x em retina) dá um PNG do
// tamanho exato do viewport — ótimo pra ver na tela, mas o texto pixela ao
// dar zoom depois num visualizador de imagem, porque não sobra resolução
// extra. Como o grafo é Canvas (não SVG — ver comentários no topo do
// arquivo), não existe export vetorial sem reescrever o `draw()` inteiro
// contra um contexto tipo canvas2svg; a saída pragmática é fingir um dpr
// bem mais alto só na hora do export ("supersampling"): o buffer físico
// nasce EXPORT_SCALE× maior que o normal, `draw()` desenha nele (ele já
// respeita `dpr` em tudo — sprites, lineWidth, fillText — sem precisar
// tocar numa linha da função), e o PNG final sai nítido mesmo com bastante
// zoom, ainda que não seja "infinito" como vetor de verdade.
const EXPORT_SCALE = 3; // multiplicador sobre o dpr atual da tela

document.getElementById("btn-export-png").addEventListener("click", () => {
  // Reler o transform direto do comportamento de zoom do D3, não confiar só
  // na variável `zoomTransform`: ela só é reatribuída dentro do handler
  // "zoom", então se o clique cair entre o fim de um gesto (pinça/arrasto/
  // roda) e o próximo evento, ela pode estar um frame atrás do estado real.
  // `d3.zoomTransform(canvas)` lê o transform que o D3 já mantém associado
  // ao próprio elemento — é a fonte de verdade, sem essa janela de corrida.
  zoomTransform = d3.zoomTransform(canvas);

  // Troca temporária de resolução: só o buffer físico (canvas.width/height)
  // muda, `canvas.style.width/height` (tamanho em tela) fica intocado — o
  // navegador só escala a exibição pra baixo enquanto isso, sem "pular" o
  // layout. `dpr` é a mesma variável que resizeCanvas() usa, e draw() já lê
  // tudo através dela, então não há caminho de desenho separado pra manter.
  const originalDpr = dpr;
  const originalCanvasWidth = canvas.width;
  const originalCanvasHeight = canvas.height;
  dpr = originalDpr * EXPORT_SCALE;
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  clearSpriteCache(); // sprites cacheados no dpr antigo ficariam pequenos/borrados no buffer novo

  draw();

  canvas.toBlob((blob) => {
    // Restaura o buffer físico pro tamanho de tela normal ANTES de qualquer
    // outra coisa: canvas.toBlob() já leu o buffer grande pro blob, então
    // não há mais necessidade dele, e deixar o canvas gigante em memória
    // entre um export e o próximo é desperdício à toa.
    dpr = originalDpr;
    canvas.width = originalCanvasWidth;
    canvas.height = originalCanvasHeight;
    clearSpriteCache();
    draw(); // repinta a tela no dpr normal — sem isto ficaria em branco até o próximo evento

    if (!blob) return; // navegador sem suporte a toBlob (raríssimo) — falha silenciosa, sem travar a UI
    const url = URL.createObjectURL(blob);
    const stamp = new Date().toISOString().slice(0, 10);
    const a = document.createElement("a");
    a.href = url;
    a.download = `grafo-second-brain-${stamp}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }, "image/png");
});

// ---- Exportar SVG (vetorial, zoom infinito) -------------------------------
// PNG — mesmo supersampled (ver acima) — é raster: sempre existe um teto de
// nitidez. Pra zoom de verdade sem perda nenhuma, a saída precisa ser vetor.
// draw() não serve de base pra isso: ele é o coração de performance do
// arquivo inteiro (sprites em bitmap, batching de arestas em Path2D, tiers
// de qualidade, halos com shadowBlur...), tudo pensado pra rodar a 60fps num
// celular — nada disso é vetorizável sem perder a otimização, e forçar os
// dois casos de uso (tela + export) pela mesma função misturaria duas
// preocupações que não têm nada a ver uma com a outra.
// Por isso drawForSvgExport() é uma função própria, separada, escrita do
// zero: desenha numa réplica mock do contexto 2D fornecida pela lib
// canvas2svg (global C2S, carregada no <head>) — ela implementa os mesmos
// métodos de CanvasRenderingContext2D (translate, arc, fillText,
// createRadialGradient...) só que, em vez de rasterizar pixels, vai
// acumulando um grafo de cena e serializa isso como <svg> no final.
// Gradiente e glow SAEM no export: createRadialGradient() do canvas2svg gera
// um <radialGradient> de verdade nos <defs> do SVG, não um bitmap — então dá
// pra reaproveitar a mesma técnica de sombreamento esférico (nodeGradients)
// e halo (haloGradients) que já existe pra tela, sem abrir mão de nitidez em
// zoom nenhum. O que fica de fora é só o glow "alto" via shadowBlur — essa
// propriedade não tem suporte confiável nesta lib — então "alto" e "leve"
// desenham o mesmo halo em gradiente no export; a diferença de intensidade
// entre os dois modos só existe na tela.
// Roda mais devagar que o draw() de tela (sem culling agressivo, sem
// batching, sem cache de sprite) — tudo bem, só acontece uma vez, no clique
// de exportar, não a cada frame.
// Círculo unitário desenhado como dois semicírculos, não um arco 0→2π: o
// comando de arco elíptico do SVG não representa um círculo fechado (ponto
// inicial teria que ser igual ao final), e o canvas2svg — como vários outros
// conversores canvas→svg — trata startAngle===endAngle (depois do módulo 2π)
// como "nada a desenhar", igual o Canvas nativo faz quando os dois ângulos
// batem exato. O sintoma real foi esse: halo e nó (os dois únicos lugares
// que desenhavam círculo fechado) sumiam do SVG inteiro — sobrava só fundo,
// aresta e texto, que é exatamente a tela quase preta relatada no Xplore.
function unitCircle(c) {
  c.beginPath();
  c.arc(0, 0, 1, 0, Math.PI);
  c.arc(0, 0, 1, Math.PI, Math.PI * 2);
}

// `simple`: exporta em cor chapada, sem glow nem gradiente — testado pra
// contornar visualizadores de SVG simples (Xplore no Android é o caso
// relatado) que engasgam nos <radialGradient> do export "completo", mesmo já
// sem os três problemas de sintaxe descritos acima (atributo duplicado,
// notação científica, encoding). Não mexe no styleConfig de verdade: cria
// uma cópia rasa só pra esta exportação, então o grafo em tela e o próximo
// export "completo" continuam com o estilo salvo do usuário intactos.
function drawForSvgExport(simple) {
  const svgStyle = simple ? Object.assign({}, styleConfig, { glow: "off", gradient: false }) : styleConfig;
  const c = new C2S(width, height); // tamanho em px CSS — vetor não precisa de dpr/supersampling

  c.fillStyle = (svgStyle.colors && svgStyle.colors.background) || "#1b1e21";
  c.fillRect(0, 0, width, height);

  // Gradientes construídos uma vez, no espaço unitário (-1..1 / 0..1), e
  // reaproveitados por tipo em todos os nós — exatamente a mesma técnica de
  // buildGradients(): o CanvasGradient guarda só os stops, e um
  // translate+scale por nó (mais abaixo) estica ele pro raio de fato, sem
  // precisar recriar o objeto a cada nó.
  const svgNodeGradients = {};
  const svgHaloGradients = {};
  if (svgStyle.gradient || svgStyle.glow !== "off") {
    Object.keys(svgStyle.colors || {}).forEach(type => {
      if (type === "background" || type === "edge") return;
      const color = svgStyle.colors[type] || "#888";
      if (svgStyle.gradient) {
        const g = c.createRadialGradient(-0.3, -0.35, 0, 0, 0, 1);
        g.addColorStop(0, mixWhite(color, 0.55));
        g.addColorStop(1, color);
        svgNodeGradients[type] = g;
      }
      if (svgStyle.glow !== "off") {
        const h = c.createRadialGradient(0, 0, 0, 0, 0, 1);
        h.addColorStop(0, hexToRgba(color, 0.5));
        h.addColorStop(1, hexToRgba(color, 0));
        svgHaloGradients[type] = h;
      }
    });
  }

  c.save();
  c.translate(zoomTransform.x, zoomTransform.y);
  c.scale(zoomTransform.k, zoomTransform.k);

  // Mesmo critério de "dentro da tela" do draw() principal, só que sem culling
  // por índice espacial: aqui não há orçamento de frame a respeitar.
  const [wx0, wy0] = zoomTransform.invert([0, 0]);
  const [wx1, wy1] = zoomTransform.invert([width, height]);
  const pad = 80;
  const inView = (n) => n.x >= wx0 - pad && n.x <= wx1 + pad && n.y >= wy0 - pad && n.y <= wy1 + pad;

  // Arestas: um beginPath/stroke por aresta (sem o batching em Path2D do
  // draw() de tela — aqui não corre a 60fps, então o custo extra não importa,
  // e evita depender de suporte a Path2D dentro do mock do canvas2svg).
  if (svgStyle.edgeVisibility !== "off") {
    c.lineWidth = 1.2 / zoomTransform.k;
    c.strokeStyle = svgStyle.colors.edge;
    data.edges.forEach(e => {
      const s = endpoint(e.source), t = endpoint(e.target);
      if (!s || !t || !isNodeVisible(s) || !isNodeVisible(t)) return;
      if (!inView(s) && !inView(t)) return;
      const dim = edgeDimmed(e);
      c.globalAlpha = dim ? 0.08 : svgStyle.edgeOpacity;
      // setLineDash pode não existir nesta versão do mock — checar antes de
      // chamar evita estourar a função inteira por causa de um detalhe
      // cosmético (linha tracejada vs. sólida) que não é o motivo do export.
      if (typeof c.setLineDash === "function") {
        c.setLineDash(e.kind === "reference" ? [3, 3] : []);
      }
      c.beginPath();
      c.moveTo(s.x, s.y);
      c.lineTo(t.x, t.y);
      c.stroke();
    });
    c.globalAlpha = 1;
  }

  // Nós: halo de glow (se ligado) por trás, depois o próprio nó — em
  // gradiente esférico se `svgStyle.gradient` estiver ligado, senão cor
  // chapada. translate+scale por nó pra reaproveitar os gradientes unitários
  // construídos acima (mesmo truque de drawHalo()/getNodeSprite() na tela).
  data.nodes.forEach(n => {
    if (!isNodeVisible(n) || !inView(n)) return;
    const r = radiusOf(n);
    const dim = nodeDimmed(n);
    const type = n.type;

    if (svgStyle.glow !== "off") {
      c.save();
      c.globalAlpha = dim ? 0.08 : 1;
      c.translate(n.x, n.y);
      c.scale(r * 2.4, r * 2.4);
      unitCircle(c);
      c.fillStyle = svgHaloGradients[type] || "transparent";
      c.fill();
      c.restore();
    }

    c.save();
    c.globalAlpha = dim ? 0.08 : 1;
    c.translate(n.x, n.y);
    c.scale(r, r);
    unitCircle(c);
    c.fillStyle = svgStyle.gradient ? (svgNodeGradients[type] || typeColorRaw(n)) : typeColorRaw(n);
    c.fill();
    // lineWidth compensado pelo scale(r,r): 1px de verdade vira r depois de
    // escalado, então 1/r devolve a espessura real de contorno pretendida.
    c.lineWidth = 1 / r;
    c.strokeStyle = "#0b1220";
    c.stroke();
    c.restore();
  });
  c.globalAlpha = 1;

  // Rótulos — o motivo original do pedido: em SVG o texto é elemento <text>
  // de verdade, então fica nítido em qualquer zoom, ao contrário do PNG.
  if (labelsShown) {
    c.font = `${svgStyle.labelSize}px -apple-system, "Segoe UI", Helvetica, Arial, sans-serif`;
    c.textAlign = "center";
    c.fillStyle = getLabelColor();
    data.nodes.forEach(n => {
      if (n.type === "reference" || !isNodeVisible(n) || !inView(n)) return;
      c.globalAlpha = nodeDimmed(n) ? 0.08 : 0.85;
      c.fillText(n.title, n.x, n.y - (2 + radiusOf(n)));
    });
    c.globalAlpha = 1;
  }

  c.restore();

  // getSerializedSvg() devolve width/height fixos em px (o tamanho da tela
  // de onde foi exportado) e nenhum viewBox — abrir esse arquivo direto
  // (Chrome, Xplore etc.) mostra o SVG no tamanho físico original, sem
  // escalar pro viewport do visualizador: um grafo exportado de um celular
  // de ~400px de largura aparece "pequeno, no canto superior esquerdo" numa
  // tela grande, porque é isso mesmo que os 400px valem lá.
  // A primeira tentativa trocou width/height por "100%", mas isso quebrou o
  // Xplore: visualizadores de SVG simples/nativos (bem diferentes de um
  // motor de navegador completo) em geral precisam de um width/height NUMÉRICO
  // pra saber que tamanho de bitmap alocar antes de desenhar — percentual sem
  // um viewport de referência dá 0 ou indefinido pra eles, o que rende tela
  // preta/vazia. Por isso width/height voltam a ser o valor em px de origem
  // (compatível com qualquer visualizador, simples ou não) e quem ganha o
  // comportamento responsivo é só quem entende `style` (CSS) — ou seja,
  // navegador de verdade — via `width:100%;height:100%` mais viewBox pra
  // escalar o conteúdo interno proporcionalmente sem distorcer.
  let svgString = c.getSerializedSvg(true); // true: entidades nomeadas -> numéricas, exigido por SVG standalone

  // getSerializedSvg() do canvas2svg sai com o atributo xmlns:xlink DUPLICADO
  // na tag <svg> raiz. A lib tenta corrigir um bug antigo do IE trocando a
  // primeira ocorrência de xmlns="..." pelo texto xmlns:xlink="..." (ver
  // canvas2svg.js, comentário "IE search for a duplicate xmnls"), só que o
  // serializer de DOM usado aqui (confirmado tanto em jsdom quanto no
  // comportamento de motores modernos) já declara um xmlns:xlink próprio ao
  // serializar — o "conserto" da lib não remove duplicata nenhuma, só troca
  // QUAL atributo fica duplicado: em vez de xmlns repetido, sobra
  // xmlns:xlink repetido. Atributo repetido na mesma tag é proibido pela
  // regra de unicidade do XML; testado aqui com um parser XML estrito
  // (xml.etree), o SVG cru do canvas2svg falha com "duplicate attribute".
  // O Chrome tolera isso porque abre SVG com o parser de HTML, que é
  // permissivo e ignora repetição de atributo; o Xplore usa um parser XML
  // de verdade pro visualizador de SVG, que rejeita o arquivo por violar
  // essa regra — daí o erro e a tela preta relatados, e é isso (não
  // gradiente, não círculo, não viewBox) que o Xplore realmente reclama.
  // A correção é varrer a tag <svg> raiz e manter só a primeira ocorrência
  // de cada atributo, descartando repetições, antes de montar o viewBox.
  svgString = svgString.replace(/<svg([^>]*)>/, (match, attrs) => {
    const seen = new Set();
    const dedupedAttrs = attrs.replace(/\\s+([a-zA-Z_:][-a-zA-Z0-9_:.]*)="[^"]*"/g, (attrMatch, name) => {
      if (seen.has(name)) return ""; // atributo repetido: descarta, fica só a primeira ocorrência
      seen.add(name);
      return attrMatch;
    });
    return `<svg${dedupedAttrs} viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" style="width:100%;height:100%">`;
  });

  // unitCircle() corta o círculo em dois arcos no ângulo Math.PI (ver comentário
  // acima) pra evitar o caso startAngle===endAngle que o canvas2svg trata como
  // "nada a desenhar". O problema é que Math.sin(Math.PI) no ponto de corte não
  // dá 0 exato — dá 1.2246467991473532e-16, erro de ponto flutuante inerente ao
  // IEEE 754 — e o canvas2svg serializa esse valor em notação científica dentro
  // do atributo `d` de todo <path> de nó/halo. Notação científica é válida pela
  // gramática formal de path data do SVG 1.1, e o parser de HTML do Chrome (que
  // é quem abre SVG lá) engole isso sem reclamar — mas o Xplore usa um parser de
  // SVG enxuto, que só entende números decimais simples e rejeita o path inteiro
  // ao encontrar "e-16": nó e halo somem, e é isso — não gradiente, não viewBox —
  // que produz a tela quase preta relatada lá.
  // Como esse "erro" é da ordem de 10^-16 num desenho medido em pixels, arredondar
  // pra 6 casas decimais elimina a notação científica sem qualquer perda visual
  // perceptível, e cobre não só o valor do corte do círculo como qualquer outro
  // número minúsculo que apareça por motivo semelhante em qualquer lugar do SVG.
  svgString = svgString.replace(/-?\\d*\\.?\\d+e[+-]\\d+/gi, (numStr) => {
    const rounded = Number(numStr).toFixed(6).replace(/\\.?0+$/, "");
    return rounded === "" || rounded === "-" ? "0" : rounded;
  });

  // getSerializedSvg() do canvas2svg nunca escreve o prólogo `<?xml ...?>` — o
  // próprio exemplo oficial da lib sai puro em "<svg ...>...</svg>" (conferido
  // na documentação do gliffy/canvas2svg). Os títulos dos nós são em português
  // e vêm cheios de acento (Consciência, Campeões, Cérebros...), gravados como
  // bytes UTF-8 crus dentro dos <text> — sem BOM e sem declaração de encoding
  // no arquivo. Pela gramática formal do XML, ausência de declaração e de BOM
  // significa "assuma UTF-8", e é isso que o parser de HTML do Chrome faz. Mas
  // parsers de XML enxutos/legados — a mesma categoria de parser rígido que já
  // rejeitava atributo duplicado e notação científica — não raro caem pro
  // charset padrão da plataforma em vez do padrão da spec quando não há
  // declaração explícita, o que transforma cada acento numa sequência de bytes
  // inválida pro charset errado: no Xplore isso tende a se somar aos sintomas
  // já descritos (erro ao abrir / conteúdo não desenhado), então declarar o
  // encoding explicitamente remove a ambiguidade de vez.
  svgString = '<?xml version="1.0" encoding="UTF-8"?>\\n' + svgString;

  // Duas limpezas a mais, de baixo risco (não mudam nada visualmente em
  // Chrome nem no que já testamos) pra reduzir o que um parser de SVG
  // simples/legado poderia ter de errado nesse arquivo:
  // 1) canvas2svg escreve os raios/centros de <radialGradient> com sufixo
  //    "px" (ex.: r="1px"). É um <length> válido pela gramática do SVG, mas
  //    parsers enxutos costumam só aceitar número puro nesses atributos.
  //    Como esses valores são sempre em userSpaceOnUse (sem unidade real
  //    envolvida), tirar o "px" não muda o resultado em nada.
  svgString = svgString.replace(/([a-zA-Z]+)="(-?[\\d.]+)px"/g, '$1="$2"');
  // 2) `paint-order` é propriedade de SVG2 — a ordem padrão (fill antes de
  //    stroke) já é a que canvas2svg segue nos casos onde não escreve o
  //    atributo, então remover não muda a aparência; só tira algo que um
  //    parser SVG1.1 pode não reconhecer.
  svgString = svgString.replace(/ paint-order="[^"]*"/g, "");

  return svgString;
}

function exportSvgFile(simple) {
  zoomTransform = d3.zoomTransform(canvas); // mesma fonte de verdade usada no export PNG
  const svgString = drawForSvgExport(simple);
  const blob = new Blob([svgString], { type: "image/svg+xml" });
  const url = URL.createObjectURL(blob);
  const stamp = new Date().toISOString().slice(0, 10);
  const a = document.createElement("a");
  a.href = url;
  a.download = `grafo-second-brain-${stamp}${simple ? "-simples" : ""}.svg`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

const exportSvgBtn = document.getElementById("btn-export-svg");
const exportSvgPopover = document.getElementById("export-svg-popover");

function closeExportSvgPopover() { exportSvgPopover.classList.remove("open"); }

function openExportSvgPopover() {
  // Ancorado no botão, não centralizado: abre logo abaixo dele (ou acima,
  // se não couber embaixo), e clampa na largura da viewport pra nunca sair
  // da tela no painel estreito do mobile.
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
// canvas2svg (~50 KB) só existe para o export vetorial: carrega sob demanda
// da CDN na primeira exportação. Único recurso dependente de rede — exportar
// SVG offline mostra aviso claro; PNG e todo o resto funcionam offline.
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
// ao estilo realmente salvo (ou ao padrão, se nada foi salvo ainda) — sem
// isto, um preview ao vivo cancelado ficaria "grudado" no grafo por engano.
// Só se aplica quando era o modal de Estilo: fechar Índice/Gaps não deve
// reiniciar a simulação à toa.
function revertUnsavedStylePreview() {
  if (!styleModalOpen) return;
  applyStyle(mergeWithDefaults(loadSavedStyle()));
}
document.getElementById("modal-close").addEventListener("click", revertUnsavedStylePreview);
modalOverlay.addEventListener("click", (e) => { if (e.target === modalOverlay) revertUnsavedStylePreview(); });

// ---- Endurecimento para iPhone/Safari -----------------------------------
// Safari tem um gesto de pinça PRÓPRIO da página (`gesturestart` etc, não
// padrão, não existe no Chrome/Android) que compete com o pinça-zoom do
// próprio grafo (d3.zoom). `touch-action: none` no CSS já resolve a maior
// parte, mas esses eventos são a rede de segurança para versões de iOS que
// os disparam mesmo assim — sem isto, no iPhone a página inteira "pula" de
// zoom em vez de só o grafo.
["gesturestart", "gesturechange", "gestureend"].forEach(evt => {
  document.addEventListener(evt, (e) => e.preventDefault());
});

// Safari esconde/mostra a barra de endereço sem sempre disparar `resize` na
// `window` — o evento confiável para isso é o do `visualViewport`. Sem ele,
// o grafo pode ficar com o viewBox de um tamanho de tela que já não existe
// mais depois de rolar uma vez no iPhone (sintoma: grafo "cortado" ou
// deslocado, que não acontece no Android porque o Chrome sempre dispara
// `resize` de qualquer forma).
if (window.visualViewport) {
  window.visualViewport.addEventListener("resize", ajustarViewport);
}

</script>
</body>
</html>
"""


def render_html(nodes, edges, tag_gaps, reader_payload):
    graph_b64 = _deflate_b64(_json_for_script_tag(
        {
            "nodes": nodes,
            "edges": edges,
            "tag_gaps": tag_gaps,
            "defaultStyle": GRAPH_STYLE,
            "defaultStyleMobileOverrides": GRAPH_STYLE_MOBILE_OVERRIDES,
        }
    ))
    # MathJax vai em tag PROPRIA, nao dentro do payload do leitor: sao 2,3 MB
    # (22% do payload) que so 23 dos 45 essays usam. Separado, o inflate do
    # leitor nao paga por ele, e quem abre um essay sem matematica nunca o
    # descomprime. Nao muda o tamanho do arquivo — muda memoria e parse.
    reader_b64 = ""
    mathjax_b64 = ""
    if reader_payload.get("essays"):
        payload = dict(reader_payload)
        mathjax = payload.pop("mathjax", "") or ""
        reader_b64 = _deflate_b64(_json_for_script_tag(payload))
        if mathjax:
            mathjax_b64 = _deflate_b64(_json_for_script_tag(mathjax))

    d3_src = D3_VENDORED.read_text(encoding="utf-8")
    pako_src = PAKO_VENDORED.read_text(encoding="utf-8")
    # Injeção é como <script> inline: um '</script' dentro do vendor fecharia
    # a tag no meio do arquivo. Vendor auditado, mas a rede de segurança fica.
    for name, src in (("d3", d3_src), ("pako", pako_src)):
        if "</script" in src.lower():
            raise RuntimeError(f"vendor {name} contém '</script' — não pode ir inline")

    html = HTML_TEMPLATE
    html = html.replace("__GRAPH_B64__", graph_b64)
    html = html.replace("__READER_B64__", reader_b64)
    html = html.replace("__MATHJAX_B64__", mathjax_b64)
    html = html.replace("__D3__", d3_src)
    html = html.replace("__PAKO__", pako_src)
    return html


def main():
    parser = argparse.ArgumentParser(
        description="Gera o grafo da wiki. Por padrão gera as DUAS variantes "
                    "(MySecondBrain.html leve + MySecondBrain.reader.html com "
                    "essays embutidos); --reader gera só a completa e "
                    "--no-reader gera só a leve.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--reader", dest="reader", action="store_true", default=None,
                       help="gera só a versão completa (essays embutidos em "
                            f"{READER_HTML_NAME})")
    group.add_argument("--no-reader", dest="reader", action="store_false",
                       help=f"gera só a versão leve (grafo + link .md em {OUTPUT_HTML_NAME})")
    args = parser.parse_args()
    embed = args.reader  # True (só completa) | False (só leve) | None (default → ambas)

    nodes, edges, isolated = build_graph()
    tag_gaps = compute_tag_gaps(nodes, edges)

    layout_start = time.perf_counter()
    compute_layout(nodes, edges)
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

    if want_light:
        essay_nodes = [n for n in nodes if n["type"] == "essay"]
        com_html = sum(1 for n in essay_nodes if n.get("htmlFile"))
        print(f"Versão leve ({OUTPUT_HTML_NAME}): o ícone de leitura abre "
              f"output/html/ ({com_html}/{len(essay_nodes)} essays exportados).")
        if com_html < len(essay_nodes):
            faltam = len(essay_nodes) - com_html
            print(f"  {faltam} essay(s) sem HTML exportado caem no .md — "
                  f"rode `python scripts/export_essay_html.py --all` para cobrir todos.")

    (OUTPUT_DIR / "graph.json").write_text(
        json.dumps({"nodes": nodes, "edges": edges, "tag_gaps": tag_gaps, "isolated": isolated},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (OUTPUT_DIR / "graph.md").write_text(
        f"# Grafo da Wiki\n\n{len(nodes)} páginas, {len(edges)} conexões.\n\n" + render_mermaid(nodes, edges) + "\n",
        encoding="utf-8",
    )

    def _escreve(filename, payload):
        p = OUTPUT_DIR / filename
        p.write_text(render_html(nodes, edges, tag_gaps, payload), encoding="utf-8")
        return p.stat().st_size / (1024 * 1024)

    vazio = {"essays": {}, "mathjax": "", "css": ""}
    gerados = []
    if want_light:
        gerados.append(("leve", OUTPUT_HTML_NAME, _escreve(OUTPUT_HTML_NAME, vazio)))
    if want_reader:
        gerados.append(("completa", READER_HTML_NAME, _escreve(READER_HTML_NAME, reader_payload)))

    # Legado: quem tinha atalho pro graph.html continua funcionando.
    # O redirect aponta para a variante leve — o arquivo canônico quando as
    # duas são geradas juntas.
    legacy = OUTPUT_DIR / "graph.html"
    stub = ('<!DOCTYPE html><meta charset="utf-8">'
            f'<meta http-equiv="refresh" content="0; url={OUTPUT_HTML_NAME}">'
            f'<title>Movido</title><a href="{OUTPUT_HTML_NAME}">{OUTPUT_HTML_NAME}</a>')
    if not legacy.exists() or legacy.read_text(encoding="utf-8", errors="replace") != stub:
        legacy.write_text(stub, encoding="utf-8")

    print(f"Grafo gerado: {len(nodes)} nós, {len(edges)} conexões.")
    print(f"  layout pré-calculado em {layout_ms:.0f}ms")
    for nome, fname, mb in gerados:
        print(f"  {fname} ({nome}, {mb:.1f} MB)")
    print(f"  {OUTPUT_DIR / 'graph.md'} (mermaid)")
    print(f"  {OUTPUT_DIR / 'graph.json'} (dados)")
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
