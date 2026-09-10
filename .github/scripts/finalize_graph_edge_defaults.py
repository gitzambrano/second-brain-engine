from pathlib import Path

p = Path("scripts/build_graph.py")
text = p.read_text(encoding="utf-8")
changes = [
    ("    --edge: #9aa0a8;", "    --edge: #858b93;"),
    ("    --edge-opacity: 0.55;", "    --edge-opacity: 0.28;"),
]
for old, new in changes:
    found = text.count(old)
    if found != 1:
        raise SystemExit(f"expected exactly one occurrence, found {found}: {old}")
    text = text.replace(old, new)
p.write_text(text, encoding="utf-8")

assert "    --edge: #858b93;" in text
assert "    --edge-opacity: 0.28;" in text
assert "const LABEL_SHOW_AT = 1.40;" in text
assert '"edgeOpacity": 0.28' in text
print("graph initial edge defaults finalized")
