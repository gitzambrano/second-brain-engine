import re
from pathlib import Path

path = Path("substack/posts/engenharia-em-menos-de-um-metro-cubico-a-impressora-3d-como-microcosmo-de-um-projeto-de-aeronave.md")
text = path.read_text(encoding="utf-8")

HERO_URL = "https://substack-post-media.s3.amazonaws.com/public/images/eb5713e8-9c9c-4839-816e-e155df170a21_1920x1080.jpeg"
BODY_FIG_URL = "https://substack-post-media.s3.amazonaws.com/public/images/9c0b2267-f338-4c7c-92e0-596aeb6ec15f_1640x1064.png"

# 1. Frontmatter
text = re.sub(
    r"^---[\s\S]*?---\s*",
    f"""---
title: "Engenharia em menos de um metro cúbico — A impressora 3D como microcosmo de um projeto de aeronave"
subtitle: "Como uma máquina de mesa comprime mecânica, estruturas, vibrações, termodinâmica e controle: as interfaces de engenharia de sistemas em menos de um metro cúbico."
seo_title: "A Impressora 3D como Microcosmo de um Projeto de Aeronave"
seo_description: "Por que uma impressora 3D é um laboratório de engenharia de sistemas? De vibrações e input shaping à termodinâmica de bicos e controle de voo."
source_essay: "engenharia-em-menos-de-um-metro-cubico-a-impressora-3d-como-microcosmo-de-um-projeto-de-aeronave.md"
tags: [Engenharia, Cultura-Maker, Computação, Dinâmica-de-Voo]
cover_image: "{HERO_URL}"
---

> Ensaio
> Gustavo Zambrano · Agosto de 2026

> “O desempenho de uma máquina complexa quase nunca é limitado por um componente isolado, mas pelos compromissos silenciosos que governam suas interfaces.”

![Engenharia em menos de um metro cúbico]({HERO_URL})

""",
    text
)

# 2. Inserir figura do corpo na seção de interfaces
sec_target = "## Engenharia de sistemas: o problema está nas interfaces"
if sec_target in text:
    card_md = f"""\n\n![O Efeito Dominó do Projeto de Sistemas: Como Requisitos Conflitantes Acoplam Disciplinas Físicas]({BODY_FIG_URL})\n\n"""
    text = text.replace(sec_target, sec_target + card_md)

# 3. Pullquote
pq_md = """
::: pullquote
“Em engenharia, ‘imprimir mais rápido’ ou ‘voar mais longe’ nunca é apenas um requisito de velocidade ou aerodinâmica. É uma perturbação que redistribui massas, excita modos estruturais e altera as condições de contorno de todos os subsistemas da máquina.”
:::
"""
target_pq = "## Conclusão: um laboratório de engenharia sobre a mesa"
if target_pq in text and "::: pullquote" not in text:
    text = text.replace(target_pq, target_pq + "\n" + pq_md)

# 4. Math: substituir $$...$$ por blockquotes Unicode elegantes
math_replacements = [
    (r"\$\$\s*F_i\s*=\s*m\s*a\.\s*\$\$", "> **Fᵢ = m · a**"),
    (r"\$\$\s*k\s*=\s*\\frac\{F\}\{\\delta\}\.?\s*\$\$", "> **k = F / δ**"),
    (r"\$\$\s*m\\ddot\{x\}\+c\\dot\{x\}\+kx=F\(t\),?\s*\$\$", "> **m · ẍ + c · ẋ + k · x = F(t)**"),
    (r"\$\$\s*f_n=\\frac\{1\}\{2\\pi\}\\sqrt\{\\frac\{k\}\{m\}\}\.?\s*\$\$", "> **fₙ = (1 / 2π) · √(k / m)**"),
    (r"\$\$\s*u\(t\)=K_p\s*e\(t\)\+K_i\\int_0\^t\s*e\(\\tau\)\\,d\\tau\+K_d\\frac\{de\}\{dt\},?\s*\$\$", "> **u(t) = K_p · e(t) + K_i · ∫₀ᵗ e(τ) dτ + K_d · (de/dt)**"),
    (r"\$\$\\s*\\dot\{Q\}_\{cond\}=kA\\frac\{\\Delta T\}\{L\},?\s*\$\$", "> **Q̇_cond = k · A · (ΔT / L)**"),
    (r"\$\$\\s*\\dot\{Q\}_\{conv\}=hA\(T_s-T_\\infty\)\.?\s*\$\$", "> **Q̇_conv = h · A · (T_s - T_∞)**"),
    (r"\$\$\\s*\\dot\{m\}=\\rho\s*A\s*V,?\s*\$\$", "> **ṁ = ρ · A · V**")
]

