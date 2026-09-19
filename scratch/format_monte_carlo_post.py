import re
from pathlib import Path

path = Path("substack/posts/monte-carlo-simular-e-instanciar-multiversos-computacionais-e-os-limites-do-real.md")
text = path.read_text(encoding="utf-8")

HERO_URL = "https://substack-post-media.s3.amazonaws.com/public/images/6bdbddc3-5c48-469b-beb8-37afe59062c0_1920x1080.png"
CARD_URL = "https://substack-post-media.s3.amazonaws.com/public/images/a82097a8-17bd-4ab6-8add-6a13461ab1cb_2160x1360.png"

# 1. Frontmatter
text = re.sub(
    r"^---[\s\S]*?---\s*",
    f"""---
title: "Monte Carlo, Simular e Instanciar — Multiversos Computacionais e os Limites do Real"
subtitle: "O método de Monte Carlo calcula milhares de futuros possíveis para descartar quase todos: simular um estado computacional equivale a instanciar uma realidade?"
seo_title: "Monte Carlo, Simular e Instanciar: Limites do Real"
seo_description: "O que acontece ontologicamente com os futuros descartados em simulações de Monte Carlo? Do multiverso de Everett ao universo matemático de Tegmark."
source_essay: "monte-carlo-simular-e-instanciar-multiversos-computacionais-e-os-limites-do-real.md"
tags: [Computação, Filosofia-da-Física, Teoria-da-Informação, Metafísica]
cover_image: "{HERO_URL}"
---

> Ensaio
> Gustavo Zambrano · Agosto de 2026

> “O método de Monte Carlo é uma máquina de fabricar futuros descartáveis: para cada trajetória que decidimos chamar de real, centenas de milhares de outros mundos foram computados até o fim e evaporaram silenciosamente na memória RAM.”

![Monte Carlo, Simular e Instanciar]({HERO_URL})

""",
    text
)

# 2. Inserir Body Card na seção de Duas Posições
sec_target = "## Duas Posições Sobre a Existência Computacional"
if sec_target in text:
    card_md = f"""\n\n![Simular versus Instanciar: Os Três Níveis Ontológicos da Computação]({CARD_URL})\n\n"""
    text = text.replace(sec_target, sec_target + card_md)

# 3. Inserir Callouts
callout_everett = """
::: callout
🌌 **Muitos-Mundos versus Monte Carlo: A Bifurcação Cósmica**

**A diferença física entre a probabilidade epistêmica e a ontológica**

**A Amostragem Humana:** No método de Monte Carlo clássico, a incerteza reflete ignorância ou custo computacional. Amostramos trajetórias para estimar integrais ou calcular probabilidades agregadas.

**A Ramificação Quântica:** Na interpretação de Everett, a natureza não descarta caminhos. Todos os ramos coexistem no espaço de Hilbert universal; a física simplesmente se desdobra em infinitas histórias paralelas.
:::
"""
target_everett = "## Monte Carlo Contra Muitos-Mundos de Everett"
if target_everett in text and "🌌 **Muitos-Mundos" not in text:
    text = text.replace(target_everett, target_everett + "\n" + callout_everett.strip())

callout_searle = """
::: callout
🏛️ **A Objeção da Realização Múltipla e o Erro Categorial**

**John Searle, Gilbert Ryle e a ilusão da semântica nos circuitos**

**Sintaxe não é Semântica:** A célebre Sala Chinesa de Searle adverte que manipular bits segundo regras lógicas não gera, por si só, compreensão феноmenológica ou consciência subjetiva.

**O Mapa versus o Território:** Simular tempestades em supercomputadores não molha o chão do laboratório; simular redes neurais não produz automaticamente a dor ou a alegria do vivente.
:::
"""
target_searle = "## A Objeção da Realização Múltipla e o Erro Categorial"
if target_searle in text and "🏛️ **A Objeção da Realização" not in text:
    text = text.replace(target_searle, target_searle + "\n" + callout_searle.strip())

callout_etica = """
::: callout
⚠️ **O Limiar Ético: Quando Abortar a Simulação Torna-se Problema Moral**

**O peso de mundos artificiais habitados por agentes com modelos internos**

**O Dilema da Consciência Sintética:** Se um algoritmo de Monte Carlo atinge complexidade suficiente para simular mentes com auto-preservação e sensibilidade à dor, desligar a máquina deixa de ser um ato neutro.

**A Responsabilidade do Arquiteto:** Enquanto a ciência não resolve a fronteira entre cognição funcional e senciência, operar simulações de larga escala exige prudência ontológica e rigor ético.
:::
"""
target_etica = "## O Espectro Ético da Simulação"
if target_etica in text and "⚠️ **O Limiar Ético" not in text:
    text = text.replace(target_etica, target_etica + "\n" + callout_etica.strip())

# 4. Inserir Pullquotes
pq1 = """
::: pullquote
“Um engenheiro que roda dez mil pousos virtuais de uma sonda espacial em Marte não pensa nos 9.999 choques contra o solo como mortes reais. Mas o que garante que a nossa própria história não é apenas a centésima amostra de um processo análogo rodando em outro nível de realidade?”
:::
"""
target_pq1 = "## A Dimensão Cognitiva: Monte Carlo na Mente"
if target_pq1 in text and "dez mil pousos virtuais" not in text:
    text = text.replace(target_pq1, pq1 + "\n" + target_pq1)

pq2 = """
::: pullquote
“Perguntar se simular é instanciar não é um capricho especulativo, mas o ponto exato onde a computação teórica, a física fundamental e a filosofia moral se encontram.”
:::
"""
target_pq2 = "## Conclusão: O Valor da Pergunta pela Existência"
if target_pq2 in text and "ponto exato onde a computação" not in text:
    text = text.replace(target_pq2, pq2 + "\n" + target_pq2)

# 5. Limpeza de prosa: travessões e pontos-e-vírgulas
parts = text.split("## Referências")
prose_part = parts[0]
ref_part = "## Referências" + parts[1] if len(parts) > 1 else ""

lines = prose_part.splitlines()
cleaned_lines = []
in_frontmatter = False
for line in lines:
    if line.strip() == "---":
        in_frontmatter = not in_frontmatter
        cleaned_lines.append(line)
        continue
    if in_frontmatter:
        cleaned_lines.append(line)
        continue
    # Cabeçalhos
    if line.startswith("#"):
        l = line.replace(" — ", " - ").replace("—", "-")
        cleaned_lines.append(l)
        continue
    # Sumário
    if line.strip().startswith("- ["):
        l = line.replace(" — ", " - ").replace("—", "-")
        cleaned_lines.append(l)
        continue
    # Citação de autor em bloco
    if line.startswith(">") and " — " in line:
        l = line.replace(" — ", " - ")
        cleaned_lines.append(l)
        continue
    # Imagens
    if line.startswith("!["):
        l = line.replace(" — ", " - ").replace("—", "-")
        cleaned_lines.append(l)
        continue
    # Ponto e vírgula na prosa
    l = line.replace(";", ",")
    # Travessão na prosa
    l = re.sub(r"\s+—\s+", ", ", l)
    l = l.replace("—", "-")
    cleaned_lines.append(l)

prose_part = "\n".join(cleaned_lines)
text = prose_part + "\n\n" + ref_part
path.write_text(text, encoding="utf-8")
print("[OK] Script format_monte_carlo_post executado com sucesso!")
