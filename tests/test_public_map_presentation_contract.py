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
