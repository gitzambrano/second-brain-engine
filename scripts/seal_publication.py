#!/usr/bin/env python3
"""
Sela uma publicação: roda os gates obrigatórios e carimba o resultado no
artefato.

O buraco que isto fecha: o repositório `site/` publicava qualquer coisa que
chegasse na branch. Um push manual, um merge errado ou um build feito numa
máquina com o engine vermelho iam ao ar pelo mesmo caminho de uma publicação
legítima — o deploy do site podia ficar verde enquanto a CI do engine estava
vermelha, porque as duas nunca se olhavam.

Um repositório não consegue verificar a CI do outro sem credencial. O que ele
consegue é exigir que o artefato traga consigo a prova de ter passado pelos
gates, e que essa prova cubra exatamente os bytes presentes. É isso que o selo
é:

    gates            quais checagens passaram, nominalmente
    artifact_digest  impressão do conteúdo publicado no momento do selo
    engine_commit    de qual commit do engine ele saiu

`check_artifact.py`, do lado do site, recalcula o digest e recusa o deploy se
ele não bater. Isso torna inútil selar e editar depois: qualquer byte alterado
em qualquer arquivo publicado invalida o selo. E torna impossível publicar sem
selar, porque a ausência do campo também reprova.

O selo NÃO é assinatura criptográfica: quem tem acesso de escrita ao engine
pode gerar um. Ele não existe para impedir um adversário, e sim para impedir o
acidente — publicar um artefato que ninguém validou.

Default sem argumentos: rodar os gates sobre SITE_ROOT e selar.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import build_newsletter_manifest
import console_encoding  # noqa: F401  (UTF-8 no console; ver o módulo)
from repo_paths import CODE_ROOT, SCRIPTS_DIR, SITE_ROOT

MANIFEST = "site-manifest.json"
NEWSLETTER_MANIFEST = ".github/newsletter-manifest.json"

# O que existe no checkout e NÃO vai ao ar. O digest tem de cobrir exatamente o
# conjunto que o workflow empacota em `_site/`: selar sobre o repositório e
# conferir sobre o artefato compararia listas diferentes de arquivos, e o selo
# reprovaria toda publicação legítima.
FORA_DO_ARTEFATO = {".git", ".github"}
FORA_DA_RAIZ = {"README.md", ".gitignore", ".second-brain-site", MANIFEST}


def _fora_do_artefato(path: Path, root: Path) -> bool:
    if FORA_DO_ARTEFATO & set(path.parts):
        return True
    return path.parent == root and path.name in FORA_DA_RAIZ

REQUIRED_GATES = (
    ("privacy", ["check_site_privacy.py"]),
    ("budget", ["check_site_budget.py"]),
    ("pages", ["check_site_pages.py"]),
)

TEXT_SUFFIXES = {".html", ".json", ".js", ".css", ".txt", ".md", ".xml", ".svg"}


def artifact_digest(root: Path) -> str:
    """Impressão determinística do conteúdo publicado, menos o próprio manifesto.

    O manifesto fica de fora porque é onde o selo é gravado: incluí-lo faria o
    digest depender de si mesmo. Tudo em `.github/`, inclusive o manifesto da
    newsletter, também fica fora porque nunca entra no artefato Pages.
    """
    h = hashlib.sha256()
    arquivos = sorted(
        (p for p in root.rglob("*")
         if p.is_file() and not _fora_do_artefato(p, root)),
        key=lambda p: p.relative_to(root).as_posix(),
    )
    for path in arquivos:
        dados = path.read_bytes()
        if path.suffix.lower() in TEXT_SUFFIXES:
            dados = dados.replace(b"\r\n", b"\n")
        h.update(path.relative_to(root).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256(dados).digest())
    return h.hexdigest()


def engine_commit() -> dict:
    """SHA do engine e se a árvore estava suja quando o artefato foi selado."""
    def git(*args) -> str | None:
        try:
            out = subprocess.run(["git", "-C", str(CODE_ROOT), *args],
                                 capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            return None
        return out.stdout.strip() if out.returncode == 0 else None

    sha = git("rev-parse", "HEAD")
    sujo = git("status", "--porcelain")
    return {"sha": sha, "dirty": bool(sujo) if sujo is not None else None}


def run_gates(verbose: bool = True) -> tuple[list[str], list[str]]:
    """Roda os gates obrigatórios. Retorna (passaram, falharam)."""
    passaram, falharam = [], []
    for nome, comando in REQUIRED_GATES:
        script = SCRIPTS_DIR / comando[0]
        if not script.is_file():
            falharam.append(f"{nome}: {comando[0]} não existe")
            continue
        if verbose:
            print(f"  gate {nome}: {comando[0]}…")
        proc = subprocess.run(
            [sys.executable, str(script), *comando[1:]],
            cwd=CODE_ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode == 0:
            passaram.append(nome)
        else:
            cauda = (proc.stdout + proc.stderr).strip().splitlines()[-3:]
            falharam.append(f"{nome}: " + " | ".join(cauda))
    return passaram, falharam


def seal(root: Path, verbose: bool = True) -> int:
    manifesto = root / MANIFEST
    if not manifesto.is_file():
        print(f"FALHA: {MANIFEST} não existe em {root}; rode o build antes de selar")
        return 1

    newsletter = build_newsletter_manifest.build(root / NEWSLETTER_MANIFEST)
    if verbose:
        print(f"  newsletter: {newsletter}")

    passaram, falharam = run_gates(verbose)
    if falharam:
        print(f"FALHA: {len(falharam)} gate(s) não passaram; nada foi selado")
        for item in falharam:
            print(f"  - {item}")
        return 1

    dados = json.loads(manifesto.read_text(encoding="utf-8"))
    dados["seal"] = {
        "gates": passaram,
        "engine": engine_commit(),
        "sealed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "artifact_digest": artifact_digest(root),
    }
    manifesto.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"SELADO: {', '.join(passaram)} | digest {dados['seal']['artifact_digest'][:16]}…")
    if dados["seal"]["engine"]["dirty"]:
        print("  aviso: o engine tinha mudanças não commitadas no momento do selo")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("root", nargs="?", default=None,
                    help="diretório a selar (default: SITE_ROOT)")
    ap.add_argument("--digest-only", action="store_true",
                    help="só imprime o digest do artefato, sem rodar gate nem gravar")
    args = ap.parse_args()
    root = Path(args.root) if args.root else SITE_ROOT
    if args.digest_only:
        print(artifact_digest(root))
        return 0
    return seal(root)


if __name__ == "__main__":
    raise SystemExit(main())
