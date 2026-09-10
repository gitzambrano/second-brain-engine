from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
GRAPH = ROOT / "scripts" / "build_graph.py"
PUBLIC = ROOT / "scripts" / "lib" / "build_public_map.py"
INDEX = ROOT / "scripts" / "site_src" / "index.html"
ESSAY_CSS = ROOT / "scripts" / "site_src" / "essay-theme.css"
TEST = ROOT / "tests" / "test_graph_mobile_exports_regressions.py"


def replace_exact(text: str, old: str, new: str, label: str, expected=1) -> str:
    count = text.count(old)
    if count != expected:
        raise SystemExit(f"{label}: expected {expected} occurrence(s), got {count}")
    return text.replace(old, new)


def replace_between(text: str, start_marker: str, end_marker: str, replacement: str, label: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise SystemExit(f"{label}: start marker not found")
    end = text.find(end_marker, start)
    if end < 0:
        raise SystemExit(f"{label}: end marker not found")
    if text.find(start_marker, start + len(start_marker)) >= 0:
        raise SystemExit(f"{label}: expected one start marker")
    return text[:start] + replacement + text[end:]


graph = GRAPH.read_text(encoding="utf-8")
graph = replace_exact(
    graph,
    "const LABEL_SHOW_AT = 0.96;\nconst LABEL_HIDE_AT = 0.90;",
    "const LABEL_SHOW_AT = DEVICE_IS_MOBILE ? 0.62 : 0.78;\nconst LABEL_HIDE_AT = DEVICE_IS_MOBILE ? 0.56 : 0.72;",
    "label thresholds",
)

# PNG: encode the already-HiDPI live canvas without resizing/redrawing it.
png_block = '''let pngExportBusy = false;
const exportPngBtn = document.getElementById("btn-export-png");
exportPngBtn.addEventListener("click", () => {
  if (pngExportBusy) return;
  pngExportBusy = true;
  exportPngBtn.setAttribute("aria-busy", "true");
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
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    }, "image/png");
  });
});

'''
graph = replace_between(graph, "const EXPORT_SCALE = 3;", "// ---- Exportar SVG", png_block, "PNG export")

# SVG: self-contained native writer. Keeping the download in the original click
# gesture avoids Android browsers blocking it after an asynchronous network load.
svg_block = r'''// ---- Exportar SVG ---------------------------------------------------------
// Gera SVG diretamente, sem dependência externa, no mesmo gesto de clique.
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
graph = replace_between(graph, "// ---- Exportar SVG", "// Fechar o modal de Estilo", svg_block, "SVG export")

# Remove the now-dead SVG choice popover from CSS and HTML as well. The old
# repair removed only its markup, leaving CSS behind and tripping the gate.
graph, css_removed = re.subn(
    r'\n  #export-svg-popover \{.*?\n  #export-svg-popover p \{[^\n]*\}\n',
    '\n', graph, flags=re.S,
)
graph, html_removed = re.subn(
    r'\n<div id="export-svg-popover">.*?</div>\n',
    '\n', graph, flags=re.S,
)
if css_removed != 1 or html_removed != 1:
    raise SystemExit(f"legacy SVG popover cleanup: expected 1 CSS + 1 HTML, got {css_removed} + {html_removed}")
for obsolete in ("export-svg-popover", "btn-export-svg-completo", "btn-export-svg-simples", "ensureC2S"):
    if obsolete in graph:
        raise SystemExit(f"legacy SVG export token still present: {obsolete}")
GRAPH.write_text(graph, encoding="utf-8")

public = PUBLIC.read_text(encoding="utf-8")
public = replace_exact(
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
public = replace_exact(
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
public = replace_exact(
    public,
    '    #sb-back, #sb-map-switch a, #sb-theme { min-height:36px; padding:8px 12px; font-size:13px; }',
    '    #sb-back, #sb-map-switch a { box-sizing:border-box; height:36px; min-height:36px; padding:0 12px; font-size:13px; }\n    #sb-theme { width:36px; height:36px; min-height:36px; padding:0; font-size:21px; line-height:1; }',
    "mobile public chrome",
)
PUBLIC.write_text(public, encoding="utf-8")

index = INDEX.read_text(encoding="utf-8")
index = replace_exact(
    index,
    'background:color-mix(in srgb,var(--accent) 13%,var(--panel));',
    'background:var(--accent-soft);',
    "home subscribe selected background",
)
INDEX.write_text(index, encoding="utf-8")

essay_css = ESSAY_CSS.read_text(encoding="utf-8")
essay_css = replace_exact(
    essay_css,
    'background:color-mix(in srgb,var(--sb-primary) 13%,var(--sb-panel));',
    'background:var(--sb-primary-soft);',
    "essay subscribe selected background",
)
ESSAY_CSS.write_text(essay_css, encoding="utf-8")

TEST.write_text(r'''from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = (ROOT / "scripts" / "build_graph.py").read_text(encoding="utf-8")
PUBLIC = (ROOT / "scripts" / "lib" / "build_public_map.py").read_text(encoding="utf-8")
INDEX = (ROOT / "scripts" / "site_src" / "index.html").read_text(encoding="utf-8")
ESSAY_CSS = (ROOT / "scripts" / "site_src" / "essay-theme.css").read_text(encoding="utf-8")


def test_graph_labels_appear_earlier_on_mobile_and_desktop():
    assert GRAPH.count("const LABEL_SHOW_AT = DEVICE_IS_MOBILE ? 0.62 : 0.78;") == 1
    assert GRAPH.count("const LABEL_HIDE_AT = DEVICE_IS_MOBILE ? 0.56 : 0.72;") == 1


def test_png_export_never_resizes_the_live_canvas():
    assert GRAPH.count('let pngExportBusy = false;') == 1
    block = GRAPH.split('let pngExportBusy = false;', 1)[1].split('// ---- Exportar SVG', 1)[0]
    assert 'canvas.toBlob' in block
    assert 'requestAnimationFrame' in block
    assert 'canvas.width =' not in block
    assert 'canvas.height =' not in block
    assert 'EXPORT_SCALE' not in block


def test_svg_export_is_self_contained_direct_and_has_no_legacy_popover():
    assert GRAPH.count('function buildSvgExport()') == 1
    assert GRAPH.count('new Blob([svgString]') == 1
    assert GRAPH.count('btn-export-svg").addEventListener("click", exportSvgFile)') == 1
    assert 'ensureC2S' not in GRAPH
    assert 'export-svg-popover' not in GRAPH
    assert 'btn-export-svg-completo' not in GRAPH
    assert 'btn-export-svg-simples' not in GRAPH


def test_public_map_switch_text_is_flex_centered_and_theme_glyph_is_not_shrunk():
    assert 'display: inline-flex; align-items: center; justify-content: center;' in PUBLIC
    assert 'height: 36px; min-height: 36px; padding: 0 15px;' in PUBLIC
    assert 'display: grid; place-items: center;' in PUBLIC
    assert '#sb-theme { width:36px; height:36px; min-height:36px; padding:0; font-size:21px; line-height:1; }' in PUBLIC
    assert '#sb-back, #sb-map-switch a, #sb-theme { min-height:36px; padding:8px 12px; font-size:13px; }' not in PUBLIC


def test_subscribe_ctas_use_selected_soft_accent_state():
    assert 'background:var(--accent-soft);' in INDEX
    assert 'background:var(--sb-primary-soft);' in ESSAY_CSS
''', encoding="utf-8")

print("patched graph exports, labels, public controls and subscribe CTA")
