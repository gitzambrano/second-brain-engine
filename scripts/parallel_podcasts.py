#!/usr/bin/env python3
"""
Executa a geração de podcasts em paralelo usando as contas disponíveis no NotebookLM.

Cada conta ativa executa em uma thread/worker independente com seu próprio perfil do
Chrome headless, processando múltiplos essays simultaneamente a partir de uma fila compartilhada.

    python scripts/parallel_podcasts.py               # processa a fila padrão
    python scripts/parallel_podcasts.py slug1 slug2   # processa slugs específicos
"""
from __future__ import annotations

import argparse
import queue
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import console_encoding  # noqa: F401
from repo_paths import LOCAL_DIR, SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))
import notebooklm_podcast as nlp  # isort: skip
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
    "dinamica-analitica-e-acoplamento-fisico-do-modo-dutch-roll",
    "dinamica-de-voo-de-um-rotor-teetering-controlado-por-rpm",
    "efeito-da-solidez-sobre-os-parametros-aerodinamicos-fundamentais-de-um-rotor-a-tracao-constante",
    "engenharia-em-menos-de-um-metro-cubico-a-impressora-3d-como-microcosmo-de-um-projeto-de-aeronave",
    "equacoes-analiticas-para-os-coeficientes-aerodinamicos-de-um-rotor-rigido",
    "forca-lateral-de-um-rotor-em-voo-a-frente-inflow-uniforme-e-coleman",
    "micro-hardwares-e-a-democratizacao-maker-da-queda-das-barreiras-tecnicas-ao-desafio-da-curadoria",
    "modelagem-teorica-do-efeito-solo-em-multirrotores",
    "parametros-adimensionais-que-governam-a-geometria-e-a-esteira-de-rotores",
]

print_lock = threading.Lock()


def safe_print(*args, **kwargs):
    with print_lock:
        print(*args, **kwargs)
        sys.stdout.flush()


def get_active_accounts(profiles_dir: Path) -> list[str]:
    state = nlp.load_state()
    all_acc = nlp.list_accounts(profiles_dir)
    active = []
    for acc in all_acc:
        st = state.get("accounts", {}).get(acc, {}).get("last_status")
        if st == "deslogada":
            continue
        if nlp.in_cooldown(state, acc):
            continue
        active.append(acc)
    return active


def worker_loop(account: str, q: queue.Queue[str], results: dict[str, list[str]]):
    while True:
        try:
            slug = q.get_nowait()
        except queue.Empty:
            break

        if pc.source_for(slug):
            safe_print(f"[{account}] SKIP: '{slug}' já possui podcast gerado.")
            results["skipped"].append(slug)
            q.task_done()
            continue

        now_str = datetime.now().strftime("%H:%M:%S")
        safe_print(f"[{account}] ({now_str}) Iniciando: {slug}")
        t0 = time.time()

        cmd = [sys.executable, str(SCRIPTS_DIR / "notebooklm_podcast.py"), slug, "--account", account]
        proc = subprocess.run(cmd)

        elapsed = (time.time() - t0) / 60
        if proc.returncode == 0:
            safe_print(f"[{account}] SUCESSO: '{slug}' concluído em {elapsed:.1f} min.")
            results["success"].append(slug)
        else:
            safe_print(f"[{account}] FALHA ({proc.returncode}): '{slug}' após {elapsed:.1f} min.", file=sys.stderr)
            state = nlp.load_state()
            if nlp.in_cooldown(state, account):
                safe_print(f"[{account}] Conta em cooldown/cota. Encerrando worker e devolvendo '{slug}' à fila.")
                q.put(slug)
                q.task_done()
                break
            results["failed"].append(slug)

        q.task_done()


def run_parallel(slugs: list[str]) -> int:
    profiles_dir = nlp.resolve_profiles_dir(None)
    accounts = get_active_accounts(profiles_dir)
    if not accounts:
        safe_print("Nenhuma conta disponível para execução paralela.", file=sys.stderr)
        return 1

    total = len(slugs)
    safe_print(f"=== Iniciando geração paralela: {total} essays com {len(accounts)} contas ({', '.join(accounts)}) ===")
    start_total = time.time()

    q: queue.Queue[str] = queue.Queue()
    for s in slugs:
        q.put(s)

    results: dict[str, list[str]] = {"success": [], "skipped": [], "failed": []}
    threads: list[threading.Thread] = []

    for acc in accounts:
        t = threading.Thread(target=worker_loop, args=(acc, q, results), name=f"Worker-{acc}", daemon=True)
        t.start()
        threads.append(t)
        # Espaçamento de 3 segundos na inicialização para não bater no Playwright simultâneo no exato mesmo milissegundo
        time.sleep(3)

    for t in threads:
        t.join()

    total_min = (time.time() - start_total) / 60
    safe_print("\n" + "=" * 60)
    safe_print(f"Lote paralelo finalizado em {total_min:.1f} min.")
    safe_print(f"  Sucessos : {len(results['success'])}")
    safe_print(f"  Pulados  : {len(results['skipped'])}")
    safe_print(f"  Falhas   : {len(results['failed'])}")
    if results["failed"]:
        safe_print("Essays com falha:")
        for f in results["failed"]:
            safe_print(f"  - {f}")
    safe_print("=" * 60)
    return 1 if results["failed"] and not results["success"] else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slugs", nargs="*", help="slugs a gerar (omita para usar a fila padrão de 20)")
    args = ap.parse_args()

    queue_slugs = args.slugs if args.slugs else DEFAULT_QUEUE
    return run_parallel(queue_slugs)


if __name__ == "__main__":
    raise SystemExit(main())
