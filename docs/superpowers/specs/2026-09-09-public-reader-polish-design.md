# Public Reader Polish Design

## Objective

Improve the public essay reader's type reliability, mobile header and TOC ergonomics, and browser QA without changing reading widths, columns, figure/table geometry, callboxes, or editorial content.

## Scope

The public `site/essays/*.html` pages are the only rendering target. The standalone `data/output/html` export remains untouched.

## Typography

The public-site font bundle will include and serve Playfair Display, Source Serif 4, and JetBrains Mono. The essay renderer will use those three declared families at their existing semantic roles. The build must not silently fall back to system Georgia, Times, Consolas, or equivalent fonts when preparing a publishable site.

## Mobile interaction

The header controls will keep their existing visual icon size and compact presentation while receiving 44 px square hit areas, a 4–6 px gap, and a restrained `:focus-visible` treatment. No control gains decorative chrome.

The mobile TOC will use approximately 13 px primary and 12.5 px secondary text, with hierarchy conveyed by indentation, weight, and a small tonal difference. Its active item uses only a low-intensity theme accent rail and tonal shift; smooth alignment may occur only within the TOC container.

## Non-goals

- No change to `--max-width`, reading columns, figure/table/callbox dimensions, captions, or callbox structure, colors, typography, borders, spacing, or semantics.
- No new callbox types, gradients, decorative shadows, glass effects, or new visual elements.
- No snapshot-based visual approval system.

## Browser QA

`check_site_pages.py` will audit every public essay in desktop/mobile and both explicit light/dark themes. It will report objective failures: external horizontal overflow, missing/broken or dimensionless images, viewport-escaping tables/code/MathJax, clipped visible elements, unavailable editorial fonts, out-of-viewport controls, overflowing TOC, JavaScript/request errors, and minimum readable TOC text or contrast failures. Mobile dark is a named matrix member, not an inferred default.

## Validation and publication

The site is rebuilt through the existing publish gates. Structural/unit checks cover the new QA contracts; browser QA exercises the real published corpus. The final publication runs visibility, privacy, browser, budget, and seal gates before committing and pushing `site/`. The session snapshot and QMD index are updated after the result is known.
