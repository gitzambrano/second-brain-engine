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

### `updated:` mede o texto, não a manutenção

Altere `updated:` somente quando a prosa do corpo mudar substancialmente, como capítulo novo, argumento reescrito ou seção fundida/dividida.

## Tags — Vocabulário Controlado

`tags:` das páginas e `Tags:` de `wiki/sources/manifest.md` usam o mesmo vocabulário, consolidado em `tags_in_use` de `wiki/index.json`.

- Confira `tags_in_use` antes de criar tag nova.
- Reuse uma tag existente sempre que ela cobrir o tema; crie uma nova apenas quando nenhuma servir.
- Use uma única grafia em Title Case, sem variantes por plural, acento ou sinônimo.
- Tags representam temas, não tipo de essay/source.
- Use 2 a 5 tags por essay ou source.
- Renomeação em massa exige aprovação.

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

`manifest.md` e `map.md` são catálogos editáveis; documentos originais arquivados em `wiki/sources/` permanecem intocados.

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
- A saída pública nunca expõe corpo não autorizado, link de leitura restrito ou caminho para `data/`.
- Apenas assets referenciados por essays `public` podem aparecer na saída pública.
- Metadata de essays `private` pode aparecer no catálogo e no mapa; essays `hidden` não aparecem.

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

## Callouts / caixas de destaque

Sintaxe do Obsidian. Blockquote sem `[!tipo]` é citação, nunca caixa.

Use caixa apenas para experimento, evidência, ficha, métrica ou outro bloco que interrompa a leitura deliberadamente. Use prosa quando parágrafo, subtítulo, lista ou tabela bastarem.

`note` é o tipo padrão. Use outro tipo somente para a função definida na tabela.

### A tabela

Escolha pela **função do bloco no argumento**, nunca pela cor que você quer ver.

| Tipo | Use quando o bloco é | Não use para | Título | Corpo | Quanto usar |
| --- | --- | --- | --- | --- | --- |
| `note` | ressalva, contexto, nota filosófica ou metodológica, digressão lateral | evidência, experimento, entidade, métrica | curto, ou nenhum | prosa livre | **o padrão** — na dúvida, este |
| `info` | evidência empírica: estudo, dado medido, observação documentada, resultado de terceiros | opinião, exemplo inventado, "informação interessante" | o rótulo da evidência (`Evidência`, `Estudo seminal`) | citação + resultado; `####` opcional para o achado | use com cautela |
| `example` | experimento mental, caso trabalhado, cenário hipotético, aplicação | evidência real, dado empírico | o rótulo numerado (`Experimento Mental IV`) | `####` com o nome do caso, depois a narrativa | use com cautela |
| `abstract` | mapa conceitual, definição formal, framework, síntese estrutural | resumo qualquer, nota solta | o nome do mapa ou da definição | pode conter tabela ou lista | no máximo um por seção |
| `todo` | pessoa, organização ou obra que merece ficha | tarefa | **nome da entidade** | primeiro `####` = metadados; depois, a relevância | uma por entidade citada |
| `warning` | um número-chave | atenção genérica, alerta textual | **o próprio valor** (`39%`, `0,12 ft/s`) | explicação; `---` separa a nota de fonte | raro |
| `success` aninhado | veredicto da caixa que o contém | conclusão de seção | `Veredicto` | o desfecho em uma ou duas frases | um por caixa de teste |
| `success` solto | resultado confirmado, fora de caixa | qualquer boa notícia | o rótulo do resultado | prosa curta | raro |
| `question` | objeção, tensão, pergunta em aberto que estrutura o que vem depois | pergunta retórica, FAQ | a pergunta, com `?` | o desenvolvimento da tensão | raro |
| `failure` | hipótese rejeitada, teste que falhou, alternativa descartada | erro de digitação, crítica leve | o que falhou | por que falhou | raro |
| `danger` | invalidez, risco crítico, erro conceitual grave | ênfase forte | o risco | a consequência | raríssimo |
| `bug` | defeito de implementação, falha de software | erro de raciocínio | o defeito | reprodução e efeito | raríssimo |
| `quote` | citação que merece destaque editorial | toda citação; prosa comum | nenhum, ou o contexto | texto entre `“ ”`; atribuição na linha seguinte | quando sustentar o argumento |

