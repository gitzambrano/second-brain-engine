"""Contracts the public frontend has to keep.

These are cheap structural assertions, not screenshots: they catch the two
mistakes that actually happened — the essay overlay reaching into components
the canonical template owns, and the library shipping chrome for a control the
reader cannot operate.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/site_src"


def test_public_overlay_does_not_restyle_canonical_components():
    css = (SRC / "essay-theme.css").read_text(encoding="utf-8")
    forbidden = (
        "\nstrong {",
        "\n.content h2",
        "\n.content h3",
        "\n.box {",
        "\n.box-verdict {",
        "\n.quote {",
        "\n.pull-quote {",
        "\n.card {",
        "\ntable {",
        "\npre {",
        "\ncode {",
        "\nli::marker",
    )
    for selector in forbidden:
        assert selector not in css, selector


def test_all_three_themes_are_defined_in_every_public_stylesheet():
    """Light, warm sepia and dark are first-class palettes."""
    for name in ("essay-theme.css", "site.css"):
        css = (SRC / name).read_text(encoding="utf-8").lower()
        assert "#2f5fb0" in css, name
        assert "#f4eedf" in css, name
        assert 'data-theme="sepia"' in css, name
        assert "#c9a45c" in css, name
        assert "#ffffff" in css, name
        assert "#090909" in css, name


def test_theme_controls_cycle_light_sepia_dark():
    theme = (SRC / "theme.js").read_text(encoding="utf-8")
    essay = (SRC / "essay.js").read_text(encoding="utf-8")
    index = (SRC / "index.html").read_text(encoding="utf-8")
    renderer = (ROOT / "scripts/lib/render_public_essay.py").read_text(encoding="utf-8")

    assert "['light', 'sepia', 'dark']" in theme
    assert "['light', 'sepia', 'dark']" in essay
    assert 'class="theme-disc"' in index
    assert 'class="theme-disc"' in renderer
    assert "◐" not in index


def test_the_library_ships_a_single_stylesheet():
    """The override layer is gone: site.css is the only palette on the index."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from build_site import FRONTEND_ASSETS

    assert "atlas-theme.css" not in FRONTEND_ASSETS
    assert not (SRC / "atlas-theme.css").exists()
    index = (SRC / "index.html").read_text(encoding="utf-8")
    assert index.count("<link rel=\"stylesheet\"") == 1


def test_cover_summary_is_rendered_by_the_canonical_template():
    template = (ROOT / "scripts/essay_template.html").read_text(encoding="utf-8")
    assert 'class="cover-summary"' in template
    assert "$summary$" in template


def test_the_cover_rule_is_the_top_edge_not_a_title_ornament():
    """Regression: the stripe was a flex child of a vertically centred cover,
    so it landed right on top of the title instead of framing the page."""
    template = (ROOT / "scripts/essay_template.html").read_text(encoding="utf-8")
    stripe = template.split(".stripe{", 1)[1].split("}", 1)[0]
    assert "position:absolute" in stripe
    assert "top:0" in stripe


def test_library_chrome_and_view_modes():
    index = (SRC / "index.html").read_text(encoding="utf-8")
    script = (SRC / "site.js").read_text(encoding="utf-8")

    # The order is fixed, so it is not advertised as if it were a control.
    assert "Finalizados" not in index
    assert "sort-wrap" not in index and "sortPanel" not in script
    # Two maps are two modes of one thing: the switch lives inside the map.
    assert "sphere.html" not in index
    # Four reading modes: list/grid crossed with compact/full.
    for token in ('data-layout="list"', 'data-layout="grid"',
                  'data-density="compact"', 'data-density="full"'):
        assert token in index, token
    assert "statusRank(b) - statusRank(a)" in script


def test_tag_filter_is_multi_select():
    """A second press on a chip deselects it; several themes can be on at once."""
    script = (SRC / "site.js").read_text(encoding="utf-8")
    assert "activeTags" in script
    assert "activeTags.splice(at, 1)" in script


def test_the_expander_is_a_button_outside_the_card_link():
    """Regression: the summary used to be a role=button <p> nested inside the
    card's <a>, which fired once and then stopped."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    import build_site

    source = Path(build_site.__file__).read_text(encoding="utf-8")
    assert 'class="card-expand" type="button"' in source
    assert 'class="card-summary" role="button"' not in source
