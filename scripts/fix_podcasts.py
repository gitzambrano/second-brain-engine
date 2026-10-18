#!/usr/bin/env python3
"""fix_podcasts.py - Renomeia arquivos de áudio em wiki/podcasts cujo nome não seja o slug do essay.

Analisa arquivos de áudio em DATA_ROOT/wiki/podcasts/ e aplica renomeações determinísticas:
- Identifica casamentos inequívocos por título normalizado ou correspondência de alta confiança.
- Lista arquivos ambíguos ou órfãos sem modificá-los, solicitando resolução do mantenedor.

Escopo:
    Mutador seguro em DATA_ROOT/wiki/podcasts/.
    Padrão sem argumentos renomeia casos inequívocos e relata pendências.

Entradas (Inputs):
    Arquivos em DATA_ROOT/wiki/podcasts/ e catálogo de essays em wiki/essays/*.md.
    Argumentos CLI opcionais:
        --dry-run    Apenas exibe os planos de renomeação sem tocar nos arquivos

Saídas (Outputs):
    Stdout: Lista de renomeações executadas ou pendentes.
    Sistema de arquivos: Arquivos renomeados para <slug>.m4a / <slug>.mp3.
    Exit code: 0 em sucesso.

Uso:
    python scripts/fix_podcasts.py                # renomeia inequívocos automaticamente
    python scripts/fix_podcasts.py --dry-run      # visualiza renomeações planejadas
"""
from __future__ import annotations

import argparse

import console_encoding  # noqa: F401  (UTF-8 no console; ver o módulo)
import repo_paths  # noqa: F401  (põe lib/ no sys.path)

import podcast_common as pc  # isort: skip


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="mostrar sem renomear")
    args = ap.parse_args()
    plans = pc.plan_renames()
    if not plans:
        print("nenhum podcast em wiki/podcasts")
        return 0
    pending = 0
    for plan in plans:
        if plan.status == "ok":
            print(f"ok          {plan.path.name}")
        elif plan.status == "rename":
            print(f"renomeia    {plan.path.name} -> {plan.target.name}")
        else:
            pending += 1
            print(f"{plan.status:<11} {plan.path.name}")
            for score, essay in plan.ranking[:3]:
                print(f"              {score:.2f}  {essay.slug}")
    if not args.dry_run:
        skipped = pc.apply_renames(plans)
        pending += len(skipped)
    return 2 if pending else 0


if __name__ == "__main__":
    raise SystemExit(main())
