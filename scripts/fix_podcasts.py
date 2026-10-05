#!/usr/bin/env python3
"""
Renomeia podcasts de ``wiki/podcasts`` cujo nome não é o slug de um essay.

Só age em casamento inequívoco (nome normalizado igual ao slug, ao título ou a
um segmento do título; ou similaridade muito alta com margem sobre o segundo
candidato). Os ambíguos e órfãos são listados com candidatos e ficam intactos.

Default sem argumentos: renomear os inequívocos e relatar o resto.
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
