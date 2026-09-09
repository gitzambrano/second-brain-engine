from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "scripts" / "site_src" / "index.html"


def _html() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_subscribe_is_a_compact_header_action() -> None:
    html = _html()
    header = html.index('class="topbar shell"')
    subscribe = html.index('id="subscribeOpen"')
    main = html.index("<main>")

    assert header < subscribe < main
    assert '>Assinar</button>' in html
    assert 'class="newsletter shell"' not in html


def test_subscribe_opens_compact_dialog_with_expected_kit_embed() -> None:
    html = _html()

    assert 'id="subscribeDialog"' in html
    assert 'dialog.showModal()' in html
    assert 'data-uid="4fd36350af"' in html
    assert 'src="https://gustavo-jose-zambrano.kit.com/4fd36350af/index.js"' in html
    assert "KIT_API_KEY" not in html
    assert "Receba novos essays" in html
    assert "Um e-mail quando eu publicar algo novo." in html


def test_subscribe_header_fits_narrow_mobile_contract() -> None:
    html = _html()

    assert "@media(max-width:760px)" in html
    assert '.topnav .nav-link.active{display:none}' in html
    assert "@media(max-width:360px)" in html
    assert '.brand>span:last-child{display:none}' in html
    assert '.topnav .nav-link[href="graph.html"]{display:none}' not in html
    assert '<a class="brand" href="index.html" aria-label="Second Brain">' in html
    assert ".subscribe-cta{padding-inline:9px}" in html


def test_dialog_form_is_single_column_and_full_width() -> None:
    html = _html()

    assert "flex-direction:column!important" in html
    assert ".subscribe-embed .formkit-submit{width:100%!important" in html
    assert "width:min(430px,calc(100% - 28px))" in html
