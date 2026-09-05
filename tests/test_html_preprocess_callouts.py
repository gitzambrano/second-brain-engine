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


def test_explicit_type_is_authoritative_even_when_title_suggests_another_type():
    out = transform_markdown("> [!warning] Experimento Mental I\n> corpo\n")
    assert "{.box .aviso}" in out
    assert ".experimento" not in out


def test_unknown_type_is_a_hard_error():
    with pytest.raises(CalloutError):
        transform_markdown("> [!whatever] Título\n> corpo\n")


def test_alias_is_not_canonical_source_syntax():
    assert lint_source("> [!important] Título\n> corpo\n")


def test_nested_result_becomes_verdict_footer():
    src = (
        "> [!experiment] I — Teste\n"
        "> corpo\n"
        ">\n"
        "> > [!result] Veredicto\n"
        "> > resultado\n"
    )
    out = transform_markdown(src)
    assert "{.box .experimento}" in out
    assert "{.box-verdict}" in out
    assert "[Veredicto]{.verdict-tag}" in out


def test_fenced_code_is_preserved_as_code():
    src = "```python\nprint('x')\n```\n"
    assert transform_markdown(src).strip() == src.strip()
