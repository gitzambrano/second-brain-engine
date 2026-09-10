from pathlib import Path


def replace(path: str, old: str, new: str, count: int = 1) -> None:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    found = text.count(old)
    if found != count:
        raise SystemExit(f"{path}: expected {count} occurrence(s), found {found}: {old[:100]!r}")
    p.write_text(text.replace(old, new), encoding="utf-8")


# Landing/header: home is the canonical geometry.
replace(
    "scripts/site_src/site.css",
    ".brand-mark {\n  width: 31px; height: 31px;\n  display: grid;\n  place-items: center;\n  border: 1px solid color-mix(in srgb, var(--accent) 42%, transparent);\n  border-radius: 9px;",
    ".brand-mark {\n  width: 36px; height: 36px;\n  display: grid;\n  place-items: center;\n  border: 1px solid var(--line);\n  border-radius: 10px;",
)
replace(
    "scripts/site_src/site.css",
    "  .nav-link { font-size: 13px; }\n\n  .masthead",
    "  .nav-link { font-size: 13px; }\n  .brand > span:last-child { display: none; }\n  .icon-button > span { font-size: 1.2rem; line-height: 1; }\n\n  .masthead",
)
replace(
    "scripts/site_src/index.html",
    ".subscribe-cta{display:inline-flex;align-items:center;justify-content:center;min-height:34px;padding:0 12px;border:1px solid color-mix(in srgb,var(--accent) 42%,var(--line));border-radius:999px;background:var(--accent-soft);color:var(--accent);font:650 12.5px var(--sans);cursor:pointer;transition:border-color .16s var(--ease),background .16s var(--ease),color .16s var(--ease)}",
    ".subscribe-cta{display:inline-flex;align-items:center;justify-content:center;min-height:36px;padding:0 12px;border:1px solid var(--line);border-radius:999px;background:color-mix(in srgb,var(--accent) 13%,var(--panel));color:var(--accent);font:650 12.5px var(--sans);cursor:pointer;transition:border-color .16s var(--ease),background .16s var(--ease),color .16s var(--ease)}",
)
replace(
    "scripts/site_src/index.html",
    ".subscribe-cta:hover{border-color:color-mix(in srgb,var(--accent) 72%,var(--line));background:color-mix(in srgb,var(--accent) 14%,transparent);color:var(--text-strong)}",
    ".subscribe-cta:hover{border-color:var(--line-strong);background:color-mix(in srgb,var(--accent) 17%,var(--panel));color:var(--text-strong)}",
)
replace(
    "scripts/site_src/index.html",
    "@media(max-width:760px){.topnav .nav-link.active{display:none}.subscribe-cta{min-height:32px;padding-inline:10px;font-size:12px}",
    "@media(max-width:760px){.topnav .nav-link.active{display:none}.subscribe-cta{min-height:36px;padding-inline:10px;font-size:12px}",
)

