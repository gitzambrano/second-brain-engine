#!/usr/bin/env python3
"""Publica o Atlas com um único comando: validar, construir, selar e enviar.

Uso:
    python scripts/publish_site.py

O comando não altera o corpus: ele exige os três repositórios limpos e
sincronizados. O selo executa os gates de privacidade, orçamento e navegador
uma única vez; depois disso, este script publica o artefato.

Histórico raso do site: cada publicação reescreve `main` para exatamente dois
commits — um commit órfão com a árvore do HEAD anterior e, por cima, o commit
da nova publicação. Assim o repositório público não acumula binários antigos
(os podcasts). O workflow da newsletter compara
`.github/newsletter-manifest.json` com `HEAD^`; o commit órfão carrega o
manifesto anterior, então a comparação continua válida. Como o remoto é
reescrito a cada vez, o site nunca faz `pull --rebase`: antes do build o
checkout local é alinhado a `origin/main` (o site é projeção gerada, não tem
trabalho próprio a preservar).
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
    sync_site_checkout(SITE_ROOT)


def sync_site_checkout(site: Path, remote: str = "origin", branch: str = "main") -> bool:
    """Alinha o checkout do site ao remoto, que é reescrito a cada publicação.

    Compara árvores, não histórico: as contagens ahead/behind perdem o sentido
    quando `main` é reescrita. Árvores iguais não exigem nada; diferentes,
    o checkout vira `origin/main` (o build o regenera por inteiro em seguida).
    Devolve True quando houve reset.
    """
    run("git", "fetch", remote, "--prune", cwd=site)
    remote_ref = f"{remote}/{branch}"
    remote_tree = git_output("rev-parse", f"{remote_ref}^{{tree}}", cwd=site)
    local_tree = git_output("rev-parse", "HEAD^{tree}", cwd=site)
    if local_tree == remote_tree:
        return False
    print("site: checkout local difere de origin/main; alinhando (o site é regenerado pelo build)...")
    run("git", "reset", "--hard", remote_ref, cwd=site)
    return True


def rewrite_history(site: Path, message: str, remote: str = "origin", branch: str = "main") -> str:
    """Publica com histórico de dois commits e devolve o SHA da publicação.

    1. commit órfão (sem pai) com a árvore do HEAD atual;
    2. commit da publicação por cima dele, com a árvore do working tree;
    3. `main` aponta para o novo commit; push forçado com lease explícito sobre
       o SHA que o remoto tinha na última busca;
    4. reflog expirado e `gc --prune=now`, para o binário antigo sair do disco.
    """
    old_remote = git_output("rev-parse", f"{remote}/{branch}", cwd=site)
    old_tree = git_output("rev-parse", "HEAD^{tree}", cwd=site)
    base = git_output("commit-tree", old_tree, "-m", "Publicação anterior", cwd=site)
    run("git", "add", "-A", cwd=site)
    new_tree = git_output("write-tree", cwd=site)
    head = git_output("commit-tree", new_tree, "-p", base, "-m", message, cwd=site)
    run("git", "update-ref", f"refs/heads/{branch}", head, cwd=site)
    run("git", "push", f"--force-with-lease={branch}:{old_remote}", remote, branch, cwd=site)
    run("git", "reflog", "expire", "--expire=now", "--all", cwd=site)
    run("git", "gc", "--prune=now", "--quiet", cwd=site)
    return head


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

    head = rewrite_history(SITE_ROOT, publication_message())
    print(f"site: publicado ({head[:10]}, histórico de 2 commits)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode) from exc
