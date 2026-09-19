import sys
import re
from pathlib import Path
import subprocess

# 1. Checagem de duplicação de texto nos arquivos alterados
MODIFIED_WIKI = [
    "quando-a-distancia-colapsou-por-que-a-aviacao-importa.md",
    "a-historia-da-aviacao-como-um-jogo-estrategico.md",
    "por-que-um-rotor-nao-e-um-giroscopio.md",
    "o-espaco-de-todos-os-avioes-possiveis.md",
    "aplicacao-de-modelos-de-ia-generativa-em-dinamica-de-voo-de-aeronaves.md",
    "xadrez-computacional-do-brute-force-as-redes-neurais.md",
    "validacao-estocastica-de-dinamica-de-voo-de-hume-ao-p-value.md",
]

MODIFIED_SUBSTACK = [
    "voar-e-reduzir-incerteza-a-aeronave-como-maquina-de-informacao.md",
    "a-fisica-do-que-um-modelo-decide-esquecer-informacao-aproximacao-e-os-limites-da-simulacao.md",
    "singularidade-tecnologica-a-derivada-que-engana-toda-geracao.md",
    "xadrez-computacional-do-brute-force-as-redes-neurais.md",
    "lego-e-a-fisica-do-encaixe-tolerancias-micrometricas-grade-discreta-e-a-poetica-da-restricao.md",
    "cerebros-de-boltzmann-epistemologia-e-o-limite-ontologico-da-fisica.md",
]

def check_duplicate_paragraphs(filepath: Path):
    text = filepath.read_text(encoding="utf-8")
    # Ignora frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            text = parts[2]

    # Divide em blocos separados por linhas em branco
    blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
    seen = {}
    dups = []
    for i, b in enumerate(blocks):
        # Ignora delimitadores curtos, títulos, cabeçalhos de tabela
        if len(b) < 40 or b.startswith("#") or b.startswith("|") or b.startswith("---") or b.startswith("```"):
            continue
        # Normaliza espaços
        norm = " ".join(b.split()).lower()
        if norm in seen:
            dups.append((seen[norm] + 1, i + 1, b[:80]))
        else:
            seen[norm] = i

    # Checagem de sentenças consecutivas duplicadas dentro de parágrafos
    sentences = re.split(r"(?<=[.!?])\s+", text)
    sent_dups = []
    for i in range(len(sentences) - 1):
        s1 = sentences[i].strip()
        s2 = sentences[i+1].strip()
        if len(s1) > 30 and s1.lower() == s2.lower():
            sent_dups.append(s1[:80])

    return dups, sent_dups

print("="*60)
print("AUDITORIA DE DUPLICAÇÃO DE TEXTO")
print("="*60)

total_dups = 0
for fname in MODIFIED_WIKI:
    p = Path("data/wiki/essays") / fname
    dups, sent_dups = check_duplicate_paragraphs(p)
    if dups or sent_dups:
        print(f"[DUPLICATA] Wiki: {fname}")
        for orig, dup, sample in dups:
            print(f"   Parágrafo bloco {orig} duplicado no bloco {dup}: '{sample}...'")
        for s in sent_dups:
            print(f"   Sentença consecutiva idêntica: '{s}...'")
        total_dups += len(dups) + len(sent_dups)
    else:
        print(f"[OK] Wiki: {fname} (zero duplicatas)")

for fname in MODIFIED_SUBSTACK:
    p = Path("substack/posts") / fname
    dups, sent_dups = check_duplicate_paragraphs(p)
    if dups or sent_dups:
        print(f"[DUPLICATA] Substack: {fname}")
        for orig, dup, sample in dups:
            print(f"   Parágrafo bloco {orig} duplicado no bloco {dup}: '{sample}...'")
        for s in sent_dups:
            print(f"   Sentença consecutiva idêntica: '{s}...'")
        total_dups += len(dups) + len(sent_dups)
    else:
        print(f"[OK] Substack: {fname} (zero duplicatas)")

print(f"\nTotal de duplicações encontradas: {total_dups}")
