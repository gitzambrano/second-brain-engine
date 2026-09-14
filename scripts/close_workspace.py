#!/usr/bin/env python3
"""Fecha o workspace de forma determinística.

Sem subcommand, executa `prepare`.

Ações:
- prepare: pre-flight, fixes mecânicos, rebuilds e post-flight.
- commit: executa prepare e cria commits locais separados em data e engine.
- push: exige worktrees limpas e envia data e engine separadamente.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from repo_paths import CODE_ROOT, DATA_ROOT


class CloseError(RuntimeError):
    pass


def _display(argv: list[str]) -> str:
    return " ".join(argv)


def _run(
    argv: list[str],
    *,
    cwd: Path = CODE_ROOT,
    check: bool = True,
    shell: bool = False,
) -> subprocess.CompletedProcess[str]:
    print(f"> {_display(argv)}")
    proc = subprocess.run(argv, cwd=cwd, text=True, encoding="utf-8", errors="replace", shell=shell)
    if check and proc.returncode:
        raise CloseError(f"falhou ({proc.returncode}): {_display(argv)}")
    return proc


def _python(script: str, *args: str) -> None:
    _run([sys.executable, str(CODE_ROOT / "scripts" / script), *args])


def prepare() -> None:
    for script, args in (
        ("sync_skills.py", ()),
        ("repo_paths.py", ()),
        ("check_git_isolation.py", ()),
        ("check_path_discipline.py", ()),
        ("check_repo.py", ("--quick",)),
    ):
        _python(script, *args)

    _python("fix_lint.py")

    for script, args in (
        ("build_index.py", ()),
        ("build_references.py", ()),
        ("build_graph.py", ()),
        ("build_sphere.py", ()),
        ("stats.py", ("--save",)),
    ):
        _python(script, *args)

    qmd_bin = shutil.which("qmd")
    if qmd_bin:
        is_windows = sys.platform == "win32"
        _run([qmd_bin, "status"], shell=is_windows)
        _run([qmd_bin, "update"], shell=is_windows)
        _run([qmd_bin, "embed"], shell=is_windows)

    _python("sync_skills.py", "--check")
    _python("check_repo.py", "--wiki")


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(root), *args], check=check)


def _require_git_repo(root: Path, label: str) -> None:
    proc = _git(root, "rev-parse", "--is-inside-work-tree", check=False)
    if proc.returncode:
        raise CloseError(f"{label} não é um repositório Git utilizável: {root}")


def _staged_source_originals() -> list[str]:
    proc = subprocess.run(
        ["git", "-C", str(DATA_ROOT), "diff", "--cached", "--name-only", "--", "wiki/sources"],
        cwd=CODE_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode:
        raise CloseError("não foi possível inspecionar sources staged em data")
    allowed_prefix = "wiki/sources/resumos/"
    allowed_exact = {"wiki/sources/manifest.md", "wiki/sources/map.md"}
    return [
        line.strip()
        for line in proc.stdout.splitlines()
        if line.strip() and line.strip() not in allowed_exact and not line.strip().startswith(allowed_prefix)
    ]


def _commit_repo(root: Path, message: str) -> None:
    _git(root, "add", "-A")
    if root == DATA_ROOT:
        blocked = _staged_source_originals()
        if blocked:
            raise CloseError("documento original em wiki/sources staged: " + ", ".join(blocked))
    diff = _git(root, "diff", "--cached", "--quiet", check=False)
    if diff.returncode == 0:
        print(f"sem mudanças para commit em {root}")
        return
    if diff.returncode != 1:
        raise CloseError(f"falha ao inspecionar staging em {root}")
    _git(root, "commit", "-m", message)


def commit(message: str) -> None:
    prepare()
    _require_git_repo(DATA_ROOT, "data")
    _require_git_repo(CODE_ROOT, "engine")
    _commit_repo(DATA_ROOT, message)
    _commit_repo(CODE_ROOT, message)
    _git(DATA_ROOT, "rev-parse", "--short", "HEAD")
    _git(CODE_ROOT, "rev-parse", "--short", "HEAD")


def _require_clean(root: Path, label: str) -> None:
    proc = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        cwd=CODE_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode:
        raise CloseError(f"falha ao verificar status de {label}")
    if proc.stdout.strip():
        raise CloseError(f"{label} tem mudanças não commitadas; push recusado")


def push() -> None:
    _require_git_repo(DATA_ROOT, "data")
    _require_git_repo(CODE_ROOT, "engine")
    _require_clean(DATA_ROOT, "data")
    _require_clean(CODE_ROOT, "engine")

    failures: list[str] = []
    for label, root in (("data", DATA_ROOT), ("engine", CODE_ROOT)):
        proc = _git(root, "push", "origin", "HEAD", check=False)
        if proc.returncode:
            failures.append(label)
    if failures:
        raise CloseError("push falhou em: " + ", ".join(failures))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("prepare", help="valida, corrige mecanicamente, reconstrói e valida")
    commit_parser = sub.add_parser("commit", help="executa prepare e cria commits locais separados")
    commit_parser.add_argument("--message", required=True, help="mensagem usada nos commits locais")
    sub.add_parser("push", help="exige worktrees limpas e envia data e engine separadamente")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    command = args.command or "prepare"
    try:
        if command == "prepare":
            prepare()
        elif command == "commit":
            commit(args.message)
        elif command == "push":
            push()
        else:
            raise CloseError(f"ação desconhecida: {command}")
    except CloseError as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
