import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from pathlib import Path
import re

from pathlib import Path
import re

print("=== CHECKING SUBSTACK POSTS ===")
for p in sorted(Path('substack/posts').glob('*.md')):
    txt = p.read_text(encoding='utf-8', errors='replace')
    matches = list(re.finditer(r'```([a-zA-Z0-9_-]*)\n(.*?)```', txt, re.DOTALL))
    if matches:
        print(f"\nPost: {p.name} ({len(matches)} code blocks)")
        for idx, m in enumerate(matches, 1):
            lang = m.group(1).strip()
            body = m.group(2).strip()
            start_line = txt.count('\n', 0, m.start()) + 1
            lines = body.splitlines()
            sample = lines[0][:60] if lines else ''
            print(f'  Block #{idx} (line {start_line}, lang="{lang}", lines={len(lines)}): sample="{sample}"')


for fname in files:
    p = Path('data/wiki/essays') / fname
    if not p.exists():
        print(f'{fname} NOT FOUND')
        continue
    txt = p.read_text(encoding='utf-8', errors='replace')
    matches = list(re.finditer(r'```([a-zA-Z0-9_-]*)\n(.*?)```', txt, re.DOTALL))
    print(f'=== {fname} ({len(matches)} code blocks) ===')
    for idx, m in enumerate(matches, 1):
        lang = m.group(1).strip()
        body = m.group(2).strip()
        start_line = txt.count('\n', 0, m.start()) + 1
        lines = body.splitlines()
        print(f'  Block #{idx} (line {start_line}, lang="{lang}", lines={len(lines)}):')
        for l in lines[:3]:
            print(f'    | {l[:70]}')
        if len(lines) > 3:
            print(f'    | ...')
