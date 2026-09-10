# 🛠️ Catálogo de Scripts e Ferramentas CLI

> Documentação canônica dos scripts executáveis e ferramentas de linha de comando do **`second-brain-engine`**.

Todos os scripts executáveis vivem em `scripts/` e seguem a **regra dos defaults sem argumentos**: executados sem parâmetros posicionais, executam a auditoria mais ampla, constroem todos os artefatos aplicáveis ou realizam diagnósticos globais seguros.

---

## 🧭 Convenção de Nomes Mnemônicos

Os scripts utilizam prefixos verbais padronizados que revelam imediatamente sua função:

| Prefixo | Papel | Exemplos |
| :--- | :--- | :--- |
| **`check_`** | Diagnóstico e validação read-only (não altera arquivos). | `check_repo.py`, `check_git_isolation.py`, `check_site_privacy.py` |
| **`build_`** | Compilação e geração de artefatos derivados estruturados. | `build_index.py`, `build_site.py`, `build_graph.py` |
| **`export_`** | Exportação de ensaios individuais ou em lote para formatos externos. | `export_essay_html.py`, `export_essay_pdf.py` |
| **`find_`** | Localização, pesquisa e rastreamento de referências na base. | `find_text.py`, `find_backlinks.py` |
| **`fix_`** | Correções mecânicas automatizadas e determinísticas de formatação. | `fix_lint.py` |
| **`set_`** | Mutadores explícitos de metadados no frontmatter dos arquivos. | `set_visibility.py` |

---

## 📋 Catálogo Completo por Categoria

### 1. Qualidade e Diagnóstico do Repositório

| Script | Finalidade | Exemplo de Uso |
| :--- | :--- | :--- |
| **`check_repo.py`** | Portal unificado de qualidade do repositório (grupos: `--quick`, `--wiki`, `--exports`, `--site`, `--architecture`, `--full`). | `python scripts/check_repo.py --quick` |
| **`check_git_isolation.py`** | Valida a disciplina e o isolamento entre os três repositórios Git aninhados (`.`, `data/`, `site/`). | `python scripts/check_git_isolation.py` |
| **`check_path_discipline.py`** | Garante que scripts e testes usem `repo_paths.py` e não caminhos hardcoded. | `python scripts/check_path_discipline.py` |
| **`check_script_defaults.py`** | Audita se todos os scripts CLI em `scripts/` respeitam a regra de default sem argumentos e se o catálogo está alinhado. | `python scripts/check_script_defaults.py` |
| **`check_skills.py`** | Valida frontmatter, metadata, ferramentas, referências e contratos normativos de todas as skills em `.agents/skills/`. | `python scripts/check_skills.py` |
| **`sync_skills.py`** | Espelha `.agents/skills/` e `.agents/agents/` em `.claude/`. `--check` detecta drift sem escrever; `--quiet` é o modo do hook `SessionStart`. | `python scripts/sync_skills.py` |
| **`check_env.py`** | Diagnostica dependências do ambiente Python e ferramentas externas (Pandoc, LuaLaTeX, Playwright). | `python scripts/check_env.py` |

### 2. Publicação e Atlas Web (`site/`)

