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

all_drafts = []
cursor = None

while True:
    params = {"limit": 20}
    if cursor:
        params["cursor"] = cursor
    r = api._session.get(f"{api.publication_url}/drafts", params=params)
    data = r.json()
    posts = data.get("posts", [])
    all_drafts.extend(posts)
    print(f"Fetched {len(posts)} posts (total now: {len(all_drafts)})")
    if not data.get("hasMore"):
        break
    cursor = data.get("nextCursor")
    if not cursor:
        break

print(f"\nTotal remote drafts fetched: {len(all_drafts)}")
for d in all_drafts:
    pid = d.get("id")
    title = d.get("title")
    slug = d.get("slug")
    is_pub = d.get("is_published")
    post_date = d.get("post_date")
    audience = d.get("audience")
    print(f"[{pid}] title: '{title}' | slug: '{slug}' | pub: {is_pub} | date: {post_date}")
