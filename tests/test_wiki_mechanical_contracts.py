from __future__ import annotations

import json

from conftest import run_script


def _codes(mini_brain, strict: bool = False):
    args = ["kitchen-sink", "--json"]
    if strict:
        args.append("--strict")
    proc = run_script("check_wiki.py", *args, data_root=mini_brain)
    payload = json.loads(proc.stdout)
    codes = {issue["code"] for essay in payload["essays"] for issue in essay["issues"]}
    return proc, codes


def _insert_before_references(mini_brain, text: str):
    path = mini_brain / "wiki" / "essays" / "kitchen-sink.md"
    original = path.read_text(encoding="utf-8")
    path.write_text(original.replace("## Referências", text + "\n## Referências", 1), encoding="utf-8")


def test_callout_contracts_report_invalid_structure_and_semantics(mini_brain):
    _insert_before_references(mini_brain, """
> [!hint] Atalho
> #### inválido
>
> ## Heading proibido

> [!warning] Atenção
> Sem número.

> [!todo]
> Sem entidade.

> [!note] Mapa Conceitual
> Deveria ser abstract.
""")

    _proc, codes = _codes(mini_brain)

    assert {"CALLOUT_ALIAS", "CALLOUT_HEADING_LEVEL", "CALLOUT_WARNING_TITLE",
            "CALLOUT_TODO_TITLE", "CALLOUT_NOTE_SHOULD_ABSTRACT"} <= codes


def test_figure_and_editorial_heuristics_are_reported_without_autofix(mini_brain):
    _insert_before_references(mini_brain, """
Nesta seção veremos por que estudos mostram que o modelo entende o problema.
![diagrama](../assets/arquivo-sem-padrao.png)
![figura sem legenda](../assets/kitchen-sink_fig2.png)

""")
    path = mini_brain / "wiki" / "essays" / "kitchen-sink.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        "[1] Doe, J., *Synthetic Reference for Pipeline Qualification*, Example Technical Press, 2026. — Referência completamente fictícia usada apenas por esta fixture. [Link](https://example.com/source)",
        "[1] Doe, J., *Synthetic Reference for Pipeline Qualification*, Example Technical Press, 2026. — Referência completamente fictícia usada apenas por esta fixture. [Link](https://example.com/source)\n\n[3] Autor, Título sem itálico. [Link](https://example.com/source) sobra",
    )
    path.write_text(text, encoding="utf-8")

    _proc, codes = _codes(mini_brain)

    assert {"FIGURE_FILENAME", "FIGURE_CAPTION_MISSING", "METADISCOURSE",
            "VAGUE_AUTHORITY", "ANTHROPOMORPHIZATION", "REF_SEQUENCE",
            "REF_TITLE_NOT_ITALIC", "REF_DUPLICATE_URL", "REF_LINK_NOT_FINAL"} <= codes


def test_strict_mode_fails_only_for_blocking_issues(mini_brain):
    _insert_before_references(mini_brain, "> [!hint] Alias proibido\n> Texto.")

    proc, codes = _codes(mini_brain, strict=True)

    assert "CALLOUT_ALIAS" in codes
    assert proc.returncode == 1


def test_updated_metadata_contract_distinguishes_substantive_and_metadata_diffs():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from check_wiki import classify_updated_diff

    substantive = "\n".join(["--- a/wiki/essays/x.md", "+++ b/wiki/essays/x.md", "+---", "+tags: [Teste]", "+---"] + [f"+parágrafo {n}" for n in range(12)])
    metadata_only = "\n".join(["--- a/wiki/essays/x.md", "+++ b/wiki/essays/x.md", "+---", "+updated: 2026-09-09", "+---"])

    assert classify_updated_diff(substantive) == "BODY_CHANGED_UPDATED_UNCHANGED"
    assert classify_updated_diff(metadata_only) == "UPDATED_CHANGED_WITHOUT_BODY"
