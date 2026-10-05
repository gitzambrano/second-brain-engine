---
name: doctor
description: >
  Executa o diagnóstico read-only completo do repositório com check_repo.py.
  Use para verificar saúde de arquitetura, skills, corpus, exports e ambiente sem
  corrigir, editar, commitar ou fazer push.
metadata:
  second-brain-role: "diagnostic"
  second-brain-mode: "read"
  second-brain-scope: "repository"
  second-brain-approval: "none"
  second-brain-closure: "none"
allowed-tools: Bash Read
---
# Doctor

**[script]** Diagnóstico do sistema, não manutenção editorial.

Execute:

```bash
python scripts/check_repo.py
```

Sem argumentos, `check_repo.py` executa o diagnóstico completo. Em um clone skeleton, ausência de essays/HTML/PDF é `SKIP`, não erro.

Reporte por grupo: Repository, Skills, Script defaults, Wiki, References, Podcasts, HTML, PDF, Environment. Não faça correções automaticamente. Se houver falha, informe o código e o caminho; encaminhe correções de conteúdo para `/organize` e falhas de infraestrutura para manutenção do repo.

Não chame o subagent `update`, não altere `wiki/`, não rode fixers, não faça commit/push.
