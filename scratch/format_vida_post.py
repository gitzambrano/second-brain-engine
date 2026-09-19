import re
from pathlib import Path

path = Path("substack/posts/o-que-e-vida-um-ensaio-nas-fronteiras-da-existencia.md")
text = path.read_text(encoding="utf-8")

HERO_URL = "https://substack-post-media.s3.amazonaws.com/public/images/0c76b7ae-1f2e-4fdb-9925-6050bf8170f4_1920x1080.png"
CARD_URL = "https://substack-post-media.s3.amazonaws.com/public/images/75cf720e-82f6-4dbd-b704-a7e1f9158d68_2160x1382.png"

# 1. Frontmatter
text = re.sub(
    r"^---[\s\S]*?---\s*",
    f"""---
title: "O Que É Vida? Um Ensaio nas Fronteiras da Existência"
subtitle: "Catorze perspectivas sobre vida (da bioquímica ao princípio da energia livre de Friston, da autopoiese ao panpsiquismo) tratadas como estratégias complementares, não rivais."
seo_title: "O Que É Vida? Um Ensaio nas Fronteiras da Existência"
seo_description: "Da bioquímica e termodinâmica de Schrödinger ao Princípio da Energia Livre de Friston: um mapeamento das 14 fronteiras sobre a definição de vida."
source_essay: "o-que-e-vida-um-ensaio-nas-fronteiras-da-existencia.md"
tags: [Biologia, Termodinâmica, Filosofia, Teoria-da-Informação]
cover_image: "{HERO_URL}"
---

> Ensaio
> Gustavo Zambrano · Setembro de 2026

> “Definir a vida não é isolar uma substância mágica, mas compreender a dinâmica singular através da qual a matéria resiste à dispersão termodinâmica criando um interior autocontido.”

![O Que É Vida? Um Ensaio nas Fronteiras da Existência]({HERO_URL})

""",
    text
)

# 2. Inserir Body Infocard na Síntese
target_sintese = "## XV. Síntese: O Espectro da Vida"
if target_sintese in text:
    card_md = f"""\n\n![O Espectro da Vida: Onde as Fronteiras Teóricas se Cruzam]({CARD_URL})\n\n"""
    text = text.replace(target_sintese, target_sintese + card_md)

# 3. Inserir Pullquote
pq_md = """
::: pullquote
“A vida não é uma substância nem um privilégio exclusivo da química do carbono. É uma dinâmica persistente de não-equilíbrio, uma transição de fase estatística onde a matéria organiza a si mesma para resistir à dispersão termodinâmica.”
:::
"""
target_pq = "## Conclusão: Definições, Ética e o Futuro da Astrobiologia"
if target_pq in text and "::: pullquote" not in text:
    text = text.replace(target_pq, target_pq + "\n" + pq_md)

# 4. Inserir Callouts estruturados
callout_termo = """
::: callout
⚡ **A Termodinâmica de Schrödinger: Vida como Consumo de Negentropia**

**Como a matéria viva contorna a Segunda Lei da Termodinâmica**

**Bombeamento de Entropia:** Um organismo não viola a Segunda Lei. Ele se mantém altamente ordenado degradando energia livre do ambiente e expulsando entropia térmica para fora de sua fronteira.

**O Cristal Aperiódico:** Décadas antes da elucidação experimental do DNA, Schrödinger previu que a informação biológica precisava residir em um sólido aperiódico capaz de armazenar microcódigos estáveis.
:::
"""
target_termo = "## IV. A Definição Termodinâmica: Vida como Negentropia"
if target_termo in text and "⚡ **A Termodinâmica de Schrödinger" not in text:
    text = text.replace(target_termo, target_termo + "\n" + callout_termo.strip())

callout_auto = """
::: callout
🏛️ **A Lógica da Autopoiese: Fechamento Operacional**

**A formulação de Humberto Maturana e Francisco Varela**

**Auto-fabricação Contínua:** Uma máquina viva se diferencia de artefatos humanos porque sua produção primária é a si própria. Os processos químicos produzem a membrana física que delimita os próprios processos.

**A Fragilidade do Vivente:** Quando a rede recursiva de autoprodução de componentes cessa, o organismo morre instantaneamente, mesmo que toda a sua composição atômica permaneça inalterada.
:::
"""
target_auto = "## VII. A Definição Filosófica: Autopoiese, Intencionalidade e Consciência"
if target_auto in text and "🏛️ **A Lógica da Autopoiese" not in text:
    text = text.replace(target_auto, target_auto + "\n" + callout_auto.strip())

callout_fep = """
::: callout
🧠 **O Princípio da Energia Livre: Vida como Minimização de Surpresa**

**Karl Friston e a física estatística da agência biológica**

**O Markov Blanket:** A membrana estatística que segrega estados internos dos estados externos. Para persistir no tempo, qualquer entidade auto-organizada precisa restringir seus estados a uma faixa estreita de probabilidades homeostáticas.

**Ação e Inferência Ativa:** Viver equivale a inferir ativamente as causas do mundo exterior e agir sobre o meio para que os dados sensoriais confirmem o modelo interno de sobrevivência do próprio organismo.
:::
"""
target_fep = "## VIII. O Princípio da Energia Livre: Vida como Minimização de Surpresa"
if target_fep in text and "🧠 **O Princípio da Energia Livre" not in text:
    text = text.replace(target_fep, target_fep + "\n" + callout_fep.strip())

callout_n1 = """
::: callout
🌌 **O Viés de Autoamostragem: A Armadilha do N=1**

**Por que a astrobiologia luta para definir vida além da Terra**

**O Prisma Terráqueo:** Toda a vida conhecida compartilha a mesma base genética e descende de um único ancestral comum (LUCA). Confundir essas particularidades históricas com requisitos universais é o maior risco epistêmico da exploração espacial.

**Busca por Biosinaturas Agnósticas:** Em vez de buscar unicamente compostos idênticos aos da Terra, instrumentos astrobiológicos modernos procuram anomalias estatísticas de não-equilíbrio químico e padrões sustentados de complexidade informacional.
:::
"""
target_n1 = "## XIV. O Self-Sampling Bias: A Armadilha do N=1"
if target_n1 in text and "🌌 **O Viés de Autoamostragem" not in text:
    text = text.replace(target_n1, target_n1 + "\n" + callout_n1.strip())

# 5. Limpeza de prosa: travessões e pontos-e-vírgulas
lines = text.splitlines()
cleaned_lines = []
in_frontmatter = False
for line in lines:
    if line.strip() == "---":
        in_frontmatter = not in_frontmatter
        cleaned_lines.append(line)
        continue
    if in_frontmatter or line.startswith("#") or line.startswith("!") or line.startswith(">") or line.startswith("[^"):
        cleaned_lines.append(line)
        continue
    # Limpar travessões em prosa
    l = re.sub(r"\s+—\s+", ", ", line)
    l = re.sub(r"—", "-", l)
    # Limpar ponto e vírgula em prosa
    l = re.sub(r";", ",", l)
    cleaned_lines.append(l)

text = "\n".join(cleaned_lines)
path.write_text(text, encoding="utf-8")
print("[OK] Script format_vida_post executado com sucesso!")
