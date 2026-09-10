# 🧠 Second Brain Engine

> Motor computacional e infraestrutura de agentes para uma wiki pessoal centrada em **ensaios (*essays*), artigos (*white papers*) e estudos aprofundados** em Português do Brasil.

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Tests-Pytest-green.svg)](TESTING.md)
[![Atlas](<https://img.shields.io/badge/Atlas-Live%20Site-orange.svg>)](https://gitzambrano.github.io/second-brain-site/)

🔗 **Atalhos rápidos:**

- **[Atlas ao Vivo](https://gitzambrano.github.io/second-brain-site/)** — o site público do Second Brain: o ideário de essays, white papers e estudos, com o catálogo completo, o grafo de conexões entre essays, conceitos, entidades e referências, e o globo, que é o mesmo mapa numa esfera. O catálogo e os mapas cobrem a base inteira; o texto só abre para o que foi explicitamente autorizado.
- **[`AGENTS.md`](./AGENTS.md)** — regras operacionais, routing e convenções de agentes.
- **[`conventions/SKILL.md`](./.agents/skills/conventions/SKILL.md)** — especificação normativa de formato, estilo e frontmatter.
- **[`TESTING.md`](./TESTING.md)** — suíte de testes, fixtures e quality gates do repositório.

---

## 🏛️ Arquitetura de Repositórios

O projeto separa estritamente o **motor de código** do **conhecimento pessoal** e da **publicação web**. Três repositórios Git independentes convivem no mesmo workspace sem submodules:

| Repositório | Caminho | Visibilidade | Responsabilidade |
| :-------------------------------- | :------------ | :----------------- | :------------------------------------------------------------------------------------------------------------------------------ |
| **`second-brain-engine`** | `./` (raiz) | **Público** | Agentes (`.agents/`), scripts de automação, testes, templates do site e pipelines de qualidade. |
| **`second-brain-data`** | `data/` | **Privado** | Corpus Markdown, fontes, plano, estado da wiki e configuração portátil do Obsidian. |
| **`second-brain-site`** | `site/` | **Público** | Projeção estática gerada via GitHub Pages contendo o [Second Brain Atlas](https://gitzambrano.github.io/second-brain-site/). |

> [!NOTE]
> `data/` e `site/` são integralmente ignorados pelo Git do engine. O engine funciona de forma 100% autônoma para desenvolvimento e testes usando o corpus sintético (`tests/fixtures/mini-brain/`).

### Obsidian no fluxo de trabalho

`data/` é ao mesmo tempo a raiz do repositório privado **`second-brain-data`** e o **vault do Obsidian**. Abra `data/` no Obsidian — não `data/wiki/`.

O Obsidian é a interface humana para ler, navegar e editar o corpus. Agents e scripts trabalham diretamente nos mesmos arquivos Markdown; não existe banco ou etapa de sincronização intermediária e o Obsidian não precisa estar aberto para o engine funcionar.

A configuração portátil do vault também fica em `data/.obsidian/`:

- **Versionado:** preferências do app e aparência, plugins habilitados, configuração do grafo, hotkeys, snippets e `data.json` dos plugins.
- **Local apenas:** `workspace*`, cache e código/binários instalados de plugins de terceiros.

Assim, Git versiona o **conhecimento** e a **configuração reproduzível** do vault, mas não o estado efêmero de uma sessão do Obsidian.

### Ferramentas principais

| Ferramenta | Papel |
| --- | --- |
| **Obsidian** | leitura, navegação e edição humana do corpus |
| **qmd** | busca semântica e embeddings de `DATA_ROOT/wiki` |
| **pytest** | testes de regressão e contratos do engine |
| **Pandoc** | transformação Markdown/HTML e base dos exports |
| **LuaLaTeX** | geração tipográfica de PDF |
| **Playwright + Chromium** | validação real de browser, desktop e mobile |
| **GitHub Pages** | publicação do Atlas |

A collection qmd `secondbrain` deve apontar para `DATA_ROOT/wiki`. Use `scripts/sync_qmd.sh` ou `scripts/sync_qmd.bat` para atualizar índice e embeddings.

---

## 🚀 Início Rápido

### 1. Clonar e configurar o engine

```bash
git clone https://github.com/gitzambrano/second-brain-engine.git second-brain
cd second-brain
python -m pip install -r requirements-ci.txt
```

### 2. Preparar `data/` e `site/`

Para uma instalação já existente, clone os dois repositórios complementares **dentro da raiz do engine**, com estes nomes:

```text
second-brain/
├── data/    # repositório privado + vault do Obsidian
└── site/    # repositório público gerado
```

Para começar do zero, o bootstrap cria os esqueletos e inicializa os dois repositórios Git locais:

```bash
python scripts/bootstrap_repositories.py --create --init-git
```

O bootstrap **não cria repositórios nem remotes no GitHub**. Configure `origin` separadamente se quiser backup remoto do `data/` e publicação via `site/`.

### 3. Abrir o vault

No Obsidian, escolha **Open folder as vault** e abra a pasta `data/`. A edição manual no Obsidian e a edição por agents/scripts alteram exatamente os mesmos arquivos.

### 4. Validar a instalação

```bash
python scripts/check_repo.py --quick
python -m pytest -q -m "not html and not pdf and not slow and not browser"
```

Esse é o núcleo da CI e não exige Pandoc, LuaLaTeX ou Chromium. Essas dependências só são necessárias para exportação e testes visuais; consulte **[`TESTING.md`](./TESTING.md)**.

---

## 🔄 Fluxo de Trabalho

1. **Criar e editar conhecimento** — manualmente no Obsidian ou pelas skills; o estado persistente vive em `data/`.
2. **Revisar e manter** — agents e scripts validam estrutura, referências, metadados e derivados diretamente sobre o corpus.
3. **Versionar** — `engine/` e `data/` têm históricos Git independentes; o subagent `update` cria commits separados e só faz push quando autorizado.
4. **Publicar** — `/publish` gera `site/` a partir de `data/`, aplicando os gates de visibilidade e privacidade antes de qualquer conteúdo público.

Artefatos reproduzíveis como PDFs, HTMLs e outros outputs locais ficam em `data/output/` e não são versionados no repositório privado.

---

## 🤖 Agentes e Skills

O engine é a **fonte única** (`.agents/`) de habilidades operacionais e editoriais consumidas por agentes de IA (Claude Code, Codex e outros harnesses compatíveis).

Fonte única significa fonte única **editável**, não cópia única. Cada harness lê de um lugar diferente, então os espelhos são gerados:

```text
.agents/                 fonte única editável
    ↓ scripts/sync_skills.py
.claude/skills/          espelho gerado
.claude/agents/          espelho gerado
.codex/agents/*.toml     adaptadores específicos do Codex
```

Nunca edite `.claude/skills/` ou `.claude/agents/` à mão: o conteúdo é sobrescrito no próximo sync. O hook `SessionStart` de `.claude/settings.json` roda `python scripts/sync_skills.py --quiet` na abertura da sessão, e `--check` reprova drift em `check_repo.py --quick` e nos testes.

### Skills por fase

O routing detalhado e os contratos ficam em **[`AGENTS.md`](./AGENTS.md)** e nas próprias skills. Este resumo mantém todos os comandos descobríveis sem duplicar suas descrições.

| Fase | Comandos |
| --- | --- |
| **Ideação e criação** | `/insight`, `/outline`, `/essay` |
| **Iteração** | `/expand`, `/chapter`, `/continuity`, `/proofread`, `/polish`, `/linkify`, `/review` |
| **Fontes e estudo** | `/import`, `/digest`, `/absorb`, `/study`, `/scout` |
| **Manutenção** | `/organize`, `/sweep`, `/gaps`, `/connect`, `/merge`, `/delete`, `/plan`, `/stats`, `/status`, `/doctor` |
| **Saída e consulta** | `/handout`, `/html`, `/pdf`, `/publish`, `/query`, `/synthesize` |

### Subagents Especializados

- **`update`**: Fechamento gated: valida, corrige mecanicamente e reconstrói derivados; depois cria commits locais separados em engine/data e só então faz os pushes autorizados. Nunca publica `site/`.
- **`lint-report`**: Diagnóstico consolidado de qualidade que preserva a severidade dos checkers e agrupa os achados em Crítico, Atenção e Informativo.

---

## 🛠️ Scripts Mais Utilizados

Todos os scripts executáveis em `scripts/` possuem defaults úteis quando executados sem argumentos (consulte o catálogo completo em **[`SCRIPTS.md`](./SCRIPTS.md)**):

```bash
# Diagnóstico e Qualidade
python scripts/check_repo.py                 # Diagnóstico global do repositório
python scripts/check_repo.py --quick         # Checagem rápida de contratos e ambiente
python scripts/check_repo.py --site          # Validação estrita da sentinela de privacidade do site
python scripts/check_skills.py               # Valida frontmatter, metadata, ferramentas e referências das skills
python scripts/check_agents.py               # Valida fonte .agents, mirrors .claude, adapters Codex e hook de sync
python scripts/check_script_defaults.py      # Valida defaults dos CLIs e alinhamento com SCRIPTS.md

# Busca semântica qmd
./scripts/sync_qmd.sh                        # POSIX: atualiza índice, embeddings e status
scripts\sync_qmd.bat                         # Windows: equivalente

# Publicação do Atlas (site/)
python scripts/set_visibility.py             # Lista ensaios por visibilidade (public/private/hidden)
python scripts/set_visibility.py allow <slug> # Autoriza publicação de um ensaio
python scripts/publish_site.py               # Valida, compila, audita, sela e publica o site
python scripts/serve_site.py                 # Servidor local de pré-visualização do site

# Exportações Standalone
python scripts/export_essay_html.py <slug>   # Gera versão HTML standalone com MathJax local
python scripts/export_essay_pdf.py <slug>    # Gera versão PDF tipográfica via LuaLaTeX
python scripts/check_html_structure.py       # Auditoria estrutural do HTML exportado
python scripts/check_html_browser.py         # Teste headless de renderização no navegador
```

---

## 🌐 Publicação em Duas Camadas

O site público opera sob um modelo de **Atlas Aberto + Texto por Autorização**:

- **Catálogo & Topologia:** O índice completo e os mapas interativos (Grafo 2D e Esfera 3D) mapeiam todo o universo conceitual — revelando como ensaios, conceitos, fontes e entidades se conectam.
- **Corpo do Ensaio:** Apenas essays com `visibility: public` no frontmatter têm o corpo renderizado e linkável. Ensaios em rascunho ou notas pessoais aparecem no catálogo e mapas marcados como **privados**, impedindo leitura indevida.
- **Busca:** a busca da capa filtra os cartões já presentes na página por **título, resumo e tags** — nunca pelo corpo. O `search-index.json` é um catálogo, não um corpus: ele não carrega o texto de essay nenhum, nem dos publicados.

---

## 🧪 Testes e Qualidade

O engine conta com suíte de testes automatizados via `pytest` que rodam sobre ambientes isolados em `tmp_path`, garantindo total proteção do corpus real.

```bash
python -m pytest -q -m "not html and not pdf and not slow and not browser" # suíte rápida/core
python -m pytest tests/test_site_privacy.py                                # sentinela de privacidade
```

Consulte o arquivo **[`TESTING.md`](./TESTING.md)** para a matriz completa de testes e dependências opcionais (Pandoc, LuaLaTeX e Chromium).
