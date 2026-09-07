# Contrato Principal de Callouts e Quotes

> **Status:** normativo vigente.
>
> Este arquivo é a autoridade principal para autoria, migração e renderização de callouts e quotes do Second Brain. O renderer implementa este contrato; ele não decide a semântica do conteúdo.

---

# 0. Escopo — inegociável

A evolução de callouts e quotes só pode alterar:

- a marcação Markdown dos próprios callouts/quotes;
- o parser e a emissão estrutural desses componentes;
- CSS exclusivo desses componentes;
- filtros e ambientes PDF exclusivos desses componentes;
- testes específicos de callouts/quotes.

É proibido usar esta mudança para alterar capa, masthead, Sumário, headings globais, tipografia global, largura de coluna, margens, links, referências, tabelas, matemática, imagens, código, figuras, responsividade geral ou regras globais de paginação.

**Exceção explícita e estreita aprovada para tabelas PDF:** o cabeçalho já existente de uma tabela pode receber somente um preenchimento de fundo dourado muito leve para harmonizar com o tema editorial. Esta exceção não autoriza mudar largura de colunas, margens, fonte, tamanho, padding, bordas, quebra de página, alinhamento, conteúdo, comportamento de `longtable`, tabelas HTML nem figuras.

Em essays, a migração pode mudar apenas a marcação estrutural necessária para expressar explicitamente o tipo correto, o título autoral, um `####` interno já semanticamente existente, nesting explícito e a separação explícita entre citação e atribuição. A prosa, equações, tabelas, listas, imagens, links, código e referências permanecem intactos.

---

# 1. Regra central: zero heurística

## 1.1 O tipo explícito é a fonte de verdade

O source aceita exatamente estes 13 tipos-base nativos do Obsidian:

`note`, `abstract`, `info`, `todo`, `tip`, `success`, `question`, `warning`, `failure`, `danger`, `bug`, `example`, `quote`.

Aliases (`summary`, `tldr`, `hint`, `important`, `check`, `done`, `help`, `faq`, `caution`, `attention`, `fail`, `missing`, `error`, `cite`), tipos customizados e tipos desconhecidos são erro. Não existe fallback silencioso.

A classe visual nasce **somente** do `[!type]` explícito. O renderer não pode usar título, palavras do corpo, emoji, número, `%`, nome próprio, ano, posição, ordem, heading, link, cor ou contexto para escolher outra classe.

Consequências obrigatórias:

- `Experimento Mental III` não cria `example`; o source precisa escrever `[!example]`.
- `Ideia 07` não cria `tip`; o source precisa escrever `[!tip]`.
- `Evidência Empírica I` não cria `info`; o source precisa escrever `[!info]`.
- `Thomas Hobbes` não cria card de entidade; o source precisa usar o tipo reservado para entidade.
- `39%` não cria card estatístico; o source precisa usar o tipo reservado para métrica.
- `?`, `⚠️`, `IMPORTANTE`, `CRÍTICO` ou caixa alta não mudam o tipo.
- um blockquote simples `>` nunca vira callout.

Se o autor escolher o tipo errado, o renderer produz a aparência daquele tipo. Ele **não corrige** a intenção por inferência.

## 1.2 Estrutura explícita, não interpretação textual

O renderer pode reagir à estrutura Markdown definida neste contrato — por exemplo, título após `[!type]`, `####`, `---`, nesting e posição de blocos — porque esses elementos são marcação explícita. Ele nunca inspeciona o significado do texto contido nesses elementos.

A única exceção visual baseada em contexto estrutural já autorizada é `success` **diretamente** aninhado em outro callout: ele vira footer/veredicto do pai. O veredicto herda a cor visual do tipo explícito do pai por herança estrutural (`--boxc` no HTML e `wbtype` no PDF); ele não escolhe cor por título, corpo ou significado. Um `success` dentro de um quote que por sua vez está dentro de um callout não é filho direto e não vira veredicto.

---

# 2. Gramática canônica

## 2.1 Cabeçalho autoral + subtítulo

```markdown
> [!example] Experimento Mental III
> #### O Cérebro Dividido
> Texto da caixa.
```

Interpretação:

- `example`: chave semântica/visual invisível;
- `Experimento Mental III`: título autoral da caixa;
- `#### O Cérebro Dividido`: subtítulo real dentro da caixa;
- corpo: Markdown normal.

O renderer nunca acrescenta `EXEMPLO`, `NOTA`, `RESUMO`, `INFORMAÇÃO`, `CITAÇÃO` ou qualquer nome automático de tipo.

