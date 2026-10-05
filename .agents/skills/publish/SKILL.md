---
name: publish
description: >
  Compila, valida, sela e publica o Atlas em site/. Use somente quando o Usuário
  pedir publicação explícita; exige gates de visibilidade, privacidade, navegador
  e orçamento antes de qualquer commit/push no repositório público.
metadata:
  second-brain-role: "publisher"
  second-brain-mode: "write"
  second-brain-scope: "site"
  second-brain-approval: "before-remote"
  second-brain-closure: "site-publish"
allowed-tools: Bash Read Glob
---
# Publish

Publica o **Second Brain Atlas** no Git independente `site/`. Nenhuma outra skill constrói ou publica o site.

## Pré-condições

- o pedido de publicação deve ser explícito;
- essays legíveis publicamente precisam de `visibility: public`;
- `site/` precisa estar inicializado com `.second-brain-site`;
- esta skill nunca altera `visibility:` sem decisão explícita do Usuário.

## Gates

Execute o comando único:

```bash
python scripts/publish_site.py
```

Regras:

- o comando salva e sincroniza automaticamente qualquer mudança pendente em `./` e `data/` com `origin/main` antes de compilar;
- mudanças locais prévias em `site/` são regeneradas pelo build sem bloquear o fluxo;
- qualquer erro bloqueante de compilação ou validação interrompe a publicação antes do commit;
- ausência de Chromium é falha neste fluxo, não SKIP;
- `--allow-skip-browser` não é válido para publicação;
- o selo é obrigatório e deve corresponder ao conteúdo final e ao commit do engine que o gerou.

## Histórico raso do site

`site/` não acumula histórico binário. A cada publicação, `main` é reescrita para exatamente dois commits: um commit órfão com a árvore do HEAD anterior e, por cima, o commit da nova publicação. Em seguida o script envia com `git push --force-with-lease` (lease explícito sobre o SHA que o remoto tinha na última busca) e roda `git reflog expire --expire=now --all` e `git gc --prune=now` no checkout local.

- Como o remoto é reescrito, o site nunca faz `pull --rebase`. Antes do build, o checkout é comparado a `origin/main` por **árvore**; se difere, vira `origin/main` (o site é projeção gerada, sem trabalho próprio).
- O workflow da newsletter compara `.github/newsletter-manifest.json` com `HEAD^`. O commit órfão carrega o manifesto da publicação anterior, então a comparação continua válida.
- Se o lease falhar (alguém empurrou para o remoto sem este checkout saber), a publicação aborta; rode de novo.
- Podcasts publicados ficam em `assets/podcasts/`, têm orçamento próprio e vêm do build (`/podcast`).

## Relato

Informe:

- visibilidade: PASS|FAIL;
- privacidade: PASS|FAIL;
- navegador: PASS|FAIL;
- orçamento: PASS|FAIL;
- selo: PASS|FAIL;
- Git de `site/`: SHA/push (histórico de dois commits) ou `nada a commitar`.

Se um gate falhar, reporte o código e o artefato afetado; não publique parcialmente.
