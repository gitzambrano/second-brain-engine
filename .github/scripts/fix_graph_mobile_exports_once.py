from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRAPH = ROOT / "scripts" / "build_graph.py"
PUBLIC = ROOT / "scripts" / "lib" / "build_public_map.py"
TEST = ROOT / "tests" / "test_graph_mobile_exports_regressions.py"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: expected one occurrence, got {n}")
    return text.replace(old, new, 1)


graph = GRAPH.read_text(encoding="utf-8")
graph = replace_once(
    graph,
    "const LABEL_SHOW_AT = 0.96;\nconst LABEL_HIDE_AT = 0.90;",
    "const LABEL_SHOW_AT = DEVICE_IS_MOBILE ? 0.62 : 0.78;\nconst LABEL_HIDE_AT = DEVICE_IS_MOBILE ? 0.56 : 0.72;",
    "label thresholds",
)

# PNG: never resize/redraw the live canvas. The visible canvas is already HiDPI;
# toBlob is asynchronous and keeps the interaction surface stable while encoding.
png_start = graph.index("const EXPORT_SCALE = 3;")
svg_marker = graph.index("// ---- Exportar SVG", png_start)
png_block = '''let pngExportBusy = false;
const exportPngBtn = document.getElementById("btn-export-png");
exportPngBtn.addEventListener("click", () => {
  if (pngExportBusy) return;
  pngExportBusy = true;
  exportPngBtn.setAttribute("aria-busy", "true");
  // Let the pressed/busy state paint before the browser starts encoding.
  requestAnimationFrame(() => {
    canvas.toBlob((blob) => {
      pngExportBusy = false;
      exportPngBtn.removeAttribute("aria-busy");
      if (!blob) {
        alert("Não foi possível gerar o PNG neste navegador.");
        return;
      }
      const url = URL.createObjectURL(blob);
      const stamp = new Date().toISOString().slice(0, 10);
      const a = document.createElement("a");
      a.href = url;
      a.download = `grafo-second-brain-${stamp}.png`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      // Keep the object URL alive through the download hand-off on mobile.
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }, "image/png");
  });
});

'''
graph = graph[:png_start] + png_block + graph[svg_marker:]