## 2.2 Sem título

```markdown
> [!info]
> Resultado medido no ensaio.
```

Nenhuma faixa vazia ou título inventado é criado.

## 2.3 Conteúdo rico

Qualquer callout pode conter parágrafos, listas, links, tabelas, matemática, imagens, fenced code, headings e callouts aninhados. A caixa não modifica o comportamento global desses elementos.

## 2.4 Fold

`[!type]+` e `[!type]-` continuam válidos. HTML pode refletir o estado inicial; PDF renderiza o conteúdo aberto.

---

# 3. Referência completa dos treze tipos

A associação é fixa e determinística. Nenhuma linha desta tabela é inferida do
conteúdo: tudo vem do `[!tipo]` escrito no source.

## 3.1 Papel editorial e formato aceito

| Tipo | Quando usar | Formato aceito no source |
| --- | --- | --- |
| `info` | evidência empírica, dado factual, observação | `> [!info] Título` · `> [!info]` · `####` inicial vira subtítulo |
| `abstract` | mapa conceitual, definição, framework, síntese | idem `info` |
| `tip` | ideia, insight, proposta destacável | idem `info` |
| `example` | experimento mental, exemplo trabalhado, cenário | idem `info` |
| `note` | nota filosófica, epistemológica, metodológica | `> [!note] Título` · `> [!note]` |
| `todo` | entidade: pessoa, organização, obra | `> [!todo] Nome` + `> #### metadados` (datas · país · instituição) |
| `warning` | métrica, número-chave, estatística | `> [!warning] Valor` + corpo + `> ---` + nota de fonte |
| `success` | resultado confirmado; **aninhado**, veredicto do pai | `> [!success] Título` · aninhado: `> > [!success] Veredicto` |
| `question` | objeção, tensão, pergunta aberta | `> [!question] Título` · `> [!question]` |
| `failure` | hipótese rejeitada, teste falho | idem `question` |
| `danger` | risco ou invalidez crítica | idem `question` |
| `bug` | defeito de software/implementação | idem `question` |
| `quote` | citação com destaque editorial | `> [!quote] Título?` + `“texto”` + linha em branco + atribuição |

Todos aceitam fold (`[!tipo]+`, `[!tipo]-`) e, no corpo, Markdown normal:
parágrafos, listas, tabelas, matemática, imagens, fenced code e aninhamento.

## 3.2 Como cada tipo renderiza

`html escuro` e `html claro` dão a cor do token `--callout-<tipo>`; `pdf` dá a
cor LaTeX correspondente. O PDF tem paleta única, alinhada ao tema claro.

| Tipo | Família | HTML escuro | HTML claro | PDF (`\definecolor`) | Ambiente LaTeX |
| --- | --- | --- | --- | --- | --- |
| `info` | tab editorial | `#B08B4F` ouro | `#2F5FB0` azul | `boxev` `#2F5FB0` | `wikitab` |
| `abstract` | tab editorial | `#C0A268` ouro claro | `#2F7182` azul-petróleo | `boxmap` `#2F7182` | `wikitab` |
| `tip` | tab editorial | `#9C8347` ouro oliva | `#234A86` azul profundo | `boxid` `#234A86` | `wikitab` |
| `example` | tab editorial | `#B96A50` terracota | `#8C4A37` terracota | `boxexp` `#8C4A37` | `wikitab` |
| `note` | nota tonal, faixa lateral | `#A2988A` areia | `#4A5C77` ardósia | `boxnote` `#4A5C77` | `wikinote` |
| `todo` | entity card | `#B18A4A` bronze | `#7B5C22` bronze | `boxentity` `#7B5C22` | `wikientity` |
| `warning` | stat card | `#D66E5C` coral | `#A5483B` coral | `boxstat` `#A5483B` | `wikistat` |
| `success` | estado / rodapé | `#63A37B` verde | `#2F7951` verde | `boxsuccess` `#2F7951` | `wikistate` |
| `question` | estado | `#B76550` ferrugem | `#8A4939` ferrugem | `boxquestion` `#8A4939` | `wikistate` |
| `failure` | estado, régua tracejada | `#A95C4C` | `#874238` | `boxfailure` `#874238` | `wikistate` |
| `danger` | estado, régua forte | `#D06A58` | `#A13F34` | `boxdanger` `#A13F34` | `wikistate` |
| `bug` | estado, mono | `#C65F52` | `#963A32` | `boxbug` `#963A32` | `wikistate` |
| `quote` | pull quote | `#8A857E` cinza | `#5B6472` cinza | `quoteline` `#8A6B33` | `wikipull` |