# Public essay chrome: same geometry as the landing page and neutral control borders.
replace("scripts/site_src/essay-theme.css", "body{padding-top:56px;}", "body{padding-top:68px;}")
replace(
    "scripts/site_src/essay-theme.css",
    "position:fixed;inset:0 0 auto 0;z-index:60;height:56px;",
    "position:fixed;inset:0 0 auto 0;z-index:60;height:68px;",
)
replace(
    "scripts/site_src/essay-theme.css",
    ".sb-mark{\n  display:grid;place-items:center;width:27px;height:27px;\n  border:1px solid color-mix(in srgb,var(--sb-primary) 42%,transparent);\n  border-radius:8px;color:var(--sb-primary);background:var(--sb-primary-soft);",
    ".sb-mark{\n  display:grid;place-items:center;width:36px;height:36px;\n  border:1px solid var(--sb-line);\n  border-radius:10px;color:var(--sb-primary);background:var(--sb-primary-soft);",
)
replace(
    "scripts/site_src/essay-theme.css",
    "background:url(\"../assets/icon-32.png\") center / 18px 18px no-repeat, var(--sb-primary-soft);",
    "background:url(\"../assets/icon-32.png\") center / 20px 20px no-repeat, var(--sb-primary-soft);",
)
replace("scripts/site_src/essay-theme.css", ".sb-nav{display:flex;align-items:center;gap:16px;}", ".sb-nav{display:flex;align-items:center;gap:20px;}")
replace(
    "scripts/site_src/essay-theme.css",
    ".sb-nav a{color:var(--sb-muted) !important;font-size:13px;text-decoration:none !important;}",
    ".sb-nav a{color:var(--sb-muted) !important;font-size:14px;font-weight:500;text-decoration:none !important;}",
)
replace(
    "scripts/site_src/essay-theme.css",
    ".sb-nav button{\n  width:32px;height:32px;border:1px solid var(--sb-line);border-radius:9px;",
    ".sb-nav button{\n  width:36px;height:36px;border:1px solid var(--sb-line);border-radius:10px;",
)
replace(
    "scripts/site_src/essay-theme.css",
    ".sb-nav .sb-subscribe{\n  width:auto;height:32px;padding:0 10px;\n  border-color:color-mix(in srgb,var(--sb-primary) 42%,var(--sb-line));border-radius:999px;\n  background:var(--sb-primary-soft);color:var(--sb-primary);font:650 12px/1 Inter,ui-sans-serif,system-ui,sans-serif;\n}",
    ".sb-nav .sb-subscribe{\n  width:auto;height:36px;padding:0 12px;\n  border-color:var(--sb-line);border-radius:999px;\n  background:color-mix(in srgb,var(--sb-primary) 13%,var(--sb-surface));color:var(--sb-primary);font:650 12.5px/1 Inter,ui-sans-serif,system-ui,sans-serif;\n}",
)
replace(
    "scripts/site_src/essay-theme.css",
    "#sbTheme{border-color:color-mix(in srgb,var(--sb-primary) 42%,var(--sb-line));}",
    "#sbTheme{border-color:var(--sb-line);}",
)
replace(
    "scripts/site_src/essay-theme.css",
    "position:fixed;top:56px;left:0;right:0;z-index:61;height:2px;background:transparent;",
    "position:fixed;top:68px;left:0;right:0;z-index:61;height:2px;background:transparent;",
)
replace(
    "scripts/site_src/essay-theme.css",
    "border:1px solid var(--sb-line-strong);border-radius:999px;\n  background:color-mix(in srgb,var(--sb-surface) 96%,transparent);",
    "border:1px solid var(--sb-line);border-radius:999px;\n  background:color-mix(in srgb,var(--sb-surface) 96%,transparent);",
)
replace(
    "scripts/site_src/essay-theme.css",
    "  .sb-bar{padding-inline:14px;}",
    "  .sb-bar{height:60px;padding-inline:14px;}\n  body{padding-top:60px;}\n  body > .sb-progress:not(:has(.sb-progress-fill)){top:60px;}",
)
replace("scripts/site_src/essay-theme.css", "  .sb-nav{gap:6px;}", "  .sb-nav{gap:8px;}")
replace("scripts/site_src/essay-theme.css", "  .sb-nav a{font-size:12px;}", "  .sb-nav a{font-size:13px;}")
replace(
    "scripts/site_src/essay-theme.css",
    "  .sb-brand{font-size:13px;}",
    "  .sb-brand{gap:0;font-size:0;}\n  .sb-nav a:first-child{display:none;}",
)
replace("scripts/site_src/essay-theme.css", "  .sb-nav button{width:44px;height:44px;}", "  .sb-nav button{width:36px;height:36px;}")
replace("scripts/site_src/essay-theme.css", "  .sb-subscribe{display:none;}", "  .sb-subscribe{display:inline-flex;}")
replace("scripts/site_src/essay-theme.css", "  .sb-brand{gap:7px;font-size:0;}", "  .sb-brand{gap:0;font-size:0;}")
replace("scripts/site_src/essay-theme.css", "  .sb-nav{gap:14px;}", "  .sb-nav{gap:8px;}")
replace("scripts/site_src/essay-theme.css", "  .sb-nav a{font-size:12.5px;}", "  .sb-nav a{font-size:13px;}")
replace(
    "scripts/lib/render_public_essay.py",
    '<span class="sb-mark" aria-hidden="true"></span>Second Brain Atlas</a>',
    '<span class="sb-mark" aria-hidden="true"></span>Second Brain</a>',
)

# Dark !note gets a dedicated, slightly brighter surface; light theme is unchanged.
replace(
    "scripts/essay_template.html",
    "  --callout-note:#A2988A;\n",
    "  --callout-note:#A2988A;\n  --note-bg:color-mix(in srgb,var(--callout-note) 7%,var(--surface2));\n",
)
replace(
    "scripts/essay_template.html",
    "  --callout-note:#4A5C77;\n",
    "  --callout-note:#4A5C77;\n  --note-bg:var(--surface2);\n",
    count=2,
)
replace(
    "scripts/essay_template.html",
    ".box.callout-note{\n  border:1px solid var(--border);border-radius:3px;\n  background:var(--surface2);\n}",
    ".box.callout-note{\n  border:1px solid var(--border);border-radius:3px;\n  background:var(--note-bg,var(--surface2));\n}",
)

# Graph: labels appear a little sooner and default edges recede in both themes.
replace("scripts/build_graph.py", '        "edge": "#9aa0a8",', '        "edge": "#858b93",')
replace("scripts/build_graph.py", '    "edgeOpacity": 0.35,', '    "edgeOpacity": 0.28,')
replace(
    "scripts/build_graph.py",
    'reference: "#8a8f96", edge: "#9aa0a8", background: "#1b1e21"',
    'reference: "#8a8f96", edge: "#858b93", background: "#1b1e21"',
)
replace("scripts/build_graph.py", "edgeOpacity: 0.35, edgeVisibility:", "edgeOpacity: 0.28, edgeVisibility:")
replace(
    "scripts/build_graph.py",
    "const LABEL_SHOW_AT = 1.55;\nconst LABEL_HIDE_AT = 1.45;",
    "const LABEL_SHOW_AT = 1.40;\nconst LABEL_HIDE_AT = 1.32;",
)

