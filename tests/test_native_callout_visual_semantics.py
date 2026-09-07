from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_structural_entity_and_stat_hooks_depend_only_on_explicit_type():
    src = (ROOT / 'scripts/lib/html_preprocess.py').read_text(encoding='utf-8')
    start = src.index('def _decorate_explicit_box_structure')
    end = src.index('def _emit_box', start)
    body = src[start:end]
    assert 'callout_type == "todo"' in body
    assert 'callout_type == "warning"' in body
    assert '.entity-meta' in body
    assert '.stat-divider' in body and '.stat-source' in body
    # No semantic/content classifier belongs in this function.
    for forbidden in ['experimento', 'pessoa', 'nome próprio', 'percent', 'emoji']:
        assert forbidden not in body.lower()


def test_todo_and_warning_pdf_follow_reserved_contract_families():
    lua = (ROOT / 'scripts/pdf_boxes.lua').read_text(encoding='utf-8')
    assert "{'callout-todo', 'boxentity', 'wikientity'}" in lua
    assert "{'callout-warning', 'boxstat', 'wikistat'}" in lua
    assert "{'callout-todo', 'boxentity', 'wikitodo'}" not in lua


def test_warning_is_stat_only_because_source_explicitly_selected_warning():
    css = (ROOT / 'scripts/essay_template.html').read_text(encoding='utf-8')
    block = css.split('.box.callout-warning > .box-title p{', 1)[1].split('}', 1)[0]
    assert 'font-size:clamp(1.75rem,4.5vw,2.3rem)' in block


def test_inner_callout_heading_disables_global_gold_numbering():
    pre = (ROOT / 'scripts/lib/html_preprocess.py').read_text(encoding='utf-8')
    lua = (ROOT / 'scripts/pdf_boxes.lua').read_text(encoding='utf-8')
    assert 'def _mark_callout_inner_headings' in pre
    header = lua[lua.index('function Header(el)'):lua.index('-- Ordinary prose', lua.index('function Header(el)')) if '-- Ordinary prose' in lua else lua.index('-- ------------------------------------------------------------------\n-- Link:', lua.index('function Header(el)'))]
    assert "has_class(el, 'entity-meta')" in header
    assert "has_class(el, 'callout-inner-heading')" in header
    assert header.index("entity-meta") < header.index("callout-inner-heading")


def test_callout_work_does_not_restyle_tables_or_global_prose():
    pdf = (ROOT / 'scripts/export_essay_pdf.py').read_text(encoding='utf-8')
    lua = (ROOT / 'scripts/pdf_boxes.lua').read_text(encoding='utf-8')
    # colortbl existed in the table subsystem before this task; there must be
    # exactly that one original import and no callout-added cell tint filter.
    assert pdf.count(r'\usepackage{colortbl}') == 1
    assert r'\cellcolor{codebg}' not in lua
    assert 'function Str(el)' not in lua
