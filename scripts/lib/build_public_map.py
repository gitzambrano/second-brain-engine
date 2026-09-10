#!/usr/bin/env python3
"""
Gera o mapa público — grafo e globo — com os renderizadores da própria wiki.

`build_graph.py` e `build_sphere.py` já produzem o mapa interativo que a wiki
usa: painel de índice, resumos expansíveis, selo de rascunho, busca, estilo.
Este script não reimplementa nada disso. Ele pega o mesmo conjunto de nós, tira
o que não pode ser público e entrega aos mesmos renderizadores.

O que atravessa para o mapa público:
    título, tipo, tags, resumo (de essays), status de rascunho, grau, tamanho,
    layout, todas as conexões e a URL externa de uma entrada de bibliografia.

O que nunca atravessa:
    tudo o mais. O nó público é montado do zero a partir da allowlist
    `PUBLIC_NODE_FIELDS`, então o corpo de qualquer página, o caminho `file`
    para dentro do repositório privado e qualquer campo futuro ficam de fora por
    omissão, não por lista de proibidos. Link de leitura só existe para essay
    autorizado: um nó não publicado está no mapa e não abre.

Um site estático não esconde o que serve: título e resumo aqui são públicos.
Essa é a troca deliberada — o catálogo é público, o texto não.

Default sem argumentos: escrever o mapa público em SITE_ROOT.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import build_graph
import build_sphere
from repo_paths import SITE_ROOT, SITE_SRC_DIR
from site_common import collect_public

# --- Schema do nó público ---------------------------------------------------
# Antes daqui existia uma BLACKLIST: copiava-se o nó inteiro e removia-se
# `file`, `body`, `text`, `path`. O defeito é estrutural, não de conteúdo da
# lista: no dia em que `build_graph.py` acrescentar `notes`, `sourcePath` ou
# `privateSummary` ao nó, o campo novo é publicado sozinho, sem ninguém decidir
# nada. A arquitetura promete o contrário — privado por omissão —, então o nó
# público é montado do zero, campo a campo, a partir da allowlist abaixo.
#
# Campo novo no grafo passa a ser privado por padrão: ele simplesmente não é
# copiado, e só entra no site quando alguém o acrescenta a esta tupla.
#
# A lista foi levantada contra o que os renderizadores realmente consomem —
# os acessos `n.<campo>` / `d.<campo>` no JS de `build_graph.py` e
# `build_sphere.py`. Tirar qualquer um destes quebra o mapa:
#
#   id/title/type      identidade, rótulo e cor do nó, e as pontas das arestas
#   subtype/maturidade agrupamento de insight e de referência na legenda
#   tags/summary/status painel de Índice: filtro por tag, resumo expansível,
#                       selo de rascunho
#   degree             métrica de raio e filtro por grau
#   sizeBytes/sizeLines modo de raio alternativo ("densidade") do painel Estilo
#   x0/y0              layout do grafo 2D
#   ux/uy/uz           layout da esfera
PASSTHROUGH_NODE_FIELDS = (
    "id", "title", "type", "subtype", "maturidade", "tags", "summary", "status",
    "degree", "sizeBytes", "sizeLines", "x0", "y0", "ux", "uy", "uz",
)

# Estes três não são copiados: são decididos aqui, em `sanitize`. `htmlFile` e
# `url` são exatamente os dois campos que podem ABRIR alguma coisa, e por isso
# nunca herdam o valor da wiki — que aponta para `../../wiki/...` e para o HTML
# local em `output/html/`.
DERIVED_NODE_FIELDS = ("htmlFile", "url", "public")

PUBLIC_NODE_FIELDS = PASSTHROUGH_NODE_FIELDS + DERIVED_NODE_FIELDS

# Presentes em TODO nó público. `summary`, `status` e `maturidade` ficam de
# fora porque só existem em parte do corpus (resumo é de essay; maturidade é de
# insight; um nó de referência não tem nenhum dos três), e exigi-los
# transformaria a validação em ruído.
REQUIRED_NODE_FIELDS = (
    "id", "title", "type", "tags", "degree", "sizeBytes", "sizeLines",
    "x0", "y0", "ux", "uy", "uz", "htmlFile", "url", "public",
)

# Summaries are published for essays only; the renderer shows no others.
SUMMARY_TYPES = {"essay"}

MD_LINK = re.compile(r"\[([^\]]*)\]\([^)]*\)")
MD_EMPHASIS = re.compile(r"[*_]{1,3}")


def clean_citation(text: str) -> str:
    """Render an AIAA citation as plain text for a map label."""
    text = MD_LINK.sub(
        lambda m: "" if m.group(1).strip().lower() == "link" else m.group(1), text
    )
    text = MD_EMPHASIS.sub("", text)
    return re.sub(r"\s+", " ", text).strip(" .,;")


def essay_slug(node_id: str) -> str:
    kind, _, slug = str(node_id).partition(":")
    return slug if kind == "essay" else ""


def assert_public_schema(nodes) -> list[str]:
    """Reprova qualquer nó com chave fora do schema, ou sem chave obrigatória.

    Existe para ser chamada de fora — pela sentinela `check_site_privacy.py`,
    sobre o `graph.json` e sobre a carga embutida nos mapas, que é o que o
    navegador de fato recebe. Sem ela a allowlist protegeria só o caminho feliz:
    quem editasse `graph.json` depois do build passaria pelo portão.
    """
    errors: list[str] = []
    allowed = set(PUBLIC_NODE_FIELDS)
    for node in nodes:
        node_id = node.get("id", "<no id>")
        for field in sorted(set(node) - allowed):
            errors.append(f"field outside the public schema on node {node_id}: {field!r}")
        for field in REQUIRED_NODE_FIELDS:
            if field not in node:
                errors.append(f"required field missing on node {node_id}: {field!r}")
    return errors


def dropped_fields(nodes) -> list[str]:
    """Campos do grafo que a allowlist deixou de fora, para o build anunciar.

    Silêncio aqui seria a mesma armadilha da blacklist ao contrário: um campo
    novo e legítimo sumiria do mapa sem nenhum sinal, e o defeito só apareceria
    como um painel vazio no site publicado.
    """
    seen: set[str] = set()
    for node in nodes:
        seen.update(set(node) - set(PUBLIC_NODE_FIELDS))
    return sorted(seen)


def sanitize(nodes, published: set[str]):
    """Return public copies of the wiki nodes, in place of the private ones."""
    public_nodes = []
    for node in nodes:
        slug = essay_slug(node["id"])
        is_public = bool(slug) and slug in published

        # Allowlist: o nó público nasce vazio e só recebe o que está declarado.
        # `if field in node` preserva a ausência legítima — um nó de referência
        # não tem `status`, e inventar `None` só encheria o payload.
        clean = {field: node[field] for field in PASSTHROUGH_NODE_FIELDS if field in node}

        # A read link exists only for an authorized essay.
        clean["htmlFile"] = f"essays/{slug}.html" if is_public else None
        clean["public"] = is_public

        if node["type"] not in SUMMARY_TYPES:
            clean.pop("summary", None)
        if node["type"] == "reference":
            clean["title"] = clean_citation(node["title"])
            # Only a bibliography entry keeps an outbound URL.
            clean["url"] = node.get("url")
        else:
            clean["url"] = None

        public_nodes.append(clean)
    return public_nodes


# Chrome added only to the public copies: a way back to the Atlas, a switch
# between the two maps, and a theme that follows the site. The map's own index
# panel stays — it already highlights a node on click and opens the public page.
PUBLIC_CHROME = """
<style>
  /* z-index baixo (8): o cromo fica sob a caixa de opções/Estilo (modal
     z-index 20 e popover 30) e sob o painel, então a última linha do painel
     expandido nunca fica escondida atrás dos botões de voltar. */
  #sb-back {
    position: fixed; left: 16px; bottom: 16px; z-index: 8;
    display: inline-flex; align-items: center; gap: 8px;
    min-height: 36px; padding: 9px 15px; border-radius: 999px;
    border: 1px solid rgba(255,255,255,.16);
    background: rgba(9,9,9,.88); backdrop-filter: blur(10px);
    color: #e8eef7; font: 600 14px/1 Inter, system-ui, sans-serif;
    text-decoration: none; white-space: nowrap;
  }
  #sb-back:hover { border-color: rgba(255,255,255,.4); }
  #sb-map-switch {
    position: fixed; right: 16px; bottom: 16px; z-index: 8;
    display: inline-flex; gap: 8px;
  }
  #sb-map-switch a {
    box-sizing: border-box; display: inline-flex; align-items: center; justify-content: center;
    height: 36px; min-height: 36px; padding: 0 15px; border-radius: 999px;
    border: 1px solid rgba(255,255,255,.16);
    background: rgba(9,9,9,.88); backdrop-filter: blur(10px);
    color: #e8eef7; font: 600 14px/1 Inter, system-ui, sans-serif;
    text-decoration: none; white-space: nowrap;
  }
  #sb-map-switch a:hover, #sb-theme:hover { border-color: rgba(255,255,255,.4); }
  #sb-theme {
    box-sizing: border-box; width: 36px; height: 36px; min-height: 36px; padding: 0;
    display: grid; place-items: center; border-radius: 999px;
    border: 1px solid rgba(255,255,255,.16);
    background: rgba(9,9,9,.88); backdrop-filter: blur(10px);
    color: #e8eef7; font: 600 18px/1 Inter, system-ui, sans-serif; cursor: pointer;
  }
  /* In the light Atlas the floating chrome inverts with it. */
  :root[data-theme="light"] #sb-back,
  :root[data-theme="light"] #sb-map-switch a,
  :root[data-theme="light"] #sb-theme {
    background: rgba(255,255,255,.9);
    border-color: rgba(16,28,46,.16);
    color: #101c2e;
  }
  #sb-map-switch a[aria-current="page"] { color: #c9a45c; border-color: #c9a45c; }
  :root[data-theme="light"] #sb-map-switch a[aria-current="page"] { color: #2f5fb0; border-color: #2f5fb0; }
  /* The options panel must end above the floating chrome, never behind it —
     the detail card now grows with the connection lists, so its last row
     would otherwise sit under the "Second Brain Atlas" pill. */
  #panel { padding-bottom: 60px; }
  @media (max-width: 760px) {
    /* No celular o painel e uma folha colada no rodape — e o cromo flutuante
       ficava POR CIMA dela, cobrindo o fim do cartao de detalhe. Levantar a
       folha acima do cromo e a unica correcao que nao esconde nenhum dos dois. */
    #panel { bottom: calc(64px + env(safe-area-inset-bottom)); border-radius: 14px; }
    #panel, .panel, aside { padding-bottom: 12px; }
    #sb-back, #sb-map-switch a { box-sizing:border-box; height:36px; min-height:36px; padding:0 12px; font-size:13px; }
    #sb-theme { width:36px; height:36px; min-height:36px; padding:0; font-size:21px; line-height:1; }
  }
  /* Tema claro: o fundo e os controles do mapa seguem o tema do site. O
     fundo do canvas também é pintado por JS (ver script ao final), então
     este bloco só alinha painéis/controles que usam CSS variable. */
  html[data-theme="light"] {
    --bg: #ffffff;
    --panel: #ffffff;
    --panel-border: #d7dde4;
    --ink: #1a1f24;
    --ink-dim: #5b6570;
    --edge: #a7b0ba;
    --edge-ref: #b0b8c0;
    --reference: #6b7280;
  }
  html[data-theme="light"] #search,
  html[data-theme="light"] .btn,
  html[data-theme="light"] .idx-expand,
  html[data-theme="light"] #idx-search,
  html[data-theme="light"] .idx-range input[type="number"],
  html[data-theme="light"] #idx-maturidade,
  html[data-theme="light"] .idx-read { background: #ffffff; }
  html[data-theme="light"] .legend-item:hover,
  html[data-theme="light"] #modal .close { background: rgba(0,0,0,.05); }
</style>
<a id="sb-back" href="index.html">&larr; Second Brain Atlas</a>
<nav id="sb-map-switch" aria-label="Trocar de mapa">
  <a href="graph.html"__GRAPH_CURRENT__>Grafo</a>
  <a href="sphere.html"__SPHERE_CURRENT__>Globo</a>
  <button type="button" id="sb-theme" aria-label="Alternar tema" aria-pressed="false">&#9680;</button>
</nav>
<script>
  // The map follows the Atlas: same stored theme key, same background.
  // Framing is the renderer's job — it now fits the whole base on load for
  // every screen size, so there is nothing to press from out here.
  (function () {
    var updateMapStyle = function (theme) {
      try {
        // O tema manda no fundo, sempre. Antes um estilo salvo em
        // `localStorage` (painel Estilo) fixava `colors.background`, e
        // `applyStyle` grava esse valor como `--bg` INLINE no <html> — inline
        // vence a regra `html[data-theme="light"]` deste mesmo bloco. O
        // resultado era o mapa abrir com fundo escuro e painéis claros no
        // tema claro, e o botão de tema só trocar a cor das letras. O resto do
        // estilo salvo (cores de nó, raio, glow) continua valendo.
        if (typeof styleConfig !== 'undefined' && typeof applyStyle === 'function') {
          styleConfig.colors.background = theme === 'light' ? '#ffffff' : '#090909';
          styleConfig.colors.edge = theme === 'light' ? '#a7b0ba' : '#858b93';
          // Migrate only the legacy factory opacity; explicit user choices survive.
          if (styleConfig.edgeOpacity === 0.35) styleConfig.edgeOpacity = 0.28;
          applyStyle(styleConfig, { silent: true });
        }
      } catch (e) {}
    };

    var apply = function (theme) {
      document.documentElement.setAttribute('data-theme', theme);
      document.documentElement.dataset.theme = theme;
      document.documentElement.style.background = theme === 'light' ? '#ffffff' : '#090909';
      document.body.style.background = theme === 'light' ? '#ffffff' : '#090909';
      var button = document.getElementById('sb-theme');
      if (button) button.setAttribute('aria-pressed', String(theme === 'light'));
      updateMapStyle(theme);
    };

    var stored = null;
    try { stored = localStorage.getItem('sb-theme'); } catch (e) { /* private mode */ }
    // Mesmo padrão do Atlas: sem escolha guardada, claro. Antes o mapa lia o
    // `prefers-color-scheme` e abria preto num celular com o sistema escuro,
    // desmentindo a página de onde o leitor veio.
    if (!stored) stored = 'light';
    apply(stored);
    document.addEventListener('click', function (event) {
      if (!event.target.closest('#sb-theme')) return;
      var next = document.documentElement.getAttribute('data-theme') === 'light' ? 'dark' : 'light';
      try { localStorage.setItem('sb-theme', next); } catch (e) { /* private mode */ }
      apply(next);
    });
  })();
</script>
"""


FAVICON_RE = re.compile(r'<link rel="(?:icon|apple-touch-icon)"[^>]*>')


def favicon_link() -> str:
    """The Atlas icon, read from the index instead of copied.

    Without it the browser asks for /favicon.ico on every map page and gets a
    404, and the tab opens with no identity — the same defect the essay pages
    had. One literal, in `scripts/site_src/index.html`.
    """
    index = (SITE_SRC_DIR / "index.html").read_text(encoding="utf-8")
    # O mapa vive na raiz do site, como o índice: os caminhos valem sem ajuste.
    return "".join(FAVICON_RE.findall(index))


def with_public_chrome(html: str, current: str) -> str:
    """Add the site navigation to a generated map and drop its index panel."""
    chrome = (PUBLIC_CHROME
              .replace("__GRAPH_CURRENT__", ' aria-current="page"' if current == "graph" else "")
              .replace("__SPHERE_CURRENT__", ' aria-current="page"' if current == "sphere" else ""))
    if "</head>" in html:
        html = html.replace("</head>", favicon_link() + "</head>", 1)
    if "</body>" in html:
        return html.replace("</body>", chrome + "</body>", 1)
    return html + chrome


def build(width: int = 1900, height: int = 1200):
    nodes, edges, isolated = build_graph.build_graph()
    tag_gaps = build_graph.compute_tag_gaps(nodes, edges)

    # The two renderers read different coordinates — the graph uses x0/y0, the
    # sphere ux/uy/uz — so both layouts run over the same nodes.
    build_graph.compute_layout(nodes, edges, width=width, height=height)
    build_sphere.compute_sphere_layout(nodes, edges)

    published = {e.slug for e in collect_public()}
    public_nodes = sanitize(nodes, published)

    unknown = dropped_fields(nodes)
    if unknown:
        print("public map: campos do grafo fora da allowlist, não publicados: "
              + ", ".join(unknown), file=sys.stderr)

    # Falha fechada: se a montagem deixar escapar chave fora do schema, o build
    # para aqui em vez de gravar o mapa e deixar o vazamento para a sentinela
    # encontrar depois — ou não encontrar.
    schema_errors = assert_public_schema(public_nodes)
    if schema_errors:
        raise ValueError("public map schema violated:\n  " + "\n  ".join(schema_errors))

    return public_nodes, edges, tag_gaps, isolated


def data_payload(nodes, edges, isolated) -> dict:
    counts: dict[str, int] = {}
    for node in nodes:
        counts[node["type"]] = counts.get(node["type"], 0) + 1
    return {
        "nodes": nodes,
        "edges": edges,
        "counts": counts,
        "published": sum(1 for n in nodes if n.get("public")),
        "isolated": len(isolated),
    }


def write(root: Path, nodes, edges, tag_gaps, isolated) -> list[tuple[str, float]]:
    root.mkdir(parents=True, exist_ok=True)
    empty_reader = {"essays": {}, "mathjax": "", "css": ""}
    written = []

    # `graph.json` NÃO é publicado. Os dois mapas embutem o payload comprimido
    # que o navegador de fato lê (`id="sb-graph-data"`), e a capa virou PNG —
    # nada no site busca este arquivo. Publicá-lo era servir 883 KB para
    # ninguém, e manter duas representações do mesmo grafo que podem divergir.
    # A versão da wiki continua existindo: `build_graph.py` grava a sua em
    # `output/graph/`, que é a lida por `/organize`.

    for name, renderer, current in (
        ("graph.html", build_graph.render_html, "graph"),
        ("sphere.html", build_sphere.render_sphere_html, "sphere"),
    ):
        path = root / name
        html = with_public_chrome(renderer(nodes, edges, tag_gaps, empty_reader), current)
        path.write_text(html, encoding="utf-8")
        written.append((name, path.stat().st_size / 1024 / 1024))

    return written


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, default=SITE_ROOT,
                    help="directory to write into (default: SITE_ROOT)")
    ap.add_argument("--json", action="store_true",
                    help="print the sanitized data instead of writing")
    args = ap.parse_args()

    nodes, edges, tag_gaps, isolated = build()

    if args.json:
        print(json.dumps(data_payload(nodes, edges, isolated),
                         ensure_ascii=False, indent=2))
        return 0

    written = write(args.output, nodes, edges, tag_gaps, isolated)
    readable = sum(1 for n in nodes if n.get("public"))
    print(f"public map: {len(nodes)} nodes, {len(edges)} edges, {readable} readable")
    for name, size in written:
        print(f"  {name:12s} {size:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
