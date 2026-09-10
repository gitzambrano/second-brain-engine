from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"pattern not found in {path}: {old[:80]!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


css = ROOT / "scripts/site_src/essay-theme.css"
for old, new in [
    ("--sb-text:#172235;", "--sb-text:#0a1525;"),
    ("--sb-muted:#607087;", "--sb-muted:#5d6c81;"),
    ("--sb-line:rgba(23,34,53,.14);", "--sb-line:rgba(23,34,53,.12);"),
    ("--sb-line-strong:rgba(23,34,53,.26);", "--sb-line-strong:rgba(23,34,53,.24);"),
    ("--sb-text:#f0ede7;", "--sb-text:#ffffff;"),
    ("--sb-muted:#aaa39a;", "--sb-muted:#a6a6a6;"),
    ("--sb-line:rgba(240,237,231,.14);", "--sb-line:rgba(255,255,255,.11);"),
    ("--sb-line-strong:rgba(240,237,231,.25);", "--sb-line-strong:rgba(255,255,255,.22);"),
]:
    replace(css, old, new)

replace(css,
""".sb-bar{
  position:fixed;inset:0 0 auto 0;z-index:60;height:68px;
  display:flex;align-items:center;justify-content:space-between;gap:16px;
  padding:0 clamp(16px,4vw,40px);
  border-bottom:1px solid var(--sb-line);
  background:color-mix(in srgb,var(--sb-bg) 90%,transparent);
  backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,\"Segoe UI\",sans-serif;
}""",
""".sb-bar{
  position:fixed;top:0;left:50%;transform:translateX(-50%);z-index:60;
  width:min(1120px,calc(100% - 48px));height:68px;
  display:flex;align-items:center;justify-content:space-between;gap:16px;
  padding:0;
  border-bottom:1px solid var(--sb-line);
  background:color-mix(in srgb,var(--sb-bg) 86%,transparent);
  backdrop-filter:blur(14px);-webkit-backdrop-filter:blur(14px);
  font-family:Inter,ui-sans-serif,system-ui,-apple-system,\"Segoe UI\",sans-serif;
}""")
replace(css, "display:inline-flex;align-items:center;gap:10px;", "display:inline-flex;align-items:center;gap:11px;")
replace(css,
""".sb-nav button{
  width:36px;height:36px;border:1px solid var(--sb-line);border-radius:10px;
  background:transparent;color:var(--sb-primary);cursor:pointer;
}
.sb-nav button:hover{border-color:var(--sb-line-strong);}""",
""".sb-nav button{
  width:36px;height:36px;display:grid;place-items:center;
  border:1px solid var(--sb-line);border-radius:10px;
  background:transparent;color:var(--sb-primary);cursor:pointer;
  transition:border-color .16s cubic-bezier(.22,.61,.36,1);
}
.sb-nav button:hover{border-color:color-mix(in srgb,var(--sb-primary) 55%,var(--sb-line));}""")
replace(css,
""".sb-nav .sb-subscribe{
  width:auto;height:36px;padding:0 12px;
  border-color:var(--sb-line);border-radius:999px;
  background:color-mix(in srgb,var(--sb-primary) 13%,var(--sb-surface));color:var(--sb-primary);font:650 12.5px/1 Inter,ui-sans-serif,system-ui,sans-serif;
}""",
""".sb-nav .sb-subscribe{
  width:auto;height:36px;min-height:36px;padding:0 12px;
  display:inline-flex;align-items:center;justify-content:center;
  border-color:var(--sb-line);border-radius:999px;
  background:color-mix(in srgb,var(--sb-primary) 13%,var(--sb-surface));color:var(--sb-primary);
  font:650 12.5px Inter,ui-sans-serif,system-ui,-apple-system,\"Segoe UI\",sans-serif;
}""")
replace(css,
"""@media(max-width:720px){
  .sb-bar{height:60px;padding-inline:14px;}
  body{padding-top:60px;}
  body > .sb-progress:not(:has(.sb-progress-fill)){top:60px;}
  .sb-nav{gap:8px;}
  .sb-nav a{font-size:13px;}
  .sb-brand{gap:0;font-size:0;}
  .sb-nav a:first-child{display:none;}
  .sb-nav button{width:36px;height:36px;}
  .sb-nav #sbTheme{font-size:1.25rem;}
  .sb-subscribe{display:inline-flex;}""",
"""@media(max-width:720px){
  .sb-bar{width:min(1120px,calc(100% - 28px));height:60px;padding:0;}
  body{padding-top:60px;}
  body > .sb-progress:not(:has(.sb-progress-fill)){top:60px;}
  .sb-nav{gap:14px;}
  .sb-nav a{font-size:13px;}
  .sb-brand{gap:0;font-size:0;}
  .sb-nav a:first-child{display:none;}
  .sb-nav button{width:36px;height:36px;}
  .sb-nav #sbTheme > span{display:block;font-size:1.28rem;line-height:1;}
  .sb-nav .sb-subscribe{height:36px;min-height:36px;padding-inline:10px;font-size:12px;line-height:normal;}
  .sb-subscribe{display:inline-flex;}""")
