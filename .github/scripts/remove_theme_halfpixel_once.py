from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
paths = [
    ROOT / "scripts/site_src/index.html",
    ROOT / "scripts/site_src/essay-theme.css",
    ROOT / "tests/test_public_reader_polish_contract.py",
]
for path in paths:
    text = path.read_text(encoding="utf-8")
    old = "transform:translateY(-.5px)"
    if old not in text:
        raise SystemExit(f"missing {old} in {path}")
    path.write_text(text.replace(old, ""), encoding="utf-8")
print("removed half-pixel theme glyph offset")
