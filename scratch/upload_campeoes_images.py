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

hero_file = "substack/assets/campeoes_hero.png"
card_file = "substack/assets/campeoes_infocard.png"

hero_res = api.get_image(hero_file)
card_res = api.get_image(card_file)

print(f"HERO_CDN_URL = '{hero_res.get('url')}'")
print(f"CARD_CDN_URL = '{card_res.get('url')}'")
