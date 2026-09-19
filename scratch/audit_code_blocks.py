import sys, re
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

essays_dir = Path("data/wiki/essays")
threshold = 68

PROGRAMMING_LANGS = {
    "python", "py", "bash", "sh", "powershell", "ps1", "json", "yaml", "yml",
    "javascript", "js", "typescript", "ts", "c", "cpp", "html", "css", "sql", "rust", "go", "diff", "mermaid"
}

results_non_prog = []
results_prog = []

for p in sorted(essays_dir.glob("*.md")):
    content = p.read_text(encoding="utf-8")
    for m in re.finditer(r"```([a-zA-Z0-9_-]*)[^\n]*\n(.*?)```", content, re.DOTALL):
        lang = m.group(1).strip().lower()
        body = m.group(2)
        lines = body.splitlines()
        long_lines = [(i+1, len(l), l) for i, l in enumerate(lines) if len(l) > threshold]
        if long_lines:
            entry = (p.name, lang, len(lines), len(long_lines), max(x[1] for x in long_lines), long_lines)
            if lang in PROGRAMMING_LANGS:
                results_prog.append(entry)
            else:
                results_non_prog.append(entry)

print(f"=== NON-PROGRAMMING BLOCKS (lang not in programming langs) > {threshold} chars: {len(results_non_prog)} ===")
for name, lang, total_l, num_long, max_len, long_lines in results_non_prog:
    print(f"\n{name} | lang={lang!r} | total_lines={total_l} | long_lines={num_long} | max_len={max_len}")
    for idx, l_len, text in long_lines[:5]:
        print(f"   [L{idx} len={l_len}]: {text}")

print(f"\n=== PROGRAMMING BLOCKS > {threshold} chars: {len(results_prog)} ===")
for name, lang, total_l, num_long, max_len, long_lines in results_prog:
    print(f"{name} | lang={lang!r} | total_lines={total_l} | long_lines={num_long} | max_len={max_len}")
