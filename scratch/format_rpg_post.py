import re
from pathlib import Path

path = Path("substack/posts/rpg-de-mesa-e-a-teoria-da-informacao-entropia-narrativa-simulacao-cognitiva-e-a-linguagem-sem-limites.md")
text = path.read_text(encoding="utf-8")

HERO_URL = "https://substack-post-media.s3.amazonaws.com/public/images/14b7b60c-db6e-4f5d-97d3-b23ef82cc138_1920x1080.png"
CARD_URL = "https://substack-post-media.s3.amazonaws.com/public/images/186e11fb-3a05-46b3-bc58-31ad2bcfcfde_2160x1268.png"

# 1. Frontmatter
text = re.sub(
    r"^---[\s\S]*?---\s*",
    f"""---
title: "RPG de Mesa e a Teoria da Informação — Entropia Narrativa, Simulação Cognitiva e a Linguagem sem Limites"
subtitle: "Por que nenhuma inteligência artificial ou motor gráfico supera a largura de banda ontológica de uma mesa reunida ao redor da palavra falada."
seo_title: "RPG de Mesa e a Teoria da Informação de Shannon"
seo_description: "Entropia narrativa, simulação cognitiva e por que o RPG de mesa é uma máquina de computação analógica com largura de banda infinita."
source_essay: "rpg-de-mesa-e-a-teoria-da-informacao-entropia-narrativa-simulacao-cognitiva-e-a-linguagem-sem-limites.md"
tags: [Jogos, Teoria-da-Informação, Cibernética, Linguagem]
cover_image: "{HERO_URL}"
---

> Ensaio
> Gustavo Zambrano · Agosto de 2026

> “Entre todas as mídias interativas criadas pela humanidade, apenas o RPG de mesa aceita como ação válida qualquer proposição que a imaginação consiga pronunciar em linguagem natural.”

![RPG de Mesa e a Teoria da Informação]({HERO_URL})

""",
    text
)

# 2. Substituir Callout 1 (que continha tabela) pelo Body Card + Callout limpo
target_c1 = """::: callout
**A Termodinâmica Informacional das Mídias Interativas**

#### Entropia de Decisão por Turno (`H = -∑ p_i \log₂ p_i`)
| Meio Interativo | Espaço de Ações (`N`) | Entropia Nominal (`H`) | Custo Marginal do Imprevisto |
| :--- | :--- | :--- | :--- |
| **Videogame Linear** | `N = 1` (árvore estática) | `H ≈ 0 bits` | Infinito (exige reescrita de código ou assets) |
| **Videogame Mundo Aberto** | `N ≈ 50` (ações mapeadas) | `H ≈ 5{,}6 bits` | Elevadíssimo (animações, física de colisão, dublagem) |
| **RPG de Mesa (Mesa Viva)** | `N ≈ 10^3+` (linguagem natural aberta) | `H \ge 10 bits` | **Zero:** absorvido instantaneamente pela escuta do mestre |
:::"""

card_block = f"""
![A Termodinâmica Informacional das Mídias Interativas]({CARD_URL})

::: callout
📊 **A Termodinâmica Informacional das Mídias Interativas**

**A Entropia de Decisão de Shannon: H = -∑ pᵢ log₂ pᵢ**

**Videogames Lineares (H ≈ 0 bits):** O jogador percorre uma árvore de decisão estática e fechada. Qualquer ação fora do script quebra a simulação ou encontra uma parede invisível.

**Mundos Abertos AAA (H ≈ 5.6 bits):** Mapeiam dezenas de comandos no controle sob física programada, mas o custo marginal de qualquer novo evento imprevisto é astronômico.

**RPG de Mesa (H ≥ 10 bits):** Espaço combinatório infinito em linguagem natural aberta, com custo marginal zero de processamento semântico, absorvido pela mente viva do mestre.
:::
"""

if target_c1 in text:
    text = text.replace(target_c1, card_block.strip())
else:
    # Se não achar string exata, buscar por regex
    text = re.sub(r"::: callout\s*\*\*A Termodinâmica Informacional[\s\S]*?:::", card_block.strip(), text)

