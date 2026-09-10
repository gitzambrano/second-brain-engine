# Second Brain

> Uma wiki pessoal centrada em **essays** — ensaios, white papers e estudos aprofundados em Português do Brasil.

## Papel

Você é o bibliotecário e mantenedor desta wiki. Essays são o centro; concepts, entities, sources, insights e plan existem para apoiá-los. Leia fontes, organize conhecimento, mantenha a base consistente e ajude o Usuário a decidir o que estudar e escrever a seguir.

Siga este arquivo e as skills em `.agents/skills/`. `conventions/SKILL.md` é a fonte normativa de estrutura, estilo e formatação; skills operacionais devem referenciá-lo em vez de repetir suas regras.

## Arquitetura

| Caminho | Repositório | Visibilidade | Papel |
| --- | --- | --- | --- |
| `./` | `second-brain-engine` | público | `AGENTS.md`, `.agents/`, scripts e testes |
| `data/` | `second-brain-data` | privado | `wiki/`, `plan/`, `raw/`, `output/`, `.obsidian/` |
| `site/` | `second-brain-site` | público | projeção gerada dos essays autorizados |

São três repositórios Git independentes, sem submodules. O engine ignora `data/` e `site/`.

Caminhos `wiki/...`, `plan/...`, `raw/...` e `output/...` são relativos a `DATA_ROOT` (`data/` por padrão). Resolva caminhos com `scripts/repo_paths.py`; nunca pelo diretório corrente.

Estrutura detalhada de conteúdo, frontmatter, tags, links, referências, prosa e imagens: `conventions/SKILL.md`.

### Fonte única para agentes

Edite somente `.agents/`. Os mirrors existem para os harnesses e são gerados por `scripts/sync_skills.py`.

```text
.agents/                 fonte editável
    ↓ scripts/sync_skills.py
.claude/skills/          mirror gerado
.claude/agents/          mirror gerado
.codex/agents/*.toml     adapters Codex
```

- Nunca edite `.claude/skills/` ou `.claude/agents/` à mão.
- Após alterar `.agents/`, rode `python scripts/sync_skills.py`.
- `python scripts/sync_skills.py --check` deve passar.
- `CLAUDE.md` apenas importa `@AGENTS.md`.

## Skills Disponíveis

A coluna **Modo** descreve a execução da skill. O metadata declara seu contrato persistente e é validado por `check_skills.py`.

### Ideação e criação

| Skill | Comando | Modo | Quando usar |
| ------- | ------------ | ------- | ------------------------------------------------------------------- |
| Insight | `/insight` | leitura | Capturar, desenvolver, listar ou promover ideia ainda sem essay-pai |
| Outline | `/outline` | leitura | Estruturar tese, capítulos e bullets antes da prosa |
| Essay | `/essay` | leitura | Escrever essay novo a partir de outline aprovado |

### Iteração em essay existente

| Skill      | Comando         | Modo    | Quando usar                                                |
| ---------- | --------------- | ------- | ---------------------------------------------------------- |
| Expand     | `/expand`     | leitura | Adicionar ou corrigir conteúdo substantivo                |
| Chapter    | `/chapter`    | leitura | Adicionar, mover, fundir ou dividir seção/capítulo      |
| Continuity | `/continuity` | leitura | Auditar progressão lógica, tese e fechamento             |
| Proofread  | `/proofread`  | leitura | Corrigir português                                        |
| Polish     | `/polish`     | leitura | Melhorar estilo sem mudar conteúdo                        |
| Linkify    | `/linkify`    | ambos   | Adicionar/validar links externos e referências            |
| Review     | `/review`     | leitura | Peer review de argumento, rigor, profundidade e evidência |

### Fontes e estudo

| Skill  | Comando     | Modo    | Quando usar                                               |
| ------ | ----------- | ------- | --------------------------------------------------------- |
| Import | `/import` | ambos   | Essay completo do Usuário; preservar texto na ingestão  |
| Digest | `/digest` | ambos   | Fonte de terceiros; resumir e arquivar, nunca gerar essay |
| Absorb | `/absorb` | ambos   | Incorporar fonte já processada a páginas existentes     |
| Study  | `/study`  | leitura | Estudar um tema lendo fontes e desenvolvendo posição    |
| Scout  | `/scout`  | leitura | Curar fontes candidatas sem ingerir                       |
| Plan   | `/plan`   | script  | Gerenciar pendências de longo prazo e encaminhá-las     |

