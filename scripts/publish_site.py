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
    """Garante que os três repositórios estejam prontos e sincronizados para publicação.

    Salva automaticamente qualquer mudança pendente em engine e data antes de
    compilar o site, e sincroniza os commits com o GitHub. Não bloqueia por
    alterações prévias em site, pois o build irá regenerá-lo.
    """
    for label, root in (("engine", CODE_ROOT), ("data", DATA_ROOT)):
        if not root.is_dir():
            raise SystemExit(f"{label}: repositório ausente em {root}")
        if git_output("status", "--porcelain", cwd=root):
            print(f"{label}: salvando alterações locais automaticamente...")
            run("git", "add", ".", cwd=root)
            run(
                "git",
                "commit",
                "-m",
                f"{label}: atualização automática antes da publicação ({date.today():%Y-%m-%d})",
                cwd=root,
            )
        run("git", "fetch", "origin", "--prune", cwd=root)
        counts = git_output("rev-list", "--left-right", "--count", "main...origin/main", cwd=root)
        ahead, behind = (int(part) for part in counts.split())
        if behind > 0:
            print(f"{label}: atualizando {behind} commit(s) da nuvem...")
            run("git", "pull", "--rebase", "origin", "main", cwd=root)
        if ahead > 0:
            print(f"{label}: enviando {ahead} commit(s) para o GitHub...")
            run("git", "push", "origin", "main", cwd=root)

    if not SITE_ROOT.is_dir():
        raise SystemExit(f"site: repositório ausente em {SITE_ROOT}")
    run("git", "fetch", "origin", "--prune", cwd=SITE_ROOT)
    counts = git_output("rev-list", "--left-right", "--count", "main...origin/main", cwd=SITE_ROOT)
    ahead, behind = (int(part) for part in counts.split())
    if behind > 0:
        print(f"site: atualizando {behind} commit(s) da nuvem...")
        run("git", "pull", "--rebase", "origin", "main", cwd=SITE_ROOT)


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
