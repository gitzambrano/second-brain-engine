---
name: conventions
description: >
  Fonte normativa de estrutura, frontmatter, tags, sources, links, referências,
  prosa, imagens e regras editoriais da wiki. Use como referência pelas skills
  que leem ou alteram conteúdo; não executa um workflow próprio.
metadata:
  second-brain-role: "normative-reference"
  second-brain-mode: "read"
  second-brain-scope: "repository"
  second-brain-approval: "none"
  second-brain-closure: "none"
allowed-tools: Read WebFetch WebSearch
---
# Conventions

**[leitura]** Fonte única das regras de conteúdo e formatação. Não replique estas regras em outras skills; cite esta seção e siga.

## Onde as coisas vão — tabela canônica

| Pasta | Conteúdo | Regra |
| --- | --- | --- |
| `wiki/essays/` | Ensaio, white paper ou estudo com tese sustentada | `/essay`, `/import` |
| `wiki/concepts/` | Conceito, framework ou teoria sem tese própria | Página curta de apoio |
| `wiki/entities/` | Pessoa, obra, organização ou ferramenta | Página curta de apoio |
| `wiki/insights/` | Uma ideia ainda sem essay-pai | `/insight` |
| `wiki/sources/<tipo>/` | Documento original processado | Tipo define a subpasta |
| `wiki/sources/resumos/` | Resumo de uma fonte de terceiros | `/digest` |
| `wiki/handouts/` | Resumo de uma página de um essay | `/handout` |
| `wiki/assets/` | Figuras e imagens | Sempre arquivo separado |
| `wiki/book-chapters/` | Projeto futuro | Não usar ainda |
| `plan/plano.md` | Trabalho futuro | `/plan` |
| `wiki/status.md` | Estado da sessão | `/status` |

Regra de decisão: tese própria → essay; definição sem tese → concept/entity; ideia sem lar → insight; material bruto → source.

## Frontmatter

Páginas da wiki:

```yaml
---
tags: [Tag 1, Tag 2]
sources: [source-filename.md]
created: YYYY-MM-DD
updated: YYYY-MM-DD
---
```

Essays acrescentam:

```yaml
summary: "Resumo em prosa contínua, entre 200 e 530 caracteres."
status: draft | revisao | finalizado
visibility: public     # opcional; ver ## Publicação
```

`summary:`: 200–530 caracteres, uma linha, aspas duplas; descreva o arco do argumento, não apenas o tema.

`visibility:` é opcional; ausência significa `private`.

### `updated:` mede o texto, não a manutenção

Altere `updated:` somente quando a prosa do corpo mudar substancialmente, como capítulo novo, argumento reescrito ou seção fundida/dividida.

Não altere por correção mecânica, frontmatter, byline, cabeçalho, `## Sumário`, `## Conexões`, `## Referências`, wikilink, link externo, tag, renomeação ou `visibility:`.

## Tags — Vocabulário Controlado

`tags:` das páginas e `Tags:` de `wiki/sources/manifest.md` usam o mesmo vocabulário, consolidado em `tags_in_use` de `wiki/index.json`.

- Confira `tags_in_use` antes de criar tag nova. Se o índice estiver desatualizado, rode `python scripts/build_index.py`.
- Reuse uma tag existente sempre que ela cobrir o tema; crie uma nova apenas quando nenhuma servir.
- Use uma única grafia em Title Case, sem variantes por plural, acento ou sinônimo.
- Tags representam temas, não tipo de essay/source.
- Use 2 a 5 tags por essay ou source.
- `/organize` audita quase-duplicatas; renomeação em massa exige aprovação.

## Tipos de Source — Vocabulário Controlado

`Tipo:` no manifesto define a subpasta física.

| Tipo | Subpasta |
| --- | --- |
| Ensaio Completo Importado | `ensaio-importado/` |
| Web Clipping | `web-clipping/` |
| Artigo Acadêmico | `artigo-academico/` |
| Livro | `livro/` |
| Documentação Técnica | `documentacao-tecnica/` |
| Transcrição | `transcricao/` |
| Ideias | `ideias/` |
| Outro | `outro/` |

