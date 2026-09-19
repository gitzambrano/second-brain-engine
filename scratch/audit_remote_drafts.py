import os
import json
import re
from dotenv import load_dotenv
from pathlib import Path

load_dotenv("substack/.env")
from substack.api import Api

api = Api(
    email=os.getenv("SUBSTACK_EMAIL"),
    password=os.getenv("SUBSTACK_PASSWORD"),
    publication_url=os.getenv("SUBSTACK_PUB_URL")
)

# Fetch all remote drafts with limit=20
posts = []
cursor = None
while True:
    params = {"limit": 20}
    if cursor:
        params["cursor"] = cursor
    r = api._session.get(f"{api.publication_url}/drafts", params=params)
    data = r.json()
    batch = data.get("posts", [])
    posts.extend(batch)
    if not data.get("hasMore") or not data.get("nextCursor"):
        break
    cursor = data.get("nextCursor")

drafts = [p for p in posts if not p.get("is_published")]
print(f"Total remote drafts to audit: {len(drafts)}")

def analyze_prosemirror(doc):
    """Walk through ProseMirror JSON and look for code_blocks, math, arrows, duplicate bylines, etc."""
    issues = []
    text_blocks = []
    
    def walk(node):
        ntype = node.get("type")
        if ntype == "code_block":
            text = "".join([c.get("text", "") for c in node.get("content", [])])
            # Check for math/equations
            if any(sym in text for sym in ["=", "+", "−", "×", "≈", "√", "∫", "∑", "α", "β", "λ", "θ"]):
                if not any(kw in text for kw in ["def ", "import ", "return ", "const ", "let ", "function "]):
                    issues.append(f"CODE_BLOCK_MATH: {text[:60]}...")
            if any(arrow in text for arrow in ["──>", "-->", "==>", "│", "▼", "▲"]):
                issues.append(f"CODE_BLOCK_ARROWS: {text[:60]}...")
            if any(box in text for box in ["┌", "┐", "└", "┘", "├", "┤"]):
                issues.append(f"CODE_BLOCK_BOX: {text[:60]}...")
                
        if ntype == "paragraph":
            ptext = "".join([c.get("text", "") for c in node.get("content", [])])
            text_blocks.append(ptext.strip())
            
        for child in node.get("content", []):
            walk(child)

    walk(doc)
    
    # Check duplicate bylines in text_blocks
    byline_count = sum(1 for p in text_blocks if "Gustavo Zambrano" in p)
    if byline_count > 1:
        issues.append(f"DUPLICATE_BYLINE: {byline_count} occurrences of author byline")
        
    return issues

report = {}
for d in drafts:
    pid = d.get("id")
    slug = d.get("slug")
    title = d.get("title") or slug
    print(f"\nAuditing remote draft [{pid}] {slug}...")
    
    # Fetch full draft details
    try:
        full = api.get_draft(pid)
        body = full.get("body")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except Exception:
                pass
        if isinstance(body, dict):
            issues = analyze_prosemirror(body)
            report[pid] = {"slug": slug, "issues": issues}
            if issues:
                for iss in issues:
                    print(f"  ⚠️  {iss}")
            else:
                print("  ✅ Clean ProseMirror!")
        else:
            print(f"  (Body is not ProseMirror dict: {type(body)})")
    except Exception as e:
        print(f"  Error fetching draft {pid}: {e}")

Path("scratch/remote_draft_audit.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
print("\nSaved report to scratch/remote_draft_audit.json")
