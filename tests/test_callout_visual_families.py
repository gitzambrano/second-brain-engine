from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_html_visual_families_are_selected_only_by_explicit_type_classes():
    t = (ROOT / "scripts" / "essay_template.html").read_text(encoding="utf-8")
    assert "Explicit callout visual families v2" in t
    for typ in ("example", "info", "abstract", "note", "todo", "warning"):
        assert f"callout-{typ}" in t
    assert ".box.callout-todo" in t
    assert ".box.callout-warning" in t
    # Contract-reserved structures: explicit todo + authored H4 is entity
    # metadata; explicit warning + authored rule may expose stat source.
    assert ".callout-todo > h4.entity-meta" in t
    assert ".callout-warning > .stat-source" in t


def test_pdf_maps_explicit_types_to_fixed_environments():
    lua = (ROOT / "scripts" / "pdf_boxes.lua").read_text(encoding="utf-8")
    expected = {
        "callout-example": "wikitab",
        "callout-info": "wikitab",
        "callout-abstract": "wikitab",
        "callout-note": "wikinote",
        "callout-todo": "wikientity",
        "callout-warning": "wikistat",
    }
    for cls, env in expected.items():
        assert cls in lua and env in lua
    assert "get_box_style" in lua
    assert "get_box_color" not in lua


def test_pdf_has_dedicated_family_environments():
    pdf = (ROOT / "scripts" / "export_essay_pdf.py").read_text(encoding="utf-8")
    for env in ("wikitab", "wikinote", "wikientity", "wikistat", "wikistate"):
        assert f"{{{env}}}" in pdf
    assert "\\wbentitymeta" in pdf
    assert "\\wbstatdivider" in pdf
