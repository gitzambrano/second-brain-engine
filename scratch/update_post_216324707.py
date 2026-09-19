import os
import json
import time
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("substack/.env")
from substack.api import Api
from substack.post import Post
import sys

sys.path.insert(0, "substack")
from publish_essay import sanitize_prosemirror_nodes, append_second_brain_footer

POST_ID = 216324707
POST_PATH = Path("substack/posts/voar-e-reduzir-incerteza-a-aeronave-como-maquina-de-informacao.md")

cookie = os.getenv("SUBSTACK_COOKIE")
sid = cookie if "=" in cookie else f"substack.sid={cookie}"
api = Api(cookies_string=sid, publication_url=os.getenv("SUBSTACK_PUB_URL", "https://gzambrano.substack.com"))
user_id = api.get_user_id()

raw = POST_PATH.read_text(encoding="utf-8")
meta = {}
body = raw
if raw.startswith("---"):
    parts = raw.split("---", 2)
    if len(parts) >= 3:
        body = parts[2].strip()
        for line in parts[1].strip().splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"').strip("'")

existing = api.get_draft(POST_ID)
title = meta.get("title") or existing.get("title")
subtitle = meta.get("subtitle") or existing.get("subtitle") or ""
cover_url = meta.get("cover_image") or existing.get("cover_image")

if cover_url and cover_url not in body:
    hero_md = f"\n\n![{title}]({cover_url})\n\n"
    if "## Sumário" in body:
        body = body.replace("## Sumário", hero_md + "## Sumário", 1)
    else:
        body = hero_md + body

post = Post(title=title, subtitle=subtitle, user_id=user_id, audience="everyone")
post.from_markdown(body, api=api)
append_second_brain_footer(post)
sanitize_prosemirror_nodes(post.draft_body)

payload = {
    "draft_body": json.dumps(post.draft_body),
    "title": title,
    "subtitle": subtitle,
}
if cover_url:
    payload["cover_image"] = cover_url

print(f"[*] Atualizando rascunho #{POST_ID} na API do Substack...")
api.put_draft(POST_ID, **payload)
print("    [OK] Rascunho salvo com sucesso!")
