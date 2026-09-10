from __future__ import annotations

import json
from pathlib import Path

import pymupdf as fitz
import pytest
from conftest import run_script


def _data_root(tmp_path: Path) -> Path:
    root = tmp_path / "brain"
    for rel in ("output/html", "output/pdf", "wiki/essays"):
        (root / rel).mkdir(parents=True, exist_ok=True)
    return root


@pytest.mark.html
def test_html_render_checker_accepts_valid_and_rejects_broken(tmp_path):
    root = _data_root(tmp_path)
    good = root / "output/html/good.html"
    good.write_text(
        '<!DOCTYPE html><html lang="pt-BR"><head><meta charset="utf-8">'
        '<style>body{max-width:800px;margin:auto}</style></head><body>'
        '<a href="#x">x</a><h2 id="x">X</h2><p>ok</p></body></html>',
        encoding="utf-8",
    )
    ok = run_script("check_html_browser.py", "good", "--json", data_root=root)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    payload = json.loads(ok.stdout)
    assert payload["errors"] == 0

    bad = root / "output/html/bad.html"
    bad.write_text(
        '<!DOCTYPE html><html><body style="width:2000px">'
        '<a href="#missing">bad</a><p>[[raw]]</p></body></html>',
        encoding="utf-8",
    )
    fail = run_script("check_html_browser.py", "bad", "--json", data_root=root)
    assert fail.returncode == 1, fail.stdout + fail.stderr
    payload = json.loads(fail.stdout)
    codes = {x["code"] for x in payload["issues"]}
    assert {"PAGE_HORIZONTAL_OVERFLOW", "BROKEN_TOC_NAVIGATION", "VISIBLE_WIKILINK"} <= codes


@pytest.mark.html
def test_structure_checker_flags_box_that_swallowed_a_chapter(tmp_path):
    """Caixa é callout, não capítulo: heading de seção dentro dela é erro."""
    root = _data_root(tmp_path)
    (root / "output/html/leak.html").write_text(
        '<!DOCTYPE html><html><body><div class="content">'
        '<div class="box aviso"><div class="box-badge"><p>Aviso</p></div>'
        '<p>corpo do callout</p><h2 id="s">Seção engolida</h2>'
        + "<p>bloco</p>" * 20
        + "</div></div></body></html>",
        encoding="utf-8",
    )
    fail = run_script("check_html_structure.py", "leak", "--json", data_root=root)
    assert fail.returncode == 1, fail.stdout + fail.stderr
    payload = json.loads(fail.stdout)
    codes = {i["code"] for values in payload["issues"].values() for i in values}
    assert {"BOX_CONTAINS_SECTION", "BOX_TOO_MANY_BLOCKS"} <= codes


@pytest.mark.pdf
def test_pdf_checkers_accept_valid_and_reject_invalid(tmp_path):
    root = _data_root(tmp_path)
    good = root / "output/pdf/good.pdf"
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=595.28, height=841.89)
        if i == 2:
            page.insert_text((60, 80), "Capítulo", fontsize=18)
            page.insert_text((60, 115), "Corpo válido.", fontsize=12)
        else:
            page.insert_text((60, 80), "Capa" if i == 0 else "Sumário", fontsize=14)
    doc.save(good)
    doc.close()
    content = run_script("check_pdf_content.py", "good", "--json", data_root=root)
    layout = run_script("check_pdf_layout.py", "good", "--json", data_root=root)
    assert content.returncode == 0, content.stdout + content.stderr
    assert layout.returncode == 0, layout.stdout + layout.stderr

    bad = root / "output/pdf/bad.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.insert_text((20, 40), "bad", fontsize=12)
    doc.save(bad)
    doc.close()
    broken = run_script("check_pdf_content.py", "bad", "--json", data_root=root)
    assert broken.returncode == 1, broken.stdout + broken.stderr
    payload = json.loads(broken.stdout)
    assert any(i["code"] == "PAGE_SIZE_INVALID" for i in payload["issues"])


