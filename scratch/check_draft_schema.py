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

def check_schema_errors(node, path="doc"):
    errors = []
    ntype = node.get("type")
    marks = node.get("marks", [])
    if ntype == "text" and len(marks) > 1:
        types = [m.get("type") for m in marks]
        if "code" in types and ("strong" in types or "em" in types):
            txt = node.get("text", "")[:30]
            errors.append(f"CONFLICT_MARK: {types} in '{txt}' at {path}")
    if ntype == "list_item":
        content = node.get("content", [])
        if not content or content[0].get("type") != "paragraph":
            first_type = content[0].get("type") if content else "None"
            errors.append(f"INVALID_LIST_ITEM: first child is {first_type} at {path}")
    for i, c in enumerate(node.get("content", [])):
        errors.extend(check_schema_errors(c, f"{path}.{ntype}[{i}]"))
    return errors

for pid, slug in new_draft_ids:
    d = api.get_draft(pid)
    dbody_raw = d.get("draft_body")
    if not dbody_raw:
        print(f"[{pid}] {slug}: Sem draft_body")
        continue
    dbody = json.loads(dbody_raw)
    errs = check_schema_errors(dbody)
    if errs:
        print(f"[{pid}] {slug}: {len(errs)} SCHEMA ERRORS!")
        for e in errs[:5]:
            print(f"   ⚠️  {e}")
    else:
        print(f"[{pid}] {slug}: Schema OK")
