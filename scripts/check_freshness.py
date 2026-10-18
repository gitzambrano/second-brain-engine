#!/usr/bin/env python3
"""check_freshness.py - Auditoria heurística read-only de alegações temporais em essays.

Sinaliza frases no presente ("atualmente", "estado da arte", "versão atual", etc.)
dentro de ensaios cuja data de ``updated:`` ultrapassa o limiar de frescor configurado,
indicando que a afirmação pode merecer revisão bibliográfica ou contextual.

Escopo:
    Validação read-only puramente consultiva. Warnings nunca bloqueiam CI.
    Default sem argumentos audita todos os essays com limiar de 365 dias.

Entradas (Inputs):
    Arquivos Markdown em DATA_ROOT/wiki/essays/*.md.
    Argumentos CLI opcionais:
        --days INT    Limiar de dias desde updated: (padrão: 365)
        --json        Emite diagnóstico formatado em JSON

Saídas (Outputs):
    Stdout: Lista de frases temporais encontradas por essay com número de dias decorridos.
    JSON: {"check": "freshness", "status": "pass"|"warn", "errors": 0, "warnings": [...]}
    Exit code: 0 sempre (apenas avisos consultivos).

Uso:
    python scripts/check_freshness.py             # auditoria com limiar padrão de 365 dias
    python scripts/check_freshness.py --days 180  # limiar mais estrito de 6 meses
    python scripts/check_freshness.py --json      # saída estruturada em JSON
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re

from repo_paths import ESSAYS_DIR, relative_data

UPDATED_RE = re.compile(r"(?m)^updated:\s*(\d{4}-\d{2}-\d{2})\s*$")
FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.S)

TEMPORAL_CLAIMS = [re.compile(pattern, re.I) for pattern in (
    r"\batualmente\b",
    r"\bhoje\b",
    r"\bmais recente\b",
    r"\bvers[aã]o atual\b",
    r"\bestado da arte\b",
    r"\bno momento\b",
    r"\bhoje em dia\b",
    r"\bcurrently\b",
    r"\blatest\b",
    r"\bcurrent version\b",
)]


def audit(days: int) -> list[dict]:
    issues: list[dict] = []
    if not ESSAYS_DIR.exists():
        return issues

    today = dt.date.today()
    for path in sorted(ESSAYS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8-sig")
        match = UPDATED_RE.search(text)
        if not match:
            continue
        try:
            updated = dt.date.fromisoformat(match.group(1))
        except ValueError:
            continue
        age = (today - updated).days
        if age < days:
            continue

        body = FRONTMATTER_RE.sub("", text, count=1)
        in_code = False
        for number, line in enumerate(body.splitlines(), 1):
            if line.strip().startswith("```"):
                in_code = not in_code
                continue
            if in_code or line.lstrip().startswith("#"):
                continue
            if any(claim.search(line) for claim in TEMPORAL_CLAIMS):
                issues.append({
                    "code": "STALE_CANDIDATE",
                    "severity": "WARNING",
                    "path": str(relative_data(path)),
                    "line": number,
                    "age_days": age,
                    "message": line.strip()[:180],
                })
    return issues


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--days", type=int, default=365,
                    help="minimum age in days before a claim is questioned")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on-warning", action="store_true")
    args = ap.parse_args()

    issues = audit(max(1, args.days))
    if args.json:
        print(json.dumps({
            "status": "warn" if issues else "pass",
            "warnings": len(issues),
            "issues": issues,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"freshness: {'WARN' if issues else 'PASS'} — {len(issues)} candidate(s)")
        for issue in issues:
            print(f"  WARNING {issue['path']}:{issue['line']}: {issue['message']}")
    return 1 if issues and args.fail_on_warning else 0


if __name__ == "__main__":
    raise SystemExit(main())
