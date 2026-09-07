from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from export_essay_pdf import (  # noqa: E402
    _sob_cabecalho_de_caixa,
    inject_chapter_kickers,
)


def test_box_title_and_internal_subtitle_are_one_pagination_header():
    source = """::: {.box .callout-example}

::: {.box-title}

Experimento Mental III

:::

#### O Cérebro Dividido

Texto da caixa.

:::
"""
    lines = source.splitlines()
    idx = lines.index("#### O Cérebro Dividido")
    assert _sob_cabecalho_de_caixa(lines, idx)

    out = inject_chapter_kickers(source)
    between = out.split("Experimento Mental III", 1)[1].split("#### O Cérebro Dividido", 1)[0]
    assert "\\sbnobreak" in between
    assert "\\sbsubneed" not in between


def test_normal_h4_keeps_exact_subheading_reservation():
    source = """Texto anterior.

#### Subtítulo Normal

Primeira linha do corpo.
"""
    lines = source.splitlines()
    idx = lines.index("#### Subtítulo Normal")
    assert not _sob_cabecalho_de_caixa(lines, idx)
    assert "\\sbsubneed{4}{Subtítulo Normal}" in inject_chapter_kickers(source)


def test_chapter_immediately_followed_by_explicit_callout_gets_nobreak():
    from scripts.lib.html_preprocess import transform_markdown
    from scripts.export_essay_pdf import inject_chapter_kickers

    src = "## Derek Parfit: e o Fim do Eu Substancial\n\n> [!note] Derek Parfit\n> corpo\n"
    parsed = transform_markdown(src)
    assert "::: {.box .callout-note}" in parsed
    out = inject_chapter_kickers(parsed)
    heading = "## Derek Parfit: e o Fim do Eu Substancial"
    after = out.split(heading, 1)[1]
    before_box = after.split("::: {.box .callout-note}", 1)[0]
    assert "\\nobreak" in before_box


def test_chapter_followed_by_plain_paragraph_does_not_get_callout_nobreak():
    from scripts.export_essay_pdf import inject_chapter_kickers

    src = "## Capítulo\n\nParágrafo normal.\n"
    out = inject_chapter_kickers(src)
    heading = "## Capítulo"
    after = out.split(heading, 1)[1]
    assert "\\nobreak" not in after