Limite: até **6 caixas por mil palavras**.

Se o essay tiver mais de oito caixas, use mais de um tipo quando houver funções distintas. Use o rótulo existente para definir o tipo. Não invente rótulo ou função para criar variedade. Sequências uniformes de fichas ou catálogos podem manter um único tipo.

### Forma do bloco

```markdown
> [!example] Experimento Mental III
> #### O Cérebro Dividido
> Texto da caixa.
>
> > [!success] Veredicto
> > O desfecho.
```

- **O título é autoral.** Preserve o rótulo existente. Sem rótulo, escreva `> [!tipo]` sozinho.
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

No `todo`, o título é o **nome** e o `####` contém metadados. No `warning`, o título é o **número** e `---` separa a fonte. No `quote`, a atribuição vem depois de uma linha em branco, começando por travessão.

### O que não fazer

- alias (`tldr`, `summary`, `hint`, `important`, `caution`, `cite`, …) ou tipo inventado — é erro, não há fallback;
- escolher o tipo pela cor que ele produz;
- promover prosa comum a caixa só para dar destaque;
- usar `note` como depósito de tudo que sobrou;
- usar `warning` como "atenção" — ele é reservado a número;
- repetir o mesmo rótulo em dezenas de caixas: isso é um molde, não um destaque.

## Dois tipos de essay

- **Originais (`/import`)**: preserve a prosa do autor. Tradução ou edição substantiva exige pedido explícito. O documento arquivado em `wiki/sources/` permanece intocado.
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

São gerados e nunca editados manualmente.

Antes de escrever uma citação nova, procure a fonte em `wiki/references.md` por URL ou título. Se já existir, reutilize a citação canônica. Edição/tradução diferente conta como fonte distinta.

`concepts/` e `entities/` não recebem `## Referências` própria.

## Idioma

Escreva o conteúdo da wiki em **Português do Brasil**.

- Use Português do Brasil na prosa, headings, legendas, tabelas e texto visível de callouts.
- Preserve nomes próprios, títulos oficiais, siglas, símbolos, variáveis, nomes de funções, identificadores de código e termos cuja tradução reduza a precisão.
- Termos técnicos em inglês podem permanecer em inglês quando forem a forma consagrada na área ou quando a tradução introduzir ambiguidade. Use o mesmo termo de forma consistente ao longo do texto.
- Preserve o idioma original de títulos bibliográficos.
- Os identificadores de callout (`note`, `info`, `example`, etc.) permanecem em inglês porque fazem parte da sintaxe.

## Estilo de prosa

Vale para texto novo ou reescrito pela wiki. Texto original importado só muda sob pedido editorial explícito.

### Regras gerais

1. **Uma proposição principal por frase.** Prefira frase direta, completa e sem enchimento. Divida a frase quando ela acumular afirmação, ressalva, consequência e comentário lateral. Conexões estreitamente dependentes podem permanecer juntas; concisão não é estilo telegráfico.

2. **Um tema por parágrafo.** Abra o parágrafo com o tema e desenvolva esse mesmo ponto. Se o texto muda de mecanismo para consequência, de evidência para interpretação ou para outra ideia independente, considere um novo parágrafo.

3. **Use o mesmo termo para o mesmo conceito.** Mantenha grafia consistente para termos, siglas, unidades e variáveis. Não alterne sinônimos apenas para evitar repetição quando isso puder sugerir conceitos diferentes.

   Evite: usar `ângulo de ataque` e depois `incidência` para a mesma variável sem definir a equivalência.  
   Prefira: escolher um termo canônico ou explicitar a diferença entre conceitos próximos.

