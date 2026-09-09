from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_html_tab_is_flush_and_uses_exact_frame_color():
    s = (ROOT / 'scripts/essay_template.html').read_text(encoding='utf-8')
    assert 'border:1px solid var(--boxc);' in s
    # A faixa nao tem borda em cima nem a esquerda: quem faz esses dois
    # lados e a moldura da caixa, entao ela nao precisa de recuo negativo
    # (que o `overflow:hidden` cortava, deixando duas linhas coincidentes).
    assert 'display:inline-block;margin:0;' in s
    assert 'border:1px solid var(--boxc);border-top:0;border-left:0;' in s
    # O rotulo fecha a direita e embaixo com filete proprio.
    assert 'background:color-mix(in srgb,var(--boxc) 15%,transparent);' in s
    assert 'color:var(--boxc);' in s
    assert 'font-size:13.6px;font-weight:600' in s
    # `info`/`abstract` levam o tint cheio; `example`, um mais leve —
    # mas nunca igual ao da caixa, senao o rotulo deixa de se destacar.
    assert '.box.callout-example > .box-title p{' in s
    assert 'background:color-mix(in srgb,var(--boxc) 9%,transparent);' in s


def test_pdf_tab_title_is_readable_uppercase_and_breathes():
    s = (ROOT / 'scripts/export_essay_pdf.py').read_text(encoding='utf-8')
    assert 'colback=boxbg,colframe=#1,boxrule=.55pt' in s
    assert r'\setlength{\fboxsep}{4.8pt}' in s
    assert r'\fontsize{9.6pt}{11.6pt}\selectfont\ttfamily\bfseries' in s
    assert r'\MakeUppercase{#1}' in s
    assert r'\vspace{10pt}\nobreak' in s


def test_pdf_entity_title_and_metadata_are_legible_and_spaced():
    s = (ROOT / 'scripts/export_essay_pdf.py').read_text(encoding='utf-8')
    assert r'\newenvironment{wikientity}' in s
    assert r'top=13pt,bottom=10pt' in s
    assert r'\fontsize{14pt}{17pt}\selectfont\bfseries\color{sblink}' in s
    assert r'\fontsize{11.8pt}{14pt}\selectfont\ttfamily\color{wbtype}' in s
    assert r'\vspace{8pt}\nobreak' in s


def test_inner_callout_headings_are_structural_and_not_gold_numbered():
    pre = (ROOT / 'scripts/lib/html_preprocess.py').read_text(encoding='utf-8')
    lua = (ROOT / 'scripts/pdf_boxes.lua').read_text(encoding='utf-8')
    assert 'def _mark_callout_inner_headings' in pre
    assert '.callout-inner-heading' in pre
    assert "has_class(el, 'callout-inner-heading')" in lua


def test_pdf_verdict_spacing_and_font_are_coherent():
    s = (ROOT / 'scripts/pdf_boxes.lua').read_text(encoding='utf-8')
    assert r'\vspace{12pt}' in s
    assert r'\vspace{9pt}' in s
    assert 'fontsize{9.7pt}{12pt}' in s and 'sffamily' in s and 'bfseries' in s
    verdict = s[s.index('function Span(el)'):s.index('-- ------------------------------------------------------------------\n-- Div:')]
    assert r'\ttfamily' not in verdict


def test_callout_task_leaves_table_renderer_alone():
    py = (ROOT / 'scripts/export_essay_pdf.py').read_text(encoding='utf-8')
    lua = (ROOT / 'scripts/pdf_boxes.lua').read_text(encoding='utf-8')
    assert py.count(r'\usepackage{colortbl}') == 1
    assert r'\cellcolor{codebg}' not in lua
