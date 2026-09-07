from pathlib import Path

from scripts.lib.html_preprocess import transform_markdown

ROOT = Path(__file__).resolve().parents[1]


def test_untitled_callout_gets_structural_class_only():
    untitled = transform_markdown("> [!info]\n> Corpo sem titulo.\n")
    titled = transform_markdown("> [!info] Titulo autoral\n> Corpo.\n")
    assert ".box-untitled" in untitled
    assert ".box-untitled" not in titled
    assert ".callout-info" in untitled and ".callout-info" in titled


def test_html_untitled_box_has_top_breathing_room():
    css = (ROOT / "scripts" / "essay_template.html").read_text(encoding="utf-8")
    assert ".box.box-untitled{padding-top:.95rem;}" in css


def test_pdf_titled_and_untitled_tab_top_spacing_are_distinct():
    pdf = (ROOT / "scripts" / "export_essay_pdf.py").read_text(encoding="utf-8")
    assert r"\newenvironment{wikitabuntitled}" in pdf
    assert "top=0pt,bottom=10pt" in pdf
    assert "top=13pt,bottom=10pt" in pdf


def test_pdf_table_header_tint_is_narrow_and_subtle():
    lua = (ROOT / "scripts" / "pdf_boxes.lua").read_text(encoding="utf-8")
    pdf = (ROOT / "scripts" / "export_essay_pdf.py").read_text(encoding="utf-8")
    assert r"\usepackage{colortbl}" in pdf
    assert r"\\cellcolor{sbink!8!white}" in lua
    assert "local CAP = 90" in lua
    assert "w[i] / total" in lua


def test_pdf_untitled_routing_uses_structural_class():
    lua = (ROOT / "scripts" / "pdf_boxes.lua").read_text(encoding="utf-8")
    assert "has_class(el, 'box-untitled') and env == 'wikitab'" in lua
    assert "env = 'wikitabuntitled'" in lua
