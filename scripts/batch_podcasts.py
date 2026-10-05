#!/usr/bin/env python3
"""
Executa a geração em lote de podcasts para uma lista ordenada de essays.

    python scripts/batch_podcasts.py               # gera a fila padrão (20 essays)
    python scripts/batch_podcasts.py slug1 slug2   # gera slugs específicos

Pula automaticamente os essays que já tiverem podcast gerado. Continua para o
próximo essay em caso de falha transitória individual.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import console_encoding  # noqa: F401
from repo_paths import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR / "lib"))
import podcast_common as pc  # isort: skip

DEFAULT_QUEUE = [
    # Already done or in-flight:
    "tags-como-ontologia-minima-categorias-rigidas-taxonomia-viva-e-a-filosofia-da-organizacao",
    "psicometria-o-que-os-testes-realmente-medem",
    "quem-e-voce-identidade-pessoal-como-continuidade-de-um-padrao",
    "ontologia-e-metafisica-da-existencia-de-deus-a-existencia-do-universo",
    "chatgpts-e-zumbis-filosoficos-uma-reflexao-sobre-consciencia-e-inteligencia-artificial",
    "autopoiese-consciencia-e-os-limites-do-vivo",
    # Ensaios de Engenharia selecionados pelo Usuário:
    "efeito-solo-em-superficies-aerodinamicas-asa-fixa-vs-rotativa",
    "modelos-de-inflow-para-rotores-da-teoria-de-quantidade-de-movimento-ao-inflow-dinamico",
    "metodos-matematicos-e-computacionais-na-engenharia-aeroespacial",
    "o-teorema-do-stagger-de-munk-e-sua-universalidade-em-sistemas-aerodinamicos-de-multiplas-superficies",
    "rotores-e-giroscopios-construcao-fisica-e-matematica-a-partir-das-leis-de-newton",
    "mente-aumentada-agentes-llm-second-brain-e-a-fronteira-da-cognicao",
    "xadrez-computacional-do-brute-force-as-redes-neurais",
    "etica-moralidade-e-as-barreiras-para-a-automacao-na-engenharia-aeronautica",
    "validacao-estocastica-de-dinamica-de-voo-de-hume-ao-p-value",
    # Filosofia, Consciência, Psicometria & Sociedade (não-engenharia):
    "epistemologia-e-os-limites-do-conhecimento-de-platao-a-mecanica-quantica",
    "monte-carlo-simular-e-instanciar-multiversos-computacionais-e-os-limites-do-real",
    "godel-turing-e-os-limites-da-computacao",
    "cerebros-de-boltzmann-epistemologia-e-o-limite-ontologico-da-fisica",
    "selecao-natural-em-sistemas-de-regras-da-evolucao-sem-biologia-aos-metas-competitivos-e-self-play",
    "neo-chauvinismo-da-cognicao-antropocentrica",
    "instanciar-e-simular-uma-investigacao-sobre-a-natureza-das-leis-naturais",
    "compatibilismo-o-livre-arbitrio-como-propriedade-de-um-sistema-natural",
    "rpg-de-mesa-e-a-teoria-da-informacao-entropia-narrativa-simulacao-cognitiva-e-a-linguagem-sem-limites",
    "a-fenomenologia-do-tabuleiro-teoria-dos-jogos-presenca-encarnada-e-a-renascenca-analogica",
    "ficcao-cientifica-como-incubadora-teorica-sci-fi-prototyping-monte-carlo-narrativo-e-a-imaginacao-hipotetica",
    "o-que-e-vida-um-ensaio-nas-fronteiras-da-existencia",
    "o-principio-antropico",
    "a-arquitetura-do-ilimitado-geometria-topologia-e-os-quatro-niveis-de-multiverso",
    "o-grande-filtro-do-antropocentrismo",
    "o-modelo-de-empresa-que-a-sociedade-merece",
    "lego-e-a-fisica-do-encaixe-tolerancias-micrometricas-grade-discreta-e-a-poetica-da-restricao",
    "ensaio-sobre-o-amor-porque-os-poetas-estavam-errados",
    "campeoes-por-acaso-por-que-atletas-de-elite-sao-anomalias-estatisticas",
    "modelagem-estatistica-para-a-copa-do-mundo-fifa-2026",
    "ia-na-gestao-de-projetos-aeronauticos",
]


def run_batch(slugs: list[str]) -> int:
    total = len(slugs)
    success = []
    skipped = []
    failed = []

    print(f"=== Iniciando lote de podcasts: {total} essays na fila ===")
    start_total = time.time()

    for idx, slug in enumerate(slugs, 1):
        if pc.source_for(slug):
            print(f"[{idx}/{total}] SKIP: '{slug}' já possui podcast gerado.")
            skipped.append(slug)
            continue

        print(f"\n[{idx}/{total}] ({datetime.now().strftime('%H:%M:%S')}) Iniciando: {slug}")
        t0 = time.time()

        cmd = [sys.executable, str(SCRIPTS_DIR / "notebooklm_podcast.py"), slug]
        proc = subprocess.run(cmd)

        elapsed_min = (time.time() - t0) / 60
        if proc.returncode == 0:
            print(f"[{idx}/{total}] SUCESSO: '{slug}' concluído em {elapsed_min:.1f} min.")
            success.append(slug)
        else:
            print(f"[{idx}/{total}] FALHA: '{slug}' saiu com código {proc.returncode} após {elapsed_min:.1f} min.", file=sys.stderr)
            failed.append(slug)

    total_min = (time.time() - start_total) / 60
    print("\n" + "=" * 60)
    print(f"Lote finalizado em {total_min:.1f} min.")
    print(f"  Sucessos : {len(success)}")
    print(f"  Pulados  : {len(skipped)}")
    print(f"  Falhas   : {len(failed)}")
    if failed:
        print("Essays com falha:")
        for f in failed:
            print(f"  - {f}")
    print("=" * 60)
    return 1 if failed and not success else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slugs", nargs="*", help="slugs a gerar (omita para usar a fila padrão de 20)")
    args = ap.parse_args()

    queue = args.slugs if args.slugs else DEFAULT_QUEUE
    return run_batch(queue)


if __name__ == "__main__":
    raise SystemExit(main())
