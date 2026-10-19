---
name: podcast
description: >
  Gerencia os podcasts de áudio dos essays: ingere um mp3/m4a, gera um novo no
  NotebookLM por automação de navegador, valida e diagnostica. Use quando o
  Usuário pedir podcast de um essay, trouxer um áudio para arquivar ou quiser
  conferir os podcasts; a publicação no site segue /publish.
metadata:
  second-brain-role: "producer"
  second-brain-mode: "mixed"
  second-brain-scope: "page"
  second-brain-approval: "before-write"
  second-brain-closure: "none"
allowed-tools: Bash Read Glob
---
# Podcast

Gerencia os episódios de áudio dos essays em `wiki/podcasts/<slug>.<m4a|mp3>`, com slug idêntico ao do essay. Arquivos brutos ficam fora do Git de `data/`. Ao publicar via `/publish`, `scripts/build_site.py` converte uma versão compacta (AAC mono 48 kbps) para `site/assets/podcasts/` e insere o player apenas para essays com `visibility: public`.

Esta skill nunca altera `visibility:` nem o texto de um essay.

## Scripts e Subcomandos

### 1. Ingestão: `scripts/ingest_podcast.py`

Arquiva e vincula um arquivo de áudio local existente:

```bash
python scripts/ingest_podcast.py <arquivo> [essay]
```

- **O que faz:** valida o formato do áudio via ffmpeg, correlaciona o arquivo ao essay correspondente (por slug, título ou trecho da prosa) e move o arquivo para `wiki/podcasts/<slug>.<ext>`.
- **Ambiguidade (código 2):** se mais de um essay for candidato, o script lista as opções. Pergunte ao Usuário qual é o correto e reexecute passando o slug explícito.

### 2. Geração: `scripts/notebooklm_podcast.py`

Gera o áudio via NotebookLM usando perfil local de navegador:

```bash
python scripts/notebooklm_podcast.py <essay>
```

- **O que faz:** cria um caderno no Gemini Notebook/NotebookLM, envia o corpo do essay como fonte, aplica as diretrizes de áudio de `.agents/skills/podcast/prompt.md` em português do Brasil, aguarda a geração, baixa o áudio gerado e o repassa automaticamente para `ingest_podcast.py`.
- **Autenticação e contas:** utiliza perfis em `.local/notebooklm/profiles/`. Se a sessão estiver deslogada, solicite ao Usuário autenticar via `python scripts/notebooklm_podcast.py --login <pasta>`.
- **Opções úteis:**
  - `--account <pasta>`: força uma conta específica.
  - `--headed`: abre o navegador visível (essencial para depurar falhas visuais).
  - `--force`: substitui podcast existente.
  - `--dry-run`: simula sem gerar.
  - Sem argumentos: lista essays públicos sem podcast e status das contas.
- **Atenção:** confirme com o Usuário antes de iniciar a geração, pois consome cotas da conta.

### 3. Auditoria e Correção: `scripts/check_podcasts.py` e `scripts/fix_podcasts.py`

```bash
python scripts/check_podcasts.py
python scripts/fix_podcasts.py
```

- **`check_podcasts.py` verifica:**
  - Correspondência exata entre o slug do áudio e o slug do essay;
  - Áudios órfãos em `wiki/podcasts/` sem essay correspondente;
  - Integridade do arquivo de áudio via ffmpeg;
  - Projeção no site: presença de cópia web em `site/assets/podcasts/` para essays públicos e garantia de que essays privados/ocultos não tenham player publicado;
  - Vazamento de contas: assegura que e-mails e dados de sessão de `.local/` não vazaram para o repositório.
- **`fix_podcasts.py`:** renomeia automaticamente arquivos com correspondência inequívoca e reporta casos ambíguos para decisão manual.

## Fechamento

Podcasts só vão ao ar publicamente após `/publish`. Ofereça `/status update` caso o trabalho da sessão tenha sido relevante.

## Skills relacionadas

- `/publish`
- `/doctor`