| Script | Finalidade | Exemplo de Uso |
| :--- | :--- | :--- |
| **`set_visibility.py`** | Define o nível de visibilidade de essays (`allow`, `deny`, `hide`, `set-exclusive`) no frontmatter. | `python scripts/set_visibility.py allow dutch-roll` |
| **`check_visibility_field.py`** | Audita a conformidade e os valores válidos do campo `visibility:` em todos os essays da wiki. | `python scripts/check_visibility_field.py` |
| **`check_essay_slugs.py`** | Garante que todo arquivo em `wiki/essays/` seja o slug ASCII em `kebab-case` de seu H1 completo. | `python scripts/check_essay_slugs.py` |
| **`rename_essay_files.py`** | Migra os arquivos de essays para o slug completo do H1 e reaponta wikilinks e assets de figuras. | `python scripts/rename_essay_files.py --apply` |
| **`visibility.py`** | Leitor utilitário que relata a distribuição de visibilidade do corpus (público, privado, oculto). | `python scripts/visibility.py` |
| **`build_site.py`** | Compila os essays autorizados para HTML e gera os índices e mapas interativos em `site/`. | `python scripts/build_site.py` |
| **`publish_site.py`** | Comando único de publicação: valida visibilidade, constrói, sela, cria o commit em `site/` e envia para `main`. Exige os três repositórios limpos e sincronizados. | `python scripts/publish_site.py` |
| **`check_site_privacy.py`** | **Sentinela estrita de privacidade**: garante que nenhum texto ou link não autorizado chegue a `site/`. | `python scripts/check_site_privacy.py` |
| **`check_site_pages.py`** | Abre cada página do site construído num navegador real (celular e desktop) e audita overflow, imagens, âncoras, console e vazamento de Markdown, mais uma auditoria própria de `graph.html` e `sphere.html`. Sem navegador é **erro**; `--allow-skip-browser` degrada para SKIP em diagnóstico local. | `python scripts/check_site_pages.py` |
| **`check_site_budget.py`** | Orçamento de tamanho por artefato público e do site inteiro. | `python scripts/check_site_budget.py` |
| **`seal_publication.py`** | Reexecuta os gates de publicação e sela `site-manifest.json` com o commit do engine e a impressão do artefato público. | `python scripts/seal_publication.py` |
| **`build_favicons.py`** | Assa o ícone do Atlas a partir da arte-mestra em `site_src/brand/`: recorta o xadrez por croma, recolore a variante dourada, engrossa o traço nos tamanhos pequenos e grava PNG, apple-touch e `.ico`. | `python scripts/build_favicons.py` |
| **`check_agents.py`** | Coerência da arquitetura de agentes: `.agents/` como fonte, espelhos `.claude/`, adaptadores `.codex/`, hook de sync e documentação. | `python scripts/check_agents.py` |
| **`serve_site.py`** | Inicia servidor HTTP local leve para inspecionar e testar o Atlas gerado antes do deploy. | `python scripts/serve_site.py` |

### 3. Manutenção da Wiki e Conteúdo (`data/`)

| Script | Finalidade | Exemplo de Uso |
| :--- | :--- | :--- |
| **`close_workspace.py`** | Fecha o workspace de forma determinística. Sem subcommand executa `prepare`; `commit` roda `prepare` antes dos commits locais; `push` exige worktrees limpas. | `python scripts/close_workspace.py` |
| **`build_index.py`** | Gera o catálogo consolidado de ensaios em `wiki/index.md` e `wiki/index.json`. | `python scripts/build_index.py` |
| **`build_references.py`** | Consolida a bibliografia de todas as fontes em `wiki/references.md` e `.json`. | `python scripts/build_references.py` |
| **`build_graph.py`** | Gera a visualização interativa do grafo 2D de conexões em `output/graph/`. | `python scripts/build_graph.py` |
| **`build_sphere.py`** | Gera a visualização tridimensional interativa em esfera de nós conceituais. | `python scripts/build_sphere.py` |
| **`stats.py`** | Gera o dashboard analítico de saúde e métricas do corpus em `output/stats/`. | `python scripts/stats.py --save` |
| **`check_wiki.py`** | Auditoria de estrutura, callouts, figuras, referências e sinais editoriais; `--strict` bloqueia CI em erros objetivos. | `python scripts/check_wiki.py --strict` |
| **`check_references.py`** | Valida integridade e completude das referências bibliográficas dos ensaios. | `python scripts/check_references.py` |
| **`check_dedupe.py`** | Detecta potenciais duplicidades conceituais e quase-duplicatas na wiki. | `python scripts/check_dedupe.py` |
| **`check_freshness.py`** | Sinaliza ensaios com alegações temporais antigas que necessitam de revisão. | `python scripts/check_freshness.py` |
| **`check_gaps.py`** | Identifica lacunas léxicas, mecânicas e semânticas entre os nós da base. | `python scripts/check_gaps.py` |
| **`check_title.py`** | Valida convenções tipográficas e ortográficas nos títulos de ensaios. | `python scripts/check_title.py` |
| **`fix_lint.py`** | Aplica correções mecânicas automatizadas (remoção de tags redundantes, ordenação, etc.). | `python scripts/fix_lint.py` |
| **`retag.py`** | Utilitário para renomear ou migrar tags em lote nos arquivos da wiki. | `python scripts/retag.py tagA tagB` |
| **`migrate_private_data.py`** | Utilitário para migração e reestruturação controlada do diretório de dados. | `python scripts/migrate_private_data.py` |

### 4. Exportações Standalone e Validação