Reuse um tipo existente. `Outro` só quando nenhum tipo específico servir.

`manifest.md` e `map.md` são catálogos editáveis; a regra de não modificar `wiki/sources/` protege os documentos originais.

## Status de essay (draft | revisao | finalizado)

`status:` existe apenas em essays.

- `/essay` cria `draft`.
- `/import` cria `finalizado` por padrão; use `draft` se o original for rascunho.
- Essay antigo sem status é tratado como `draft` até `/organize` corrigir.

Status protege a prosa, não a formatação mecânica. `/organize` e `fix_lint.py` podem corrigir estrutura/formatação em qualquer status.

Para skills que editam prosa:
- **Batch:** pule `revisao` e `finalizado`; informe a contagem no fim.
- **Essay nomeado pelo Usuário:** edite normalmente. Se era `finalizado`, avise ao final.

## Publicação

`visibility:` controla leitura do texto; `tags:` nunca controla exposição.

| `visibility:` | Resultado |
| --- | --- |
| `public` | catálogo + mapa + corpo e link de leitura |
| `private` | catálogo + mapa; sem corpo nem link de leitura |
| `hidden` | ausente do site, do índice da wiki e do grafo da wiki |
| campo ausente ou valor inválido | tratado como `private` |
| `publish: true` (legado) | equivale a `public` |

As grafias `público`, `privado` e `oculto` também são aceitas.

Regras:

- `visibility:` só se aplica a essays.
- Nenhuma skill define ou altera `visibility:` automaticamente; exige decisão explícita do Usuário.
- Nenhum corpo não autorizado, link de leitura restrito ou caminho para `data/` pode aparecer na saída pública.
- Nenhum corpo de essay entra nos arquivos de dados do site.
- Imagem só é copiada se for referenciada por essay `public` e estiver em `DATA_ROOT/wiki/assets`.
- Metadata de essays `private` pode aparecer no catálogo e no mapa; essays `hidden` não aparecem.
- Aplicação e verificação: `scripts/set_visibility.py`, `scripts/check_visibility_field.py` e `scripts/check_site_privacy.py`.

Detalhes de implementação do site não pertencem aqui.

## Byline do essay

Logo após o H1:

```markdown
# Título do Essay

> Tipo
> Gustavo Zambrano · Mês de Ano
```

`Tipo`: `Ensaio`, `White Paper`, `Brainstorm`, `Estudo` ou `Análise`.

Não use `[[wikilinks]]` nem `:` na byline.

## Estrutura obrigatória do essay

1. H1 + byline.
2. `## Sumário` logo após a byline, com links para todos os H2 de conteúdo.
3. Introdução como primeira seção de conteúdo. Não crie `## Resumo Executivo` em essays novos.
4. Corpo autocontido com links externos na primeira ocorrência dos termos relevantes.
5. `## Referências` com heading exato e bibliografia no padrão abaixo.
6. `## Conexões` como última seção, contendo apenas relações internas.

`Referências` e `Conexões` não entram no Sumário.

## Regra de links — Obsidian é o leitor primário

| Uso | Forma |
| --- | --- |
| Outra página | `[[slug-do-arquivo\|Título Visível]]` |
| Seção do mesmo arquivo | `[[#Texto Exato Do Heading]]` ou `[[#Texto\|Display]]` |
| Corpo do essay | links externos `[texto](url)`; sem wikilinks para outras páginas |
| `## Conexões` | apenas `[[slug\|Título]]` |
| `## Referências` | links externos bibliográficos |

Regras:
- O alvo de wikilink é o nome do arquivo, não o H1.
- Não coloque link Markdown dentro de heading.
- Não remeta a outro essay no corpo; registre a relação em `## Conexões`.
- Trabalho bibliográfico modifica `## Referências`, não links do corpo.
- Essays completos devem ter cerca de 10 links externos ou mais quando o tema oferecer material relevante.
- Use caminhos relativos para imagens e Markdown puro nos artefatos gerados.
- Valide no Obsidian mudanças de sintaxe que alterem comportamento de clique.

