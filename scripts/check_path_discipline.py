#!/usr/bin/env python3
"""check_path_discipline.py - Barra scripts que fixam caminhos wiki/plan/raw/output locais ao engine.

Audita scripts do repositório garantindo que caminhos de dados privados (wiki, plan, raw, output)
sejam sempre resolvidos via ``repo_paths`` (DATA_ROOT) e nunca construídos diretamente
a partir da raiz do engine público (CODE_ROOT).

Escopo:
    Validação estática read-only em scripts Python de SCRIPTS_DIR.
    Exceções permitidas declaradas em EXEMPT (como o próprio repo_paths.py).

Entradas (Inputs):
    Arquivos Python em scripts/*.py.
    Argumentos CLI opcionais:
        --json    Emite diagnóstico formatado em JSON

Saídas (Outputs):
    Stdout: Status PASS ou FAIL com linhas e padrões proibidos encontrados.
    JSON: {"check": "path_discipline", "status": "pass"|"fail", "errors": [...], "warnings": [...]}
    Exit code: 0 em conformidade, 1 se houver caminho hardcoded proibido.

Uso:
    python scripts/check_path_discipline.py         # auditoria padrão
    python scripts/check_path_discipline.py --json  # saída estruturada em JSON
"""
from __future__ import annotations

import argparse
import json
import re

from repo_paths import SCRIPTS_DIR

FORBIDDEN = [
    re.compile(r"\b(?:ROOT_DIR|CODE_ROOT)\s*/\s*[\"']" + name + r"[\"']")
    for name in ("wiki", "plan", "raw", "output")
]

# repo_paths defines the roots; the migration tool and this checker must name the
# legacy locations literally in order to do their job.
EXEMPT = {"repo_paths.py", "migrate_private_data.py", "check_path_discipline.py"}


def audit() -> list[dict[str, str]]:
    issues = []
    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        if path.name in EXEMPT:
            continue
        source = path.read_text(encoding="utf-8-sig")
        if any(pattern.search(source) for pattern in FORBIDDEN):
            issues.append({
                "path": str(path.relative_to(SCRIPTS_DIR.parent)),
                "message": "hard-coded engine-local data path; import repo_paths",
            })
    return issues


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    issues = audit()
    if args.json:
        print(json.dumps({
            "status": "fail" if issues else "pass",
            "issues": issues,
            "errors": [f"{i['path']}: {i['message']}" for i in issues],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"path-discipline: {'FAIL' if issues else 'PASS'}")
        for issue in issues:
            print(f"  ERROR {issue['path']}: {issue['message']}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
