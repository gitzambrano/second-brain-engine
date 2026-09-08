from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.html_preprocess import transform_markdown  # noqa: E402


def test_plain_nested_quotes_preserve_all_levels():
    src = (
        '> “Outer starts.\n'
        '> > “Inner quote.”\n'
        '> Outer ends.”\n'
    )
    out = transform_markdown(src)
    assert out.count('{.quote}') == 2
    assert 'Outer starts.' in out
    assert 'Inner quote.' in out
    assert 'Outer ends.' in out


def test_inner_closing_mark_never_closes_outer_quote():
    src = '> Outer prose without explicit quote marks.\n> > “Inner only.”\n> Outer tail.\n'
    out = transform_markdown(src)
    assert out.count('{.quote}') == 2
    assert 'Outer tail.' in out


def test_success_inside_quote_inside_callout_is_not_direct_verdict():
    src = (
        '> [!example] Parent\n'
        '> > “quoted”\n'
        '> > > [!success] Nested in quote\n'
        '> > > body\n'
    )
    out = transform_markdown(src)
    assert '{.box .callout-example}' in out
    assert '{.quote}' in out
    assert '{.box .callout-success}' in out
    assert '{.box-verdict .callout-success}' not in out


def test_direct_success_is_still_verdict():
    src = '> [!example] Parent\n> > [!success] Verdict\n> > body\n'
    out = transform_markdown(src)
    assert '{.box-verdict .callout-success}' in out


def test_template_contract_for_tabs_quotes_verdict_and_tables():
    s = (ROOT / 'scripts' / 'essay_template.html').read_text(encoding='utf-8')
    # Sem borda em cima nem a esquerda: quem faz esses dois lados e a
    # moldura da caixa, entao o rotulo nao precisa de recuo negativo.
    assert 'display:inline-block;margin:0;' in s
    assert 'padding:0 0 1.15rem' in s
    assert 'color:var(--boxc);margin-bottom:.5rem' in s
    assert 'font-size:2.35rem' in s
    assert '.quote-text p{text-align:justify' in s
    wide = s.split('@media (min-width:1400px){', 1)[1].split('}', 2)[0]
    assert '.content > table' not in wide


def test_pdf_quote_marks_are_discreet_and_verdict_uses_parent_color():
    py = (ROOT / 'scripts' / 'export_essay_pdf.py').read_text(encoding='utf-8')
    lua = (ROOT / 'scripts' / 'pdf_boxes.lua').read_text(encoding='utf-8')
    assert r'\fontsize{18pt}{18pt}' in py
    assert r'\fontsize{34pt}{34pt}' not in py
    assert 'textcolor{wbtype}' in lua and 'rule{\\\\linewidth}{0.4pt}' in lua
    assert "has_class(el, 'verdict-tag')" in lua