Exportadores convertem links de seção, removem `## Conexões` e limpam wikilinks residuais.


## Callouts / caixas de destaque

Sintaxe do Obsidian. Blockquote sem `[!tipo]` é citação, nunca caixa.

Antes de escolher o tipo, decida se o bloco precisa mesmo de caixa. Caixa é para o que **interrompe** a leitura de propósito: um experimento, uma evidência, uma ficha, um número. O que continua o argumento é prosa. Se a estrutura normal do texto — parágrafo, subtítulo, lista, tabela — já resolve, não crie caixa.

**Escolhido que vai ter caixa, o padrão é `note`.** Ela emoldura sem gritar, e é o que serve para a maioria dos casos: ressalva, contexto, digressão. Os outros tipos existem para quando o bloco tem uma função *específica* que a tabela abaixo nomeia. Na dúvida entre `note` e qualquer outro, use `note`.

### A tabela

Escolha pela **função do bloco no argumento**, nunca pela cor que você quer ver.

| Tipo | Use quando o bloco é | Não use para | Título | Corpo | Quanto usar |
| --- | --- | --- | --- | --- | --- |
| `note` | ressalva, contexto, nota filosófica ou metodológica, digressão lateral | evidência, experimento, entidade, métrica | curto, ou nenhum | prosa livre | **o padrão** — na dúvida, este |
| `info` | evidência empírica: estudo, dado medido, observação documentada, resultado de terceiros | opinião, exemplo inventado, "informação interessante" | o rótulo da evidência (`Evidência`, `Estudo seminal`) | citação + resultado; `####` opcional para o achado | com cautela: dez seguidas viram muro |
| `example` | experimento mental, caso trabalhado, cenário hipotético, aplicação | evidência real, dado empírico | o rótulo numerado (`Experimento Mental IV`) | `####` com o nome do caso, depois a narrativa | com cautela, pelo mesmo motivo |
| `abstract` | mapa conceitual, definição formal, framework, síntese estrutural | resumo qualquer, nota solta | o nome do mapa ou da definição | pode conter tabela ou lista | raro: um por seção, no máximo |
| `tip` | ideia, insight, proposta, intuição destacável | explicação comum, evidência | o rótulo da ideia | prosa curta | raro |
| `todo` | pessoa, organização ou obra que merece ficha | tarefa (não existe tarefa em essay) | **nome da entidade** | primeiro `####` = metadados (datas · país · instituição); depois, a relevância | um por entidade citada de fato |
| `warning` | um número-chave e só | atenção genérica, alerta textual | **o próprio valor** (`39%`, `0,12 ft/s`) | explicação; `---` separa a nota de fonte | raro: o número tem de carregar a seção |
| `success` aninhado | veredicto da caixa que o contém | conclusão de seção | `Veredicto` | o desfecho em uma ou duas frases | um por caixa que faz teste |
| `success` solto | resultado confirmado, fora de caixa | qualquer boa notícia | o rótulo do resultado | prosa curta | raro |
| `question` | objeção, tensão, pergunta em aberto que estrutura o que vem depois | pergunta retórica, FAQ | a pergunta, com `?` | o desenvolvimento da tensão | raro |
| `failure` | hipótese rejeitada, teste que falhou, alternativa descartada | erro de digitação, crítica leve | o que falhou | por que falhou | raro |
| `danger` | invalidez, risco crítico, erro conceitual grave | ênfase forte qualquer | o risco | a consequência | rarísssimo |
| `bug` | defeito de implementação, falha de software | erro de raciocínio | o defeito | reprodução e efeito | rarísssimo |
| `quote` | citação que merece destaque editorial | toda citação; prosa comum | nenhum, ou o contexto | texto entre `“ ”`; atribuição na linha seguinte | quando a citação sustenta o argumento |

Regra de proporção: até **6 caixas por mil palavras**. Acima disso a página vira mostruário e a prosa perde o fio. Um essay inteiramente sem caixa é resultado válido e comum — `xadrez-computacional` tem uma só em 23 mil palavras.

Regra de variedade: se o essay passa de oito caixas, use **mais de um tipo**. Oito caixas iguais em fila achatam a leitura tanto quanto oito cores diferentes a estilhaçam.

