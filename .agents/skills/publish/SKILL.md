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

Publica o **Second Brain Atlas** no repositório público `site/`. Nenhuma outra skill constrói ou publica o site.

## Pré-condições

- Pedido de publicação deve ser explícito.
- Essays legíveis publicamente precisam de `visibility: public`.
- Nunca altere `visibility:` sem decisão explícita do Usuário.
- `site/` precisa estar inicializado com `.second-brain-site`.

## Execução

Execute o comando único de publicação:

```bash
python scripts/publish_site.py
```

O script executa de forma autônoma:
1. Sincronização prévia de `./` e `data/` com `origin/main`.
2. Compilação do site e gates de validação (visibilidade, privacidade, Chromium, orçamento e selo).
3. Publicação em `site/` mantendo histórico raso de 2 commits com `--force-with-lease`.

Qualquer falha bloqueante interrompe o fluxo antes do commit remoto. Ausência de Chromium é falha neste fluxo.

## Relato

Informe o status dos gates:
- Visibilidade: PASS|FAIL
- Privacidade: PASS|FAIL
- Navegador: PASS|FAIL
- Orçamento: PASS|FAIL
- Selo: PASS|FAIL
- Git de `site/`: SHA/push ou `nada a commitar`

Se algum gate falhar, reporte o código e o artefato afetado; nunca publique parcialmente.
