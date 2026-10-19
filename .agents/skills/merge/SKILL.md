---
name: merge
description: >
  Funde duas páginas do mesmo tipo, reaponta backlinks e remove a página
  absorvida. Use para duplicatas confirmadas; exige aprovação explícita do plano
  completo antes da primeira escrita.
metadata:
  second-brain-role: "destructive-maintenance"
  second-brain-mode: "write"
  second-brain-scope: "pages"
  second-brain-approval: "before-write"
  second-brain-closure: "multi-page"
allowed-tools: Bash Read Write Edit Glob Grep AskUserQuestion
---
# Merge

Funde duas páginas do mesmo tipo em uma só. Toda a análise e confirmação ocorrem antes da primeira escrita.

## 1. Pré-flight (somente leitura)

1. **Validação de tipos:** `/merge <slug-a> <slug-b>`. Ambas devem pertencer à mesma pasta (`essays` com `essays`, `concepts` com `concepts`, etc.). Tipos diferentes não fundem; sugira `/chapter` se for incorporar um concept em um essay.
2. **Leitura completa:** leia ambas as páginas na íntegra.
3. **Página sobrevivente:** use a indicada pelo Usuário. Se não especificada, pergunte (`AskUserQuestion`) — tipicamente a mais densa, mais antiga ou mais referenciada.
4. **Levantamento de backlinks:**
   ```bash
   python scripts/find_backlinks.py "<Título da Absorvida>"
   ```
   Cada menção deve ser reapontada para a sobrevivente.
5. **Rastro e derivados:** verifique entradas em `wiki/sources/manifest.md` e derivados a reconstruir (`build_index.py`, `build_references.py`).
6. **Plano de fusão de conteúdo:**
   - `tags`: união sem duplicatas (máximo 5; priorize as mais específicas).
   - `sources`: união sem duplicatas.
   - `created`: preserve a data mais antiga.
   - `updated`: data de hoje.
   - **Corpo:** incorpore o conteúdo exclusivo da absorvida sem duplicar argumentos equivalentes. Para essay, ajuste `## Sumário`.
   - **Contradições:** se houver teses ou dados divergentes, pare antes de escrever e consulte o Usuário conforme a regra de contradição de `conventions/SKILL.md`.

## 2. Confirmação explícita

Apresente o plano consolidado ao Usuário antes de qualquer escrita (`AskUserQuestion`):
- Página sobrevivente selecionada e página a ser removida;
- Síntese do conteúdo a ser fundido e descartado;
- Lista de backlinks que serão reapontados;
- Entradas de manifesto ou derivados a regenerar.

Prossiga apenas após confirmação explícita ("sim").

## 3. Aplicação atômica

Execute a sequência sem novas pausas (conclua a unidade inteira sem interrupção entre reapontar e apagar, evitando deixar a wiki quebrada):
1. Grave a página sobrevivente com o conteúdo fundido.
2. Reaponte cada backlink: substitua `[[slug-absorvido|...]]` por `[[slug-sobrevivente|Título Sobrevivente]]`.
3. Apague o arquivo da página absorvida.
4. Atualize `wiki/sources/manifest.md` se aplicável.
5. Regenere os derivados (`build_index.py`, `build_references.py`).
6. Registre em `wiki/log.md`:
   ```markdown
   ## [YYYY-MM-DD] merge | Título Sobrevivente ← Título Absorvido
   Fundidos N links reapontados.
   ```

## 4. Verificação

```bash
python scripts/check_wiki.py
```

A operação só é válida quando o comando passa com sucesso. Links quebrados deixados para trás configuram falha do fluxo; resolva imediatamente.

## Limites

- Nunca funde páginas de tipos diferentes.
- Nunca escreve antes da aprovação do plano consolidado.
- Não faça reescrita estilística durante a fusão; melhorias de estilo pertencem a `/polish`.

## Skills relacionadas

- `/organize` — identifica duplicatas via `check_dedupe.py`
- `/delete` — remoção sem preservação de conteúdo
- `/chapter` — incorporação de conceitos dentro de essays
