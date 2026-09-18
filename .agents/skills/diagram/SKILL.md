---
name: diagram
description: >
  Modela, valida e compila diagramas conceituais e arquiteturais em Mermaid
  para essays. Use quando precisar de diagramas de blocos, fluxogramas ou
  mapas estruturais com renderização estática para o corpus.
metadata:
  second-brain-role: "visual-designer"
  second-brain-mode: "mixed"
  second-brain-scope: "single-essay"
  second-brain-approval: "none"
  second-brain-closure: "artifact"
allowed-tools: Bash Read Write Glob
---
# Diagram

**[ambos]** Modela, valida e compila diagramas Mermaid para essays, gerando artefato estático em `wiki/assets/` e referenciando na prosa.

## Princípios

1. **Legibilidade multiplataforma**: use nós com preenchimento sólido (`#1E293B` ou `#FFFFFF`), bordas contrastantes e linhas de tom intermediário (`#94A3B8`, `#0EA5E9` ou `#475569`). O diagrama deve ser legível tanto em fundo branco (PDF/site claro) quanto escuro (site escuro).
2. **Sintaxe segura**: coloque sempre o texto dos nós entre aspas duplas: `id["texto"]`. Nunca use caracteres especiais (`(`, `)`, `[`, `]`) soltos no rótulo.
3. **Ergonomia visual**:
   - Limite de 7 a 12 nós por diagrama.
   - Use `subgraph` para isolar responsabilidades ou fases lógicas.
   - Use `flowchart TD` para fluxos e hierarquias verticais; `flowchart LR` para pipelines sequenciais horizontais.
4. **Completude textual**: o diagrama apoia a prosa, mas nunca a substitui. O texto deve descrever a lógica essencial do fluxo de forma autocontida.

## Fluxo de Execução

1. Localize a seção do essay onde o diagrama será inserido.
2. Escreva o código-fonte Mermaid em `wiki/assets/<slug-do-essay>_fig<N>.mmd`.
3. Compile o arquivo para PNG:
   ```bash
   python scripts/mermaid_to_png.py wiki/assets/<slug-do-essay>_fig<N>.mmd wiki/assets/<slug-do-essay>_fig<N>.png
   ```
   Se o compilador acusar erro de sintaxe, corrija o `.mmd` e repita a compilação até obter sucesso.
4. Insira a figura no essay conforme `conventions/SKILL.md`:
   ```markdown
   ![Descrição textual sucinta](../assets/<slug-do-essay>_fig<N>.png)

   *Figura N. Legenda descritiva do diagrama.*
   ```
5. Assegure a explicação dos elementos do diagrama na prosa adjacente.
6. Feche a edição validando o essay:
   ```bash
   python scripts/check_wiki.py <slug-do-essay>
   ```
