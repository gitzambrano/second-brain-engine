#!/usr/bin/env python3
"""migrate_private_data.py - Copia e confere dados pessoais legados para data/ antes de apagar.

Utilitário de migração da estrutura monolítica legada para a arquitetura de 3 repositórios:
- Origens legadas: ./wiki ./plan ./raw ./output ./.obsidian
- Destino: ./data/<mesmo caminho relativo>
- Valida integridade byte a byte via hashes SHA-256 antes de qualquer exclusão.

Escopo:
    Utilitário de migração estrutural. Sem argumentos executa inventário consultivo.
    Nunca toca em ./data/.git e nunca escreve no repositório público do engine.

Entradas (Inputs):
    Diretórios legados na raiz do engine.
    Argumentos CLI opcionais:
        --copy        Copia arquivos sem apagar a origem
        --verify      Confere cada arquivo de origem com o destino por SHA-256
        --finalize    Confere por hash e apaga os diretórios legados na raiz do engine

Saídas (Outputs):
    Stdout: Log de arquivos migrados, conferidos ou excluídos.
    Exit code: 0 em sucesso, 1 em falha de cópia ou divergência de hash.

Uso:
    python scripts/migrate_private_data.py            # inventário de migração
    python scripts/migrate_private_data.py --copy     # copia para data/
    python scripts/migrate_private_data.py --verify   # valida integridade por hash
    python scripts/migrate_private_data.py --finalize # limpa diretórios antigos após validação
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

from repo_paths import CODE_ROOT, DATA_ROOT

LEGACY = ("wiki", "plan", "raw", "output", ".obsidian")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def files_under(root: Path):
    if not root.exists():
        return []
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and ".git" not in p.parts
    )


def inventory():
    rows = []
    for name in LEGACY:
        root = CODE_ROOT / name
        fs = files_under(root)
        rows.append((name, len(fs), sum(p.stat().st_size for p in fs)))
    return rows


def copy_all():
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    for name in LEGACY:
        src, dst = CODE_ROOT / name, DATA_ROOT / name
        if not src.exists():
            continue
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True, copy_function=shutil.copy2)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)


def verify():
    problems = []
    checked = 0
    for name in LEGACY:
        srcroot, dstroot = CODE_ROOT / name, DATA_ROOT / name
        for src in files_under(srcroot):
            rel = src.relative_to(srcroot)
            dst = dstroot / rel
            checked += 1
            if not dst.exists():
                problems.append(f"MISSING {name}/{rel}")
            elif src.stat().st_size != dst.stat().st_size:
                problems.append(f"SIZE {name}/{rel}")
            elif digest(src) != digest(dst):
                problems.append(f"SHA256 {name}/{rel}")
    return checked, problems


def finalize():
    checked, problems = verify()
    if problems:
        raise SystemExit(
            "verification failed; nothing deleted:\n" + "\n".join(problems[:100])
        )
    for name in LEGACY:
        src = CODE_ROOT / name
        if src.is_dir():
            shutil.rmtree(src)
        elif src.exists():
            src.unlink()
    print(f"verified {checked} file(s); legacy engine data removed")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--copy", action="store_true")
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--finalize", action="store_true")
    args = ap.parse_args()

    if not any((args.copy, args.verify, args.finalize)):
        print("legacy private-data inventory:")
        for name, count, size in inventory():
            print(f"  {name:10s} files={count:5d} bytes={size}")
        print("no changes made")
        return 0

    if args.copy:
        copy_all()
        print("copy complete; run --verify before any deletion")
    if args.verify:
        checked, problems = verify()
        if problems:
            print("verification: FAIL")
            for problem in problems[:100]:
                print(" ", problem)
            return 1
        print(f"verification: PASS ({checked} file(s))")
    if args.finalize:
        finalize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
