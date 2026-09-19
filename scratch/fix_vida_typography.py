import re
from pathlib import Path

path = Path("substack/posts/o-que-e-vida-um-ensaio-nas-fronteiras-da-existencia.md")
text = path.read_text(encoding="utf-8")

# 1. Semicolons específicos
text = text.replace(
    "Entre os cenários hipotéticos mais estudados destacam-se: o **silício** em Titã (-179°C), tendo metano líquido como solvente; a **amônia líquida** (-33°C a -78°C) funcionando como solvente polar alternativo à água; o **ácido sulfúrico** em suspensão nas camadas superiores das nuvens de Vênus; e o **nitrogênio líquido** em Plutão, abrigando potenciais processos autocatalíticos criogênicos.",
    "Entre os cenários hipotéticos mais estudados destacam-se: o **silício** em Titã (-179°C), tendo metano líquido como solvente, a **amônia líquida** (-33°C a -78°C) funcionando como solvente polar alternativo à água, o **ácido sulfúrico** em suspensão nas camadas superiores das nuvens de Vênus, e o **nitrogênio líquido** em Plutão, abrigando potenciais processos autocatalíticos criogênicos."
)

text = text.replace(
    "Suzanne Simard [^11] documentou “árvores mãe” — indivíduos centrais que mantêm a floresta como sistema. Na ficção, Le Guin antecipou isso em *The Word for World is Forest*; Cameron em *Avatar*.",
    "Suzanne Simard [^11] documentou “árvores mãe”, indivíduos centrais que mantêm a floresta como sistema. Na ficção, Le Guin antecipou isso em *The Word for World is Forest*, e Cameron explorou em *Avatar*."
)

text = text.replace(
    "Manifestações biológicas com efeitos quânticos funcionais incluem: a **fotossíntese**, com coerência quântica demonstrada na transferência de energia entre complexos antena (Graham Fleming, 2007); a **magnetorrecepção aviária**, baseada em pares de radicais entrelaçados na retina de aves migratórias; o **olfato**, potencialmente mediado por efeito túnel quântico de elétrons segundo Luca Turin; e a catálise por **enzimas**, onde o tunelamento quântico de prótons acelera reações vitais.",
    "Manifestações biológicas com efeitos quânticos funcionais incluem: a **fotossíntese**, com coerência quântica demonstrada na transferência de energia entre complexos antena (Graham Fleming, 2007), a **magnetorrecepção aviária**, baseada em pares de radicais entrelaçados na retina de aves migratórias, o **olfato**, potencialmente mediado por efeito túnel quântico de elétrons segundo Luca Turin, e a catálise por **enzimas**, onde o tunelamento quântico de prótons acelera reações vitais."
)

text = text.replace(
    "A tabela abaixo mapeia os principais candidatos a esse espaço multidimensional, avaliando cada entidade segundo as sete definições exploradas. ✓ = satisfaz o critério; ✗ = não satisfaz; ~ = parcialmente ou ambiguamente.",
    "A tabela abaixo mapeia os principais candidatos a esse espaço multidimensional, avaliando cada entidade segundo as sete definições exploradas. O símbolo ✓ indica que satisfaz o critério, ✗ indica que não satisfaz, e ~ indica conformidade parcial ou ambígua."
)

# Qualquer outro ponto e vírgula na prosa antes de ## Referências
parts = text.split("## Referências")
prose_part = parts[0]
ref_part = "## Referências" + parts[1] if len(parts) > 1 else ""

# Substituir ponto e vírgula soltos na prosa por vírgula
prose_lines = prose_part.splitlines()
new_lines = []
for l in prose_lines:
    if l.startswith("|") or l.startswith("!"):
        new_lines.append(l)
    else:
        new_lines.append(l.replace(";", ","))
prose_part = "\n".join(new_lines)

# Substituir travessões (—) na prosa e títulos por vírgulas ou hífens
# Deixar apenas na byline inicial se necessário
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
    # Se for cabeçalho
    if line.startswith("#"):
        l = line.replace(" — ", " - ").replace("—", "-")
        cleaned_lines.append(l)
        continue
    # Se for item do sumário
    if line.strip().startswith("- ["):
        l = line.replace(" — ", " - ").replace("—", "-")
        cleaned_lines.append(l)
        continue
    # Se for imagem de tabela
    if line.startswith("![Tabela:"):
        l = line.replace(" — ", " - ").replace("—", "-")
        cleaned_lines.append(l)
        continue
    # Se for citação de autor em bloco: > "texto" — Autor
    if line.startswith(">") and " — " in line:
        l = line.replace(" — ", " - ")
        cleaned_lines.append(l)
        continue
    # Prosa regular
    l = re.sub(r"\s+—\s+", ", ", line)
    l = l.replace("—", "-")
    cleaned_lines.append(l)

prose_part = "\n".join(cleaned_lines)
text = prose_part + ref_part
path.write_text(text, encoding="utf-8")
print("[OK] Tipografia e pontuação ajustadas com sucesso!")
