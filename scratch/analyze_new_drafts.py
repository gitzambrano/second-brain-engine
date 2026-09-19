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

# Os 9 drafts novos criados recentemente
new_draft_ids = [
    (216380774, "lego-e-a-fisica-do-encaixe"),
    (216381367, "quem-e-voce-identidade-pessoal"),
    (216381714, "o-principio-antropico"),
    (216382120, "a-fenomenologia-do-tabuleiro"),
    (216382533, "engenharia-em-menos-de-um-metro-cubico"),
    (216383096, "o-que-e-vida"),
    (216383684, "ficcao-cientifica-como-incubadora-teorica"),
    (216384954, "campeoes-por-acaso"),
    (216386174, "rpg-de-mesa-e-a-teoria-da-informacao"),
]

print("="*70)
print("AUDITORIA DOS NOVOS DRAFTS REMOTOS NO SUBSTACK")
print("="*70)

for pid, label in new_draft_ids:
    d = api.get_draft(pid)
    slug = d.get("slug")
    dbody_raw = d.get("draft_body")
    if not dbody_raw:
        print(f"[{pid}] {label}: Sem draft_body!")
        continue
    try:
        dbody = json.loads(dbody_raw)
    except Exception as e:
        print(f"[{pid}] {label}: Erro ao decodificar JSON do draft_body: {e}")
        continue
        
    code_blocks = []
    bylines = []
    callouts = []
    footnotes = []
    
    def walk(n):
        ntype = n.get("type")
        if ntype == "code_block":
            txt = "".join([c.get("text", "") for c in n.get("content", [])])
            code_blocks.append(txt)
        elif ntype == "paragraph":
            ptxt = "".join([c.get("text", "") for c in n.get("content", [])])
            if "Gustavo Zambrano" in ptxt:
                bylines.append(ptxt.strip())
        elif ntype == "captioned_image":
            pass
        elif ntype == "footnote":
            footnotes.append(n)
        for c in n.get("content", []):
            walk(c)
            
    walk(dbody)
    
    # Análise de problemas
    issues = []
    if len(bylines) > 1:
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
            
    print(f"\n[{pid}] {slug}:")
    print(f"  Code blocks: {len(code_blocks)} | Bylines: {len(bylines)}")
    if issues:
        for iss in issues:
            print(f"  ⚠️  {iss}")
    else:
        print("  ✅ 100% LIMPO E CONFORME!")
