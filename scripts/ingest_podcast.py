#!/usr/bin/env python3
"""
Ingere um podcast (mp3/m4a) na wiki: valida, casa com o essay e arquiva.

    python scripts/ingest_podcast.py arquivo.m4a [essay]

O destino é ``DATA_ROOT/wiki/podcasts/<slug>.<ext>``. ``essay`` pode ser o slug,
o título ou qualquer trecho dele; sem ``essay`` o nome do arquivo é casado com os
slugs e títulos. Só age quando o casamento é inequívoco: com ambiguidade lista
os candidatos e sai com código 2, sem tocar em nada.

Default sem argumentos: validar os podcasts já em ``wiki/podcasts`` e renomear os
de nome inequívoco (o mesmo que ``fix_podcasts.py``), mostrando o que sobra.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import console_encoding  # noqa: F401  (UTF-8 no console; ver o módulo)
from repo_paths import PODCASTS_DIR

import podcast_common as pc  # isort: skip

EXIT_AMBIGUOUS = 2


def resolve_slug(query: str, essays: dict, explicit: bool = False):
    """``(slug | None, ranking)``: slug exato, ou o único casamento de alta confiança."""
    match, ranking = pc.resolve_essay(query, essays, min_substring=5 if explicit else 15)
    return (match.slug if match else None), ranking


def ingest(path: Path, essay: str | None = None, copy: bool = False,
           force: bool = False, dry_run: bool = False) -> tuple[int, str]:
    """Valida e arquiva. Devolve ``(código de saída, mensagem)``."""
    path = Path(path)
    if not path.is_file():
        return 1, f"arquivo não encontrado: {path}"
    if not pc.find_ffmpeg():
        return 1, "ffmpeg indisponível; não é possível validar o áudio"
    errors = [f for f in pc.integrity_findings(path) if f.severity == "ERROR"]
    if errors:
        return 1, "áudio inválido: " + "; ".join(f"{f.code}: {f.message}" for f in errors)

    essays = pc.load_essays()
    if not essays:
        return 1, "nenhum essay encontrado"
    slug, ranking = resolve_slug(essay or path.stem, essays, explicit=bool(essay))
    if slug is None:
        lines = [f"  {score:.2f}  {e.slug}  ({e.title})" for score, e in ranking]
        return EXIT_AMBIGUOUS, ("casamento ambíguo; informe o essay explicitamente. Candidatos:\n"
                                + "\n".join(lines))

    dest = PODCASTS_DIR / f"{slug}{path.suffix.lower()}"
    if path.resolve() == dest.resolve():
        return 0, f"já arquivado: {dest.name}"
    other = pc.source_for(slug)
    if (dest.exists() or other) and not force:
        return 1, f"já existe podcast para '{slug}' ({(other or dest).name}); use --force para substituir"
    if dry_run:
        return 0, f"(dry-run) {path.name} -> {dest.relative_to(PODCASTS_DIR.parent.parent)} [{essays[slug].visibility}]"
    PODCASTS_DIR.mkdir(parents=True, exist_ok=True)
    if other and other != dest:
        other.unlink()
    (shutil.copy2 if copy else shutil.move)(str(path), str(dest))
    note = "" if essays[slug].public else f" (essay {essays[slug].visibility}: não será publicado)"
    return 0, f"{path.name} -> wiki/podcasts/{dest.name}{note}"


def fix_in_place(dry_run: bool = False) -> int:
    plans = pc.plan_renames()
    if not plans:
        print("nenhum podcast em wiki/podcasts")
        return 0
    status = 0
    for plan in plans:
        if plan.status == "ok":
            print(f"ok         {plan.path.name}")
        elif plan.status == "rename":
            print(f"renomear   {plan.path.name} -> {plan.target.name}")
        else:
            status = EXIT_AMBIGUOUS
            print(f"{plan.status:<10} {plan.path.name}")
            for score, e in plan.ranking[:3]:
                print(f"             {score:.2f}  {e.slug}")
    if not dry_run:
        pc.apply_renames(plans)
    return status


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("file", nargs="?", help="mp3/m4a a ingerir; omita para corrigir wiki/podcasts")
    ap.add_argument("essay", nargs="?", help="slug ou título do essay (opcional)")
    ap.add_argument("--copy", action="store_true", help="copiar em vez de mover")
    ap.add_argument("--force", action="store_true", help="substituir um podcast existente")
    ap.add_argument("--dry-run", action="store_true", help="mostrar sem alterar")
    args = ap.parse_args()
    if not args.file:
        return fix_in_place(args.dry_run)
    code, message = ingest(Path(args.file), args.essay, args.copy, args.force, args.dry_run)
    print(message, file=sys.stderr if code else sys.stdout)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
