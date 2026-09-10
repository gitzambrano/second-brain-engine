from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
index = ROOT / "scripts/site_src/index.html"
essay_css = ROOT / "scripts/site_src/essay-theme.css"
graph = ROOT / "scripts/build_graph.py"
test_reader = ROOT / "tests/test_public_reader_polish_contract.py"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"missing expected text in {path}: {old[:100]!r}")
    if text.count(old) != 1:
        raise SystemExit(f"expected one occurrence in {path}, got {text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Landing header: make its mobile geometry explicit and canonical.
replace_once(
    index,
    ".subscribe-cta{display:inline-flex;align-items:center;justify-content:center;min-height:36px;padding:0 12px;border:1px solid var(--line);border-radius:999px;background:color-mix(in srgb,var(--accent) 13%,var(--panel));color:var(--accent);font:650 12.5px var(--sans);cursor:pointer;transition:border-color .16s var(--ease),background .16s var(--ease),color .16s var(--ease)}",
    ".subscribe-cta{display:inline-flex;align-items:center;justify-content:center;box-sizing:border-box;height:36px;min-height:36px;padding:0 12px;border:1px solid var(--line);border-radius:999px;background:color-mix(in srgb,var(--accent) 13%,var(--panel));color:var(--accent);font:650 12.5px/1 var(--sans);white-space:nowrap;cursor:pointer;transition:border-color .16s var(--ease),background .16s var(--ease),color .16s var(--ease)}",
)
replace_once(
    index,
    "@media(max-width:760px){.topnav .nav-link.active{display:none}.subscribe-cta{min-height:36px;padding-inline:10px;font-size:12px}.subscribe-dialog-head{padding:22px 48px 0 20px}.subscribe-embed{padding:16px 20px 20px}.subscribe-dialog h2{font-size:1.4rem}}",
    "@media(max-width:760px){.topnav .nav-link.active{display:none}.topnav .nav-link{line-height:1.6}.subscribe-cta{height:36px;min-height:36px;padding-inline:10px;font-size:12px;line-height:1}#themeToggle>span{width:100%;height:100%;display:grid;place-items:center;font-size:21px;line-height:1;transform:translateY(-.5px)}.subscribe-dialog-head{padding:22px 48px 0 20px}.subscribe-embed{padding:16px 20px 20px}.subscribe-dialog h2{font-size:1.4rem}}",
)
replace_once(
    index,
    "@media(max-width:360px){.brand{gap:0}.brand>span:last-child{display:none}.topnav{gap:8px}.subscribe-cta{padding-inline:9px}}",
    "@media(max-width:360px){.brand{gap:0}.brand>span:last-child{display:none}}",
)

# Essay header: use the exact mobile metrics of the landing header instead of
# inheriting the essay body's 17.5px / 1.78 serif rhythm.
replace_once(
    essay_css,
    ".sb-brand{\n  display:inline-flex;align-items:center;gap:11px;\n  color:var(--sb-text) !important;font-weight:700;font-size:14px;\n  text-decoration:none !important;\n}",
    ".sb-brand{\n  display:flex;align-items:center;gap:11px;\n  color:var(--sb-text) !important;font-weight:700;font-size:14px;line-height:1.6;letter-spacing:-.02em;\n  text-decoration:none !important;\n}",
)
replace_once(
    essay_css,
    ".sb-nav a{color:var(--sb-muted) !important;font-size:14px;font-weight:500;text-decoration:none !important;}",
    ".sb-nav a{color:var(--sb-muted) !important;font-size:14px;font-weight:500;line-height:1.6;text-decoration:none !important;}",
)
replace_once(
    essay_css,
    ".sb-nav button{\n  width:36px;height:36px;display:grid;place-items:center;\n  border:1px solid var(--sb-line);border-radius:10px;\n  background:transparent;color:var(--sb-primary);cursor:pointer;\n  transition:border-color .16s cubic-bezier(.22,.61,.36,1);\n}",
    ".sb-nav button{\n  box-sizing:border-box;width:36px;height:36px;padding:0;display:grid;place-items:center;\n  border:1px solid var(--sb-line);border-radius:10px;\n  background:transparent;color:var(--sb-primary);cursor:pointer;\n  font-family:Inter,ui-sans-serif,system-ui,-apple-system,\"Segoe UI\",sans-serif;line-height:1;\n  transition:border-color .16s cubic-bezier(.22,.61,.36,1);\n}",
)
replace_once(
    essay_css,
    ".sb-nav .sb-subscribe{\n  width:auto;height:36px;min-height:36px;padding:0 12px;\n  display:inline-flex;align-items:center;justify-content:center;\n  border-color:var(--sb-line);border-radius:999px;\n  background:color-mix(in srgb,var(--sb-primary) 13%,var(--sb-surface));color:var(--sb-primary);\n  font:650 12.5px Inter,ui-sans-serif,system-ui,-apple-system,\"Segoe UI\",sans-serif;\n}",
    ".sb-nav .sb-subscribe{\n  box-sizing:border-box;width:auto;height:36px;min-height:36px;padding:0 12px;\n  display:inline-flex;align-items:center;justify-content:center;\n  border-color:var(--sb-line);border-radius:999px;\n  background:color-mix(in srgb,var(--sb-primary) 13%,var(--sb-surface));color:var(--sb-primary);\n  font:650 12.5px/1 Inter,ui-sans-serif,system-ui,-apple-system,\"Segoe UI\",sans-serif;white-space:nowrap;\n}",
)
replace_once(
    essay_css,
    "  .sb-nav #sbTheme > span{display:block;font-size:1.28rem;line-height:1;}\n  .sb-nav .sb-subscribe{height:36px;min-height:36px;padding-inline:10px;font-size:12px;line-height:normal;}",
    "  .sb-nav #sbTheme > span{width:100%;height:100%;display:grid;place-items:center;font-size:21px;line-height:1;transform:translateY(-.5px);}\n  .sb-nav .sb-subscribe{height:36px;min-height:36px;padding-inline:10px;font-size:12px;line-height:1;}",
)

# Labels: make auto labels appear substantially earlier than the previous 1.16x zoom.
replace_once(graph, "const LABEL_SHOW_AT = 1.16;", "const LABEL_SHOW_AT = 0.96;")
replace_once(graph, "const LABEL_HIDE_AT = 1.10;", "const LABEL_HIDE_AT = 0.90;")

# Update the existing regression contract to match the slightly larger, optically centered glyph.
replace_once(
    test_reader,
    'assert ".sb-nav #sbTheme > span{display:block;font-size:1.28rem;line-height:1;}" in css',
    'assert ".sb-nav #sbTheme > span{width:100%;height:100%;display:grid;place-items:center;font-size:21px;line-height:1;transform:translateY(-.5px);}" in css',
)

# Any test/snapshot that names the exact graph constants should follow the canonical source.
for path in (ROOT / "tests").glob("test_*.py"):
    text = path.read_text(encoding="utf-8")
    newer = text.replace("const LABEL_SHOW_AT = 1.16;", "const LABEL_SHOW_AT = 0.96;")
    newer = newer.replace("const LABEL_HIDE_AT = 1.10;", "const LABEL_HIDE_AT = 0.90;")
    if newer != text:
        path.write_text(newer, encoding="utf-8")

print("mobile header + graph label patch applied")
