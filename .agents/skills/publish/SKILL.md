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

## Relato

Informe:

- visibilidade: PASS|FAIL;
- privacidade: PASS|FAIL;
- navegador: PASS|FAIL;
- orçamento: PASS|FAIL;
- selo: PASS|FAIL;
- Git de `site/`: SHA/push ou `nada a commitar`.

Se um gate falhar, reporte o código e o artefato afetado; não publique parcialmente.
