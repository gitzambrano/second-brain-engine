import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PDF = (ROOT / 'scripts' / 'export_essay_pdf.py').read_text(encoding='utf-8')


def test_every_pdf_box_has_top_padding_at_least_equal_to_bottom():
    """Caixa nenhuma encosta o texto na borda de cima.

    A unica excecao e a caixa COM faixa de titulo: ali a faixa nasce colada na
    borda superior por contrato, e o respiro fica entre a faixa e o corpo.
    """
    pares = re.findall(r"top=(\d+)pt,bottom=(\d+)pt,parbox=false", PDF)
    assert len(pares) >= 8, pares
    for topo, base in pares:
        if topo == "0":
            continue                      # wikitab: faixa colada por contrato
        assert int(topo) >= int(base), (topo, base)


def test_titled_tab_keeps_its_band_flush_and_breathes_below_it():
    assert "top=10pt,bottom=10pt,parbox=false" in PDF
    assert r"\vspace{14pt}\nobreak" in PDF   # faixa -> corpo


def test_pdf_titled_callouts_keep_body_away_from_title():
    # Regras estruturais de familia. Nenhuma palavra de titulo/corpo e olhada.
    assert r"\vspace{14pt}\nobreak" in PDF  # tab -> body
    assert r"\vspace{12pt}\nobreak" in PDF  # note/state -> body
    assert r"\vspace{10pt}\nobreak" in PDF  # entity -> body
