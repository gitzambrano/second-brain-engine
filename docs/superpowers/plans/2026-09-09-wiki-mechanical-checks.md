# Wiki Mechanical Checks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand `check_wiki.py` with objective structural checks, conservative editorial heuristics and CI-strict failure semantics.

**Architecture:** Keep `check_wiki.py` as the single read-only entrypoint. Extract small pure helpers in the same module for callouts, figures, prose signals, references and Git metadata; each helper returns standard issue dictionaries so existing JSON and human reports remain compatible.

**Tech Stack:** Python 3.11, PyYAML, pytest, Git CLI.

**Spec:** User-approved requirements in this task, constrained by `.agents/skills/conventions/SKILL.md`.

## Global Constraints

- No content is rewritten or corrected automatically.
- Objective malformed syntax is `ERROR`; editorial heuristics are `WARNING` or `INFO`.
- `--strict` returns non-zero only for `CRITICAL` and `ERROR`.
- Tests use `tests/fixtures/mini-brain/`, never `data/`.

---

### Task 1: Callout and figure contracts

**Files:** `scripts/check_wiki.py`, `tests/test_wiki_mechanical_contracts.py`

- [ ] Add failing fixture mutations for invalid callout type, alias, warning title, todo title, internal H2/H3, callout density, second abstract, figure filename/order/caption mismatch.
- [ ] Run the focused pytest module and observe each missing code fail.
- [ ] Add a blockquote-aware parser and figure scanner that return issue dictionaries.
- [ ] Run focused pytest and commit the passing contract.

### Task 2: Editorial and reference contracts

**Files:** `scripts/check_wiki.py`, `tests/test_wiki_mechanical_contracts.py`

- [ ] Add failing mutations for metadiscourse, anthropomorphization, vague authority, promotional/vague uncertainty, reference sequence/title/Link position/duplicate URL/mutable-source access date.
- [ ] Run focused pytest and observe failure.
- [ ] Add conservative regular-expression checks outside code fences and reference parsing.
- [ ] Run focused pytest and commit the passing contract.

### Task 3: Git freshness, visibility and strict CI

**Files:** `scripts/check_wiki.py`, `tests/test_wiki_mechanical_contracts.py`, `scripts/check_repo.py`

- [ ] Add failing tests for `--strict` exit behavior and visibility folded into the checker.
- [ ] Run focused pytest and observe failure.
- [ ] Add `--strict`, reuse `check_visibility_field.audit()`, and add a Git comparison helper that skips safely without a parent revision.
- [ ] Run focused pytest, full wiki gate and corpus audit; classify all real-corpus findings without modifying essays.

### Task 4: Publication closure

**Files:** generated `site/` only

- [ ] Run the complete test suite appropriate to changed scripts and `python scripts/check_repo.py --quick`.
- [ ] Rebuild site and run visibility, privacy, browser, budget and seal gates.
- [ ] Commit/push engine and site only after every blocking gate passes.
