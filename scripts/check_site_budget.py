#!/usr/bin/env python3
"""check_site_budget.py - Orçamento de tamanho e integridade dos artefatos públicos.

Audita os limites de tamanho em disco dos arquivos servidos pelo site público para
prevenir inchaço acidental ou inclusão de dados desnecessários em bundles estáticos:
- Tetos específicos para index.html, 404.html, graph.html, sphere.html, etc.
- Orçamento global para podcasts em áudio (teto por arquivo individual e total conjunto).

Escopo:
    Auditoria estática read-only do tamanho de arquivos em SITE_ROOT.
    Ultrapassar o teto declarado exige justificativa expressa e revisão dos limites declarados.

Entradas (Inputs):
    Arquivos em SITE_ROOT.
    Argumentos CLI opcionais:
        --json    Emite diagnóstico formatado em JSON

Saídas (Outputs):
    Stdout: Tamanho medido vs. orçamento para cada categoria e artefato público.
    JSON: {"check": "site_budget", "status": "pass"|"warn"|"fail", "issues": [...]}
    Exit code: 0 em conformidade, 1 se algum artefato estourar o orçamento declarado.

Uso:
    python scripts/check_site_budget.py         # auditoria de tamanho padrão
    python scripts/check_site_budget.py --json  # saída estruturada em JSON
"""
from __future__ import annotations

import argparse
import fnmatch

import console_encoding  # noqa: F401  (UTF-8 no console; ver o módulo)
from repo_paths import SITE_ROOT
from sanity_common import CheckResult

# Podcasts: cada cópia publicada (AAC mono 48 kbps) e a soma de todas.
PODCAST_PREFIX = "assets/podcasts/"
PODCAST_FILE_KB = 25 * 1024
PODCASTS_TOTAL_MB = 700

# Teto em KB por padrão de caminho, relativo a SITE_ROOT. A primeira regra que
# casa vence, então o específico vem antes do genérico.
BUDGETS_KB: list[tuple[str, int]] = [
    ("index.html", 400),
    ("404.html", 32),
    ("graph.html", 1200),
    ("sphere.html", 900),
    # Catálogo, não corpus: sem o corpo dos essays isto fica na casa das
    # dezenas de KB. O teto está em 400 para acusar um corpo que volte.
    ("search-index.json", 400),
    ("site-manifest.json", 64),
    ("assets/mathjax/*", 4096),
    ("assets/cover-*.png", 512),
    ("assets/favicon.ico", 32),
    ("assets/icon-*.png", 512),
    ("assets/apple-touch-icon.png", 128),
    ("assets/fonts/*", 256),
    ("assets/*.css", 128),
    ("assets/*.js", 128),
    ("assets/media/*", 1024),
    # Áudio tem orçamento próprio (PODCASTS_TOTAL_MB) e fica fora do teto do site.
    ("assets/podcasts/*", PODCAST_FILE_KB),
    ("essays/*.html", 1600),
]

# Teto do site inteiro. Não é o mesmo que a soma dos tetos individuais: serve
# para pegar o caso de "cada arquivo dentro do limite, mil arquivos novos".
TOTAL_MB = 60


def budget_for(relative: str) -> int | None:
    for pattern, limit in BUDGETS_KB:
        if fnmatch.fnmatch(relative, pattern):
            return limit
    return None


def audit(root=None) -> CheckResult:
    root = root or SITE_ROOT
    result = CheckResult("site-budget")

    if not root.is_dir():
        result.skip("NO_SITE", f"site root not found: {root}")
        return result

    files = [p for p in sorted(root.rglob("*")) if p.is_file() and ".git" not in p.parts]
    if not files:
        result.skip("NO_FILES", f"nothing built in {root}")
        return result

    total_kb = 0.0
    podcast_kb = 0.0
    checked = 0
    for path in files:
        relative = path.relative_to(root).as_posix()
        kb = path.stat().st_size / 1024
        if relative.startswith(PODCAST_PREFIX):
            podcast_kb += kb
        else:
            total_kb += kb
        limit = budget_for(relative)
        if limit is None:
            continue
        checked += 1
        if kb > limit:
            result.error(
                "OVER_BUDGET",
                f"{relative}: {kb:.0f} KB excede o teto de {limit} KB",
                relative,
            )
        elif kb > limit * 0.85:
            result.warning(
                "NEAR_BUDGET",
                f"{relative}: {kb:.0f} KB, {kb / limit:.0%} do teto de {limit} KB",
                relative,
            )

    total_mb = total_kb / 1024
    if total_mb > TOTAL_MB:
        result.error("SITE_OVER_BUDGET", f"site inteiro: {total_mb:.1f} MB excede {TOTAL_MB} MB")

    podcast_mb = podcast_kb / 1024
    if podcast_mb > PODCASTS_TOTAL_MB:
        result.error("PODCASTS_OVER_BUDGET",
                     f"podcasts: {podcast_mb:.1f} MB excede {PODCASTS_TOTAL_MB} MB")
    result.meta["podcasts_mb"] = round(podcast_mb, 2)
    result.meta["files"] = len(files)
    result.meta["budgeted"] = checked
    result.meta["total_mb"] = round(total_mb, 2)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on-warning", action="store_true")
    args = ap.parse_args()
    result = audit()
    result.print(args.json)
    return result.exit_code(args.fail_on_warning)


if __name__ == "__main__":
    raise SystemExit(main())