4. **Explicite causa, condição, contraste e sequência quando necessários.** Use conectores apenas quando representarem a relação lógica real.

   Evite: `O rotor acelera. Portanto, a pá avança.` quando a relação causal não foi estabelecida.  
   Prefira: use `portanto`, `porque`, `embora`, `se` ou `quando` somente quando essa relação fizer parte do argumento.

5. **Prefira verbos simples e precisos a perífrases e nominalizações.**

   Evite: `foi realizada uma avaliação da influência de X`.  
   Prefira: `avaliamos a influência de X` ou `a análise mede a influência de X`, conforme o agente real da ação.

6. **Corpo argumentativo em prosa; bullets apenas para listas reais.** Use listas para condições, hipóteses, critérios, etapas ou itens independentes. Não fragmente raciocínio contínuo apenas para tornar a página mais escaneável.

7. **Não use ponto e vírgula na prosa.** Separe em frases ou use outra construção sintática.

8. **Use travessões raramente: no máximo 1 a 2 em todo o corpo de um essay.** Não os use como pontuação padrão para comentários laterais.

   Evite: `O modelo — apesar da simplificação — reproduz — em parte — a tendência.`  
   Prefira: `Apesar da simplificação, o modelo reproduz parte da tendência.`

9. **Use parênteses apenas para informação curta.** Evite colocar argumento dentro deles. Evite também atalhos tipográficos como `/`, `~`, `--`, `5-30`, `Cap.`/`Sec.`, `e.g.` e `i.e.` quando uma formulação normal for mais clara.

10. **Elimine metadiscurso dispensável.** Não anuncie o que o texto fará, acabou de fazer ou pretende demonstrar quando a própria argumentação já mostra isso.

    Evite: `Nesta seção, veremos como o modelo funciona.`  
    Prefira: `O modelo combina duas hipóteses.`

    Evite: `Como vimos anteriormente, esse resultado é importante.`  
    Prefira: declare diretamente qual resultado importa e qual é sua consequência.

11. **Evite frases de efeito, tríades, paralelismos e contrastes simétricos usados apenas para ritmo ou ênfase.** Use essas estruturas somente quando cada elemento expressar uma distinção necessária ao argumento.

    Evite: `Não é apenas uma equação; é uma janela para a própria natureza do voo.`  
    Prefira: descreva o que a equação permite calcular ou compreender.

12. **Não atribua autoridade a fontes vagas.** `Estudos mostram`, `a literatura indica` ou `especialistas afirmam` exigem fonte identificável.

    Evite: `Estudos mostram que a configuração é mais estável.`  
    Prefira: `Johnson [3] encontrou maior amortecimento de arfagem nessa configuração.`

13. **Preserve a voz do autor.** Corrija clareza, precisão e excessos sem uniformizar o texto em um estilo genérico. Não substitua escolha autoral válida apenas porque outra formulação seria possível.

14. **Escreva apenas o estado final do argumento.** Não mencione versões anteriores, correções, pedidos do Usuário ou alternativas descartadas fora da própria discussão intelectual do essay.

    Evite: `Na versão anterior, esta seção tratava X.`  
    Prefira: escreva diretamente a versão final.

### Regras adicionais para essays técnicos

1. **Use português claro, conciso, formal e assertivo.** Precisão técnica tem prioridade sobre ornamentação, mas não elimine explicações necessárias apenas para encurtar o texto.

2. **Não antropomorfize código, modelos, equações ou teorias.** Descreva o mecanismo ou a operação real.

   Evite: `O modelo sabe que a aeronave está próxima do solo.`  
   Prefira: `O modelo reduz a velocidade induzida quando a razão \(h/R\) diminui.`

   Evite: `A equação tenta compensar o efeito.`  
   Prefira: `O termo adicional compensa o efeito.`

3. **Prefira voz ativa quando o agente for conhecido.** A voz passiva é aceitável quando o agente é irrelevante, desconhecido ou quando o objeto da ação é deliberadamente o foco.

   Evite: `Foi calculada a derivada usando diferenças centrais.`  
   Prefira: `O algoritmo calcula a derivada por diferenças centrais.`

