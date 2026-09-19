import re
from pathlib import Path

path = Path("substack/posts/ficcao-cientifica-como-incubadora-teorica-sci-fi-prototyping-monte-carlo-narrativo-e-a-imaginacao-hipotetica.md")
text = path.read_text(encoding="utf-8")

HERO_URL = "https://substack-post-media.s3.amazonaws.com/public/images/a3c4b653-ae09-467a-9635-9c00fd56b744_1920x1080.png"
CARD_URL = "https://substack-post-media.s3.amazonaws.com/public/images/c9ebeed9-f92f-467f-a909-7f45c326f373_2160x1300.png"

# 1. Frontmatter
text = re.sub(
    r"^---[\s\S]*?---\s*",
    f"""---
title: "Ficção Científica como Incubadora Teórica — Sci-Fi Prototyping, Monte Carlo Narrativo e a Imaginação Hipotética"
subtitle: "A ficção científica não é profecia nem entretenimento escapista: funciona como uma sandbox computacional de baixo custo para testar hipóteses, interfaces e dilemas sociais."
seo_title: "Ficção Científica como Incubadora Teórica e Sci-Fi Prototyping"
seo_description: "Como a ficção científica atua como simulação de Monte Carlo narrativa e laboratório de design tecnológico antes do primeiro protótipo de bancada."
source_essay: "ficcao-cientifica-como-incubadora-teorica-sci-fi-prototyping-monte-carlo-narrativo-e-a-imaginacao-hipotetica.md"
tags: [Literatura, Filosofia-da-Ciência, Teoria-da-Informação, Modelagem]
cover_image: "{HERO_URL}"
---

> Ensaio
> Gustavo Zambrano · Agosto de 2026

> “A ficção científica não acerta porque prevê o futuro com precisão mecânica, mas porque coloniza a imaginação dos futuros engenheiros com as formas daquilo que vale a pena construir.”

![Ficção Científica como Incubadora Teórica]({HERO_URL})

""",
    text
)

# 2. Inserir Body Card na seção de Sci-Fi Prototyping
sec_target = "## Sci-Fi Prototyping: a Ficção Como Ferramenta de Design"
if sec_target in text:
    card_md = f"""\n\n![O Loop da Imaginação Tecnológica: Da Premissa Contrafactual à Cristalização em Design]({CARD_URL})\n\n"""
    text = text.replace(sec_target, sec_target + card_md)

# 3. Pullquotes
pq1_md = """
::: pullquote
“A narrativa especulativa funciona como uma simulação de Monte Carlo de custo computacional quase nulo: ao lançar personagens, incentivos perversos e leis físicas em rota de colisão, descobrimos onde o sistema quebra antes de gastar bilhões de dólares ou vidas humanas.”
:::
"""
target_pq1 = "## O Viés de Sobrevivência na Narrativa Tecnológica"
if target_pq1 in text and "::: pullquote" not in text:
    text = text.replace(target_pq1, pq1_md + "\n" + target_pq1)

pq2_md = """
::: pullquote
“Projetar uma tecnologia sem exercitar sua ficção prévia é como construir uma aeronave sem passar pelo túnel de vento: o primeiro voo acontece diretamente no mundo real, com todos os seus riscos catastróficos.”
:::
"""
target_pq2 = "## Conclusão: O Rascunho Narrativo do Futuro"
if target_pq2 in text and "túnel de vento" not in text:
    text = text.replace(target_pq2, pq2_md + "\n" + target_pq2)

# 4. Limpar e reformatar callouts existentes
def clean_callout(block):
    # remover ####
    b = re.sub(r"####\s*(.*)", r"**\1**\n", block)
    # transformar listas em parágrafos com bold
    b = re.sub(r"^\s*-\s*\*\*(.*?)\*\*", r"**\1**", b, flags=re.MULTILINE)
    # adicionar emojis
    if "Asimov" in b and not b.startswith("::: callout\n📚"):
        b = b.replace("::: callout\n", "::: callout\n📚 ")
    if "Monte Carlo" in b and not b.startswith("::: callout\n🎲"):
        b = b.replace("::: callout\n", "::: callout\n🎲 ")
    return b

text = re.sub(r"::: callout[\s\S]*?:::", lambda m: clean_callout(m.group(0)), text)

# 5. Adicionar 2 novos callouts para atingir densidade editorial
callout_brian = """
::: callout
⚡ **Brian David Johnson e o Sci-Fi Prototyping Corporativo**

**O método de engenharia que nasceu nos laboratórios da Intel**

**A Ficção Baseada em Fatos:** Ao contrário da ficção científica tradicional, o *Sci-Fi Prototyping* usa como ponto de partida dados científicos reais e pesquisas laboratoriais em andamento para projetar um futuro plausível de 5 a 10 anos à frente.

**O Protótipo como História:** A narrativa curta coloca pessoas reais interagindo com a tecnologia hipotética, forçando a equipe de engenharia a antecipar fricções de usabilidade, privacidade e rejeição cultural antes do desenvolvimento do silício.
:::
"""

target_cb = "O conceito de *Sci-Fi Prototyping* (SFP), cunhado por Brian David Johnson"
if target_cb in text and "⚡ **Brian David Johnson" not in text:
    text = text.replace(target_cb, callout_brian.strip() + "\n\n" + target_cb)

callout_institucional = """
::: callout
🏛️ **Institucionalizar a Imaginação: O Dilema Burocrático**

**Exércitos e corporações contratando escritores de ficção científica**

**A Red Team Narrativa:** Ministérios da Defesa da França e dos EUA já utilizam equipes de ficcionistas para projetar ameaças cibernéticas e geopolíticas contraintuitivas que oficiais treinados jamais considerariam.

**O Paradoxo da Captura:** Quando a imaginação especulativa é submetida a comitês corporativos ou militares, ela corre o risco de perder sua principal virtude: a irreverência subversiva que expõe as fraquezas sistêmicas da própria instituição contratante.
:::
"""

target_ci = "## Institucionalizar a Imaginação?"
if target_ci in text and "🏛️ **Institucionalizar a Imaginação" not in text:
    text = text.replace(target_ci, target_ci + "\n" + callout_institucional.strip())

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
print("[OK] Script format_scifi_post executado com sucesso!")
