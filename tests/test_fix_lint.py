from fix_lint import fix_unlinked_citations, save_file_content


def test_save_file_content_normalizes_crlf(tmp_path):
    path = tmp_path / "page.md"

    save_file_content(path, "uma\r\nduas\r\n")

    assert path.read_bytes() == b"uma\nduas\n"


def test_fix_unlinked_citations():
    text = (
        "Texto de introdução com citação [1] e múltipla [2, 3].\n"
        "Fórmula $x[1]$ e bloco `código [1]` e fenced:\n"
        "```python\n[1] não deve mudar\n```\n"
        "Link existente [1](#referências) e [[#Referências|[1]]] intocados.\n"
        "[99] não existe na bibliografia e não deve mudar.\n\n"
        "## Referências\n\n"
        "[1] Autor, *Obra*, 2020. [Link](https://example.com)\n"
        "[2] Autor2, *Obra2*, 2021. [Link](https://example.com)\n"
        "[3] Autor3, *Obra3*, 2022. [Link](https://example.com)\n"
    )

    fixed, count = fix_unlinked_citations(text)
    assert count == 3  # [1], [2, 3] -> 1 + 2 = 3
    assert "Texto de introdução com citação [[#Referências|[1]]] e múltipla [[#Referências|[2]]], [[#Referências|[3]]]." in fixed
    assert "Fórmula $x[1]$" in fixed
    assert "`código [1]`" in fixed
    assert "```python\n[1] não deve mudar\n```" in fixed
    assert "[99] não existe" in fixed

