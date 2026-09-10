from pathlib import Path

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
