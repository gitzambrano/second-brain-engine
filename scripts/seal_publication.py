#!/usr/bin/env python3
"""seal_publication.py - Sela uma publicação pública: executa gates e grava o manifesto de integridade.

Garante que o artefato publicado em site/ traga a prova criptográfica de ter passado
por todos os gates obrigatórios de qualidade antes do deploy no GitHub Pages:
1. Executa os gates: privacy, budget e browser page check.
2. Calcula o hash SHA-256 consolidado de todos os bytes servidos (artifact_digest).
3. Registra o commit correspondente do engine e gera SITE_ROOT/site-manifest.json.

Escopo:
    Portão de integridade e selagem do repositório site/. Altera apenas o site-manifest.json.
    Qualquer modificação subsequente em site/ invalida o selo gerado.

Entradas (Inputs):
    Arquivos em SITE_ROOT e commit corrente em CODE_ROOT.
    Argumentos CLI opcionais:
        --allow-skip-browser    Permite pular teste de navegador em ambiente restrito
        --json                  Emite resultado da selagem em JSON

Saídas (Outputs):
    Gravação de SITE_ROOT/site-manifest.json contendo commit, digest e lista de gates aprovados.
    Stdout: Resumo com hash do artefato selado.
    Exit code: 0 em sucesso na selagem, 1 em falha de qualquer gate obrigatório.

Uso:
    python scripts/seal_publication.py                      # selagem padrão completa
    python scripts/seal_publication.py --allow-skip-browser  # selagem sem checagem de browser
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