Regra de paleta: o tema claro é azul sobre branco e o escuro é dourado sobre
preto, então os quatro tipos de uso comum (`info`, `abstract`, `tip`, `note`)
saem em tons da cor do tema. Cor destoante — terracota, coral, verde, ferrugem
— fica reservada para ênfase deliberada. Citação é cinza nos dois temas.

## 3.3 Estruturas reservadas

Sem título, a caixa não ganha faixa vazia e recebe respiro no topo em HTML
(`.box-untitled`) e no PDF (`wikitabuntitled`). Com título, a faixa nasce colada
na borda superior esquerda e o topo não leva respiro extra.

`success` aninhado herda a cor da caixa pai e vira o rodapé dela. `todo` reserva
o primeiro `####` como metadados; `warning` reserva o `---` como divisor antes
da nota de fonte. Nada disso inspeciona o texto.

---

# 4. Famílias visuais

## 4.1 Tab editorial — `example`, `tip`, `info`, `abstract`

É a família de referência para experimentos mentais, ideias, evidências e mapas conceituais.

### HTML

- caixa ocupa a largura normal da coluna;
- moldura hairline discreta;
- **o título autoral vira uma faixa retangular preenchida no canto superior esquerdo**;
- a faixa começa exatamente na borda superior e esquerda da caixa: sem recuo, sem margem e sem gap entre faixa e moldura;
- o preenchimento da faixa deve encostar visualmente na própria moldura externa, cobrindo qualquer filete que criaria um halo de 1 px no canto;
- depois da faixa existe um respiro vertical explícito de aproximadamente `0.65rem` antes do primeiro subtítulo ou parágrafo; não depender de colapso de margens do elemento seguinte;
- cantos da faixa quadrados; não usar pill;
- título da faixa em `JetBrains Mono`/mono equivalente, **uppercase visual**, letter-spacing amplo, peso normal/semibold;
- `text-transform: uppercase` é apresentação; o source não é reescrito;
- a cor preenchida da faixa é a cor explícita do tipo;
- `####` interno aparece abaixo como heading serif/display de destaque;
- corpo volta à tipografia normal do essay;
- sem sombra pesada e sem gradiente.

Variação cromática fixa:

- `example`: terracota/ferrugem;
- `tip`: ouro/oliva;
- `info`: azul/ciano dessaturado;
- `abstract`: teal/azul ou ouro frio, distinto de `info`.

Não existe regra do tipo “se o título contém Experimento, use faixa terracota”. A faixa terracota existe porque o tipo é `example`.

### PDF

A hierarquia deve ser a mesma, mas simplificada: regra/moldura leve, título autoral em pequeno versalete/mono e subtítulo `####` preservado. Não reproduzir efeitos que prejudiquem paginação.

## 4.2 Nota editorial — `note`

Referência visual: bloco tonal com faixa lateral forte, mais parecido com nota editorial do que com a moldura de experimento.

### HTML

- sem tab no canto;
- fundo levemente tingido pela cor de `note`;
- faixa lateral de 4–5 px;
- sem moldura completa obrigatória; se houver, deve ser quase invisível;
- título autoral em sans sem serifa, preservando capitalização, símbolos e emoji escritos pelo autor; não aplicar `text-transform` nem `MakeUppercase` nesta família; letter-spacing moderado, peso 650–750;
- corpo com maior contraste e bom respiro;
- pode usar sans no corpo da nota se isso ficar confinado a `.callout-note`; não altera a prosa global.

Exemplo:

```markdown
> [!note] Nota Filosófica
> Um problema recorrente na psicologia é definir precisamente o construto...
```

O renderer não escreve `NOTA FILOSÓFICA`; esse texto precisa estar no source.

### PDF

Faixa lateral forte + fundo quase branco/cinza tonal; título pequeno em sans/mono. Deve continuar breakable.

## 4.3 Entity card — `todo`

Usado quando uma pessoa, organização, obra ou fonte merece um bloco contextual próprio. **Nada vira entity card automaticamente.**

Formato preferencial:

```markdown
> [!todo] Thomas Hobbes
> #### 1588 – 1679 · Inglaterra
> Hobbes foi um dos primeiros a formalizar...
```

### HTML

