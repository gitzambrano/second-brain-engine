import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def _load_exporter():
    sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        "visual_pdf_exporter", SCRIPTS / "export_essay_pdf.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_highlighted_code_blocks_keep_internal_mobile_scroll():
    template = (SCRIPTS / "essay_template.html").read_text(encoding="utf-8")
    assert "pre.sourceCode{overflow-x:auto !important" in template


def test_unicode_symbols_have_portable_pdf_mapping():
    exporter = (SCRIPTS / "export_essay_pdf.py").read_text(encoding="utf-8")
    for line in (
        r"\newunicodechar{ℵ}{\ensuremath{\aleph}}",
        r"\newunicodechar{₀}{\ensuremath{{}_0}}",
        r"\newunicodechar{₁}{\ensuremath{{}_1}}",
        r"\newunicodechar{✓}{\ding{51}}",
        r"\newunicodechar{✗}{\ding{55}}",
    ):
        assert line in exporter


def test_display_math_fit_uses_display_delimiters():
    lua = (SCRIPTS / "pdf_boxes.lua").read_text(encoding="utf-8")
    assert r"\\[\\sbfit{" in lua
    assert r"\\makebox[\\linewidth][c]{\\sbfit{" not in lua


def test_sumario_is_measured_automatically_without_frontmatter_knob():
    exporter = (SCRIPTS / "export_essay_pdf.py").read_text(encoding="utf-8")
    assert r"\newsavebox{\sbtocmeasurebox}" in exporter
    assert r"\Needspace{\sbtocneed}" in exporter
    assert "pdf_sumario_newpage" not in exporter
    assert "pdf_fit_display_math" not in exporter


def test_sumario_kicker_is_inside_measured_toc_block():
    mod = _load_exporter()
    source = "## Sumário\n\n- [[#Introdução]]\n\n## Introdução\n\nTexto."
    out = mod.inject_chapter_kickers(source)
    before_intro = out.split("## Introdução", 1)[0]
    assert r"\sbkicker{Sumário}" not in before_intro
    assert "## Sumário" in before_intro
    assert r"\sbkicker{Introdução}" in out


def test_table_pressure_is_structural_and_header_local():
    lua = (SCRIPTS / "pdf_boxes.lua").read_text(encoding="utf-8")
    assert "local total_floor = 0" in lua
    assert "if total_floor > CAP and el.head and el.head.rows then" in lua
    assert r"\\footnotesize{}" in lua
    assert r"\\begingroup\\footnotesize%" not in lua


def test_pdf_table_headers_prevent_hyphenation_before_breaking_words():
    lua = (SCRIPTS / "pdf_boxes.lua").read_text(encoding="utf-8")
    assert r"\\hyphenpenalty=10000\\exhyphenpenalty=10000\\raggedright" in lua


def test_pdf_reference_tokens_get_discretionary_breaks():
    lua = (SCRIPTS / "pdf_boxes.lua").read_text(encoding="utf-8")
    assert "local function break_reference_tokens(inlines)" in lua
    assert "new_content = break_reference_tokens(new_content)" in lua
    assert r"\\allowbreak{}" in lua


def test_pdf_table_word_floor_has_real_font_and_padding_margin():
    lua = (SCRIPTS / "pdf_boxes.lua").read_text(encoding="utf-8")
    assert "floor_[i] = math.max(floor_[i] * 1.30, 3)" in lua


def test_visual_export_has_no_per_essay_controls_or_known_slugs():
    combined = "\n".join(
        (SCRIPTS / name).read_text(encoding="utf-8")
        for name in ("export_essay_pdf.py", "pdf_boxes.lua", "essay_template.html")
    )
    for forbidden in (
        "pdf_sumario_newpage",
        "pdf_fit_display_math",
        "cy-inflow-uniforme-coleman",
        "epistemologia-e-limites-do-conhecimento",
        "forma-do-universo",
        "definicoes-de-vida",
    ):
        assert forbidden not in combined

# Final CI trigger after the PDF-spacing and Kit-fixture gate fixes.
