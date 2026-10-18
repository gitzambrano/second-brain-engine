"""build_newsletter_manifest.py - Constrói o manifesto de newsletter a partir de metadados de essays.

Filtra ensaios públicos elegíveis que possuam o campo ``newsletter_issue: N`` no frontmatter:
- Extrai título, subtítulo, resumo, tempo de leitura e URL canônica.
- O manifesto gerado fica sob .github/ no site e alimenta a ação de notificação via Kit.

Escopo:
    Módulo de biblioteca de publicação de newsletter.
    Gera manifesto privado no repositório site/, fora do artefato público servido pelo Pages.

Entradas (Inputs):
    Metadados de ensaios públicos em SITE_ROOT/essays/.

Saídas (Outputs):
    Gravação de SITE_ROOT/.github/newsletter-manifest.json.
"""
from __future__ import annotations

import json
from pathlib import Path

from repo_paths import SITE_ROOT
from site_common import (
    collect_public,
    parse,
    plain_text,
    public_body_for_index,
    reading_minutes,
)

OUTPUT_NAME = ".github/newsletter-manifest.json"


def _clip(text: str, limit: int = 150) -> str:
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:-")
    return (cut or text[: limit - 1]).rstrip() + "…"


def collect_newsletter_entries() -> list[dict[str, object]]:
    public = collect_public()
    allowed = {essay.slug for essay in public}
    entries: list[dict[str, object]] = []

    for essay in public:
        meta, _body = parse(essay.path)
        if "newsletter_issue" not in meta:
            continue

        issue = str(meta["newsletter_issue"]).strip()
        if not issue.isdecimal() or int(issue) < 1:
            continue
        identity = f"{essay.slug}:{issue}"
        summary = str(meta.get("newsletter_summary") or essay.summary).strip()
        subject = str(meta.get("newsletter_subject") or f"Novo essay — {essay.title}").strip()
        preview = str(meta.get("newsletter_preview") or _clip(summary)).strip()
        body = plain_text(public_body_for_index(essay, allowed))

        entries.append(
            {
                "id": identity,
                "slug": essay.slug,
                "title": essay.title,
                "subject": subject,
                "preview_text": preview,
                "summary": summary,
                "updated": essay.updated,
                "minutes": reading_minutes(body),
                "path": f"essays/{essay.slug}.html",
            }
        )

    entries.sort(key=lambda entry: str(entry["id"]))
    return entries


def build(output: Path | None = None) -> Path:
    output = output or (SITE_ROOT / OUTPUT_NAME)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {"version": 2, "entries": collect_newsletter_entries()}
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return output


def main() -> int:
    path = build()
    print(f"newsletter manifest: {path}")
    return 0