- superfície sólida discreta, sem moldura completa pesada;
- faixa lateral 4–6 px em ouro/bronze;
- título autoral é o **nome da entidade**, em display serif, peso 700, sem tab;
- primeiro `####` é apresentado como linha de metadados: mono, uppercase visual, letter-spacing amplo, cor de acento;
- corpo serifado normal;
- sem avatar, ícone, bandeira ou imagem inventada.

A regra é estrutural e fixa: dentro de `todo`, o título é o nome; `####` é o nível de metadata. O renderer não verifica se há ano, país, nome próprio ou organização.

### PDF

Card simples com faixa lateral, nome em serif forte e metadata em mono pequeno. Nenhuma inferência textual.

## 4.4 Stat card — `warning`

Usado para um número, proporção, data, intervalo ou indicador que precisa dominar visualmente a caixa.

Formato preferencial:

```markdown
> [!warning] 39%
> Empresas no quartil superior de diversidade de gênero têm esta probabilidade adicional de superar financeiramente as do quartil inferior.
> ---
> [McKinsey, Diversity Matters Even More, 2023](https://example.org)
```

### HTML

- card com fundo de superfície elevado;
- border hairline completa e border-radius discreto, aproximadamente 8–10 px;
- faixa lateral 5–6 px em coral/terracota;
- título autoral muito grande, em display serif, cor coral, funcionando como **valor em evidência**;
- o renderer não verifica se o título é número: qualquer título de `[!warning]` recebe esse tratamento;
- corpo em serif, ligeiramente maior que metadata e menor que o valor;
- `---` dentro do callout cria divisor horizontal explícito;
- o parágrafo posterior ao divisor é a fonte/nota de rodapé do card, em mono menor e cor de link/acento;
- nenhum prefixo `ESTATÍSTICA`, `%`, `DADO` ou `FONTE` é inventado.

### PDF

Valor autoral destacado com tamanho maior, faixa lateral e divisor da fonte. Manter legibilidade e quebra de página; se a caixa for longa, pode quebrar sem perder a hierarquia.

## 4.5 Estados — `success`, `question`, `failure`, `danger`, `bug`

Esses tipos permanecem semanticamente diretos e visualmente diferentes da família tab, note, entity e stat.

- `success`: verde quando é um callout independente; quando é filho direto de outro callout, torna-se footer/veredicto e usa **a cor do pai**, herdada estruturalmente do tipo explícito do pai.
- `question`: ferrugem/roxo-terra suave, moldura ou regra média; nunca procura `?`.
- `failure`: regra tracejada; resultado negativo.
- `danger`: regra sólida forte e contraste maior; sem fundo vermelho saturado.
- `bug`: linguagem técnica, regra dupla/tracejada e mono no título; sem ícone de inseto.

O título autoral continua sendo o único título visível.

---

# 5. Quotes

## 5.1 Quote comum

```markdown
> “Texto da citação.”
>
> Autor, *Obra*, ano
```

A aspa explícita delimita o texto citado. O conteúdo após a aspa de fechamento, ainda no mesmo blockquote, é atribuição.

HTML: texto em itálico, aspas tipográficas **discretas** (ornamento secundário, nunca dominante), atribuição menor em mono/sans. Em desktop, o texto citado dentro da caixa é justificado como a prosa do essay; a atribuição não é justificada. PDF: versão ainda mais discreta, com aspas pequenas e sem ornamento dominante.

Um blockquote sem aspas explícitas não autoriza o renderer a adivinhar onde termina a citação e começa a atribuição.

## 5.2 `[!quote]`

Usa a mesma gramática, com destaque editorial maior. Título após `[!quote]` é opcional e autoral. Nunca imprimir `CITAÇÃO`, `AUTOR` ou `OBRA` automaticamente.

## 5.3 Nesting de quotes

Quotes podem conter outros quotes, inclusive em múltiplos níveis, usando a profundidade Markdown explícita (`>`, `> >`, `> > >`, ...). O parser preserva a árvore de blockquotes; ele remove apenas um nível por passagem. Aspas de uma citação interna nunca podem fechar a citação externa. A profundidade de quote não conta como profundidade de callout e não transforma um `success` em veredicto a menos que o `success` seja filho direto de um callout.

---

# 6. Tokens de tema

No HTML, cada tipo tem `--callout-<type>` com valor dark e light explicitamente distintos. A mesma identidade cromática é preservada, mas luminância e saturação são calibradas por tema.

Regras:

