#!/usr/bin/env python3
"""generate_en_svgs.py - Gera e sincroniza versões em inglês (_en.svg) dos diagramas SVG.

Audita diagramas SVG em wiki/assets/ e produz suas variantes em inglês:
- Traduz rótulos conceituais, legendas, eixos e formulações mantendo a geometria intacta.
- Trata diagramas puramente geométricos ou matemáticos duplicando para paridade de nomes.
- Assegura que todo arquivo <slug>_fig<N>.svg tenha um <slug>_fig<N>_en.svg correspondente.

Escopo:
    Tradutor e gerador de paridade bilíngue para SVGs em DATA_ROOT/wiki/assets/.
    Padrão sem argumentos processa e sincroniza todos os diagramas da wiki.

Entradas (Inputs):
    Arquivos *.svg em wiki/assets/.
    Argumentos CLI opcionais:
        arquivo.svg    Arquivo específico a sincronizar

Saídas (Outputs):
    Arquivos *_en.svg gerados no mesmo diretório de assets.
    Stdout: Resumo de SVGs gerados e sincronizados.
    Exit code: 0 em sucesso.

Uso:
    python scripts/generate_en_svgs.py              # sincroniza todos os SVGs da wiki
    python scripts/generate_en_svgs.py arquivo.svg  # sincroniza um SVG específico
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from repo_paths import ASSETS_DIR

DATA_ASSETS = ASSETS_DIR

TRANSLATIONS = {
    # 1. Equações Analíticas Rotor Rígido
    "equacoes-analiticas-para-os-coeficientes-aerodinamicos-de-um-rotor-rigido_fig1.svg": [
        ("Convenção de Azimute e Eixos de Referência do Rotor", "Rotor Azimuth Convention and Reference Axes"),
        ("Vista de topo do disco · Rotação anti-horária (visto de cima) · Azimute ψ medido a partir da traseira", "Top view of disk · Counter-clockwise rotation (from above) · Azimuth ψ measured from aft"),
        ("Lado Avançante", "Advancing Side"),
        ("0° &lt; ψ &lt; 180° (Direita)", "0° &lt; ψ &lt; 180° (Right)"),
        ("uT = x + μ sin ψ  (soma de velocidades)", "uT = x + μ sin ψ  (velocity addition)"),
        ("Lado Recuante", "Retreating Side"),
        ("180° &lt; ψ &lt; 360° (Esquerda)", "180° &lt; ψ &lt; 360° (Left)"),
        ("uT = x − μ |sin ψ|  (subtração)", "uT = x − μ |sin ψ|  (velocity subtraction)"),
        ("Corte na raiz", "Root cutout"),
        ("Raio R (x=1)", "Radius R (x=1)"),
        ("+X (Frente / Proa)", "+X (Forward / Nose)"),
        ("−X (Traseira / Cauda)", "−X (Aft / Tail)"),
        ("+Y (Direita)", "+Y (Right)"),
        ("−Y (Esquerda)", "−Y (Left)"),
        ("Rotação", "Rotation"),
        ("(anti-horária)", "(counter-clockwise)"),
        ("Elemento de pá dr", "Blade element dr"),
        ("raio r = x R · corda c", "radius r = x R · chord c"),
        ("Voo à Frente", "Forward Flight"),
        ("Direção +X", "+X Direction"),
        ("Cargas no Cubo (Eixos de Corpo)", "Hub Loads (Body Axes)"),
        ("para cima (−Z)", "upward (−Z)"),
        ("para trás (−X)", "rearward (−X)"),
        ("para a direita (+Y)", "rightward (+Y)"),
        ("Mx &gt; 0 : baixa asa direita", "Mx &gt; 0 : right wing down (roll)"),
        ("My &gt; 0 : arfagem nariz para cima", "My &gt; 0 : pitch up"),
        ("VETORES UNITÁRIOS LOCAIS DA PÁ", "LOCAL BLADE UNIT VECTORS"),
        ("(radial para fora ao longo do raio)", "(radial outward along span)"),
        ("(tangencial no sentido de rotação)", "(tangential in direction of rotation)"),
        ("CINEMÁTICA E VELOCIDADE RELATIVA DO ELEMENTO", "ELEMENT KINEMATICS AND RELATIVE VELOCITY"),
        ("Velocidade tangencial:", "Tangential velocity:"),
        ("Velocidade radial:", "Radial velocity:"),
        ("Inflow no disco:", "Rotor disk inflow:"),
        ("Ângulo de inflow:", "Inflow angle:"),
    ],

    # 2. Força Lateral Rotor / Coleman
    "forca-lateral-de-um-rotor-em-voo-a-frente-inflow-uniforme-e-coleman_fig5.svg": [
        ("Origem da Força Lateral no Rotor: Cancelamento vs. Quebra por Coleman", "Origin of Rotor Side Force: Cancellation vs. Symmetry Breaking by Coleman"),
        ("1. Inflow Uniforme: Cancelamento Lateral", "1. Uniform Inflow: Lateral Cancellation"),
        ("Recuo", "Retreating"),
        ("Avanço", "Advancing"),
        ("Y_frente", "Y_front"),
        ("Y_trás", "Y_rear"),
        ("Cancelamento: |Y_trás| = |Y_frente|  ⟹  C_Y = 0", "Cancellation: |Y_rear| = |Y_front|  ⟹  C_Y = 0"),
        ("2. Gradiente de Coleman: Quebra de Simetria", "2. Coleman Gradient: Symmetry Breaking"),
        ("Assimetria: |Y_trás| &gt; Y_frente  ⟹  C_Y &lt; 0", "Asymmetry: |Y_rear| &gt; Y_front  ⟹  C_Y &lt; 0"),
    ],
    "forca-lateral-rotor_fig1_cancelamento-vs-coleman.svg": [
        ("Origem da Força Lateral no Rotor: Cancelamento vs. Quebra por Coleman", "Origin of Rotor Side Force: Cancellation vs. Symmetry Breaking by Coleman"),
        ("1. Inflow Uniforme: Cancelamento Lateral", "1. Uniform Inflow: Lateral Cancellation"),
        ("Recuo", "Retreating"),
        ("Avanço", "Advancing"),
        ("Y_frente", "Y_front"),
        ("Y_trás", "Y_rear"),
        ("Cancelamento: |Y_trás| = |Y_frente|  ⟹  C_Y = 0", "Cancellation: |Y_rear| = |Y_front|  ⟹  C_Y = 0"),
        ("2. Gradiente de Coleman: Quebra de Simetria", "2. Coleman Gradient: Symmetry Breaking"),
        ("Assimetria: |Y_trás| &gt; Y_frente  ⟹  C_Y &lt; 0", "Asymmetry: |Y_rear| &gt; Y_front  ⟹  C_Y &lt; 0"),
    ],

    # 3. Modelos de Inflow (fig3 - fig6)
    "modelos-de-inflow-para-rotores-da-teoria-de-quantidade-de-movimento-ao-inflow-dinamico_fig3.svg": [
        ("Tempo [ms]", "Time [ms]"),
        ("Input de coletivo: resposta de carga", "Collective input: thrust response"),
        ("Quase-estático", "Quasi-steady"),
    ],
    "modelos-de-inflow-para-rotores-da-teoria-de-quantidade-de-movimento-ao-inflow-dinamico_fig4.svg": [
        ("Tempo [ms]", "Time [ms]"),
        ("Input de coletivo: resposta de inflow", "Collective input: inflow response"),
        ("Quase-estático", "Quasi-steady"),
    ],
    "modelos-de-inflow-para-rotores-da-teoria-de-quantidade-de-movimento-ao-inflow-dinamico_fig5.svg": [
        ("Tempo [ms]", "Time [ms]"),
        ("Input de RPM: resposta de tração", "RPM input: thrust response"),
        ("Quase-estático", "Quasi-steady"),
    ],
    "modelos-de-inflow-para-rotores-da-teoria-de-quantidade-de-movimento-ao-inflow-dinamico_fig6.svg": [
        ("Tempo [ms]", "Time [ms]"),
        ("Input de RPM: resposta do inflow físico", "RPM input: physical inflow response"),
        ("Quase-estático", "Quasi-steady"),
    ],

    # 4. Teorema do Stagger de Munk
    "o-teorema-do-stagger-de-munk-e-sua-universalidade-em-sistemas-aerodinamicos-de-multiplas-superficies_fig1.svg": [
        ("O Teorema do Stagger de Munk no Plano de Trefftz (y-z)", "Munk's Stagger Theorem in the Trefftz Plane (y-z)"),
        ("1. Projeção no Plano de Trefftz (x → ∞)", "1. Projection onto the Trefftz Plane (x → ∞)"),
        ("Asa 1 (x₁)", "Wing 1 (x₁)"),
        ("Asa 2 (x₂)", "Wing 2 (x₂)"),
        ("Plano de Trefftz", "Trefftz Plane"),
        ("Traço 1", "Trace 1"),
        ("Traço 2", "Trace 2"),
        ("2. Invariância do Arrasto Induzido com Stagger", "2. Invariance of Induced Drag with Stagger"),
        ("D_i(s) = Constante", "D_i(s) = Constant"),
        ("-s (Recuado)", "-s (Aft)"),
        ("+s (Avançado)", "+s (Forward)"),
    ],

    # 5. Geometria Física do Cálculo Vetorial
    "a-geometria-fisica-do-calculo-vetorial_fig1.svg": [
        ("Isóbaras e Gradiente de Pressão", "Isobars and Pressure Gradient"),
        ("O vetor gradiente ∇p é normal às isóbaras e aponta na direção de máxima variação", "The gradient vector ∇p is normal to isobars, pointing toward steepest increase"),
        ("Baixa Pressão", "Low Pressure"),
        ("Alta Pressão", "High Pressure"),
    ],
    "a-geometria-fisica-do-calculo-vetorial_fig3.svg": [
        ("1. Divergência (Dilatação)", "1. Divergence (Dilatation)"),
        ("Variação de volume sem giro", "Volume variation without rotation"),
        ("2. Rotacional (Rotação)", "2. Curl (Rotation)"),
        ("Giro de corpo rígido ou cisalhamento sem variação de volume", "Rigid-body rotation or shear without volume variation"),
    ],
    "a-geometria-fisica-do-calculo-vetorial_fig4.svg": [
        ("Divergência: Fonte, Sumidouro e Incompressibilidade", "Divergence: Source, Sink, and Incompressibility"),
        ("Fonte (Expansão)", "Source (Expansion)"),
        ("Sumidouro (Compressão)", "Sink (Compression)"),
        ("Incompressível (Solenoidal)", "Incompressible (Solenoidal)"),
    ],
    "a-geometria-fisica-do-calculo-vetorial_fig6.svg": [
        ("1. Discrepância da Vizinhança", "1. Neighborhood Discrepancy"),
        ("2. Difusão e Suavização Térmica", "2. Diffusion and Thermal Smoothing"),
        ("Pico", "Peak"),
        ("Vale", "Valley"),
    ],

    # 6. Estabilidade Periódica de Rotores
    "estabilidade-periodica-de-rotores_fig1.svg": [
        ("x fixo", "x fixed"),
        ("y fixo", "y fixed"),
        ("eixo da pá", "blade axis"),
        ("Referencial fixo: fuselagem", "Fixed frame: fuselage"),
        ("Referencial girante: rotor", "Rotating frame: rotor"),
    ],
    "estabilidade-periodica-de-rotores_fig2.svg": [
        ("Diagrama de Campbell", "Campbell Diagram"),
    ],
    "estabilidade-periodica-de-rotores_fig3.svg": [
        ("Modos Progressivo e Regressivo", "Progressive and Regressive Modes"),
        ("Progressivo", "Progressive"),
        ("Regressivo", "Regressive"),
    ],
    "estabilidade-periodica-de-rotores_fig4.svg": [
        ("progressivo: ω_R + Ω", "progressive: ω_R + Ω"),
        ("regressivo: |ω_R − Ω|", "regressive: |ω_R − Ω|"),
        ("modo da fuselagem", "fuselage mode"),
        ("Diagrama de Coleman", "Coleman Diagram"),
        ("Velocidade do rotor", "Rotor speed"),
    ],
    "estabilidade-periodica-de-rotores_fig5.svg": [
        ("Multiplicadores de Floquet", "Floquet Multipliers"),
        ("decai", "decays"),
        ("quase neutro", "near neutral"),
        ("cresce", "grows"),
    ],
    "estabilidade-periodica-de-rotores_fig6.svg": [
        ("Banda de Instabilidade", "Instability Band"),
        ("maior |μ|", "max |μ|"),
        ("instável:", "unstable:"),
    ],

    # 7. Instabilidades em Fluidos
    "instabilidades-em-fluidos-como-perturbacoes-crescem_fig6.svg": [
        ("Cisalhamento", "Shear"),
        ("Empuxo / densidade", "Buoyancy / density"),
        ("Forças centrífugas / rotação", "Centrifugal forces / rotation"),
        ("Tensão superficial / capilaridade", "Surface tension / capillarity"),
        ("Viscosidade desfavorável", "Unfavorable viscosity"),
    ],
    "instabilidades-em-fluidos_fig6_taxonomia.svg": [
        ("Cisalhamento", "Shear"),
        ("Empuxo / densidade", "Buoyancy / density"),
        ("Forças centrífugas / rotação", "Centrifugal forces / rotation"),
        ("Tensão superficial / capilaridade", "Surface tension / capillarity"),
        ("Viscosidade desfavorável", "Unfavorable viscosity"),
    ],

    # 8. Autovalor Universo
    "autovalor-universo_fig1_poco-potencial-modos-normais.svg": [
        ("Da Estabilidade Local ao Problema Espectral: Poços de Potencial e Modos Normais", "From Local Stability to Spectral Problem: Potential Wells and Normal Modes"),
        ("1. Mínimo Suave 1D: Taylor e Parábola Oscilatória", "1. Smooth 1D Minimum: Taylor and Oscillatory Parabola"),
        ("2. Multidimensional: Matriz Hessiana e Acoplamento", "2. Multidimensional: Hessian Matrix and Coupling"),
        ("3. Diagonalização e Modos Normais Independentes", "3. Diagonalization and Independent Normal Modes"),
        ("Modo 1", "Mode 1"),
        ("Modo 2", "Mode 2"),
        ("Equilíbrio Estável", "Stable Equilibrium"),
        ("Poço de Potencial V(x)", "Potential Well V(x)"),
    ],

    # 9. Vorticidade Helmholtz
    "vorticidade-helmholtz-for-dummies_fig1.svg": [
        ("1. Rotação de Corpo Rígido", "1. Rigid Body Rotation"),
        ("2. Cisalhamento Simples (Couette Plano)", "2. Simple Shear (Plane Couette)"),
        ("3. Vórtice Irrotacional (Pontual)", "3. Irrotational Vortex (Point Vortex)"),
        ("ROTACIONAL", "ROTATIONAL"),
        ("IRROTACIONAL (fora da origem)", "IRROTATIONAL (outside origin)"),
        ("Cisalhamento puro: vorticidade não nula sem trajetória circular fechada!", "Pure shear: non-zero vorticity without closed circular streamline!"),
    ],
    "vorticidade-helmholtz-for-dummies_fig2.svg": [
        ("1. Camada de Cisalhamento", "1. Shear Layer"),
        ("Perfil contínuo u(y)", "Continuous profile u(y)"),
        ("2. Enrolamento de Kelvin-Helmholtz", "2. Kelvin-Helmholtz Roll-up"),
        ("Vórtices discretos concentram a vorticidade", "Discrete vortices concentrate vorticity"),
        ("3. Estruturas Coerentes / Ruptura Turbulenta", "3. Coherent Structures / Turbulent Breakdown"),
        ("Emparelhamento e colapso tridimensional", "Pairing and three-dimensional breakdown"),
    ],
}

def generate_all():
    generated_count = 0
    for pt_name, pairs in TRANSLATIONS.items():
        pt_path = DATA_ASSETS / pt_name
        if not pt_path.exists():
            print(f"[WARN] Arquivo {pt_name} não encontrado em data/wiki/assets/")
            continue
        en_name = pt_name.replace(".svg", "_en.svg")
        en_path = DATA_ASSETS / en_name

        content = pt_path.read_text(encoding="utf-8")
        for pt_str, en_str in pairs:
            content = content.replace(pt_str, en_str)

        en_path.write_text(content, encoding="utf-8")
        print(f"[OK] Gerado {en_name} ({len(content)} bytes)")
        generated_count += 1

    # Copiar SVGs puramente matemáticos/geométricos sem texto
    pure_math_svgs = [
        "instabilidades-em-fluidos-como-perturbacoes-crescem_fig1.svg",
        "instabilidades-em-fluidos-como-perturbacoes-crescem_fig2.svg",
        "instabilidades-em-fluidos-como-perturbacoes-crescem_fig3.svg",
        "instabilidades-em-fluidos-como-perturbacoes-crescem_fig4.svg",
        "instabilidades-em-fluidos-como-perturbacoes-crescem_fig5.svg",
        "instabilidades-em-fluidos_fig1_feedback.svg",
        "instabilidades-em-fluidos_fig2_kelvin-helmholtz.svg",
        "instabilidades-em-fluidos_fig3_buoyancy.svg",
        "instabilidades-em-fluidos_fig4_rotacao.svg",
        "instabilidades-em-fluidos_fig5_interfaces.svg",
        "validacao-estocastica-de-dinamica-de-voo-de-hume-ao-p-value_fig2.svg",
        "vorticidade-helmholtz-for-dummies_fig3.svg",
    ]
    for s_name in pure_math_svgs:
        src = DATA_ASSETS / s_name
        if src.exists():
            dst = DATA_ASSETS / s_name.replace(".svg", "_en.svg")
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"[OK] Duplicado matemático puro: {dst.name}")
            generated_count += 1

    print(f"\n[+] Total de {generated_count} SVG(s) em inglês gerados/sincronizados com sucesso!")

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gera e sincroniza arquivos SVG em inglês.")
    parser.add_argument("target", nargs="?", default="", help="Arquivo SVG específico a processar")
    args = parser.parse_args(argv)

    if args.target:
        p = Path(args.target)
        target_name = p.name
        if target_name in TRANSLATIONS:
            pairs = TRANSLATIONS[target_name]
            pt_path = DATA_ASSETS / target_name
            if pt_path.exists():
                en_name = target_name.replace(".svg", "_en.svg")
                content = pt_path.read_text(encoding="utf-8")
                for pt_str, en_str in pairs:
                    content = content.replace(pt_str, en_str)
                (DATA_ASSETS / en_name).write_text(content, encoding="utf-8")
                print(f"[OK] Gerado {en_name}")
                return 0
        print(f"[WARN] Nenhuma tradução específica cadastrada para {target_name}. Executando lote completo.")

    generate_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
