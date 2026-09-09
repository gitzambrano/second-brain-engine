# Public Reader Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make public essay pages typographically reliable, ergonomically legible on mobile, and fully covered by objective real-corpus browser QA without changing their layout geometry.

**Architecture:** Extend the existing public font bundle and public-essay renderer rather than the standalone export pipeline. Keep all reader styling in its current template/Atlas overlay boundary, and extend the site QA probe into a four-state viewport/theme matrix.

**Tech Stack:** Python, Pandoc template/CSS/JavaScript, Playwright, pytest, self-hosted WOFF2.

**Spec:** `docs/superpowers/specs/2026-09-09-public-reader-polish-design.md`

## Global Constraints

- Do not alter any reading width, column, figure, table, callbox, or reading-area width.
- Do not change callbox colors, fonts, borders, spacing, design, or semantics.
- Do not formalize or restructure figures or captions.
- The target is `site/essays`; do not regenerate standalone output HTML.
- Browser QA must test every public essay in desktop/mobile and explicit light/dark themes.

---

### Task 1: Make public reader fonts self-hosted and verifiable

**Files:**
- Modify: `scripts/lib/fetch_fonts.py`
- Modify: `scripts/build_site.py`
- Modify: `scripts/lib/render_public_essay.py`
- Test: `tests/test_site_font_contract.py`

- [ ] **Step 1: Write failing tests for the public font contract**

Assert that the site font request contains Playfair Display, Source Serif 4, and JetBrains Mono; that the built reader references local WOFF2 assets; and that system font fallbacks are not the declared public-reader family.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `pytest tests/test_site_font_contract.py -v`

Expected: FAIL because the current public bundle contains only Inter.

- [ ] **Step 3: Implement the smallest shared-font bundle extension**

Add a site-specific Google Fonts request for the three editorial families and make `build_site.py` serve it under `site/assets/fonts`. Ensure the renderer reads those local declarations and preserves its current semantic font mapping.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `pytest tests/test_site_font_contract.py -v`

Expected: PASS.

### Task 2: Polish header and TOC interaction without changing layout geometry

**Files:**
- Modify: `scripts/lib/render_public_essay.py`
- Test: `tests/test_public_reader_mobile_contract.py`

- [ ] **Step 1: Write failing CSS/DOM contract tests**

Assert 44 px header control hit areas, compact inter-control gap, `:focus-visible`, mobile TOC minimum sizes, a low-intensity active-state rail, and no assignments to reading-width, figure, table, or callbox selectors.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `pytest tests/test_public_reader_mobile_contract.py -v`

Expected: FAIL because the current header and TOC contracts are absent.

- [ ] **Step 3: Implement minimal CSS and TOC tracking**

Keep visible icon dimensions unchanged while enlarging button hit targets. Add restrained keyboard focus. Adjust only mobile TOC font-size/line-height/padding and add an IntersectionObserver that applies the active class and smooth, contained TOC alignment.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `pytest tests/test_public_reader_mobile_contract.py -v`

Expected: PASS.

### Task 3: Expand real-corpus site browser QA

**Files:**
- Modify: `scripts/check_site_pages.py`
- Test: `tests/test_check_site_pages.py`

- [ ] **Step 1: Write failing matrix and probe tests**

Assert that four explicit reader states are audited (`desktop-light`, `desktop-dark`, `mobile-light`, `mobile-dark`) and that the probe diagnoses missing editorial fonts, invalid image dimensions, table/code/MathJax overflow, clipped controls, TOC overflow, and unreadable TOC values.

- [ ] **Step 2: Run the focused test to verify it fails**

Run: `pytest tests/test_check_site_pages.py -v`

Expected: FAIL because the existing checker has viewport-only coverage.

- [ ] **Step 3: Implement objective probe checks and theme matrix**

Set the theme explicitly through local storage before each load; audit every generated public essay under all four states. Report only measurable failures and retain the existing site-level map/index checks.

- [ ] **Step 4: Run the focused test to verify it passes**

Run: `pytest tests/test_check_site_pages.py -v`

Expected: PASS.

### Task 4: Build, validate, publish, and record state

**Files:**
- Modify: `data/wiki/status.md`
- Generated: `site/`

- [ ] **Step 1: Run targeted and repository checks**

Run focused pytest files, `python scripts/check_repo.py --quick`, and the full publication gate sequence.

- [ ] **Step 2: Build and publish only after every gate passes**

Run `set_visibility.py`, `check_visibility_field.py`, `build_site.py`, privacy/browser/budget checks, and `seal_publication.py`; commit and push the separate `site` repository.

- [ ] **Step 3: Update session status and QMD**

Recalculate `wiki/status.md` with actual pending counts, then refresh the `secondbrain` QMD collection.
