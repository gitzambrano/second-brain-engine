"""Regression coverage for public Markdown sanitization."""

from lib.site_common import sanitize_private_wikilinks
from export_essay_html import prepare_body


def test_sanitizer_preserves_wikilink_shaped_python_matrix_literal_in_fence():
    markdown = """Antes, [[nota-privada]].

```python
H = np.array([[1.0, 0.0]])
R = np.array([[0.5]])
```

Depois, [[ensaio-publico|leitura pública]].
"""

    sanitized = sanitize_private_wikilinks(markdown, {"ensaio-publico"})

    assert "Antes, referência interna." in sanitized
    assert "H = np.array([[1.0, 0.0]])" in sanitized
    assert "R = np.array([[0.5]])" in sanitized
    assert "[[ensaio-publico|leitura pública]]" in sanitized


def test_html_preparation_keeps_matrix_brackets_inside_fenced_python(tmp_path):
    source = tmp_path / "matriz.md"
    source.write_text(
        """---
title: Matriz
---
# Matriz

```python
H = np.array([[1.0, 0.0]])
```
""",
        encoding="utf-8",
    )

    body, *_rest = prepare_body(source)

    assert "H = np.array([[1.0, 0.0]])" in body
