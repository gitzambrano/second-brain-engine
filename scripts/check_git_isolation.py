#!/usr/bin/env python3
"""check_git_isolation.py - Valida o isolamento dos Gits aninhados e a identidade de cada repositório.

Verifica a regra arquitetural dos 3 repositórios Git independentes (. engine, data/ e site/):
garante que o engine ignore data/ e site/ no .gitignore, que não haja submodules,
que remotes correspondam aos repositórios esperados e que nenhum arquivo de repo aninhado
esteja versionado no pai.

Escopo:
    Validação read-only de repositórios Git. data/ e site/ ausentes são tratados como avisos
    para permitir clones esqueleto. --strict promove ausência de repo aninhado ou remote
    incorreto a erro bloqueante.

Entradas (Inputs):
    Estrutura de diretórios e configuração Git em CODE_ROOT, DATA_ROOT e SITE_ROOT.
    Argumentos CLI opcionais:
        --strict    Exige presença estrita e remotes corretos de data/ e site/
        --json      Emite diagnóstico formatado em JSON

Saídas (Outputs):
    Stdout: Status PASS, WARN ou FAIL com mensagens descritivas de isolamento Git.
    JSON: {"check": "git_isolation", "status": "pass"|"warn"|"fail", "errors": [...], "warnings": [...]}
    Exit code: 0 em sucesso/aviso, 1 em violação de isolamento Git.

Uso:
    python scripts/check_git_isolation.py           # diagnóstico padrão
    python scripts/check_git_isolation.py --strict  # modo rigoroso
    python scripts/check_git_isolation.py --json    # saída estruturada em JSON
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from repo_paths import CODE_ROOT, DATA_ROOT, SITE_ROOT, path_layout_valid

EXPECTED = {
    "engine": "second-brain-engine",
    "data": "second-brain-data",
    "site": "second-brain-site",
}


def run(*args: str, cwd: Path = CODE_ROOT) -> subprocess.CompletedProcess:
    return subprocess.run(
        list(args), cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace"
    )


def git_top(root: Path) -> str | None:
    if not root.exists():
        return None
    p = run("git", "-C", str(root), "rev-parse", "--show-toplevel")
    return str(Path(p.stdout.strip()).resolve()) if p.returncode == 0 else None


def origin(root: Path) -> str | None:
    p = run("git", "-C", str(root), "remote", "get-url", "origin")
    return p.stdout.strip() if p.returncode == 0 else None


def outer_ignores(path: Path) -> bool:
    try:
        rel = path.resolve().relative_to(CODE_ROOT.resolve())
    except ValueError:
        return True  # env-overridden external fixture/worktree
    p = run("git", "-C", str(CODE_ROOT), "check-ignore", "-q", str(rel))
    return p.returncode == 0


def tracked_under(rel: str) -> list[str]:
    p = run("git", "-C", str(CODE_ROOT), "ls-files", "--", rel)
    return [x for x in p.stdout.splitlines() if x.strip()] if p.returncode == 0 else []


def gitlinks() -> list[str]:
    p = run("git", "-C", str(CODE_ROOT), "ls-files", "--stage")
    out = []
    if p.returncode == 0:
        for line in p.stdout.splitlines():
            if line.startswith("160000 "):
                out.append(line.split("\t", 1)[-1])
    return out


def audit(strict: bool = False):
    errors, warnings, info = [], [], []

    if not path_layout_valid():
        errors.append("logical roots overlap")

    engine_top = git_top(CODE_ROOT)
    if engine_top != str(CODE_ROOT.resolve()):
        errors.append(f"engine Git root mismatch: {engine_top}")

    if (CODE_ROOT / ".gitmodules").exists():
        errors.append(".gitmodules exists; nested repos must not be submodules")

    gl = gitlinks()
    if any(x in {"data", "site"} or x.startswith(("data/", "site/")) for x in gl):
        errors.append(f"outer Git index contains gitlink(s): {gl}")

    for rel, root in (("data", DATA_ROOT), ("site", SITE_ROOT)):
        if root.exists() and root.is_relative_to(CODE_ROOT):
            if not outer_ignores(root):
                errors.append(f"outer engine Git does not ignore /{rel}/")
            tracked = tracked_under(rel)
            if tracked:
                errors.append(f"outer engine Git tracks {rel}: {tracked[:10]}")

    for name, root in (("data", DATA_ROOT), ("site", SITE_ROOT)):
        if not root.exists():
            (errors if strict else warnings).append(f"{name} root missing: {root}")
            continue
        top = git_top(root)
        if top != str(root.resolve()):
            (errors if strict else warnings).append(
                f"{name} is not an independent Git root: {top}"
            )
        else:
            info.append(f"{name} git={top}")
        remote = origin(root)
        if not remote:
            (errors if strict else warnings).append(f"{name} has no origin remote")
        elif EXPECTED[name] not in remote:
            (errors if strict else warnings).append(
                f"{name} origin does not reference {EXPECTED[name]}: {remote}"
            )

    eng_remote = origin(CODE_ROOT)
    if eng_remote and EXPECTED["engine"] not in eng_remote:
        (errors if strict else warnings).append(
            f"engine origin does not reference second-brain-engine: {eng_remote}"
        )

    if SITE_ROOT.exists() and not (SITE_ROOT / ".second-brain-site").exists():
        (errors if strict else warnings).append(
            "site missing .second-brain-site safety marker"
        )

    return errors, warnings, info


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()
    e, w, i = audit(args.strict)
    payload = {
        "status": "fail" if e else "warn" if w else "pass",
        "errors": e, "warnings": w, "info": i,
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"workspace: {payload['status'].upper()}")
        for message in e:
            print(f"  ERROR   {message}")
        for message in w:
            print(f"  WARNING {message}")
        for message in i:
            print(f"  INFO    {message}")
    return 1 if e else 0


if __name__ == "__main__":
    raise SystemExit(main())
