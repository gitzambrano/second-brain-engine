import re
from pathlib import Path

path = Path("substack/posts/campeoes-por-acaso-por-que-atletas-de-elite-sao-anomalias-estatisticas.md")
text = path.read_text(encoding="utf-8")

HERO_URL = "https://substack-post-media.s3.amazonaws.com/public/images/2592436e-f8f1-4548-b176-1b49cb6647bb_1920x1080.png"
CARD_URL = "https://substack-post-media.s3.amazonaws.com/public/images/7c82426d-ca77-4d8d-8231-78df7aed3b07_2160x1248.png"

# 1. Frontmatter
text = re.sub(
    r"^---[\s\S]*?---\s*",
    f"""---
title: "Campeões por Acaso — Por Que Atletas de Elite São Anomalias Estatísticas"
subtitle: "O status de atleta de elite obedece às leis de valores extremos: a conjunção multiplicativa de genética, idade relativa, geografia e viés de sobrevivência."
seo_title: "Campeões por Acaso: Atletas de Elite e a Estatística"
seo_description: "Por que atletas olímpicos e de elite são anomalias estatísticas multivariadas, e não apenas o resultado de força de vontade e treino duro."
source_essay: "campeoes-por-acaso-por-que-atletas-de-elite-sao-anomalias-estatisticas.md"
tags: [Estatística, Esporte, Fisiologia, Filosofia]
cover_image: "{HERO_URL}"
---

> Ensaio
> Gustavo Zambrano · Agosto de 2026

> “O campeão olímpico não treinou dez vezes mais do que o quinquagésimo colocado mundial. A diferença milimétrica no pódio é o produto acumulado de dezenas de loterias biológicas e contextuais que nenhum atleta escolheu.”

![Campeões por Acaso — Por Que Atletas de Elite São Anomalias Estatísticas]({HERO_URL})

""",
    text
)

# 2. Inserir Body Card na seção de Estatística do Acaso
sec_target = "## 3. A Estatística do Acaso: Evidências Empíricas"
if sec_target in text:
    card_md = f"""\n\n![A Anatomia da Anomalia: Os Quatro Filtros Invisíveis do Esporte de Elite]({CARD_URL})\n\n"""
    text = text.replace(sec_target, sec_target + card_md)

# 3. Inserir Pullquotes
pq1_md = """
::: pullquote
“A meritocracia do pódio sofre de um viés de sobrevivência radical: ouvimos os discursos de quem venceu atribuindo tudo ao esforço, porque os milhares que treinaram com idêntico sacrifício e quebraram os ossos ou ligamentos no caminho nunca recebem um microfone.”
:::
"""
target_pq1 = "## 4. A Psicologia do Acaso"
if target_pq1 in text and "::: pullquote" not in text:
    text = text.replace(target_pq1, pq1_md + "\n" + target_pq1)

pq2_md = """
::: pullquote
“A disciplina e o treino obsessivo são condições estritamente necessárias, mas profundamente insuficientes. O pódio é reservado para a intersecção improvável entre esforço máximo e um bilhete premiado na loteria do universo.”
:::
"""
target_pq2 = "## Conclusão"
if target_pq2 in text and "condições estritamente necessárias" not in text:
    text = text.replace(target_pq2, pq2_md + "\n" + target_pq2)

# 4. Ajustar callouts com emojis
text = text.replace("::: callout\n**Tese Central**", "::: callout\n💡 **Tese Central**")
text = text.replace("::: callout\n**O Problema Central Deste Paper**", "::: callout\n⚠️ **O Problema Central Deste Ensaio**")
text = text.replace("::: callout\n**O Estudo Original de Barnsley (1985)**", "::: callout\n🏒 **O Estudo Original de Barnsley (1985)**")
text = text.replace("::: callout\n**A Matemática do Funil Esportivo**", "::: callout\n🎲 **A Matemática do Funil Esportivo**")
text = text.replace("::: callout\n**A Revisão da Teoria das 10.000 Horas**", "::: callout\n⏱️ **A Revisão da Teoria das 10.000 Horas**")

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
print("[OK] Script format_campeoes_post executado com sucesso!")
