import re
from pathlib import Path

t = Path("substack/posts/rpg-de-mesa-e-a-teoria-da-informacao-entropia-narrativa-simulacao-cognitiva-e-a-linguagem-sem-limites.md").read_text(encoding="utf-8")
print("Display math:", len(re.findall(r"\$\$[\s\S]*?\$\$", t)))
print("Inline math:", len(re.findall(r"(?<!\\)\$([^\$\n]+)\$", t)))
for im in re.findall(r"(?<!\\)\$([^\$\n]+)\$", t):
    print(" ", repr(im))

callouts = re.findall(r"::: callout[\s\S]*?:::", t)
print(f"Callouts: {len(callouts)}")
for i, c in enumerate(callouts):
    print(f"--- Callout {i+1} ---")
    print(c[:150])

pullquotes = re.findall(r"::: pullquote[\s\S]*?:::", t)
print(f"Pullquotes: {len(pullquotes)}")