# Public graph/globe chrome: match site control height and reserve bottom-sheet space.
replace(
    "scripts/lib/build_public_map.py",
    "    padding: 9px 15px; border-radius: 999px;",
    "    min-height: 36px; padding: 9px 15px; border-radius: 999px;",
    count=2,
)
replace(
    "scripts/lib/build_public_map.py",
    "    padding: 9px 13px; border-radius: 999px;",
    "    min-height: 36px; padding: 9px 13px; border-radius: 999px;",
)
replace("scripts/lib/build_public_map.py", "  #panel { padding-bottom: 56px; }", "  #panel { padding-bottom: 60px; }")
replace(
    "scripts/lib/build_public_map.py",
    "    #panel { bottom: 58px; border-radius: 14px; }",
    "    #panel { bottom: calc(64px + env(safe-area-inset-bottom)); border-radius: 14px; }",
)
replace(
    "scripts/lib/build_public_map.py",
    "    #sb-back, #sb-map-switch a, #sb-theme { padding: 7px 11px; font-size: 12px; }",
    "    #sb-back, #sb-map-switch a, #sb-theme { min-height:36px; padding:8px 12px; font-size:13px; }",
)
replace("scripts/lib/build_public_map.py", "    --edge: #5b6570;", "    --edge: #a7b0ba;")
replace(
    "scripts/lib/build_public_map.py",
    "          styleConfig.colors.edge = theme === 'light' ? '#8a99aa' : '#9aa0a8';\n          applyStyle(styleConfig, { silent: true });",
    "          styleConfig.colors.edge = theme === 'light' ? '#a7b0ba' : '#858b93';\n          // Migrate only the legacy factory opacity; explicit user choices survive.\n          if (styleConfig.edgeOpacity === 0.35) styleConfig.edgeOpacity = 0.28;\n          applyStyle(styleConfig, { silent: true });",
)

# Existing tests intentionally encoded the previous UI; update those contracts.
replace(
    "tests/test_public_reader_polish_contract.py",
    "def test_mobile_reader_controls_preserve_compact_visuals_with_44px_hit_targets():",
    "def test_mobile_reader_controls_preserve_compact_36px_visuals():",
)
replace(
    "tests/test_public_reader_polish_contract.py",
    '    assert "width:44px;height:44px" in css',
    '    assert "width:36px;height:36px" in css',
)
replace(
    "tests/test_public_reader_polish_contract.py",
    '    assert ".sb-nav{gap:6px" in css',
    '    assert ".sb-nav{gap:8px" in css',
)
replace(
    "tests/test_public_reader_polish_contract.py",
    '    assert ".sb-subscribe{display:none" in css',
    '    assert ".sb-subscribe{display:inline-flex" in css',
)
replace(
    "tests/test_public_reader_polish_contract.py",
    '    assert "#sbTheme{border-color:color-mix(in srgb,var(--sb-primary) 42%,var(--sb-line));}" in css',
    '    assert "#sbTheme{border-color:var(--sb-line);}" in css',
)

# Fail locally in the runner if any requested regression contract is missing.
site_css = Path("scripts/site_src/site.css").read_text(encoding="utf-8")
index = Path("scripts/site_src/index.html").read_text(encoding="utf-8")
essay_css = Path("scripts/site_src/essay-theme.css").read_text(encoding="utf-8")
renderer = Path("scripts/lib/render_public_essay.py").read_text(encoding="utf-8")
template = Path("scripts/essay_template.html").read_text(encoding="utf-8")
graph = Path("scripts/build_graph.py").read_text(encoding="utf-8")
public_map = Path("scripts/lib/build_public_map.py").read_text(encoding="utf-8")

assert "width: 36px; height: 36px" in site_css
assert ".brand > span:last-child { display: none; }" in site_css
assert ".topnav .nav-link.active{display:none}" in index
assert "border:1px solid var(--line)" in index.split(".subscribe-cta{", 1)[1].split("}", 1)[0]
assert "height:68px" in essay_css and "height:60px" in essay_css
assert ".sb-nav a:first-child{display:none;}" in essay_css
assert ".sb-subscribe{display:inline-flex;}" in essay_css
assert "#sbTheme{border-color:var(--sb-line);}" in essay_css
assert "position:fixed;top:68px;left:0;right:0;z-index:61;height:2px" in essay_css
assert "body > .sb-progress:not(:has(.sb-progress-fill)){top:60px;}" in essay_css
assert 'id="sbProgressFill"' in renderer
assert ">Second Brain</a>" in renderer
assert "--note-bg:color-mix(in srgb,var(--callout-note) 7%,var(--surface2));" in template
assert "background:var(--note-bg,var(--surface2));" in template
assert "const LABEL_SHOW_AT = 1.40;" in graph and "const LABEL_HIDE_AT = 1.32;" in graph
assert '"edgeOpacity": 0.28' in graph and '"edge": "#858b93"' in graph
assert "#a7b0ba" in public_map and "#858b93" in public_map
assert "min-height: 36px" in public_map
assert "bottom: calc(64px + env(safe-area-inset-bottom))" in public_map
assert "z-index: 8" in public_map
