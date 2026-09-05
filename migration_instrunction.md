# Callout Migration Instructions

This file is the migration contract for Second Brain highlight boxes. The goal is to make box semantics explicit in Markdown while preserving the existing HTML/PDF visual language.

## Non-negotiable rule: no type inference

A callout exists only when the Markdown contains an explicit Obsidian header:

```markdown
> [!experiment] Experimento Mental I — O Navio de Teseu Biológico
> Corpo da caixa.
```

The exporter must **never** infer a type from the title, body, emoji, bold text, label wording, position, or surrounding section.

Consequences:

- `> Experimento Mental I` is a normal blockquote, not an experiment box.
- `> ⚠️ Atenção` is a normal blockquote unless it starts with an explicit `[!warning]`/`[!danger]` header.
- `> [!warning] Experimento Mental I` is a warning because the type is `warning`; the title does not override it.
- Unknown callout types are errors.
- Obsidian aliases such as `important`, `caution`, `check`, `faq`, and `cite` are not canonical source syntax; use the canonical type instead.

Plain blockquotes remain plain quotes:

```markdown
> Texto citado.
> Autor ou fonte.
```

## Titles

The text after `[!type]` is an arbitrary author-facing title. It may be omitted.

```markdown
> [!concept] Mapa Conceitual
> ...

> [!concept] Um título completamente diferente
> ...
```

Both boxes are `concept`. The title never changes the semantic type or visual family.

Obsidian folding markers (`+` and `-`) are parsed, but essays should avoid relying on folding because PDF is static and standalone HTML must remain readable without interaction.

## Canonical semantic types

These custom types are supported by the exporters and by `.obsidian/snippets/second-brain-callouts.css` in the data vault.

| Type | Use | HTML/PDF identity |
| --- | --- | --- |
| `experiment` | thought experiment, controlled scenario, test case | experiment/rust |
| `evidence` | empirical evidence, measured data, observed result | evidence/accent |
| `concept` | conceptual map, framework, high-level model | map/gold |
| `definition` | precise definition or terminology | map/gold |
| `assumption` | assumption, premise, modeling hypothesis | map/gold |
| `method` | procedure, recommended method, implementation method | map/gold |
| `source` | source-specific note or documentary basis | map/gold |
| `argument` | objection, attack, counterargument, philosophical tension | attack/rust |
| `result` | result, verdict, outcome; preferred as a nested callout | verdict/evidence |
| `conclusion` | local conclusion or synthesis | idea/gold |
| `idea` | brainstorm item, design idea, proposal | idea/gold |
| `meta` | editorial/meta note about the essay itself | neutral |
| `person` | compact person/philosopher profile | person card |
| `book` | compact book/work profile | book card |
| `pullquote` | author-selected typographic pull quote | pull quote |
| `epigraph` | opening or section epigraph | epigraph |
| `code` | short code/configuration note when a callout wrapper is useful | neutral |

The canonical native Obsidian types are also accepted: `note`, `abstract`, `info`, `todo`, `tip`, `success`, `question`, `warning`, `failure`, `danger`, `bug`, `example`, and `quote`.

Prefer the semantic Second Brain type when it exactly describes the role of the box. Use a native type for generic notes or when the native meaning is clearer.

## Rendering contract

The source type is the only classifier.

1. `scripts/lib/html_preprocess.py` parses explicit `> [!type]` blocks.
2. It maps the explicit type to the existing semantic HTML family (`.experimento`, `.evidencia`, `.mapa`, `.ataque`, `.aviso`, `.ideia`, `.generico`, cards, or quote components).
3. `scripts/essay_template.html` provides the established visual styling. Do not redesign the page shell to implement callouts.
4. `scripts/pdf_boxes.lua` reads the emitted semantic class. It does not inspect badge/title/body text to choose a color or type.
5. The Obsidian vault snippet gives custom callout types a matching visual identity in Obsidian.

Current family mapping:

| Types | Family |
| --- | --- |
| `experiment`, `example` | `experimento` |
| `evidence`, `info`, `success`, `result` | `evidencia` |
| `concept`, `definition`, `abstract`, `assumption`, `method`, `source` | `mapa` |
| `argument`, `question`, `failure` | `ataque` |
| `warning`, `danger`, `bug` | `aviso` |
| `idea`, `tip`, `conclusion` | `ideia` |
| `note`, `todo`, `meta`, `code` | `generico` |
| `person`, `book` | cards |
| `pullquote`, `epigraph` | typographic pull quotes |
| `quote` | explicit quote component |

## Nested results

Nested callouts are supported to depth 2. Use `result`/`conclusion` inside a semantic box when the result belongs to that box:

```markdown
> [!experiment] Experimento Mental III — O Cérebro Dividido
> Descrição do experimento.
>
> > [!result] Veredicto
> > A teoria não preserva unicidade sob divisão.
```

The exporter renders the nested result as the existing verdict footer. No search for the words “Veredicto”, “Resultado”, or “Resposta” occurs.

## Code blocks and mobile

Do not automatically convert fenced code blocks. A migration decision must be explicit.

Keep a fenced code block when exact syntax, indentation, whitespace, or copy/paste semantics matter. Always specify the language when known.

Use a callout with normal Markdown instead when the block is really explanatory pseudocode, a sequence of conceptual steps, a configuration explanation, a sample result, or prose that was put in monospace only for emphasis. Useful replacements include:

- `[!example]` or `[!experiment]` for a worked example;
- `[!method]` for a procedure;
- `[!info]` or `[!concept]` for explanatory structure;
- `[!success]`/`[!result]` for expected output;
- `[!warning]`/`[!danger]` for unsafe or invalid usage.

A real code fence may live inside a callout, but the wrapper does not make long code lines responsive. Real code remains horizontally scrollable on mobile. Prefer splitting long lines where the language permits it.

No exporter or migration script may decide that a block “looks like code” or “looks like a concept” and silently change its type.

## Migration procedure for legacy essays

1. Generate HTML and PDF from the untouched current source and keep them as BEFORE baselines.
2. Identify each legacy highlighted component manually from the source and existing export.
3. Assign one explicit callout type to each component.
4. Rewrite only that component to `> [!type] Title` syntax. Preserve prose verbatim unless the user requested editorial changes.
5. Keep ordinary blockquotes ordinary.
6. Keep real fenced code as code unless a manual migration decision says otherwise.
7. Regenerate HTML/PDF with the same exporters.
8. Compare BEFORE/AFTER. Outside callout regions, visual changes are regressions.
9. Validate Obsidian rendering with the custom snippet enabled.

The one-time migration may involve manual classification. The production exporter must never contain legacy label/emoji/body heuristics to reproduce that classification.
