---
name: sweep
description: >
  Orquestra revisão completa de um essay ou do corpus: manutenção mecânica,
  continuidade, português, estilo e links. Use para pente-fino amplo; corrige
  automaticamente o inequívoco e acumula decisões editoriais para o relatório.
metadata:
  second-brain-role: "review-orchestrator"
  second-brain-mode: "write"
  second-brain-scope: "essay-or-corpus"
  second-brain-approval: "conditional"
  second-brain-closure: "multi-essay"
allowed-tools: Bash Read Write Edit Glob Grep WebSearch WebFetch AskUserQuestion
---
# Sweep

Orquestra, nessa ordem lógica, as dimensões de `/organize`, `/continuity`, `/proofread`, `/polish` e `/linkify`.

A lógica de cada dimensão vive na skill correspondente. Durante o sweep, reutilize a mesma leitura do essay, os mesmos achados e o mesmo contexto entre etapas; não reinicie cada skill como um workflow independente quando isso apenas repetir leitura ou validação.

## Escopo

```text
/sweep          → todos os essays elegíveis
/sweep <slug>   → essay específico
```

No corpus, siga a regra de status de `conventions/SKILL.md`: pule `revisao` e `finalizado`. Em essay nomeado, processe mesmo nesses estados e informe isso no resumo final.

## Execução

Processe um essay por vez.

1. Leia o essay uma vez e reúna o contexto necessário para todas as dimensões.
2. Aplique primeiro a manutenção mecânica de `/organize`.
3. Avalie continuidade e estrutura com os critérios de `/continuity`, reutilizando a leitura já feita.
4. Aplique correções inequívocas de português e estilo segundo `/proofread` e `/polish`, sem repetir uma passada completa sobre trechos já resolvidos.
5. Verifique links e referências segundo `/linkify`.
6. Quando surgir decisão editorial substantiva, registre `decisão necessária` e continue o restante do escopo.
7. Execute o fechamento e as validações mecânicas uma vez ao final de cada essay, salvo quando uma etapa intermediária realmente exigir um checker para decidir como prosseguir.

Não faça prompts de escala, estimativas de duração ou oferta de lotes. O escopo já foi definido pelo comando.

## Relatório

Entregue um único relatório consolidado:

```markdown
## Sweep — N essay(s)

### Resumo
- processados: N
- pulados por status: K
- fixes mecânicos: X
- continuidade corrigida: Y
- decisões editoriais pendentes: Z
- correções de português: W
- correções de estilo: V
- links/referências: U

### Decisões necessárias
- [essay] — [localização] — [decisão]

### Por essay
- [Título] — [resumo curto]
```

Não exponha cada microcorreção durante a execução.

## Fechamento

Registre uma entrada consolidada em `wiki/log.md` quando houver mudanças. Nenhuma etapa de `/sweep` altera `updated:` por revisão mecânica, linguística ou estilística; uma correção estrutural/substantiva aplicada no fluxo segue a regra de data da skill que efetivamente mudou o corpo.

Depois do batch, ofereça o subagent `update` **somente** para regenerar derivados e executar commit/push após autorização explícita do Usuário. Ofereça `/status update` quando o trabalho for substancial.

## Limites

- Não duplica checklists das skills chamadas.
- Não bloqueia o corpus por uma decisão editorial de um único essay.
- Não escolhe silenciosamente entre alternativas substantivas.
- `/review` continua sendo a auditoria crítica profunda de argumento e evidência.
