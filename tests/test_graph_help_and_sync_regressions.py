"""Regression tests for:
1) Syncing hiddenTypes between graph and sphere via localStorage
2) Earlier label zoom threshold on graph and sphere
3) Replacing verbose inline style hints with help popup/tooltips
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH = (ROOT / "scripts" / "build_graph.py").read_text(encoding="utf-8")
SPHERE = (ROOT / "scripts" / "build_sphere.py").read_text(encoding="utf-8")


def test_hidden_types_persisted_and_shared_between_graph_and_sphere():
    for name, src in (("graph", GRAPH), ("sphere", SPHERE)):
        assert 'const HIDDEN_TYPES_KEY = "sb-hidden-types-v1";' in src, f"{name} missing HIDDEN_TYPES_KEY"
        assert "function loadHiddenTypes()" in src, f"{name} missing loadHiddenTypes"
        assert "function saveHiddenTypes()" in src, f"{name} missing saveHiddenTypes"
        assert "function syncLegendDom()" in src, f"{name} missing syncLegendDom"
        assert "saveHiddenTypes();" in src, f"{name} missing saveHiddenTypes invocation"


def test_label_zoom_thresholds_appear_earlier():
    assert "const LABEL_SHOW_AT = DEVICE_IS_MOBILE ? 0.48 : 0.60;" in GRAPH
    assert "const LABEL_HIDE_AT = DEVICE_IS_MOBILE ? 0.42 : 0.54;" in GRAPH
    assert "zoomK >= 0.7;" in SPHERE


def test_options_panel_has_help_popup_and_no_inline_hints():
    for name, src in (("graph", GRAPH), ("sphere", SPHERE)):
        assert '<div id="style-help-popup"' in src, f"{name} missing style-help-popup"
        assert ".style-help-popup {" in src, f"{name} missing style-help-popup CSS"
        assert ".style-help-icon {" in src, f"{name} missing style-help-icon CSS"
        assert "optLabel(" in src, f"{name} missing optLabel helper"
        assert "data-help=" in src, f"{name} missing data-help attribute"

        # Check renderStylePanel has no verbose inline hint paragraphs
        panel_code = src.split("function renderStylePanel(", 1)[1].split("document.getElementById(\"btn-style\")", 1)[0]
        assert '<p class="style-hint">' not in panel_code, f"{name} still has <p class=\"style-hint\"> in renderStylePanel"