### Forma do bloco

```markdown
> [!example] Experimento Mental III
> #### O Cérebro Dividido
> Texto da caixa.
>
> > [!success] Veredicto
> > O desfecho.
```

- **O título é autoral.** É o rótulo que o texto já tinha; não invente, não encurte, não traduza. Sem rótulo, escreva `> [!tipo]` sozinho.
- **`####` é o subtítulo da caixa.** `##` e `###` dentro dela quebram o Sumário.
- **Dentro da caixa vale Markdown normal**: parágrafos, listas, tabelas, matemática, código e caixas aninhadas.
- **Aspas tipográficas `“ ”` separam citação de atribuição.** Sem elas não há atribuição destacada — e nunca acrescente aspas que o autor não escreveu.

Quatro tipos têm forma própria:

```markdown
> [!todo] Thomas Hobbes
> #### 1588 – 1679 · Inglaterra
> Por que ele importa para este argumento.

> [!warning] 39%
> O que o número mede.
> ---
> [McKinsey, *Diversity Matters Even More*, 2023](https://exemplo)

> [!info] Evidência
> #### Pacientes frontais e a metamorfose do caráter
> Estudo, amostra, resultado.

> [!quote]
> “A vida é o modo pelo qual a matéria encontrou de contemplar a si mesma.”
>
> — atribuído a Carl Sagan
```

No `todo` o título é o **nome** e o `####` é a linha de metadados. No `warning` o título é o **próprio número** e o `---` separa a explicação da fonte. No `quote` a atribuição vem depois de uma linha em branco, começando por travessão.

### O que não fazer

- alias (`tldr`, `summary`, `hint`, `important`, `caution`, `cite`, …) ou tipo inventado — é erro, não há fallback;
- escolher o tipo pela cor que ele produz;
- promover prosa comum a caixa só para dar destaque;
- usar `note` como depósito de tudo que sobrou;
- usar `warning` como "atenção" — ele é reservado a número;
- repetir o mesmo rótulo em dezenas de caixas: isso é um molde, não um destaque.

## Dois tipos de essay

- **Originais (`/import`)**: preserve a prosa do autor na ingestão; aplique apenas as transformações autorizadas em `/import`. Tradução ou edição substantiva exige pedido explícito. O documento arquivado em `wiki/sources/` permanece intocado.
- **Criados (`/essay`)**: texto novo, livremente iterável pelas skills editoriais.

## Formato de `## Referências` — padrão AIAA

Uma entrada por parágrafo, numerada `[N]` na ordem de citação.

```markdown
## Referências

[1] Cheeseman, I. C., e Bennett, W. E., *The Effect of the Ground on a Helicopter Rotor in Forward Flight*, Aeronautical Research Council Reports and Memoranda, No. 3021, HMSO, London, 1955. — Nota contextual opcional. [Link](https://example.org/arc-rm-3021)

[2] *Blade Element Momentum Theory*, Wikipedia, The Free Encyclopedia. [Link](https://en.wikipedia.org/wiki/Blade_element_momentum_theory)
```

Regras:
- Título sempre em itálico.
- Até 3 autores: liste todos. Acima disso: primeiro autor + `et al.`.
- Preserve subtítulo quando existir.
- Use container completo; inclua `Vol.`, `No.` e `pp.` quando aplicável.
- Sem autor identificado: comece pelo título.
- O link externo é `[Link](url)` e fica no final.
- Nota contextual, quando houver, vem antes de `[Link]`.
- Entrada sem link é válida quando não existe versão digital confiável.
- Para fonte mutável (Wikipedia, README, página sem versão fixa), inclua data de acesso.
- Prefira DOI/editor; depois fonte institucional; SEP para filosofia; Wikipedia apenas para conceitos gerais.
- Não repita a mesma URL normalizada no mesmo essay.
- Nunca use negrito no nome do autor.
- `## Referências` vazia em essay com claims externos é erro.

Antes de criar ou corrigir uma referência, confirme título, autores e container na fonte. Não complete dados bibliográficos de memória.