for pat, rep in math_replacements:
    text = re.sub(pat, rep, text)

# Também lidar com inline math simples
text = re.sub(r"\$m\$", "`m`", text)
text = re.sub(r"\$a\$", "`a`", text)
text = re.sub(r"\$k\$", "`k`", text)
text = re.sub(r"\$c\$", "`c`", text)
text = re.sub(r"\$F\(t\)\$", "`F(t)`", text)
text = re.sub(r"\$e\(t\)\$", "`e(t)`", text)
text = re.sub(r"\$a \\to 2a\$", "`a → 2a`", text)
text = re.sub(r"\$F_i = m a\$", "`F_i = m · a`", text)
text = re.sub(r"\$k = F/\\delta\$", "`k = F/δ`", text)
text = re.sub(r"\$\\omega_n = \\sqrt\{k/m\}\$", "`ω_n = √(k/m)`", text)
text = re.sub(r"\$\\dot\{V\} = A \\cdot v\$", "`V̇ = A · v`", text)

# 5. Adicionar Callouts bem formatados
callout1 = """
::: callout
⚙️ **O Acoplamento Multidisciplinar: O Efeito Dominó do Requisito de Aceleração**

**A cascata física disparada por uma decisão aparentemente simples de desempenho**

**Cinemática e Inércia:** Dobrar a aceleração dobra a força inercial (`Fᵢ = m · a`) exercida sobre pórticos e correias.

**Estruturas e Vibrações:** A força extra deflete componentes elásticos e excita modos de ressonância natural, gerando efeito fantasma (*ghosting*) e perda de precisão geométrica.

**Termodinâmica e Fluidos:** Velocidades maiores exigem taxas elevadas de extrusão volumétrica, empurrando o hotend para o limite térmico e forçando ventiladores a resfriar camadas sob transientes severos.
:::
"""

target_c1 = "A mesma lógica aparece em uma aeronave. Aumentar a envergadura"
if target_c1 in text and "⚙️ **O Acoplamento Multidisciplinar" not in text:
    text = text.replace(target_c1, callout1.strip() + "\n\n" + target_c1)

callout2 = """
::: callout
🔥 **O Paradoxo Térmico da Manufatura Aditiva**

**Fusão pontual versus resfriamento localizado: o equilíbrio termodinâmico**

**A Barreira do Heat Break:** O gradiente de temperatura deve cair centenas de graus em milímetros para impedir o entupimento prematuro por condução ascendente (*heat creep*).

**A Termodinâmica Intercamadas:** Resfriar rápido demais impede a difusão molecular entre camadas e provoca delaminação estrutural sob tração, enquanto resfriar devagar demais derrete balanços e pontes geométricas.
:::
"""

target_c2 = "A termodinâmica introduz outra forma de acoplamento entre disciplinas."
if target_c2 in text and "🔥 **O Paradoxo Térmico" not in text:
    text = text.replace(target_c2, callout2.strip() + "\n\n" + target_c2)

callout3 = """
::: callout
✈️ **A Aeronave na Bancada: O Valor Pedagógico do Acoplamento**

**Por que sistemas mecatrônicos compactos formam os melhores engenheiros**

**Sensibilidade às Consequências:** Em arquiteturas fortemente integradas, nenhum parâmetro é isolado. Ajustar uma variável sempre consome a margem de outro subsistema.

**O Ciclo de Feedback Imediato:** Ao contrário de um programa aeroespacial cujos ensaios levam anos, a impressora 3D materializa falhas mecânicas, dinâmicas e de controle em questão de minutos na bancada.
:::
"""

target_c3 = "A impressora 3D de bancada é um laboratório completo de engenharia de sistemas"
if target_c3 in text and "✈️ **A Aeronave na Bancada" not in text:
    text = text.replace(target_c3, callout3.strip() + "\n\n" + target_c3)

# 6. Limpeza de prosa: travessões em prosa e pontos-e-vírgulas
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
print("[OK] Script format_post_impressora executado com sucesso!")
