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

Cada essay pode ter um podcast gerado por IA (NotebookLM). O original fica em `wiki/podcasts/<slug>.m4a` (ou `.mp3`), com o **slug exatamente igual ao nome do arquivo do essay**. Os originais são grandes: ficam só em disco, fora do Git de `data/`. Ao publicar, `scripts/build_site.py` recodifica uma cópia enxuta (AAC mono 48 kbps) em `site/assets/podcasts/` e o player aparece abaixo da assinatura do essay, somente para `visibility: public`. Essay `private` ou `hidden` nunca publica áudio.

Esta skill nunca altera `visibility:` nem o texto de um essay.

## Subcomandos

### `ingest <arquivo> [essay]`

Arquiva um mp3/m4a que o Usuário já tem.

```bash
python scripts/ingest_podcast.py <arquivo> [essay]
```

O script valida o áudio, casa o arquivo com o essay (slug, título ou trecho) e move para `wiki/podcasts/<slug>.<ext>`. Casamento ambíguo sai com código 2 e lista os candidatos: pergunte ao Usuário qual é e rode de novo com o essay explícito. Não escolha por conta própria.

### `generate <essay>`

Gera o podcast no NotebookLM, sem gastar tokens de LLM:

```bash
python scripts/notebooklm_podcast.py <essay>
```

O script abre o NotebookLM com um perfil de navegador local, cria um caderno, cola o corpo do essay (sem frontmatter, Sumário e Conexões) como fonte, personaliza o Resumo em áudio em português do Brasil, no formato mais longo disponível, com o prompt de `.agents/skills/podcast/prompt.md`, espera a geração (até 30 min), baixa o áudio e o entrega a `ingest_podcast.py`.

Contas e perfis:

- cada subpasta de `.local/notebooklm/profiles/` é um perfil e uma conta; `--profiles-dir` ou a variável `NOTEBOOKLM_PROFILES_DIR` apontam outra pasta;
- o rodízio segue a ordem alfabética das pastas; limite de uso coloca a conta em cooldown e passa à próxima; `--account <pasta>` força uma;
- o estado (cooldowns, depuração, downloads) vive em `.local/notebooklm/`, nunca em repositório; nenhuma conta ou e-mail entra em arquivo versionado;
- o script nunca digita senha. Sessão deslogada é reportada; peça ao Usuário para entrar com `python scripts/notebooklm_podcast.py --login <pasta>`.

Opções úteis: `--headed` (ver o navegador), `--delete-notebook`, `--timeout <min>`, `--dry-run`, `--force` (substituir podcast existente). Sem argumentos, o script lista os essays públicos sem podcast e o estado dos perfis.

Se o NotebookLM truncar o prompt, o script aborta e informa quantos caracteres foram aceitos; encurte `prompt.md` com o Usuário em vez de seguir truncado. Falha de fluxo grava captura de tela e HTML em `.local/notebooklm/debug/` e informa o passo que falhou.

Antes de gerar, confirme com o Usuário qual essay e que a geração consome cota das contas.

### `check`

```bash
python scripts/check_podcasts.py
python scripts/fix_podcasts.py
```

`check_podcasts.py` audita nomes, órfãos, integridade do áudio (ffmpeg), cópias e players no site e vazamento de conta. `fix_podcasts.py` renomeia somente os nomes de casamento inequívoco e lista os ambíguos sem tocá-los. Reporte cada achado com o código e o arquivo.

## Depois

Podcast novo só vai ao ar numa publicação explícita (`/publish`). Ofereça `/status update` se o trabalho foi substancial.

## Skills relacionadas

- `/publish`
- `/doctor`
