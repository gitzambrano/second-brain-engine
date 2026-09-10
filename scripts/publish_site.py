#!/usr/bin/env python3
"""Publica o Atlas com um único comando: validar, construir, selar e enviar.

Uso:
    python scripts/publish_site.py

O comando não altera o corpus: ele exige os três repositórios limpos e
sincronizados. O selo executa os gates de privacidade, orçamento e navegador
uma única vez; depois disso, este script cria e envia o commit do artefato
público.
"""
from __future__ import annotations

import subprocess
import sys
from datetime import date
from pathlib import Path

from repo_paths import CODE_ROOT, DATA_ROOT, SCRIPTS_DIR, SITE_ROOT


def run(*command: str, cwd: Path = CODE_ROOT) -> None:
    """Executa uma etapa visível e interrompe a publicação em caso de falha."""
    print("+", " ".join(command))
    subprocess.run(command, cwd=cwd, check=True)


def git_output(*command: str, cwd: Path) -> str:
    proc = subprocess.run(
        ("git", *command),
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.stdout.strip()


def repositories_ready() -> None:
    """Recusa publicar a partir de árvores sujas ou diferentes da nuvem."""
    repositories = (("engine", CODE_ROOT), ("data", DATA_ROOT), ("site", SITE_ROOT))
    for label, root in repositories:
        if not root.is_dir():
            raise SystemExit(f"{label}: repositório ausente em {root}")
        if git_output("status", "--porcelain", cwd=root):
            raise SystemExit(f"{label}: há mudanças locais; faça commit ou descarte-as antes de publicar")
        run("git", "fetch", "origin", "--prune", cwd=root)
        counts = git_output("rev-list", "--left-right", "--count", "main...origin/main", cwd=root)
        ahead, behind = (int(part) for part in counts.split())
        if ahead or behind:
            raise SystemExit(
                f"{label}: main local e origin/main divergem (ahead={ahead}, behind={behind}); sincronize antes de publicar"
            )


def site_has_changes() -> bool:
    return bool(git_output("status", "--porcelain", cwd=SITE_ROOT))


def publication_message() -> str:
    return f"Publicação do site: {date.today():%Y-%m-%d}"


def main(argv: list[str] | None = None) -> int:
    if argv:
        raise SystemExit("publish_site.py não aceita argumentos; execute-o sem flags")

    repositories_ready()
    run(sys.executable, str(SCRIPTS_DIR / "check_visibility_field.py"))
    run(sys.executable, str(SCRIPTS_DIR / "build_site.py"))
    # O selo chama privacidade, orçamento e QA de navegador uma única vez.
    run(sys.executable, str(SCRIPTS_DIR / "seal_publication.py"))

    if not site_has_changes():
        print("site: nada a publicar")
        return 0

    run("git", "add", ".", cwd=SITE_ROOT)
    run("git", "commit", "-m", publication_message(), cwd=SITE_ROOT)
    run("git", "push", "origin", "main", cwd=SITE_ROOT)
    print("site: publicado")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