4. **Use gerúndio somente quando sua relação temporal, causal ou lógica for clara e necessária.** Não use gerúndio como conexão genérica entre duas afirmações.

   Evite: `A velocidade aumenta, causando uma mudança no regime e produzindo maior estabilidade.`  
   Prefira: `O aumento de velocidade muda o regime aerodinâmico. Essa mudança aumenta o amortecimento.`

5. **Evite `isso/isto` com referente ambíguo e simplifique cadeias longas de `de/da/do`.** Nomeie novamente o conceito quando houver mais de um referente possível.

   Evite: `Isso modifica sua resposta.`  
   Prefira: `O aumento do amortecimento modifica a resposta de arfagem.`

6. **Não use linguagem promocional ou superlativos sem medida objetiva.** Evite `revolucionário`, `extraordinário`, `fundamental`, `crucial`, `impressionante` ou `dramático` apenas para intensificar a afirmação.

   Evite: `O método produz uma melhoria dramática.`  
   Prefira: `O erro RMS cai de 12% para 4%.`

7. **Não aumente a importância de um resultado além do que a evidência permite.** Separe resultado observado, interpretação e alcance.

   Evite: `O resultado demonstra definitivamente a validade do modelo.`  
   Prefira: `O modelo reproduz os dados deste conjunto dentro de 5%; isso sustenta sua validade neste regime de operação.`

8. **Evite qualificadores vagos quando não representarem incerteza real.** `Possivelmente`, `potencialmente`, `de certa forma`, `em grande medida` e `pode-se dizer` não substituem a origem da incerteza.

   Evite: `O efeito possivelmente decorre da esteira.`  
   Prefira: `A atribuição à esteira é incerta porque o ensaio não separa os efeitos de interferência e indução.`

   Quando houver incerteza, diga sua origem: hipótese, limitação dos dados, aproximação do modelo, erro de medição ou evidência conflitante.

9. **Não encerre uma seção com conclusão genérica que não acrescente informação.**

   Evite: `Assim, fica claro que compreender esses efeitos é fundamental para o projeto.`  
   Prefira: encerre com o resultado específico ou avance diretamente para a próxima seção.

## Formato do índice (`wiki/index.md`)

Gerado; nunca editar à mão.

```markdown
- [Título do Essay](essays/nome-do-arquivo.md) — Resumo do frontmatter, em uma linha só.
  `tag-1` · `tag-2`
```

Contém apenas essays, em ordem decrescente de `created`, usando `summary` e `tags` do frontmatter.

## Formato de páginas em `wiki/insights/`

Frontmatter: `tags`, `sources`, `created`, `updated`, `maturidade: solta | germinando | madura | absorvida`. Corpo curto em prosa e `## Conexões`.

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

`Tags:` é obrigatório e usa o mesmo vocabulário das páginas.

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

1. Salve imagens em `wiki/assets/` com o nome `<slug-do-essay>_fig<N>.<ext>`, onde `N` é a ordem de aparição no texto. Nunca use base64 inline.
2. Use caminho relativo: `../assets/...` em essays e `../../assets/...` em resumos de sources.
3. Descreva em texto a informação essencial de gráficos e diagramas.
4. Toda figura tem legenda em itálico logo abaixo da imagem:

   ```markdown
   ![alt](../assets/arquivo.png)

   *Figura 3. Curva de calibração do modelo contra os placares observados.*
   ```

5. Numere as figuras sequencialmente a partir de 1. A legenda deve identificar a figura sem simplesmente repetir o alt ou o argumento do parágrafo.

## Regra de contradição entre fontes

Se uma fonte nova ou uma afirmação do Usuário contradizer conteúdo existente, não escolha um lado nem faça média. Mostre as duas versões com localização exata e espere a decisão do Usuário antes de editar.

## Fechamento padrão de essay único

Skills que editam um essay específico fecham com:

```bash
python scripts/check_wiki.py <slug>
python scripts/fix_lint.py <slug>
```

Aplique correções mecânicas inequívocas e reporte o restante.