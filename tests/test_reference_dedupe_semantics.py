from check_dedupe import is_reviewed_title_exception, reference_core
from check_references import check_essay


def test_reference_core_ignores_context_note():
    a = "Author, A., *Book Title*, Publisher, 2020. — Nota A. [Link](https://example.com/book)"
    b = "Author, A., *Book Title*, Publisher, 2020. — Nota B. [Link](https://example.com/book)"
    assert reference_core(a) == reference_core(b)


def test_reference_core_detects_bibliographic_difference():
    a = "Author, A., *Book Title*, Publisher, 2020. [Link](https://example.com/book)"
    b = "Author, A., *Book Title*, Other Publisher, 2020. [Link](https://example.com/book)"
    assert reference_core(a) != reference_core(b)


def test_reviewed_title_exceptions_are_symmetric():
    reviewed_pairs = (
        ("Modelo de Influxo de Pitt–Peters", "Modelo de Influxo de Peters–He"),
        ("David Albert", "David Hilbert"),
        ("Evan Thompson", "Ken Thompson"),
    )
    for a, b in reviewed_pairs:
        assert is_reviewed_title_exception(a, b)
        assert is_reviewed_title_exception(b, a)


def test_unreviewed_title_pair_is_not_suppressed():
    assert not is_reviewed_title_exception("David Albert", "Albert Einstein")


def test_unused_reference_is_not_a_lint_issue(tmp_path):
    essay = tmp_path / "essay.md"
    essay.write_text(
        """# Teste

Por Autor

Texto com citação [1].

## Referências

[1] Autor, A., *Usada*, Editora, 2020. [Link](https://example.com/a)

[2] Autor, B., *Leitura complementar*, Editora, 2021. [Link](https://example.com/b)
""",
        encoding="utf-8",
    )
    result = check_essay(essay)
    assert all(issue["code"] != "REFERENCIA_NAO_USADA" for issue in result["issues"])
