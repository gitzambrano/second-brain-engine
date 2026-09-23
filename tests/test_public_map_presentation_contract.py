"""Contracts for the public graph and globe presentation defaults."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_maps_start_with_quieter_edges_and_true_auto_labels():
    graph = (ROOT / "scripts" / "build_graph.py").read_text(encoding="utf-8")
    sphere = (ROOT / "scripts" / "build_sphere.py").read_text(encoding="utf-8")

    assert '"edgeOpacity": 0.35' in graph
    assert '"edgeOpacity": 0.35' in sphere
    assert 'labels: "auto"' in graph
    assert 'labels: "auto"' in sphere
    assert "const LABEL_SHOW_AT = 1.55" in graph
    assert "const LABEL_HIDE_AT = 1.45" in graph


def test_map_chrome_uses_larger_nonwrapping_navigation_labels():
    source = (ROOT / "scripts" / "lib" / "build_public_map.py").read_text(encoding="utf-8")

    assert "font: 600 14px/1 Inter" in source
    assert "white-space: nowrap;" in source

def test_graph_default_has_no_node_halo_and_migrates_the_legacy_default_once():
    graph = (ROOT / "scripts" / "build_graph.py").read_text(encoding="utf-8")

    python_defaults = graph.split("GRAPH_STYLE_MOBILE_OVERRIDES", 1)[0]
    factory_fallback = graph.split("const FACTORY_STYLE =", 1)[1].split("const MOBILE_OVERRIDES", 1)[0]

    assert '"glow": "off",' in python_defaults
    assert 'glow: "off"' in factory_fallback
    assert 'const STYLE_GLOW_MIGRATION_KEY = "sb-graph-glow-default-v2";' in graph
    assert 'saved.glow === "leve"' in graph
    assert 'saved.glow = "off";' in graph

