from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.html_preprocess import (  # noqa: E402
    CalloutError, NATIVE_TYPES, lint_source, transform_markdown,
)


def test_plain_blockquote_is_never_inferred_as_box():
    out = transform_markdown("> Experimento Mental I\n> ⚠️ Atenção\n> corpo\n")
    assert "{.quote}" in out
    assert ".experimento" not in out
    assert ".aviso" not in out


def test_native_type_is_authoritative_even_when_title_suggests_another_type():
    out = transform_markdown("> [!warning] Experimento Mental I\n> corpo\n")
    assert "{.box .callout-warning}" in out
    assert ".experimento" not in out


def test_custom_type_is_rejected():
    with pytest.raises(CalloutError):
        transform_markdown("> [!experiment] Título\n> corpo\n")


def test_unknown_type_is_a_hard_error():
    with pytest.raises(CalloutError):
        transform_markdown("> [!whatever] Título\n> corpo\n")


def test_alias_is_not_canonical_source_syntax():
    assert lint_source("> [!important] Título\n> corpo\n")


def test_nested_success_becomes_verdict_footer():
    src = (
        "> [!example] Experimento Mental I\n"
        "> #### Teste\n"
        "> corpo\n"
        ">\n"
        "> > [!success] Veredicto\n"
        "> > resultado\n"
    )
    out = transform_markdown(src)
    assert "{.box .callout-example}" in out
    assert "{.box-verdict .callout-success}" in out
    assert "[Veredicto]{.verdict-tag}" in out


def test_title_is_verbatim_and_does_not_select_style():
    out = transform_markdown("> [!tip] Experimento Mental XX\n> corpo\n")
    assert "{.box .callout-tip}" in out
    assert "Experimento Mental XX" in out
    assert ".experimento" not in out


def test_heading_inside_callout_is_preserved():
    src = "> [!abstract] Conceito\n> Intro.\n>\n> ### Subtítulo interno\n> Texto.\n"
    out = transform_markdown(src)
    assert "### Subtítulo interno" in out


def test_fenced_code_inside_callout_is_preserved():
    src = "> [!example] Código\n> ```python\n> print('x')\n> ```\n"
    out = transform_markdown(src)
    assert "```python" in out
    assert "print('x')" in out


def test_fenced_code_outside_callout_is_preserved():
    src = "```python\nprint('x')\n```\n"
    assert transform_markdown(src).strip() == src.strip()


def test_native_callout_output_has_no_legacy_family_class():
    legacy = {"generico", "mapa", "evidencia", "nivel", "ideia", "ataque", "aviso", "experimento"}
    for typ in NATIVE_TYPES - {"quote"}:
        out = transform_markdown(f"> [!{typ}] Título\n> corpo\n")
        assert f".callout-{typ}" in out
        for family in legacy:
            assert f".{family}" not in out, (typ, family, out)

def test_callout_type_never_becomes_visible_badge_text():
    out = transform_markdown("> [!note] Minha observação\n> corpo\n")
    assert "{.box-title}" in out
    assert "Minha observação" in out
    assert "{.box-badge}" not in out
    assert "\nNota\n" not in out


def test_authored_header_and_internal_subtitle_remain_distinct():
    src = (
        "> [!example] Experimento Mental III\n"
        "> #### O Cérebro Dividido\n"
        "> Texto da caixa.\n"
    )
    out = transform_markdown(src)
    assert "{.box-title}" in out
    assert "Experimento Mental III" in out
    assert "#### O Cérebro Dividido" in out
    assert "\nExemplo\n" not in out


def test_plain_quote_separates_explicit_attribution():
    src = '> “Texto citado.”\n> Autor, *Obra*\n'
    out = transform_markdown(src)
    assert "{.quote-text}" in out
    assert "Texto citado." in out
    assert "{.quote-attribution}" in out
    assert "Autor, *Obra*" in out
    assert "“Texto citado.”" not in out


def test_quote_callout_uses_last_paragraph_as_legacy_attribution_fallback():
    src = (
        "> [!quote]\n"
        "> Texto citado sem marcas no legado.\n"
        ">\n"
        "> Autor, Obra\n"
    )
    out = transform_markdown(src)
    assert "{.pull-quote .callout-quote}" in out
    assert "{.quote-text}" in out
    assert "{.quote-attribution}" in out




def test_todo_h4_is_entity_metadata_only_when_todo_is_explicit():
    todo = transform_markdown("> [!todo] Thomas Hobbes\n> #### 1588 – 1679 · Inglaterra\n> corpo\n")
    note = transform_markdown("> [!note] Thomas Hobbes\n> #### 1588 – 1679 · Inglaterra\n> corpo\n")
    assert "#### 1588 – 1679 · Inglaterra" in todo
    assert "#### 1588 – 1679 · Inglaterra" in note
    assert ".entity-meta" in todo
    assert ".entity-meta" not in note
    assert "{.box .callout-todo}" in todo
    assert "{.box .callout-note}" in note


def test_warning_authored_rule_becomes_stat_source_only_when_warning_is_explicit():
    warning = transform_markdown("> [!warning] 39%\n> descrição\n> ---\n> Fonte\n")
    info = transform_markdown("> [!info] 39%\n> descrição\n> ---\n> Fonte\n")
    assert ".stat-divider" in warning and ".stat-source" in warning
    assert ".stat-divider" not in info and ".stat-source" not in info
    assert "---" in info
    assert "{.box .callout-warning}" in warning
    assert "{.box .callout-info}" in info


def test_keywords_never_select_visual_family():
    cases = {
        "note": "Experimento Mental III",
        "abstract": "Ideia 07",
        "tip": "Evidência Empírica I",
        "info": "Thomas Hobbes 1588 1679",
        "question": "39%",
    }
    for typ, title in cases.items():
        out = transform_markdown(f"> [!{typ}] {title}\n> corpo\n")
        assert f"{{.box .callout-{typ}}}" in out
