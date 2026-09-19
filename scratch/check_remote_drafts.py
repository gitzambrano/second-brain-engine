import os
import json
from dotenv import load_dotenv
from pathlib import Path

load_dotenv("substack/.env")
from substack.api import Api

api = Api(
    email=os.getenv("SUBSTACK_EMAIL"),
    password=os.getenv("SUBSTACK_PASSWORD"),
    publication_url=os.getenv("SUBSTACK_PUB_URL")
)

print("Fetching drafts from Substack API...")
res = api.get_drafts()
items = res if isinstance(res, list) else res.get("posts", [])
print(f"Total drafts found: {len(items)}")

for d in items:
    post_id = d.get("id")
    title = d.get("title")
    slug = d.get("slug")
    is_published = d.get("is_published")
    audience = d.get("audience")
    post_date = d.get("post_date")
    print(f"[{post_id}] '{title}' (slug: {slug}, pub: {is_published}, date: {post_date})")

Path("scratch/remote_drafts.json").write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
print("Saved raw draft list to scratch/remote_drafts.json")