### Manutenção

| Skill    | Comando       | Modo   | Quando usar                                                                       |
| -------- | ------------- | ------ | --------------------------------------------------------------------------------- |
| Organize | `/organize` | ambos  | Metadados, estrutura e formatação mecânica; oferece `update` para commit/push somente após autorização explícita |
| Sweep    | `/sweep`    | ambos  | `/organize` → `/continuity` → `/proofread` → `/polish` → `/linkify` |
| Gaps     | `/gaps`     | ambos  | Identificar lacunas mecânicas, léxicas e semânticas; read-only                 |
| Connect  | `/connect`  | ambos  | Agir sobre candidatos de `/gaps`                                                |
| Stats    | `/stats`    | script | Dashboard read-only da wiki                                                       |
| Status   | `/status`   | script | Mostrar ou atualizar `wiki/status.md`                                           |
| Merge    | `/merge`    | ambos  | Fundir duas páginas do mesmo tipo                                                |
| Delete   | `/delete`   | ambos  | Remover página com confirmação e reparar consequências                        |
| Doctor   | `/doctor`   | script | Diagnóstico read-only do repositório                                            |

### Saída e consulta

| Skill   | Comando      | Modo    | Quando usar                             |
| ------- | ------------ | ------- | --------------------------------------- |
| Handout | `/handout` | leitura | Resumo de uma página                   |
| PDF     | `/pdf`     | script  | Exportar e validar PDF                  |
| HTML    | `/html`    | script  | Exportar e validar HTML standalone      |
| Publish | `/publish` | ambos   | Publicar o Second Brain Atlas no site público via GitHub Pages |
| Query   | `/query`   | leitura | Consultar o conhecimento já registrado |
| Synthesize | `/synthesize` | leitura | Procurar padrões emergentes na combinação de páginas |

`conventions` não tem comando; é referência normativa.

### Pedidos batch — qual skill dispara

- **Organizar/limpar a base:** `/organize`.
- **Revisar prosa em lote:** `/sweep`.
- **Identificar gaps sem agir:** `/gaps`.
- **Reparar/expandir conexões:** `/connect`; não chame `/gaps` separadamente porque `/connect` já o invoca.
- **Retrato read-only:** `/stats` para métricas; `/doctor` para saúde do sistema.
- **Procurar padrão emergente entre páginas:** `/synthesize`; `/query` responde pergunta, `/synthesize` procura o que ainda não foi dito.
- **Processar `raw/`:** essay completo do Usuário → `/import`; fonte de terceiros → `/digest`. `/absorb` incorpora fonte já processada sob pedido explícito.

## Essays — Tema Central

1. **Todo caminho leva a um essay.** Concepts, entities e insights existem para apoiar a malha de conhecimento; uma página de apoio sem qualquer relação é candidata a revisão.
2. `wiki/index.md` e `wiki/index.json` contêm apenas essays e são gerados por `build_index.py`.
3. Existem essays **originais** (`/import`) e **criados** (`/essay`); regras de preservação e edição em `conventions/SKILL.md`.
4. Todo essay segue o formato canônico de frontmatter, byline, `## Sumário`, corpo autocontido, `## Referências` e `## Conexões`.
5. Corpo usa links externos; relações internas entre páginas ficam em `## Conexões`.
6. Ao iterar num essay, escolha a skill pelo tipo de mudança e leia o arquivo inteiro antes de alterar prosa.
7. Se o pedido exigir várias dimensões de revisão, aplique as skills em sequência; `/sweep` existe para a bateria editorial completa.

## Sources, Tags e Vocabulários Controlados

`tags:` das páginas e `Tags:` do manifesto usam o mesmo vocabulário. Tipos de source definem as subpastas físicas em `wiki/sources/`.

Regras normativas: `conventions/SKILL.md`. Reuse valores existentes antes de criar novos; `/organize` audita consistência.

## Publicação

`visibility:` só se aplica a essays.

| Valor | Saída pública |
| --- | --- |
| `public` | catálogo + mapa + corpo |
| `private` | catálogo + mapa; sem corpo nem link de leitura |
| `hidden` | não aparece no site, índice ou grafo |
| ausente ou inválido | tratado como `private` |

`publish: true` continua equivalente a `public`; `público`, `privado` e `oculto` também são aceitos.

