---
name: diagram
description: >
  Modela, valida e compila diagramas conceituais e arquiteturais em Mermaid e
  SVG para essays, garantindo paridade bilíngue (PT/EN) e renderização Retina 2x.
  Use quando precisar de diagramas de blocos, fluxogramas ou ilustrações técnicas.
metadata:
  second-brain-role: "visual-designer"
  second-brain-mode: "mixed"
  second-brain-scope: "single-essay"
  second-brain-approval: "none"
  second-brain-closure: "artifact"
allowed-tools: Bash Read Write Glob
---
# Diagram

**[ambos]** Modela, valida e compila diagramas em SVG e Mermaid para essays, assegurando paridade bilíngue estrita (PT/EN), gerando artefatos estáticos em `wiki/assets/` e referenciando na prosa.

## Princípios

1. **Escolha do formato**:
   - **SVG (`.svg`)**: formato padrão e mandatório para ilustrações conceituais ricas, representações físicas, geometria espacial, cinemática, perfis aerodinâmicos e gráficos técnicos.
   - **Mermaid (`.mmd`)**: indicado para fluxogramas de decisão, arquitetura de sistemas e pipelines de dados sequenciais.
2. **Paridade Bilíngue Estrita (PT / EN)**:
   - Todo diagrama visual vetorial deve ter versão em Português e versão em Inglês:
     - PT: `wiki/assets/<slug-do-essay>_fig<N>.svg`
     - EN: `wiki/assets/<slug-do-essay>_fig<N>_en.svg`
   - A versão em inglês traduz rótulos, legendas, eixos e anotações, mantendo rigorosamente idênticos o layout, cores, proporções e elementos geométricos.
   - Para diagramas puramente matemáticos ou geométricos sem texto, o arquivo `_en.svg` replica o conteúdo para garantir consistência de resolução em publicações bilíngues.
3. **Renderização de Alta Definição (Retina 2x)**:
   - Todo arquivo vetorial precisa do respectivo arquivo `.png` irmão compilado em alta fidelidade.
   - Compilação via Chromium/Playwright garante suporte integral a marcadores de setas (`<marker>`), polígonos 3D, gradientes lineares e regras CSS avançadas (que quebram em renderizadores simplificados).
4. **Legibilidade multiplataforma**:
   - Use fundos sólidos (cartões `#ffffff` ou `#f8fafc`) e texto com contraste elevado (`#0f172a`, `#1e293b`).
   - Use viewBox explícito com largura e altura bem definidas (ex.: `viewBox="0 0 1200 680"`).
   - O diagrama deve permanecer perfeitamente legível tanto em exportações para PDF/LaTeX (fundo branco) quanto no Atlas web (modos claro e escuro).
5. **Completude textual**: o diagrama apoia a prosa, mas nunca a substitui. O texto do ensaio deve descrever a lógica essencial de forma autocontida.

## Fluxo de Execução

1. Localize a seção do essay onde o diagrama será inserido.
2. **Criação do Diagrama em Português (PT)**:
   - Se for SVG: escreva `wiki/assets/<slug-do-essay>_fig<N>.svg`.
   - Se for Mermaid: escreva `wiki/assets/<slug-do-essay>_fig<N>.mmd`.
3. **Geração da Versão em Inglês (EN)**:
   - Para diagramas SVG, crie o arquivo correspondente `<slug-do-essay>_fig<N>_en.svg` ou sincronize com:
     ```bash
     python scripts/generate_en_svgs.py <slug-do-essay>_fig<N>.svg
     ```
4. **Compilação dos Binários PNG Retina 2x**:
   - Para SVGs (PT e EN):
     ```bash
     python scripts/svg_to_png.py <slug-do-essay>_fig<N>.svg
     python scripts/svg_to_png.py <slug-do-essay>_fig<N>_en.svg
     ```
   - Para diagramas Mermaid:
     ```bash
     python scripts/mermaid_to_png.py wiki/assets/<slug-do-essay>_fig<N>.mmd wiki/assets/<slug-do-essay>_fig<N>.png
     ```
5. **Inserção no Essay**:
   - Referencie o PNG relativo no ensaio conforme `conventions/SKILL.md`:
     ```markdown
     ![Descrição textual sucinta](../assets/<slug-do-essay>_fig<N>.png)

     *Figura N. Legenda descritiva do diagrama.*
     ```
6. **Validação da Wiki**:
   - Feche a edição validando o essay:
     ```bash
     python scripts/check_wiki.py <slug-do-essay>
     ```