# SVG: replace the canvas2svg/CDN path with a self-contained native SVG writer.
# It runs synchronously inside the user's click, so Android browsers do not lose
# the user gesture before the download starts.
svg_start = graph.index("// ---- Exportar SVG")
svg_end = graph.index("// Fechar o modal de Estilo", svg_start)
svg_block = r'''// ---- Exportar SVG ---------------------------------------------------------
// Gera SVG diretamente, sem canvas2svg/CDN. O download acontece no mesmo
// gesto de clique, o que é importante no Android: downloads disparados depois
// de uma Promise de rede podem ser bloqueados por perder o gesto do usuário.
function escapeXml(value) {
  return String(value).replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&apos;"
  }[ch]));
}
function svgNumber(value) {
  const n = Number(value);
  return Number.isFinite(n) ? String(Math.round(n * 1000) / 1000) : "0";
}
function buildSvgExport() {
  zoomTransform = d3.zoomTransform(canvas);
  const bg = (styleConfig.colors && styleConfig.colors.background) || "#1b1e21";
  const edgeColor = (styleConfig.colors && styleConfig.colors.edge) || "#858b93";
  const [wx0, wy0] = zoomTransform.invert([0, 0]);
  const [wx1, wy1] = zoomTransform.invert([width, height]);
  const pad = 80;
  const inView = n => n && n.x >= wx0 - pad && n.x <= wx1 + pad && n.y >= wy0 - pad && n.y <= wy1 + pad;
  const parts = [
    '<?xml version="1.0" encoding="UTF-8"?>',
    `<svg xmlns="http://www.w3.org/2000/svg" width="${svgNumber(width)}" height="${svgNumber(height)}" viewBox="0 0 ${svgNumber(width)} ${svgNumber(height)}" preserveAspectRatio="xMidYMid meet">`,
    `<rect width="100%" height="100%" fill="${escapeXml(bg)}"/>`,
    `<g transform="translate(${svgNumber(zoomTransform.x)} ${svgNumber(zoomTransform.y)}) scale(${svgNumber(zoomTransform.k)})">`,
  ];

  if (styleConfig.edgeVisibility !== "off") {
    data.edges.forEach(e => {
      const s = endpoint(e.source), t = endpoint(e.target);
      if (!s || !t || !isNodeVisible(s) || !isNodeVisible(t)) return;
      if (!inView(s) && !inView(t)) return;
      const opacity = edgeDimmed(e) ? 0.08 : styleConfig.edgeOpacity;
      const dash = e.kind === "reference" ? ' stroke-dasharray="3 3"' : "";
      parts.push(`<line x1="${svgNumber(s.x)}" y1="${svgNumber(s.y)}" x2="${svgNumber(t.x)}" y2="${svgNumber(t.y)}" stroke="${escapeXml(edgeColor)}" stroke-opacity="${svgNumber(opacity)}" stroke-width="1.2" vector-effect="non-scaling-stroke"${dash}/>`);
    });
  }

  data.nodes.forEach(n => {
    if (!isNodeVisible(n) || !inView(n)) return;
    const r = radiusOf(n);
    const opacity = nodeDimmed(n) ? 0.08 : 1;
    const fill = typeColorRaw(n);
    parts.push(`<circle cx="${svgNumber(n.x)}" cy="${svgNumber(n.y)}" r="${svgNumber(r)}" fill="${escapeXml(fill)}" fill-opacity="${svgNumber(opacity)}" stroke="#0b1220" stroke-width="1" vector-effect="non-scaling-stroke"/>`);
  });

  if (labelsShown) {
    const labelColor = getLabelColor();
    data.nodes.forEach(n => {
      if (n.type === "reference" || !isNodeVisible(n) || !inView(n)) return;
      const opacity = nodeDimmed(n) ? 0.08 : (isLightTheme() ? 0.78 : 0.85);
      const y = n.y - (2 + radiusOf(n));
      parts.push(`<text x="${svgNumber(n.x)}" y="${svgNumber(y)}" fill="${escapeXml(labelColor)}" fill-opacity="${svgNumber(opacity)}" font-size="${svgNumber(styleConfig.labelSize)}" font-family="-apple-system,Segoe UI,Helvetica,Arial,sans-serif" text-anchor="middle">${escapeXml(n.title)}</text>`);
    });
  }

  parts.push("</g></svg>");
  return parts.join("\n");
}

function exportSvgFile() {
  const svgString = buildSvgExport();
  const blob = new Blob([svgString], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const stamp = new Date().toISOString().slice(0, 10);
  const a = document.createElement("a");
  a.href = url;
  a.download = `grafo-second-brain-${stamp}.svg`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

document.getElementById("btn-export-svg").addEventListener("click", exportSvgFile);

'''
graph = graph[:svg_start] + svg_block + graph[svg_end:]

# Remove the obsolete two-choice popover from the generated HTML template.
pop_start = graph.index('<div id="export-svg-popover">')
pop_end = graph.index('</div>', pop_start) + len('</div>')
graph = graph[:pop_start] + graph[pop_end:]
GRAPH.write_text(graph, encoding="utf-8")

