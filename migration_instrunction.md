# Callout Migration Instructions

This file defines the Second Brain callout contract for authors, migrations, HTML export, PDF export, and Obsidian.

## Core rule

The Markdown source uses **only canonical native Obsidian callout types**:

```markdown
> [!example] Experimento Mental III — O Cérebro Dividido
> Texto da caixa.
```

The order is always:

1. native Obsidian type: `[!example]`;
2. free author title: `Experimento Mental III — O Cérebro Dividido`;
3. body Markdown.

The title is visible in Obsidian and is preserved by HTML/PDF export. The title may be any text and never changes the type.

The exporter must **never infer a callout type** from title, body, emoji, bold text, wording, numbering, position, surrounding section, or legacy CSS class.

Examples:

```markdown
> [!warning] Experimento Mental I
> This is a warning because the type is `warning`.

> Experimento Mental I
> This is a normal blockquote because it has no `[!type]` header.
```

Unknown types, custom types, and aliases are rejected in canonical source.

## Canonical types

Use these native Obsidian identifiers only:

| Type | Second Brain use | Primary HTML/PDF identity |
| --- | --- | --- |
| `note` | generic note, editorial note, compact person/work note when no stronger type applies | neutral note/card language |
| `abstract` | definition, conceptual map, framework, model, conceptual aside | gold/map language |
| `info` | evidence, observation, measured data, documentary context | blue/evidence language |
| `todo` | action, procedure to execute, implementation checklist | action/accent language |
| `tip` | idea, insight, recommendation, design proposal | gold/idea language |
| `success` | result, verdict, confirmed outcome, local positive conclusion | result/evidence language |
| `question` | objection, counterargument, open question, philosophical tension | rust/attack language |
| `warning` | limitation, caveat, attention, borderline interpretation | amber/warning language |
| `failure` | failed test, rejected result, invalid condition | failure/rust language |
| `danger` | critical invalidity or high-severity warning | strong warning/rust language |
| `bug` | software defect or implementation fault | technical error language |
| `example` | thought experiment, worked example, scenario, test case | experiment/rust language |
| `quote` | pull quote, epigraph, deliberately highlighted quotation | typographic quote language |

Do not use aliases such as `summary`, `tldr`, `hint`, `important`, `check`, `done`, `help`, `faq`, `caution`, `attention`, `fail`, `missing`, `error`, or `cite`. Use the canonical type instead.

## Titles

The title after `[!type]` is free text and is part of the document content.

```markdown
> [!tip] Ideia 01 — RAG para documentação
> ...

> [!tip] Nome completamente diferente
> ...
```

Both are `tip`. Their visual family is identical because only the explicit type selects rendering.

Do not parse title prefixes such as `Ideia`, `Experimento Mental`, `Evidência`, `Ataque`, `Atenção`, or numbering to choose a style.

Do not auto-number callouts. If the title must say `Ideia 01` or `Experimento Mental IV`, write that numbering explicitly in the source.

## Body content

A callout body is normal Markdown. It may contain:

- multiple paragraphs;
- emphasis and links;
- lists;
- tables;
- equations;
- images;
- fenced code;
- headings/subheadings such as `###` and `####`;
- nested callouts.

Example:

```markdown
> [!abstract] Modelo de validação
> Introdução curta.
>
> ### Hipóteses
> Texto da subseção.
>
> ### Critério
> Texto da segunda subseção.
```

The exporter must preserve those headings inside the box. It must not flatten them into a title or infer a new callout type from them.

## Nested callouts

Nested native callouts are supported. A nested `success` is rendered as the established verdict/result footer because that behavior depends only on the explicit type and nesting, never on wording:

```markdown
> [!example] Experimento Mental III — O Cérebro Dividido
> Descrição do experimento.
>
> > [!success] Veredicto
> > A teoria não preserva unicidade sob divisão.
```

Other nested callouts remain normal nested callouts.

## Rendering contract

`[!type]` is the sole classifier.

1. `scripts/lib/html_preprocess.py` parses explicit native Obsidian callouts.
2. It adds an output class derived from the native type, such as `.callout-example` or `.callout-warning`.
3. The same explicit type maps to an existing Second Brain visual family used by `scripts/essay_template.html`.
4. `scripts/pdf_boxes.lua` reads emitted classes. It never searches badge/title/body text.
5. The callout title is emitted verbatim as the visible box title.
6. The rest of the essay shell — cover, typography, headings, TOC, margins, tables, figures, code, pagination — is outside the callout migration contract and must not change because of callout parsing.

Native type to established family:

| Native type | Existing visual family / historical components that informed it |
| --- | --- |
| `example` | `experiment`, `test-card`, worked-example boxes |
| `info` | empirical-evidence boxes, data/result cards |
| `abstract` | conceptual maps, definitions, explanatory asides, general conceptual callouts |
| `question` | `steelman`, attack/objection boxes, philosophical tensions |
| `warning` | warning/caveat callouts |
| `danger` | danger/critical callouts |
| `failure` | negative/invalid-result treatment |
| `bug` | technical fault treatment |
| `tip` | idea/recommendation boxes |
| `todo` | implementation/action/procedure boxes |
| `success` | verdict/result treatment |
| `note` | neutral notes and low-emphasis contextual cards |
| `quote` | `pull-quote`, `pullquote`, epigraph-style highlights |

Historical HTML components used to plan these identities include `callout-note`, `callout-warn`, `callout-danger`, `test-card`, `pval-card`, `pullquote`, `experiment`, `verdict`, `philosopher-card`, `disturbing-moment`, `pull-quote`, `neuro-box`, `steelman`, `aside`, and the general `callout` family.

## Code and mobile

Fenced code remains fenced code whenever exact syntax, indentation, whitespace, line structure, or copy/paste behavior matters. The exporter must not automatically convert code to another box type.

Some old blocks were formatted as code even though they were really prose-like structures. On mobile those blocks can be unnecessarily wide and require horizontal scrolling. Such a block may be **manually** migrated when its semantic role is clear:

- pseudocode or worked example → `[!example]`;
- implementation steps/checklist → `[!todo]`;
- explanatory model/configuration description → `[!abstract]` or `[!info]`;
- recommendation → `[!tip]`;
- expected result/output → `[!success]`;
- invalid use/caveat → `[!warning]`, `[!failure]`, or `[!danger]`.

Real code may also live inside any callout:

```markdown
> [!example] Exemplo de configuração
> ```python
> value = compute_case()
> ```
```

No production script may decide that a block “looks like code”, “looks like an idea”, or “looks like a warning” and silently change it.

## Migration procedure

For each legacy essay:

1. Generate HTML and PDF from the untouched source and keep them as BEFORE baselines.
2. Inspect the existing HTML components and source manually.
3. Assign a native Obsidian type to every intentional highlight.
4. Write `> [!type] Title` explicitly. Preserve the title and prose as document content.
5. Keep ordinary blockquotes ordinary.
6. Keep real fenced code as code unless a manual editorial migration is explicitly chosen.
7. Regenerate with the same HTML/PDF exporters.
8. Compare BEFORE/AFTER. Changes outside the highlighted components are regressions.
9. Test the Markdown directly in Obsidian; no custom callout type or CSS snippet is required for semantic recognition.

Manual classification is allowed during one-time migration. Runtime inference is not.