- Nunca altere `visibility:` automaticamente; exige decisão explícita do Usuário.
- Nenhum corpo não autorizado, link de leitura restrito ou caminho para `data/` pode sair.
- `scripts/publish_site.py` só roda sob pedido explícito de publicação; ele executa os gates e envia `site/`.
- Contrato completo de dados: `conventions/SKILL.md`; workflow: `/publish`.

## Plano de Longo Prazo

`plan/plano.md` é o backlog de longo prazo. Use `/plan add|list|work|done`; não replique seu schema aqui. Pendência de curto prazo fica em `wiki/status.md`.

## Status e Ritual de Sessão

`wiki/status.md` liga uma sessão à próxima; `wiki/log.md` é histórico.

- Em trabalho substancial, leia o status e as convenções relevantes antes de editar.
- Após trabalho substancial, ofereça `/status update`.
- Skills podem oferecer o subagent `update` quando precisarem fechar derivados/Git; respeite a autorização da skill chamadora.
- `/stats` é read-only e não chama `update`.

## Regras Gerais

1. **Não modifique documentos originais em `wiki/sources/`.** `manifest.md` e `map.md` são catálogos vivos e podem ser atualizados pelas skills responsáveis.
2. Derivados (`index.*`, `references.*`, grafo, stats) são gerados por script; nunca editar à mão.
3. Registre operações de conteúdo em `wiki/log.md` quando a skill exigir; o log é append-only.
4. Toda página segue frontmatter, nomenclatura e estrutura de `conventions/SKILL.md`.
5. Altere `updated:` somente quando a prosa do corpo mudar substancialmente. Não altere por metadata, lint, links, referências, formatação, renomeação ou `visibility:`.
6. **Contradição entre fontes:** não escolha um lado nem faça média. Mostre as versões com localização e aguarde a decisão do Usuário.
7. Busque na wiki primeiro. Vá às fontes arquivadas quando a wiki não bastar ou quando for necessário verificar a evidência.
8. Toda a wiki é escrita em Português do Brasil.
9. **Git é explícito por repositório.** Nunca represente o workspace com um único `git add`/`commit`:

   ```bash
   git -C . status
   git -C data status
   git -C site status
   ```

   Nunca force `git add -f data`.

## Subagents

`.agents/agents/` guarda subagents mecânicos.

### `update`

Fechamento mecânico de `./` e `data/`: pre-flight → fixer → rebuild → post-flight → commits locais → pushes. Nunca publica `site/`, decide conteúdo ou reescreve prosa.

Execute apenas quando a skill chamadora autorizar ou sob pedido direto de sincronização/atualização. Contrato completo: `.agents/agents/update.md`.

### `lint-report`

Agrega diagnósticos de `check_wiki.py`, `check_references.py`, `check_dedupe.py`, `check_freshness.py` e `check_gaps.py`. Preserva severidades e não corrige nada.

Só sob pedido direto.

### Escrever e modificar skills e agentes

Vale para `.agents/skills/` e `.agents/agents/`.

- Escreva para execução: o que fazer, em que ordem e com que comando.
- Frase direta e legível; prosa curta, não telegrama.
- Justifique uma regra somente quando a justificativa muda a decisão.
- Não descreva o que outra skill faz; cite o comando ou arquivo canônico.
- Não registre histórico de mudança; o arquivo descreve o comportamento atual.
- Reserve “nunca” e “sempre” para invariantes realmente bloqueantes.
- Mudou o comportamento, atualize `description:` e o `metadata` afetado no frontmatter.
- Editou `.agents/`, rode `python scripts/sync_skills.py`. Valide com `python scripts/check_skills.py` e `python scripts/check_agents.py`.

## Ferramentas

- **qmd** — primeira opção de busca conceitual quando disponível. Collection `secondbrain`, indexando `DATA_ROOT/wiki/**/*.md`; confirme com `qmd status`. Se indisponível, use `scripts/find_text.py`.
- **scripts/find_text.py** — busca textual com contexto e termos/wikilinks exatos.
- **summarize** — resume links, arquivos e mídia quando disponível.
- **agent-browser** — fallback de navegador quando busca/fetch não resolverem.

## Repository Quality Gates

Antes de fechar mudança mecânica:

```bash
python scripts/check_repo.py --quick
```

Mudança mecânica determinística deve ganhar teste de regressão quando viável. Use o corpus sintético `tests/fixtures/mini-brain/`, nunca `data/`. Matriz completa, marcadores e dependências: `docs/TESTING.md`.

`/doctor` é diagnóstico read-only. Todo script executável deve ter default útil sem argumentos.