public = PUBLIC.read_text(encoding="utf-8")
public = replace_once(
    public,
    '''  #sb-map-switch a {
    min-height: 36px; padding: 9px 15px; border-radius: 999px;
    border: 1px solid rgba(255,255,255,.16);
    background: rgba(9,9,9,.88); backdrop-filter: blur(10px);
    color: #e8eef7; font: 600 14px/1 Inter, system-ui, sans-serif;
    text-decoration: none; white-space: nowrap;
  }''',
    '''  #sb-map-switch a {
    box-sizing: border-box; display: inline-flex; align-items: center; justify-content: center;
    height: 36px; min-height: 36px; padding: 0 15px; border-radius: 999px;
    border: 1px solid rgba(255,255,255,.16);
    background: rgba(9,9,9,.88); backdrop-filter: blur(10px);
    color: #e8eef7; font: 600 14px/1 Inter, system-ui, sans-serif;
    text-decoration: none; white-space: nowrap;
  }''',
    "map switch controls",
)
public = replace_once(
    public,
    '''  #sb-theme {
    min-height: 36px; padding: 9px 13px; border-radius: 999px;
    border: 1px solid rgba(255,255,255,.16);
    background: rgba(9,9,9,.88); backdrop-filter: blur(10px);
    color: #e8eef7; font: 600 14px/1 Inter, system-ui, sans-serif; cursor: pointer;
  }''',
    '''  #sb-theme {
    box-sizing: border-box; width: 36px; height: 36px; min-height: 36px; padding: 0;
    display: grid; place-items: center; border-radius: 999px;
    border: 1px solid rgba(255,255,255,.16);
    background: rgba(9,9,9,.88); backdrop-filter: blur(10px);
    color: #e8eef7; font: 600 18px/1 Inter, system-ui, sans-serif; cursor: pointer;
  }''',
    "map theme control",
)
public = replace_once(
    public,
    '    #sb-back, #sb-map-switch a, #sb-theme { min-height:36px; padding:8px 12px; font-size:13px; }',
    '    #sb-back, #sb-map-switch a { box-sizing:border-box; height:36px; min-height:36px; padding:0 12px; font-size:13px; }\n    #sb-theme { width:36px; height:36px; min-height:36px; padding:0; font-size:21px; line-height:1; }',
    "mobile public chrome",
)
PUBLIC.write_text(public, encoding="utf-8")

TEST.write_text(r'''from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = (ROOT / "scripts" / "build_graph.py").read_text(encoding="utf-8")
PUBLIC = (ROOT / "scripts" / "lib" / "build_public_map.py").read_text(encoding="utf-8")


def test_graph_labels_appear_materially_earlier_on_mobile():
    assert "const LABEL_SHOW_AT = DEVICE_IS_MOBILE ? 0.62 : 0.78;" in GRAPH
    assert "const LABEL_HIDE_AT = DEVICE_IS_MOBILE ? 0.56 : 0.72;" in GRAPH


def test_png_export_never_resizes_the_live_canvas():
    block = GRAPH.split('let pngExportBusy = false;', 1)[1].split('// ---- Exportar SVG', 1)[0]
    assert 'canvas.toBlob' in block
    assert 'requestAnimationFrame' in block
    assert 'canvas.width =' not in block
    assert 'canvas.height =' not in block
    assert 'EXPORT_SCALE' not in block


def test_svg_export_is_self_contained_and_direct():
    block = GRAPH.split('// ---- Exportar SVG', 1)[1].split('// Fechar o modal de Estilo', 1)[0]
    assert 'buildSvgExport' in block
    assert 'new Blob([svgString]' in block
    assert 'btn-export-svg").addEventListener("click", exportSvgFile)' in block
    assert 'ensureC2S' not in block
    assert 'canvas2svg' not in block
    assert 'export-svg-popover' not in GRAPH


def test_public_map_switch_text_is_flex_centered_and_theme_glyph_is_not_shrunk():
    assert '#sb-map-switch a {' in PUBLIC
    assert 'display: inline-flex; align-items: center; justify-content: center;' in PUBLIC
    assert 'height: 36px; min-height: 36px; padding: 0 15px;' in PUBLIC
    assert '#sb-theme {' in PUBLIC
    assert 'display: grid; place-items: center;' in PUBLIC
    assert '#sb-theme { width:36px; height:36px; min-height:36px; padding:0; font-size:21px; line-height:1; }' in PUBLIC
    assert '#sb-back, #sb-map-switch a, #sb-theme { min-height:36px; padding:8px 12px; font-size:13px; }' not in PUBLIC
''', encoding="utf-8")

print("patched graph exports, label thresholds, public controls, and regression tests")