replace(css,
"""@media(max-width:520px){
  .sb-brand{gap:0;font-size:0;}
  .sb-nav{gap:8px;}
  .sb-nav a{font-size:13px;}
}""",
"""@media(max-width:520px){
  .sb-brand{gap:0;font-size:0;}
  .sb-nav{gap:14px;}
  .sb-nav a{font-size:13px;}
}""")

render = ROOT / "scripts/lib/render_public_essay.py"
replace(render, '<a href="../index.html">Essays</a>', '<a class="active" href="../index.html">Ensaios</a>')
replace(render, '<button type="button" id="sbTheme" aria-label="Alternar tema" aria-pressed="false">◐</button>', '<button type="button" id="sbTheme" aria-label="Alternar tema" aria-pressed="false"><span aria-hidden="true">◐</span></button>')

site_css = ROOT / "scripts/site_src/site.css"
replace(site_css, ".icon-button > span { font-size: 1.2rem; line-height: 1; }", ".icon-button > span { font-size: 1.28rem; line-height: 1; }")

graph = ROOT / "scripts/build_graph.py"
replace(graph, "const LABEL_SHOW_AT = 1.40;", "const LABEL_SHOW_AT = 1.16;")
replace(graph, "const LABEL_HIDE_AT = 1.32;", "const LABEL_HIDE_AT = 1.10;")

# Keep contract tests aligned with the new canonical mobile header geometry.
test = ROOT / "tests/test_public_reader_polish_contract.py"
text = test.read_text(encoding="utf-8")
text = text.replace('assert ".sb-nav{gap:8px" in css', 'assert ".sb-nav{gap:14px" in css')
text = text.replace('assert ".sb-nav #sbTheme{font-size:1.25rem;}" in css', 'assert ".sb-nav #sbTheme > span{display:block;font-size:1.28rem;line-height:1;}" in css')
# stronger regression: the essay header must use the landing header's mobile rhythm.
needle = 'def test_mobile_toc_keeps_secondary_entries_readable_and_active_state_quiet():'
extra = '''def test_mobile_reader_header_matches_landing_header_rhythm():\n    css = (SRC / "essay-theme.css").read_text(encoding="utf-8")\n    landing = (SRC / "site.css").read_text(encoding="utf-8")\n    source = (ROOT / "scripts" / "lib" / "render_public_essay.py").read_text(encoding="utf-8")\n    assert ".sb-nav{gap:14px;}" in css\n    assert ".topnav { gap: 14px; }" in landing\n    assert "calc(100% - 28px)" in css\n    assert '<a class="active" href="../index.html">Ensaios</a>' in source\n    assert '<span aria-hidden="true">◐</span>' in source\n\n\n'''
if extra not in text:
    text = text.replace(needle, extra + needle)
test.write_text(text, encoding="utf-8")

# Update any exact graph-threshold regression without broad source edits.
for p in (ROOT / "tests").glob("test_*.py"):
    t = p.read_text(encoding="utf-8")
    n = t.replace('const LABEL_SHOW_AT = 1.40;', 'const LABEL_SHOW_AT = 1.16;')
    n = n.replace('const LABEL_HIDE_AT = 1.32;', 'const LABEL_HIDE_AT = 1.10;')
    n = n.replace('.icon-button > span { font-size: 1.2rem; line-height: 1; }', '.icon-button > span { font-size: 1.28rem; line-height: 1; }')
    if n != t:
        p.write_text(n, encoding="utf-8")

print("mobile header visual fix staged")
