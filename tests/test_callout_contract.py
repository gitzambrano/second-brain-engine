from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib.html_preprocess import ALIASES, NATIVE_TYPES, lint_source  # noqa: E402

CANONICAL = {
    "note", "abstract", "info", "todo", "tip", "success", "question",
    "warning", "failure", "danger", "bug", "example", "quote",
}


def test_source_type_set_is_exactly_obsidian_base_types():
    assert NATIVE_TYPES == CANONICAL


def test_every_alias_is_rejected_by_source_lint():
    for alias in ALIASES:
        assert lint_source(f"> [!{alias}] Título\n> corpo\n")


def test_html_has_theme_specific_token_for_every_native_type():
    template = (ROOT / "scripts" / "essay_template.html").read_text(encoding="utf-8")
    for typ in CANONICAL:
        token = f"--callout-{typ}:"
        # dark root + explicit light + desktop-default light
        assert template.count(token) == 3, (typ, template.count(token))


def test_native_box_selectors_use_type_specific_tokens():
    template = (ROOT / "scripts" / "essay_template.html").read_text(encoding="utf-8")
    for typ in CANONICAL - {"quote"}:
        assert f".box.callout-{typ}" in template
        assert f"--boxc:var(--callout-{typ})" in template
    assert "var(--callout-quote)" in template


def test_template_has_no_legacy_callout_family_selectors():
    template = (ROOT / "scripts" / "essay_template.html").read_text(encoding="utf-8")
    for family in ("experimento", "evidencia", "mapa", "ataque", "aviso", "nivel", "ideia", "generico"):
        assert f".box.{family}" not in template


def test_dark_and_light_callout_values_are_not_identical():
    template = (ROOT / "scripts" / "essay_template.html").read_text(encoding="utf-8")
    dark = template.split(":root{", 1)[1].split("[data-theme=\"light\"]", 1)[0]
    light = template.split("[data-theme=\"light\"]{", 1)[1].split("@media (min-width:901px)", 1)[0]
    for typ in CANONICAL:
        key = f"--callout-{typ}:"
        dark_value = dark.split(key, 1)[1].split(";", 1)[0].strip()
        light_value = light.split(key, 1)[1].split(";", 1)[0].strip()
        assert dark_value != light_value, typ
