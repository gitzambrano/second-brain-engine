#!/usr/bin/env python3
"""check_agents.py - Audita a arquitetura canônica de agentes e subagents.

Valida a integridade da cadeia de sincronização:
1. Fonte única editável é exclusivamente ``.agents/``.
2. Espelhos em ``.claude/skills/`` e ``.claude/agents/`` são idênticos byte a byte.
3. Adaptadores em ``.codex/agents/*.toml`` estão sincronizados com seus pares em .md.
4. Hook de sessão em ``.claude/settings.json`` e documentação no AGENTS.md e CLAUDE.md
   obedecem ao contrato (sem menção a plugins obsoletos ou descompasso).

Escopo:
    Validação estática read-only da arquitetura de agentes no engine.

Entradas (Inputs):
    Diretórios .agents/, .claude/, .codex/ e documentação (AGENTS.md, CLAUDE.md, docs/AGENTS.md).
    Argumentos CLI opcionais:
        --json    Emite diagnóstico formatado em JSON

Saídas (Outputs):
    Stdout: Status PASS ou FAIL com divergências entre fonte e espelhos ou termos obsoletos.
    JSON: {"check": "agents", "status": "pass"|"fail", "errors": [...], "warnings": [...]}
    Exit code: 0 em conformidade, 1 se houver descompasso (drift) ou inconsistência.

Uso:
    python scripts/check_agents.py         # auditoria padrão
    python scripts/check_agents.py --json  # saída estruturada em JSON
"""
from __future__ import annotations

import argparse
import filecmp
import json
import re
from pathlib import Path

import console_encoding  # noqa: F401
from repo_paths import CODE_ROOT
from sanity_common import CheckResult
from sync_skills import PAIRS, sync_codex

OBSOLETE_TERMS = (
    "claude-plugin",
    "extraKnownMarketplaces",
    "enabledPlugins",
    "não existem mirrors",
    "não há passo de sincronização",
)


def _files(root: Path) -> set[Path]:
    if not root.is_dir():
        return set()
    return {p.relative_to(root) for p in root.rglob("*") if p.is_file()}


def audit() -> CheckResult:
    result = CheckResult("agents")

    agents_root = CODE_ROOT / ".agents"
    if not agents_root.is_dir():
        result.error("NO_SOURCE", ".agents/ não existe: não há fonte de skills")
        return result

    skills = sorted((agents_root / "skills").glob("*/SKILL.md"))
    agents = sorted((agents_root / "agents").glob("*.md"))
    if not skills:
        result.error("NO_SKILLS", ".agents/skills/ está vazio")
    if not agents:
        result.warning("NO_AGENTS", ".agents/agents/ está vazio")
    result.meta["skills"] = len(skills)
    result.meta["agents"] = len(agents)

    for source, dest in PAIRS:
        rel = dest.relative_to(CODE_ROOT).as_posix()
        if not dest.is_dir():
            result.skip("MIRROR_ABSENT", f"{rel} ainda não foi gerado; rode sync_skills.py")
            continue
        src_files, dest_files = _files(source), _files(dest)
        for missing in sorted(src_files - dest_files):
            result.error("MIRROR_MISSING", f"{rel}: falta {missing.as_posix()}")
        for extra in sorted(dest_files - src_files):
            result.error("MIRROR_ORPHAN", f"{rel}: sobra {extra.as_posix()} (sem origem)")
        for shared in sorted(src_files & dest_files):
            if not filecmp.cmp(source / shared, dest / shared, shallow=False):
                result.error("MIRROR_DRIFT", f"{rel}: {shared.as_posix()} difere da fonte")

    escritos, sobrando = sync_codex(check_only=True)
    for nome in escritos:
        result.error("CODEX_STALE", f".codex/agents/{nome} não corresponde ao .agents/agents/*.md")
    for nome in sobrando:
        result.error("CODEX_ORPHAN", f".codex/agents/{nome} não tem agent de origem")

    settings_path = CODE_ROOT / ".claude" / "settings.json"
    if not settings_path.is_file():
        result.error("NO_SETTINGS", ".claude/settings.json ausente: o sync não roda sozinho")
    else:
        raw = settings_path.read_text(encoding="utf-8")
        try:
            settings = json.loads(raw)
        except json.JSONDecodeError as exc:
            result.error("SETTINGS_INVALID", f".claude/settings.json não é JSON válido: {exc}")
            settings = {}
        hooks = json.dumps(settings.get("hooks", {}), ensure_ascii=False)
        if "sync_skills.py" not in hooks:
            result.error("HOOK_MISSING", "SessionStart não chama scripts/sync_skills.py")
        if "SessionStart" not in hooks:
            result.error("HOOK_MISSING", "não há hook de SessionStart")
        for term in ("plugin", "marketplace"):
            if term in raw.lower():
                result.error("SETTINGS_LEGACY", f"settings.json ainda cita {term!r}")

    if (CODE_ROOT / ".claude-plugin").exists():
        result.error("LEGACY_PLUGIN", ".claude-plugin/ não pertence à arquitetura atual")

    docs = sorted(list(CODE_ROOT.glob("*.md")) + list(CODE_ROOT.glob(".agents/**/*.md")))
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        for term in OBSOLETE_TERMS:
            if re.search(re.escape(term), text, re.IGNORECASE):
                result.error(
                    "DOC_LEGACY",
                    f"{doc.relative_to(CODE_ROOT).as_posix()} descreve arquitetura fora do contrato atual: {term!r}",
                )

    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on-warning", action="store_true")
    args = ap.parse_args()
    result = audit()
    result.print(args.json)
    return result.exit_code(args.fail_on_warning)


if __name__ == "__main__":
    raise SystemExit(main())
