"""Public essays keep the authoring source while omitting redundant separators."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))


def test_public_projection_removes_authored_ornaments_only_inside_reading_content():
    from lib.render_public_essay import strip_content_ornaments

    page = (
        '<main class="content"><h2>Capítulo</h2>'
        '<div class="ornament">· · ·</div><p>Leitura.</p></main>'
        '<footer><div class="ornament">· · ·</div></footer>'
    )

    rendered = strip_content_ornaments(page)

    assert '<main class="content"><h2>Capítulo</h2><p>Leitura.</p></main>' in rendered
    assert '<footer><div class="ornament">· · ·</div></footer>' in rendered