## `wiki/references.md` e `wiki/references.json`

São gerados por `python scripts/build_references.py` e nunca editados manualmente.

Antes de escrever uma citação nova, procure a fonte em `wiki/references.md` por URL ou título. Se já existir, reutilize a citação canônica. Edição/tradução diferente conta como fonte distinta.

`concepts/` e `entities/` não recebem `## Referências` própria.

## Estilo de prosa

Vale para texto novo ou reescrito pela wiki. Texto original importado só muda sob pedido editorial explícito.

### Regras gerais

1. Uma proposição principal por frase. Prefira frase direta, completa e sem enchimento; concisão não é estilo telegráfico.
2. Abra cada parágrafo com o tema e mantenha um tema por parágrafo.
3. Use o mesmo termo para o mesmo conceito. Mantenha grafia consistente para termos, siglas, unidades e variáveis.
4. Explicite causa, condição, contraste e sequência quando necessários; use conectores apenas quando ajudarem essa lógica.
5. Prefira verbos simples e precisos a perífrases e nominalizações.
6. Corpo argumentativo em prosa; bullets apenas para listas reais.
7. Não use ponto e vírgula na prosa. Separe em frases ou use outra construção sintática.
8. Use travessões raramente: no máximo 1 a 2 em todo o corpo de um essay. Não os use como substituto recorrente de vírgulas, parênteses ou dois-pontos.
9. Parênteses apenas para informação curta. Evite atalhos tipográficos como `/`, `~`, `--`, `5-30`, `Cap.`/`Sec.`, `e.g.` e `i.e.`.
10. Elimine metadiscurso dispensável: não anuncie o que o texto fará, acabou de fazer ou pretende demonstrar quando a própria argumentação já o mostra.
11. Evite frases de efeito, tríades, paralelismos e contrastes simétricos usados apenas para ritmo ou ênfase. Use-os somente quando cada elemento expressar uma distinção necessária ao argumento.
12. Não atribua autoridade a fontes vagas. `Estudos mostram` ou `especialistas afirmam` exigem fonte identificável.
13. Preserve a voz do autor. Estas regras orientam revisão editorial, não substituição mecânica de estilo.
14. Escreva apenas o estado final do argumento. Não mencione versões anteriores, correções, pedidos do Usuário ou alternativas fora do texto final.

`check_wiki.py` cobre as regras mecânicas; `/polish` e `/proofread` cobrem as editoriais.

### Regras adicionais para essays técnicos

1. Use português claro, conciso, formal e assertivo.
2. Não antropomorfize código, modelos ou teorias.
3. Prefira voz ativa quando o agente for conhecido.
4. Use gerúndio somente quando sua relação temporal, causal ou lógica for clara e necessária; elimine gerúndio ornamental.
5. Evite `isso/isto` com referente ambíguo e simplifique cadeias longas de `de/da/do`.
6. Não use linguagem promocional ou superlativos sem medida objetiva. Evite termos como `revolucionário`, `extraordinário`, `fundamental`, `crucial`, `impressionante` ou `dramático` apenas para intensificar a afirmação.
7. Não aumente a importância de um resultado além do que a evidência permite. Descreva o efeito e sua consequência técnica diretamente.
8. Evite qualificadores vagos como `possivelmente`, `potencialmente`, `de certa forma`, `em grande medida` ou `pode-se dizer` quando não expressarem incerteza real. Quando houver incerteza, diga sua origem: hipótese, limitação dos dados, aproximação do modelo ou evidência conflitante.
9. Não encerre uma seção com conclusão genérica que não acrescente informação.

## Formato do índice (`wiki/index.md`)

Gerado por `python scripts/build_index.py`; nunca editar à mão.

```markdown
- [Título do Essay](essays/nome-do-arquivo.md) — Resumo do frontmatter, em uma linha só.
  `tag-1` · `tag-2`
```

Contém apenas essays, em ordem decrescente de `created`, usando `summary` e `tags` do frontmatter.

## Formato de páginas em `wiki/insights/`

