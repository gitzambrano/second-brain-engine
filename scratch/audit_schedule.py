import os
from dotenv import load_dotenv

load_dotenv("substack/.env")
from substack.api import Api

cookie = os.getenv("SUBSTACK_COOKIE")
cookie_str = cookie if (cookie and "=" in cookie) else (f"substack.sid={cookie}" if cookie else None)
api = Api(
    cookies_string=cookie_str,
    email=os.getenv("SUBSTACK_EMAIL"),
    password=os.getenv("SUBSTACK_PASSWORD"),
    publication_url=os.getenv("SUBSTACK_PUB_URL")
)

res = api.get_drafts()
posts = res.get("posts", [])
print(f"Total drafts/scheduled fetched: {len(posts)}")

scheduled = []
drafts = []

for p in posts:
    pid = p.get("id")
    title = p.get("title")
    pdate = p.get("post_date")
    pub = p.get("is_published")
    if pdate:
        scheduled.append((pdate, pid, title))
    else:
        drafts.append((pid, title))

scheduled.sort()
print(f"\n=== SCHEDULED QUEUE ({len(scheduled)}) ===")
for d, pid, title in scheduled:
    print(f"  {d} | #{pid} | {title}")

print(f"\n=== UNSCHEDULED DRAFTS ({len(drafts)}) ===")
for pid, title in drafts:
    print(f"  #{pid} | {title}")