- `.callout-<type>` usa `var(--callout-<type>)`;
- desktop light e `data-theme="light"` usam a mesma paleta light;
- `data-theme="dark"` restaura a paleta dark;
- nenhuma família depende somente de cor: forma, moldura, faixa, tracejado, tab ou tipografia também diferenciam;
- nenhum tipo ganha ícone automático.

O PDF não precisa de duas paletas, mas deve preservar distinções de família por regra, estrutura e tipografia.

---

# 7. Paginação e conteúdo rico

Callouts PDF são breakable quando necessário. A implementação não pode modificar `\sbneedspace`, `\sbchapterneed`, `\sbsubneed`, penalties, `titlesec`, margens ou qualquer regra global de quebra.

Invariantes:

- título do callout não fica isolado do `####` imediatamente seguinte;
- tabelas, matemática, imagens e código mantêm seus mecanismos globais;
- no HTML desktop, tabelas permanecem dentro da largura da coluna de conteúdo e qualquer largura excedente rola **dentro da própria tabela**; callouts/quotes nunca fazem a tabela escapar lateralmente da coluna;
- nenhuma caixa cria overflow horizontal;
- nesting não duplica molduras desnecessariamente;
- `success` aninhado permanece dentro da caixa pai.

---

# 8. Migração dos essays

A migração é manual por bloco semântico. Nunca executar busca/substituição baseada em palavras para escolher tipo.

Para cada callout:

1. ler o bloco no contexto;
2. escolher explicitamente um dos 13 tipos;
3. escrever o `[!type]` correto;
4. separar título autoral e `####` quando já existirem dois níveis editoriais;
5. para entity card, usar explicitamente `todo` e `####` de metadata;
6. para stat card, usar explicitamente `warning` e `---` antes da fonte quando houver;
7. preservar integralmente o conteúdo intelectual;
8. validar HTML light/dark e PDF.

Conversões proibidas:

- título contém “Experimento” → `example`;
- título contém “Ideia” → `tip`;
- título contém “Evidência” → `info`;
- linha parece nome + anos → entity;
- título contém número ou `%` → stat card;
- emoji/pontuação → warning/danger/question.

Essas classificações só podem ser feitas editorialmente no Markdown, nunca pelo renderer.

---

# 9. Corpus de regressão dos 12 essays

As mudanças deste contrato devem ser testadas, no mínimo, nestes 12 casos:

1. `validacao-estocastica-dinamica-de-voo.md`
2. `principio-antropico-v7.md`
3. `podem-as-maquinas-pensar.md`
4. `quem-e-voce.md`
5. `ia-gestao-projetos-brainstorm-v2.md`
6. `xadrez-computacional.md`
7. `comparacao-dinamica-asa-fixa-vs-rotativa.md`
8. `metodos-matematicos-engenharia-aeroespacial.md`
9. `modelos-de-inflow-para-rotores.md`
10. `cy-inflow-uniforme-coleman.md`
11. `modelagem-estatistica-copa-2026.md`
12. `universo-computavel-llms-dinamica-de-voo.md`

O lote deve cobrir:

- tab editorial (`example`, `tip`, `info`, `abstract`);
- note;
- entity (`todo`);
- stat (`warning`);
- nested success;
- quote comum e `[!quote]`;
- matemática pesada;
- figuras e mosaicos;
- tabelas;
- fenced code;
- caixas longas quebrando página.

---

# 10. Critérios de aceite

A implementação só está pronta quando:

- o contrato acima foi commitado **antes** do código que o implementa;
- os 13 tipos são os únicos aceitos;
- aliases e tipos desconhecidos falham;
- não existe fallback heurístico;
- não existe regex/classificação por título, pessoa, número, `%`, emoji ou conteúdo;
- `example`, `tip`, `info` e `abstract` têm tab realmente colado à borda superior/esquerda;
- o tab usa uppercase visual e mono espaçada;
- `note` é visualmente distinto da família tab;
- `todo` produz entity card sem detectar entidade;
- `warning` produz stat card sem detectar número;
- `success` aninhado continua footer/veredicto;
- quotes mantêm texto e atribuição explicitamente separados;
- HTML light/dark são distintos e legíveis;
- PDF preserva conteúdo e paginação sem regressão global;
- os 12 essays de regressão exportam com sucesso;
- nenhuma mudança fora de callouts/quotes aparece no diff visual ou estrutural.

---

# 11. Regra de implementação

O código deve ser mais simples que o contrato, não mais inteligente.

> **Parser lê estrutura explícita. Renderer aplica estilo explícito. Nenhuma camada tenta adivinhar o que o autor quis dizer.**
