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


def test_mobile_reader_controls_preserve_compact_visuals_with_44px_hit_targets():
    css = (SRC / "essay-theme.css").read_text(encoding="utf-8")
    assert ".sb-nav button" in css
    assert "width:44px;height:44px" in css
    assert ".sb-nav{gap:6px" in css
    assert ".sb-nav button:focus-visible" in css


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


def test_browser_audit_declares_all_reader_theme_viewport_states():
    checker = (ROOT / "scripts" / "check_site_pages.py").read_text(encoding="utf-8")
    for state in ("mobile-light", "mobile-dark", "desktop-light", "desktop-dark"):
        assert state in checker
    for code in ("EDITORIAL_FONT_UNAVAILABLE", "TOC_OVERFLOW", "CONTROL_OUTSIDE_VIEWPORT"):
        assert code in checker
    assert "if data[\"isEssay\"]:" in checker
    assert "if(!localStorage.getItem('sb-theme'))" in checker
    assert "el.closest('table')" in checker
