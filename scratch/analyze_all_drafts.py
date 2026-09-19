import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
import os
import json
from dotenv import load_dotenv

load_dotenv("substack/.env")
from substack.api import Api

api = Api(
    email=os.getenv("SUBSTACK_EMAIL"),
    password=os.getenv("SUBSTACK_PASSWORD"),
    publication_url=os.getenv("SUBSTACK_PUB_URL")
)

posts = []
cursor = None
while True:
    params = {"limit": 20}
    if cursor:
        params["cursor"] = cursor
    r = api._session.get(f"{api.publication_url}/drafts", params=params)
    data = r.json()
    posts.extend(data.get("posts", []))
    if not data.get("hasMore") or not data.get("nextCursor"):
        break
    cursor = data.get("nextCursor")

drafts = [p for p in posts if not p.get("is_published")]

print(f"Total drafts encontrados: {len(drafts)}")
print("="*70)

for d in drafts:
    pid = d.get("id")
    slug = d.get("slug")
    full = api.get_draft(pid)
    dbody_raw = full.get("draft_body")
    if not dbody_raw:
        print(f"[{pid}] {slug}: Sem draft_body")
        continue
    try:
        dbody = json.loads(dbody_raw)
    except Exception:
        print(f"[{pid}] {slug}: Erro JSON")
        continue
        
    code_blocks = []
    bylines = []
    
    def walk(n):
        ntype = n.get("type")
        if ntype == "code_block":
            txt = "".join([c.get("text", "") for c in n.get("content", [])])
            code_blocks.append(txt)
        elif ntype == "paragraph":
            ptxt = "".join([c.get("text", "") for c in n.get("content", [])])
            if "Gustavo Zambrano" in ptxt:
                bylines.append(ptxt.strip())
        for c in n.get("content", []):
            walk(c)
            
    walk(dbody)
    
    issues = []
    # Byline repetida
    if len(bylines) > 2:  # 1 no topo + 1 no footer é esperado; mais que 2 é duplicata no topo
        issues.append(f"BYLINE DUPLICADA ({len(bylines)}x)")
    for cb in code_blocks:
        first = cb.strip().splitlines()[0] if cb.strip() else ""
        if any(sym in cb for sym in ["=", "+", "−", "×", "≈", "√", "∫", "∑", "α", "β", "λ", "θ"]):
            if not any(kw in cb for kw in ["def ", "import ", "return ", "const ", "let ", "class "]):
                issues.append(f"EQUAÇÃO EM CODE BLOCK: '{first[:50]}'")
        if any(arrow in cb for arrow in ["──>", "-->", "==>", "│", "▼", "▲"]):
            issues.append(f"SETAS ASCII EM CODE BLOCK: '{first[:50]}'")
        if any(box in cb for box in ["┌", "┐", "└", "┘", "├", "┤"]):
            issues.append(f"BOX ASCII EM CODE BLOCK: '{first[:50]}'")
            
    print(f"[{pid}] {slug}:")
    print(f"  Code blocks: {len(code_blocks)} | Bylines: {len(bylines)}")
    if issues:
        for iss in issues:
            print(f"  ⚠️  {iss}")
    else:
        print("  ✅ 100% LIMPO E CONFORME!")
