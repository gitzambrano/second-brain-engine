import re
from pathlib import Path

text = Path("substack/posts/o-que-e-vida-um-ensaio-nas-fronteiras-da-existencia.md").read_text(encoding="utf-8")

math_blocks = re.findall(r"\$\$[\s\S]*?\$\$", text)
print(f"Display math count: {len(math_blocks)}")
for mb in math_blocks:
    print(" ", repr(mb))

inline_math = re.findall(r"(?<!\\)\$([^\$\n]+)\$", text)
print(f"Inline math count: {len(inline_math)}")
for im in inline_math[:10]:
    print(" ", repr(im))
