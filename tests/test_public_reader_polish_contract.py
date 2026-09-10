"""Behavioral contracts for the public essay reader polish."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts" / "site_src"


def test_public_site_font_bundle_covers_the_editorial_families():
    """A deployed reader must carry every family its editorial roles declare."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts"))
    from lib.fetch_fonts import SITE_CSS_URL

    for family in ("Playfair+Display", "Source+Serif+4", "JetBrains+Mono"):
        assert family in SITE_CSS_URL


def test_mobile_reader_controls_preserve_compact_36px_visuals():
    css = (SRC / "essay-theme.css").read_text(encoding="utf-8")
    assert ".sb-nav button" in css
    assert "width:36px;height:36px" in css
    assert ".sb-nav{gap:14px" in css
    assert ".sb-nav button:focus-visible" in css


def test_mobile_reader_header_matches_landing_header_rhythm():
    css = (SRC / "essay-theme.css").read_text(encoding="utf-8")
    landing = (SRC / "site.css").read_text(encoding="utf-8")
    source = (ROOT / "scripts" / "lib" / "render_public_essay.py").read_text(encoding="utf-8")
    assert ".sb-nav{gap:14px;}" in css
    assert ".topnav { gap: 14px; }" in landing
    assert "calc(100% - 28px)" in css
    assert '<a class="active" href="../index.html">Ensaios</a>' in source
    assert '<span aria-hidden="true">◐</span>' in source


def test_mobile_toc_keeps_secondary_entries_readable_and_active_state_quiet():
    css = (SRC / "essay-theme.css").read_text(encoding="utf-8")
    assert ".sb-toc a{font-size:13px" in css
    assert ".sb-toc a.h3{font-size:12.5px" in css
    assert "border-left-color:color-mix(in srgb,var(--sb-primary) 42%,transparent)" in css
    assert "var(--sb-primary-soft)" not in css.split(".sb-toc a.active", 1)[1].split("}", 1)[0]
    assert ".content mjx-container:not([display]){display:inline-block;max-width:100%;overflow-x:auto;}" in css


def test_mobile_table_headers_reduce_tracking_to_protect_reading_width():
    template = (ROOT / "scripts" / "essay_template.html").read_text(encoding="utf-8")
    assert "th{font-size:.82rem;letter-spacing:.06em;}" in template


def test_dark_reader_gives_chapter_rules_a_quiet_gold_tint():
    template = (ROOT / "scripts" / "essay_template.html").read_text(encoding="utf-8")
    assert ':root[data-theme="dark"] .sb-kicker::after' in template
    assert "color-mix(in srgb,var(--gold) 34%,var(--border))" in template


def test_dark_reader_separates_h3_from_h4_without_changing_light_mode():
    template = (ROOT / "scripts" / "essay_template.html").read_text(encoding="utf-8")
    assert ':root[data-theme="dark"] h3{' in template
    assert "border-bottom:1px solid color-mix(in srgb,var(--gold) 24%,transparent);" in template
    assert "font-size:1.3rem;" in template


def test_desktop_essay_chrome_keeps_subscribe_available():
    source = (ROOT / "scripts" / "lib" / "render_public_essay.py").read_text(encoding="utf-8")
    css = (SRC / "essay-theme.css").read_text(encoding="utf-8")
    assert 'id="sbSubscribe"' in source
    assert 'id="sbSubscribeDialog"' in source
    assert 'id="sbKitEmbedMount"' in source
    assert ".sb-subscribe" in css
    assert ".sb-subscribe{display:inline-flex" in css


def test_theme_control_border_matches_the_subscribe_control_presence():
    css = (SRC / "essay-theme.css").read_text(encoding="utf-8")
    assert "#sbTheme{border-color:var(--sb-line);}" in css


def test_mobile_theme_glyph_grows_without_growing_the_reader_control():
    css = (SRC / "essay-theme.css").read_text(encoding="utf-8")
    assert ".sb-nav #sbTheme > span{width:100%;height:100%;display:grid;place-items:center;font-size:21px;line-height:1;transform:translateY(-.5px);}" in css


def test_reader_footer_uses_at_least_comfortable_small_text():
    template = (ROOT / "scripts" / "essay_template.html").read_text(encoding="utf-8")
    assert "font-size:.68rem" in template


def test_kit_confirmation_note_follows_the_form_instead_of_delaying_it():
    source = (ROOT / "scripts" / "lib" / "render_public_essay.py").read_text(encoding="utf-8")
    assert source.index('class="sb-subscribe-embed"') < source.index('class="sb-subscribe-note"')


def test_essay_subscribe_dialog_keeps_confirmation_copy_concise():
    source = (ROOT / "scripts" / "lib" / "render_public_essay.py").read_text(encoding="utf-8")
    assert "Spam" in source
    assert "confirme o e-mail" in source
    for verbose in ("Promoções", "Não é spam", "então confirme"):
        assert verbose not in source
    assert 'class="sb-subscribe-note"' in source


def test_subscribe_form_field_and_button_share_the_same_width():
    index = (SRC / "index.html").read_text(encoding="utf-8")
    css = (SRC / "essay-theme.css").read_text(encoding="utf-8")
    assert '.subscribe-embed .formkit-field,.subscribe-embed [data-element="submit"]' in index
    assert '.sb-subscribe-embed .formkit-field,.sb-subscribe-embed [data-element="submit"]' in css
    assert "align-self:stretch!important" in index
    assert "align-self:stretch!important" in css
    assert "justify-content:center!important" in index
    assert "justify-content:center!important" in css


def test_browser_audit_declares_all_reader_theme_viewport_states():
    checker = (ROOT / "scripts" / "check_site_pages.py").read_text(encoding="utf-8")
    for state in ("mobile-light", "mobile-dark", "desktop-light", "desktop-dark"):
        assert state in checker
    for code in ("EDITORIAL_FONT_UNAVAILABLE", "TOC_OVERFLOW", "CONTROL_OUTSIDE_VIEWPORT"):
        assert code in checker
    assert "#sbSubscribe" in checker
    assert "if data[\"isEssay\"]:" in checker
    assert "if(!localStorage.getItem('sb-theme'))" in checker
    assert "el.closest('table')" in checker
