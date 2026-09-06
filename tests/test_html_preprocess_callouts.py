from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.html_preprocess import CalloutError, lint_source, transform_markdown  # noqa: E402


def test_plain_blockquote_is_never_inferred_as_box():
    out = transform_markdown("> Experimento Mental I\n> ⚠️ Atenção\n> corpo\n")
    assert "{.quote}" in out
    assert ".experimento" not in out
    assert ".aviso" not in out


def test_native_type_is_authoritative_even_when_title_suggests_another_type():
    out = transform_markdown("> [!warning] Experimento Mental I\n> corpo\n")
    assert "{.box .aviso .callout-warning}" in out
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
        "> [!example] Experimento Mental I — Teste\n"
        "> corpo\n"
        ">\n"
        "> > [!success] Veredicto\n"
        "> > resultado\n"
    )
    out = transform_markdown(src)
    assert "{.box .experimento .callout-example}" in out
    assert "{.box-verdict .callout-success}" in out
    assert "[Veredicto]{.verdict-tag}" in out


def test_title_is_verbatim_and_does_not_select_style():
    out = transform_markdown("> [!tip] Experimento Mental XX\n> corpo\n")
    assert "{.box .ideia .callout-tip}" in out
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