@pytest.mark.pdf
def test_export_parity_checker_detects_missing_heading(tmp_path):
    root = _data_root(tmp_path)
    md = root / "wiki/essays/parity.md"
    md.write_text(
        """---
tags: [Teste]
sources: []
created: 2026-08-31
updated: 2026-08-31
status: draft
summary: "Resumo sintético."
---
# Parity

## Capítulo Um

Texto.

## Referências

[1] A., *Título Sintético*, 2026. [Link](https://example.com)

## Conexões

[[x|X]]
""",
        encoding="utf-8",
    )
    html = root / "output/html/parity.html"
    html.write_text(
        '<!DOCTYPE html><html><body><h1>Parity</h1><h2>Capítulo Um</h2>'
        '<h2>Referências</h2><p>Título Sintético</p></body></html>',
        encoding="utf-8",
    )
    pdf = root / "output/pdf/parity.pdf"
    doc = fitz.open()
    page = doc.new_page(width=595.28, height=841.89)
    y = 60
    for text, size in (("Parity", 18), ("Capítulo Um", 16), ("Referências", 16), ("Título Sintético", 12)):
        page.insert_text((60, y), text, fontsize=size)
        y += 40
    doc.save(pdf)
    doc.close()
    good = run_script("check_export_parity.py", "parity", "--json", data_root=root)
    assert good.returncode == 0, good.stdout + good.stderr

    html.write_text(
        html.read_text(encoding="utf-8").replace("Capítulo Um", "Capítulo Removido"),
        encoding="utf-8",
    )
    broken = run_script("check_export_parity.py", "parity", "--json", data_root=root)
    assert broken.returncode == 1
    payload = json.loads(broken.stdout)
    assert any(i["code"] == "HTML_TEXT_MISSING" for i in payload["issues"])


def test_check_repo_quick_prints_non_ascii_without_crashing(tmp_path):
    """Regression: check_repo.py deve imprimir o traço '—' sem UnicodeEncodeError no Windows (cp1252)."""
    # Roda --quick no skeleton (sem corpus) que já é suficiente para activar CheckResult.print().
    result = run_script("check_repo.py", "--quick", data_root=tmp_path / "empty")
    # Em nenhuma circunstância deve abortar com traceback de UnicodeEncodeError.
    assert "UnicodeEncodeError" not in result.stderr, result.stderr
    assert result.returncode in (0, 1)  # PASS ou FAIL, nunca crash não tratado


@pytest.mark.pdf
def test_check_pdf_content_handles_inline_markdown_in_title(tmp_path):
    """Regression: título com ênfase Markdown (_Teetering_) não deve falhar com TITLE_MISSING no PDF."""
    root = _data_root(tmp_path)
    md = root / "wiki/essays/teetering.md"
    md.write_text(
        """---
tags: [Aero]
sources: []
created: 2026-08-31
updated: 2026-08-31
---
# Dinâmica de Rotor _Teetering_ Controlado

> Ensaio
> Gustavo Zambrano · Agosto de 2026

## Sumário

- [[#Capítulo]]

## Capítulo

Texto do capítulo.

## Referências

- Referência.
""",
        encoding="utf-8",
    )
    pdf = root / "output/pdf/teetering.pdf"
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=595.28, height=841.89)
        if i == 0:
            page.insert_text((60, 80), "Dinâmica de Rotor Teetering Controlado", fontsize=18)
            page.insert_text((60, 110), "Gustavo Zambrano", fontsize=12)
        elif i == 1:
            page.insert_text((60, 80), "Sumário", fontsize=14)
        else:
            page.insert_text((60, 80), "Capítulo", fontsize=14)
            page.insert_text((60, 100), "Referências", fontsize=14)
    doc.save(pdf)
    doc.close()

    result = run_script("check_pdf_content.py", "teetering", "--json", data_root=root)
    assert result.returncode == 0, result.stdout + result.stderr