Frontmatter: `tags`, `sources`, `created`, `updated`, `maturidade: solta | germinando | madura | absorvida`. Corpo curto em prosa e `## Conexões`. Detalhes de fluxo em `/insight`.

Insights ficam fora de `wiki/index.md`.

## Formato do log (`wiki/log.md`)

```markdown
## [YYYY-MM-DD] operação | Título
Descrição breve do que foi feito.
```

Append-only. Não altere entradas antigas.

## Formato do manifesto de sources (`wiki/sources/manifest.md`)

Uma entrada por fonte processada:

```markdown
## [YYYY-MM-DD] nome-do-arquivo-original.pdf
Tipo: <tipo controlado>
Tags: [tag1, tag2]
Pasta: wiki/sources/<subpasta>/
Virou: [[slug-do-essay|Essay]] | enriqueceu [[slug|Essay]] | ainda não — ver resumo | None
Verificação: referências confirmadas | não verificado — checar antes de citar
```

`Tags:` é obrigatório e usa o mesmo vocabulário das páginas. Atualize manifesto e mapa quando a fonte sair de `raw/` para `wiki/sources/`.

Numa fonte `Tipo: Ensaio Completo Importado`, `Virou:` é obrigatório. `None`, `nenhum`, `nenhuma`, `-` e `—` registram explicitamente que a fonte não virou essay.

## Formato do mapa de sources (`wiki/sources/map.md`)

Lista plana de fontes já processadas:

```markdown
- [[slug-do-source|Nome do Source]] — Tipo · Tags: tag1, tag2 · Status
  - Status: Importado como [[Essay]] | Resumido — ver resumo | Absorvido em [[Essay]]
```

`raw/` não entra no mapa.

## Nomenclatura de páginas

- Arquivo de página: kebab-case + `.md`.
- Título: Title Case.
- Wikilink: `[[nome-do-arquivo|Título Visível]]`.
- Sources preservam o nome original na subpasta do tipo.

## Tratamento de imagens

1. Salve imagens em `wiki/assets/` com o nome `<slug-do-essay>_fig<N>.<ext>`,
   onde `N` é a ordem de aparição no texto — o nome do arquivo diz sozinho
   de que essay é a figura e onde ela entra. Nunca use base64 inline.
   Figura usada por dois essays é copiada, não compartilhada: cada essay
   é dono das suas.
2. Extraia figuras relevantes de fontes durante a ingestão.
3. Use caminho relativo: `../assets/...` em essays e `../../assets/...` em resumos de sources.
4. Descreva em texto a informação essencial de gráficos e diagramas.
5. **Toda figura tem legenda.** Uma linha em itálico logo abaixo da imagem, separada por linha em branco:

   ```markdown
   ![alt](../assets/arquivo.png)

   *Figura 3. Curva de calibração do modelo contra os placares observados.*
   ```

   Numeração sequencial dentro do essay, começando em 1. Num mosaico, a legenda
   vem depois da última imagem do grupo e descreve o conjunto. Uma figura
   desdobrada em painéis usa letra: `*Figura 29 (a). …*`. A legenda é uma frase curta que diz o que a figura mostra — não repita o alt nem explique o argumento, que é papel da prosa. `fix_lint.py` avisa quando falta.

## Conversão de fontes (HTML/PDF/DOCX → Markdown)

- Preserve blockquote apenas quando o original tiver bloco semântico equivalente.
- Converta tabelas para Markdown.
- Remova TOC do original; use `## Sumário`.
- Normalize labels de capítulo e símbolos residuais.
- Extraia imagens relevantes.
- Compare o Markdown final com a fonte para verificar fidelidade.

## Regra de contradição entre fontes

Se uma fonte nova ou uma afirmação do Usuário contradizer conteúdo existente, não escolha um lado nem faça média. Mostre as duas versões com localização exata e espere a decisão do Usuário antes de editar.

## Fechamento padrão de essay único

Skills que editam um essay específico fecham com:

```bash
python scripts/check_wiki.py <slug>
python scripts/fix_lint.py <slug>
```

Aplique correções mecânicas inequívocas e reporte o restante. Use `/organize <slug>` apenas quando o Usuário pedir auditoria completa daquele essay.
