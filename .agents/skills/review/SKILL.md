---
name: review
description: >
  Faz peer review crítico de tese, lógica, validade física/matemática,
  profundidade e evidência. Use para auditoria substantiva de um essay; só edita
  depois de aprovação explícita do plano de modificação.
metadata:
  second-brain-role: "content-auditor"
  second-brain-mode: "mixed"
  second-brain-scope: "essay"
  second-brain-approval: "before-write"
  second-brain-closure: "single-essay"
allowed-tools: Bash Read Write Edit Glob Grep WebSearch WebFetch AskUserQuestion
---
# Review

Peer review crítico de conteúdo, argumento e evidência. Não faz revisão de estilo (`/polish`) nem de gramática (`/proofread`). `/continuity` cobre coerência estrutural e `/organize` cuida de metadados.

`/review` é interativo e opera em um essay por vez; nunca roda em batch.

## 1. Preparar

1. Resolva o essay alvo (`/review <slug>`); pergunte apenas se houver ambiguidade real.
2. Leia o essay inteiro na íntegra antes de qualquer análise.
3. Execute `/continuity` primeiro e reutilize seus achados (não repita o mesmo checklist).
4. Consulte a wiki com `qmd query` ou `scripts/find_text.py` antes de sugerir material externo.

## 2. Avaliar

Audite o essay em seis dimensões substantivas:

### Força argumentativa
- A tese depende de premissa frágil ou implícita?
- Qual é a objeção mais forte de um leitor informado?
- O essay responde e refuta essa objeção?
- Qual elo mais enfraquece a conclusão?

### Validade lógica e filosófica
- Há falácia formal ou informal, falsa dicotomia, generalização ou apelo indevido à autoridade?
- Conceitos importantes estão definidos e usados de forma consistente em todo o texto?
- Em tema filosófico, as objeções clássicas relevantes estão representadas com rigor?

### Validade física e matemática
- Afirmações quantitativas têm fonte, derivação ou ordem de grandeza realista?
- Unidades, hipóteses adotadas e limites de validade estão corretos?
- Há conflito com princípios físicos e leis estabelecidas?

> [!IMPORTANT]
> **Requisitos mandatórios para essays técnicos (falta de qualquer um é 🔴 Crítico):**
> 1. **Insight físico de first principles:** explicação causal do mecanismo, por que o fenômeno ocorre e como responde à variação de parâmetros.
> 2. **Desenvolvimento matemático:** equações centrais apresentadas ou derivadas com os passos matemáticos que carregam a física.

### Profundidade e completude
- Há descrição puramente fenomenológica sem o mecanismo causal subjacente?
- Algum conceito-chave ficou apenas no nível de definição abstrata?
- Falta exemplo concreto, consequência prática ou caso numérico onde seria útil?

### Citações e cobertura
- Claims históricos, empíricos ou atribuídos a terceiros têm fontes verificadas?
- Falta autor, obra, corrente ou perspectiva indispensável ao tema?
- Há seção relevante sustentada apenas por asserção autoral sem apoio externo?

### Enriquecimento
Sugira somente quando agregar valor substantivo real:
- Fonte primária, norma técnica ou livro-texto de referência;
- Experimento mental que clarifique distinções conceituais difíceis;
- Exemplo concreto, numérico ou contraexemplo revelador;
- Analogia precisa ou conexão forte com outra página da wiki.

## 3. Priorizar e reportar

Classifique cada achado por severidade:
- **🔴 Crítico:** enfraquece diretamente ou invalida a tese; exige resolução obrigatória antes de promover a `status: revisao`.
- **🟡 Moderado:** reduz rigor, clareza ou profundidade sem derrubar o argumento central.
- **🟢 Sugestão:** oportunidade de enriquecimento opcional.

Apresente o relatório consolidado ao Usuário antes de propor edição:

```markdown
## Relatório de Revisão — Título do Essay

### Visão geral
[Síntese do argumento e incorporação dos achados de /continuity]

### 🔴 Críticos
1. Problema — localização — impacto na tese.

### 🟡 Moderados
1. ...

### 🟢 Sugestões
1. ...

### Fontes e exemplos candidatos
- ...
```

## 4. Plano de modificação

Pergunte quais achados o Usuário deseja resolver. Para os itens selecionados, formule um plano numerado com:
1. **Localização:** seção e parágrafo afetados.
2. **Mudança concreta:** redação ou alteração proposta.
3. **Evidência necessária:** fonte, dado ou equação a introduzir.
4. **Efeito no argumento:** como a mudança fortalece a tese.

**Aguarde aprovação explícita antes de qualquer escrita.**

## 5. Executar o plano aprovado

Após a aprovação do Usuário:
1. Releia o trecho em contexto antes de editar.
2. Aplique estritamente as mudanças combinadas, preservando a voz do autor e as normas de `conventions/SKILL.md`.
3. Atualize `## Sumário` se houver alteração na estrutura e `## Referências` se novas fontes forem citadas.
4. Não amplie o escopo nem adicione alterações não aprovadas.

## 6. Fechar

Após concluir as modificações:
1. Atualize `updated:` no frontmatter apenas se a prosa do corpo sofreu alteração substantiva (ajuste mecânico não conta).
2. Execute a validação mecânica de essay único (`conventions/SKILL.md`):
   ```bash
   python scripts/fix_lint.py <slug>
   python scripts/check_wiki.py <slug>
   python scripts/check_references.py --file <slug>
   ```
3. Se referências mudaram: `python scripts/build_references.py`.
4. Se summary ou tags mudaram: `python scripts/build_index.py`.
5. Registre em `wiki/log.md`:
   ```markdown
   ## [YYYY-MM-DD] review | Título do Essay
   Revisão: N críticos, M moderados, K sugestões. X modificações aplicadas.
   ```
6. Se o essay estava em `status: draft` e não restar nenhum crítico pendente, pergunte se o Usuário deseja promover para `revisao` (nunca altere status automaticamente).
7. Se a edição alterou a estrutura ou a tese, ofereça rodar `/continuity`.

## Limites

- Nunca edita sem aprovação explícita do plano de modificação.
- Não transforma review em revisão de estilo (`/polish`) ou gramática (`/proofread`).
- Não inventa dados ou citações; verifique fontes antes de integrá-las.
- Contradições entre fontes seguem a regra canônica em `conventions/SKILL.md`.