# 3. Reformatar Callout 2
target_c2 = """::: callout
**Fluência Estatística versus Continuidade Ontológica**

#### Por Que Modelos de Linguagem Sofrem Como Game Masters Autônomos
- **Fluência (Geração de Superfície):** Amostragem de tokens condicionada à janela de atenção `P(w_t | w_{<t})`. Os LLMs são mestres em prosa vívida, diálogos dramáticos e descrições atmosféricas.
- **Continuidade (Manutenção de Invariantes):** Um mundo persistente exige rastreamento estrito de causalidade (inventário, status de vida ou morte de NPCs, leis físicas imutáveis). Em janelas longas, a ausência de um grafo de estado simbólico leva a contradições e alucinações irreversíveis.
:::"""

clean_c2 = """
::: callout
🤖 **Fluência Estatística versus Continuidade Ontológica**

**Por que modelos de linguagem sofrem como Game Masters autônomos**

**Fluência (Geração de Superfície):** Amostragem de tokens condicionada à janela de atenção. Os LLMs modernos são mestres em prosa vívida, diálogos dramáticos e descrições atmosféricas ricas.

**Continuidade (Manutenção de Invariantes):** Um mundo ficcional persistente exige rastreamento estrito de causalidade (inventário, status de vida ou morte de personagens, leis físicas imutáveis). Em narrativas longas, a ausência de um grafo de estado simbólico conduz a alucinações e contradições irreversíveis.
:::
"""
text = text.replace(target_c2, clean_c2.strip())

# 4. Adicionar novos callouts para pacing
callout_dado = """
::: callout
🎲 **O Dado Poliédrico: Injetor Estocástico de Realidade**

**Como o ruído randômico rompe o monopólio da intenção autoral**

**Colapso de Incerteza:** O dado introduz entropia genuína no sistema. Nenhum jogador e nenhum mestre pode garantir o desfecho exato, criando risco dramático autêntico.

**A Emergência da Consequência:** As histórias mais memoráveis de uma campanha nunca nascem de planos perfeitamente executados, mas da improvisação desesperada diante de uma falha crítica imprevista na rolagem.
:::
"""
target_dado = "## O Dado Como Gerador de Ruído e Inovação Causal"
if target_dado in text and "🎲 **O Dado Poliédrico" not in text:
    text = text.replace(target_dado, target_dado + "\n" + callout_dado.strip())

callout_mente = """
::: callout
🧠 **A Mente Estendida: A Mesa como Computador Analógico**

**Fichas, mapas e dados como andaimes da cognição distribuída**

**Cognição Compartilhada:** A simulação do mundo imaginado não reside no crânio isolado de um indivíduo, mas na rede de interações sustentada por artefatos externos sobre a mesa.

**Consenso Intersubjetivo:** A autoridade narrativa é negociada em tempo real através de regras compartilhadas, formando uma realidade simulada imune a bugs de compilação ou quedas de servidor.
:::
"""
target_mente = "## Processamento Distribuído e o Game Master Como Motor do Mundo"
if target_mente in text and "🧠 **A Mente Estendida" not in text:
    text = text.replace(target_mente, target_mente + "\n" + callout_mente.strip())

# 5. Adicionar Pullquotes
pq1 = """
::: pullquote
“Um videogame de duzentos milhões de dólares coloca uma barreira invisível quando o jogador tenta interrogar o barqueiro sobre sua infância. A mesa de RPG inventa a biografia do barqueiro em dois segundos e faz daquilo o clímax dramático da campanha.”
:::
"""
target_pq1 = "## Monte Carlo Cognitivo e os Mundos Não-Instanciados"
if target_pq1 in text and "barreira invisível" not in text:
    text = text.replace(target_pq1, pq1 + "\n" + target_pq1)

pq2 = """
::: pullquote
“Entre todas as mídias interativas criadas pela humanidade, apenas o RPG de mesa aceita como comando válido qualquer proposição que a imaginação consiga articular em linguagem natural.”
:::
"""
target_pq2 = "## Conclusão: O Ritual da Palavra Criadora"
if target_pq2 in text and "proposição que a imaginação" not in text:
    text = text.replace(target_pq2, pq2 + "\n" + target_pq2)

# 6. Limpeza de prosa: travessões e pontos-e-vírgulas
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
print("[OK] Script format_rpg_post executado com sucesso!")