| Script | Finalidade | Exemplo de Uso |
| :--- | :--- | :--- |
| **`export_essay_html.py`** | Exporta um ou todos os essays para HTML standalone autocontido com MathJax local. | `python scripts/export_essay_html.py <slug>` |
| **`export_essay_pdf.py`** | Exporta um ou todos os essays para PDF de alta qualidade tipográfica via Pandoc + LuaLaTeX. | `python scripts/export_essay_pdf.py <slug>` |
| **`check_html_structure.py`** | Valida a estrutura DOM, cabeçalhos, links internos e ausência de resíduos no HTML gerado. | `python scripts/check_html_structure.py <slug>` |
| **`check_html_browser.py`** | Abre o HTML em navegador headless (Playwright) validando layout responsivo e ausência de erros. | `python scripts/check_html_browser.py <slug>` |
| **`check_pdf_content.py`** | Valida o conteúdo textual e estrutural do PDF exportado (Páginas, Sumário, Citações). | `python scripts/check_pdf_content.py <slug>` |
| **`check_pdf_layout.py`** | Valida o layout visual do PDF (viúvas, órfãs, margens e paginação). | `python scripts/check_pdf_layout.py <slug>` |
| **`check_export_parity.py`** | Comprova a paridade semântica exata entre os artefatos Markdown, HTML e PDF. | `python scripts/check_export_parity.py <slug>` |

### 5. Busca, Navegação e Utilitários

| Script | Finalidade | Exemplo de Uso |
| :--- | :--- | :--- |
| **`find_text.py`** | Busca textual contextualizada com suporte a regex no corpus da wiki. | `python scripts/find_text.py "termo"` |
| **`find_backlinks.py`** | Rastreia e lista todas as páginas que apontam para um determinado conceito ou ensaio. | `python scripts/find_backlinks.py <slug>` |
| **`mermaid_to_png.py`** | Converte diagramas Mermaid em imagens PNG estáticas para inclusão em documentos. | `python scripts/mermaid_to_png.py` |
| **`sync_qmd.bat` / `.sh`** | Sincroniza a coleção de busca vetorial semântica do `qmd` com a pasta de dados. | `./scripts/sync_qmd.sh` |
| **`repo_paths.py`** | Ponto canônico de resolução de diretórios dos três repositórios Git (`DATA_ROOT`, `SITE_ROOT`, etc.). | `python scripts/repo_paths.py` |
| **`bootstrap_repositories.py`** | Inicializa os esqueletos e os repositórios Git complementares (`data/` e `site/`). | `python scripts/bootstrap_repositories.py --create` |

---

## 📦 Módulos Internos (`scripts/lib/`)

Arquivos que funcionam exclusivamente como bibliotecas internas e rotinas auxiliares de build vivem na subpasta **`scripts/lib/`** e não devem ser executados diretamente como comandos CLI pelo usuário:

- **`scripts/repo_paths.py`**: Resolução lógica de caminhos e variáveis de ambiente.
- **`scripts/lib/sanity_common.py`**: Estruturas de resultado `CheckResult` e classes base de testes.
- **`scripts/lib/site_common.py`**: Helpers de build, parsing de catálogo e sanitização do site.
- **`scripts/lib/console_encoding.py`**: Configuração segura de codificação UTF-8 para stdout/stderr em Windows e POSIX.
- **`scripts/lib/html_preprocess.py`**: Filtros de pré-processamento de Markdown para renderizadores Pandoc.
- **`scripts/lib/build_public_map.py`**: Algoritmos de sanitização dos nós públicos do Atlas (grafo/esfera).
- **`scripts/lib/build_cover.py`**: Assa o retrato estático do mapa que ilustra a capa do Atlas, capturando o próprio `graph.html` num navegador headless (um PNG por tema). Chamado por `build_site.py`; sem Playwright o passo é pulado e o PNG anterior permanece.
- **`scripts/lib/render_public_essay.py`**: Compilação e estilização de páginas de leitura do site.
- **`scripts/lib/fetch_fonts.py`**: Rotina interna de download e empacotamento local de fontes tipográficas.

Cada um desses módulos tem, em `scripts/`, um arquivo homônimo curto que apenas
re-exporta a versão de `lib/`. Ele não é um comando: existe porque
dezenove scripts fazem `import console_encoding` (e afins) **antes** de importar
`repo_paths`, que é quem coloca `scripts/lib/` no `sys.path`. Sem o shim, esses
imports quebrariam. Quando o módulo de `lib/` também é um comando — hoje
`build_public_map.py`, `render_public_essay.py` e `sanity_common.py` —, o shim
precisa encaminhar o `main()`: um shim que só re-exporta transforma a execução
do comando num no-op que ainda sai com código 0. `check_script_defaults.py`
verifica isso.
