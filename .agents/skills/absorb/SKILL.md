---
name: absorb
description: >
  Incorpora uma fonte já processada a essays, concepts ou entities existentes.
  Use quando o Usuário pedir explicitamente que conteúdo arquivado em
  wiki/sources/ enriqueça páginas da wiki; para apenas resumir, use /digest.
metadata:
  second-brain-role: "source-integrator"
  second-brain-mode: "write"
  second-brain-scope: "wiki-pages"
  second-brain-approval: "conditional"
  second-brain-closure: "multi-page"
allowed-tools: Bash Read Write Edit Glob Grep AskUserQuestion
---
# Absorb

Incorpora o conteúdo de uma fonte já arquivada em `wiki/sources/` a páginas existentes da wiki (essays, concepts, entities). Só roda sob pedido explícito; `/digest` nunca o chama automaticamente.

## Fluxo de Execução

1. **Definição de alvos:**
   - Confirme com o Usuário quais páginas devem ser enriquecidas.
   - Caso não especificado, consulte o resumo em `wiki/sources/resumos/<slug>.md` e busque candidatos via `qmd query "termos centrais"` antes de editar.
2. **Leitura da fonte:**
   - Consulte o resumo em `wiki/sources/resumos/` ou o texto original em `wiki/sources/<subpasta>/`.
3. **Atualização substantiva:**
   - Adicione conteúdo denso e profundo nas páginas alvo; evite inserções superficiais.
   - Adicione o arquivo ao campo `sources:` do frontmatter de cada página tocada.
   - Se adicionar entrada em `## Referências`, consulte `wiki/references.md` para reaproveitar citações canônicas existentes.
4. **Conexões internas:**
   - Atualize `## Conexões` nas páginas afetadas, garantindo bidirecionalidade quando fizer sentido (`conventions/SKILL.md`).
5. **Páginas de apoio:**
   - Se surgir conceito ou entidade relevante sem página própria, crie o stub correspondente reutilizando o vocabulário de `tags:`.
6. **Catálogos e derivados:**
   - Atualize `wiki/sources/map.md` (ex.: `Status: "Absorvido em [[pagina-a]], [[pagina-b]]"`).
   - Complete `manifest.md` se faltar `Tags:` ou entrada para a fonte.
   - Regenere derivados de referências se houver novas citações:
     ```bash
     python scripts/build_references.py
     ```
7. **Fechamento:**
   - Execute o fechamento padrão para cada essay tocado.
   - Registre em `wiki/log.md`:
     ```markdown
     ## [YYYY-MM-DD] absorb | Fonte → páginas afetadas
     ```

## Regras e Convenções

- **Contradições:** se a fonte contradiz conteúdo pré-existente, sinalize ambas as versões ao Usuário e aguarde decisão editorial; não substitua silenciosamente.
- **Handouts:** se a alteração em um essay mudar sua tese central, avise o Usuário e ofereça `/handout`.
- Prosa e referências seguem integralmente `conventions/SKILL.md`.

## Skills relacionadas

- `/digest` — etapa anterior de resumo e arquivamento de terceiros
- `/expand` — adição de conteúdo avulso por solicitação direta
- `/chapter`, `/insight`
