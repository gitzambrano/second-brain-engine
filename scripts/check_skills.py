#!/usr/bin/env python3
"""check_skills.py - Audita contratos estáticos de skills, subagents e suas referências.

Verifica a conformidade formal das skills em ``.agents/skills/`` e agentes em ``.agents/agents/``:
1. Frontmatter YAML canônico (name, description, license, metadata).
2. Tabela de metadados: command, mode (leitura/mutador/ambos/script), triggers, context, tools.
3. Ferramentas permitidas (allowed-tools) compatíveis com o modo declarado.
4. Nomes de comandos únicos e referências a scripts existentes.
5. Invariantes editoriais de estilo e ausência de caminhos hardcoded.

Escopo:
    Validação estática read-only em arquivos .agents/skills/*/SKILL.md e .agents/agents/*.md.

Entradas (Inputs):
    Arquivos Markdown e YAML em .agents/skills/ e .agents/agents/.
    Argumentos CLI opcionais:
        --json    Emite diagnóstico formatado em JSON

Saídas (Outputs):
    Stdout: Lista de issues com severidade (ERROR, WARNING, INFO) e sumário de conformidade.
    JSON: {"check": "skills", "status": "pass"|"warn"|"fail", "errors": 0, "warnings": 0, ...}
    Exit code: 0 em conformidade (ou warnings), 1 em erro de contrato ou frontmatter inválido.

Uso:
    python scripts/check_skills.py         # auditoria padrão
    python scripts/check_skills.py --json  # saída estruturada em JSON
"""
from __future__ import annotations

import argparse
import ast
import re
from collections import Counter
from pathlib import Path

import yaml
from repo_paths import CODE_ROOT, SCRIPTS_DIR, SKILLS_DIR, SUBAGENTS_DIR
from sanity_common import CheckResult

TOP_LEVEL_PATH_WORDS = {
    "wiki", "raw", "plan", "scripts", "output", "agents", "claude", "codex",
    "mnt", "tmp", "data", "home", "usr", "var", "etc",
}
WEB_TOOLS = {"WebFetch", "WebSearch"}
WRITE_TOOLS = {"Write", "Edit"}
MECHANICAL_SKILLS = {"organize", "connect", "linkify", "proofread", "polish", "sweep"}

SKILL_TOP_LEVEL_KEYS = {
    "name", "description", "license", "compatibility", "metadata", "allowed-tools",
}
REQUIRED_SB_METADATA = {
    "second-brain-role",
    "second-brain-mode",
    "second-brain-scope",
    "second-brain-approval",
    "second-brain-closure",
}
VALID_MODES = {"read", "write", "mixed"}
VALID_APPROVALS = {"none", "conditional", "before-write", "before-remote"}
VALID_CLOSURES = {
    "none", "single-essay", "multi-essay", "multi-page", "page", "draft",
    "artifact", "plan", "status", "source", "mechanical", "site-publish",
}
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
STALE_DESCRIPTION_RE = re.compile(
    r"\b(n[aã]o existe mais|foi abandonad[oa]|arquitetura antiga|antes disto|antes desse fluxo)\b",
    re.IGNORECASE,
)

SCRIPT_REF_RE = re.compile(r"scripts/([A-Za-z0-9_.-]+\.(?:py|sh|bat|lua|html))")
SLASH_REF_RE = re.compile(r"(?<![/\w.])/(?:[a-z][a-z0-9-]*)")
PY_COMMAND_RE = re.compile(r"python(?:3)?\s+scripts/([A-Za-z0-9_.-]+\.py)([^\n`]*)")
FLAG_RE = re.compile(r"(?<!\w)(--[a-zA-Z0-9][a-zA-Z0-9-]*)")
FENCE_RE = re.compile(r"```.*?```", re.S)
LINE_START_PREFIX_RE = re.compile(r"^[\s>*+\-–—#]*(?:\d+[.)]\s*)?$")
UPDATED_MENTION_RE = re.compile(r"`?\bupdated\b`?\s*:?", re.IGNORECASE)
UPDATED_MUTATION_VERB_RE = re.compile(
    r"\b(atualiz(?:e|em|ar|a|ada|ado)|alter(?:e|em|ar|a)|mex(?:a|am|er)|toqu(?:e|em)|tocar"
    r"|troqu(?:e|em)|trocar|marqu(?:e|em)|marcar|ajust(?:e|em|ar)|defin(?:a|am|ir)"
    r"|coloqu(?:e|em)|colocar|escrev(?:a|am|er)|preench(?:a|am|er)|renov(?:e|em|ar))\b",
    re.IGNORECASE,
)
UPDATED_NEGATION_RE = re.compile(r"\b(n[ãa]o|nunca|jamais|nem|nenhum|nenhuma|nenhuns|sem)\b", re.IGNORECASE)


def split_frontmatter(text: str) -> tuple[dict, str]:
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text
    raw = text[4:end]
    body_start = text.find("\n", end + 1)
    body = text[body_start + 1:] if body_start >= 0 else ""
    return yaml.safe_load(raw) or {}, body


def allowed_tools(meta: dict) -> set[str]:
    raw = meta.get("allowed-tools", meta.get("tools", []))
    if isinstance(raw, str):
        return {x for x in re.split(r"[\s,]+", raw) if x}
    if isinstance(raw, list):
        return {str(x) for x in raw}
    return set()


def script_options(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    except (OSError, SyntaxError):
        return set()
    options: set[str] = set()
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Attribute)
            or node.func.attr != "add_argument"
        ):
            continue
        current: list[str] = []
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("-"):
                current.append(arg.value)
                options.add(arg.value)
        action = next((kw.value for kw in node.keywords if kw.arg == "action"), None)
        if isinstance(action, ast.Attribute) and action.attr == "BooleanOptionalAction":
            for opt in current:
                if opt.startswith("--") and not opt.startswith("--no-"):
                    options.add("--no-" + opt[2:])
    return options


def adjacent_duplicate_sentences(body: str) -> list[str]:
    plain = re.sub(r"```.*?```", " ", body, flags=re.S)
    sentences = [re.sub(r"\s+", " ", x).strip() for x in re.split(r"(?<=[.!?])\s+", plain)]
    return [b for a, b in zip(sentences, sentences[1:]) if len(b) >= 60 and a == b]


def consecutive_duplicate_paragraphs(body: str) -> list[str]:
    paragraphs: list[str] = []
    current: list[str] = []
    in_fence = False
    for line in body.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if in_fence or line.lstrip().startswith("|"):
            continue
        if not line.strip():
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        if line.startswith("#"):
            if current:
                paragraphs.append(" ".join(current))
                current = []
            continue
        current.append(line.strip())
    if current:
        paragraphs.append(" ".join(current))
    normalized = [re.sub(r"\s+", " ", p).strip() for p in paragraphs]
    return [b for a, b in zip(normalized, normalized[1:]) if len(b) >= 80 and a == b]


def strip_fences(body: str) -> str:
    return FENCE_RE.sub(" ", body)


def updated_mutation_instructions(body: str) -> list[str]:
    found: list[str] = []
    for line in strip_fences(body).splitlines():
        for segment in re.split(r"[;.]\s|\s—\s", line):
            if not UPDATED_MENTION_RE.search(segment):
                continue
            verb = UPDATED_MUTATION_VERB_RE.search(segment)
            if not verb:
                continue
            if UPDATED_NEGATION_RE.search(segment[: verb.start()]):
                continue
            found.append(segment.strip())
    return found


def looks_like_command(body: str, match: re.Match[str]) -> bool:
    if body[match.end():match.end() + 1] == "/":
        return False
    line_start = body.rfind("\n", 0, match.start()) + 1
    prefix = body[line_start:match.start()]
    if prefix.endswith("`"):
        return True
    if prefix.lstrip().startswith("|"):
        return True
    return bool(LINE_START_PREFIX_RE.match(prefix))


def validate_skill_frontmatter(meta: dict, rel: Path, result: CheckResult) -> None:
    unknown = sorted(set(meta) - SKILL_TOP_LEVEL_KEYS)
    for key in unknown:
        result.warning(
            "FRONTMATTER_NONSTANDARD_KEY",
            (
                f"top-level key '{key}' is not part of the Agent Skills frontmatter contract; "
                "use metadata for custom fields"
            ),
            rel,
        )

    name = str(meta.get("name", "")).strip()
    if name:
        if len(name) > 64 or not SKILL_NAME_RE.fullmatch(name):
            result.error(
                "SKILL_NAME_INVALID",
                "skill name must be <=64 chars, lowercase alphanumeric with single hyphens",
                rel,
            )

    description = str(meta.get("description", "")).strip()
    if not description:
        result.error("DESCRIPTION_MISSING", "skill frontmatter must define description", rel)
    else:
        if len(description) > 1024:
            result.error(
                "DESCRIPTION_TOO_LONG",
                f"description has {len(description)} chars; maximum is 1024",
                rel,
            )
        elif len(description) > 500:
            result.warning(
                "DESCRIPTION_VERBOSE",
                f"description has {len(description)} chars; keep activation text concise",
                rel,
            )
        if not re.search(r"\buse\b", description, re.IGNORECASE):
            result.warning("DESCRIPTION_NO_TRIGGER", "description should state when to use the skill", rel)
        if STALE_DESCRIPTION_RE.search(description):
            result.error(
                "DESCRIPTION_STALE_HISTORY",
                "description contains migration/history language instead of current activation rules",
                rel,
            )

    metadata = meta.get("metadata")
    if not isinstance(metadata, dict):
        result.error("METADATA_MISSING", "skill frontmatter must define metadata mapping", rel)
        return

    missing = sorted(REQUIRED_SB_METADATA - set(metadata))
    for key in missing:
        result.error("METADATA_KEY_MISSING", f"metadata missing '{key}'", rel)

    for key, value in metadata.items():
        if not isinstance(key, str) or not isinstance(value, str):
            result.error("METADATA_TYPE_INVALID", "metadata keys and values must be strings", rel)
            break

    mode = metadata.get("second-brain-mode")
    approval = metadata.get("second-brain-approval")
    closure = metadata.get("second-brain-closure")
    role = metadata.get("second-brain-role")
    scope = metadata.get("second-brain-scope")

    if mode is not None and mode not in VALID_MODES:
        result.error(
            "METADATA_MODE_INVALID",
            f"second-brain-mode={mode!r}; expected one of {sorted(VALID_MODES)}",
            rel,
        )
    if approval is not None and approval not in VALID_APPROVALS:
        result.error(
            "METADATA_APPROVAL_INVALID",
            f"second-brain-approval={approval!r}; expected one of {sorted(VALID_APPROVALS)}",
            rel,
        )
    if closure is not None and closure not in VALID_CLOSURES:
        result.error(
            "METADATA_CLOSURE_INVALID",
            f"second-brain-closure={closure!r}; expected one of {sorted(VALID_CLOSURES)}",
            rel,
        )
    if role == "":
        result.error("METADATA_ROLE_EMPTY", "second-brain-role cannot be empty", rel)
    if scope == "":
        result.error("METADATA_SCOPE_EMPTY", "second-brain-scope cannot be empty", rel)

    tools = allowed_tools(meta)
    if mode == "read" and tools & WRITE_TOOLS:
        result.error(
            "READ_SKILL_HAS_WRITE_TOOL",
            f"read-only skill allows write tools: {', '.join(sorted(tools & WRITE_TOOLS))}",
            rel,
        )
    if mode == "read" and approval in {"before-write", "before-remote"}:
        result.error("READ_SKILL_WRITE_APPROVAL", "read-only skill declares a write/remote approval gate", rel)


def audit() -> CheckResult:
    result = CheckResult("skills")
    skill_files = sorted(SKILLS_DIR.glob("*/SKILL.md")) if SKILLS_DIR.exists() else []
    agent_files = sorted(SUBAGENTS_DIR.glob("*.md")) if SUBAGENTS_DIR.exists() else []
    skill_names = {p.parent.name for p in skill_files}
    declared: Counter[str] = Counter()
    agents = {p.stem for p in agent_files}

    for path in skill_files + agent_files:
        rel = path.relative_to(CODE_ROOT)
        text = path.read_text(encoding="utf-8-sig")
        try:
            meta, body = split_frontmatter(text)
        except yaml.YAMLError as exc:
            result.error("FRONTMATTER_INVALID", str(exc), rel)
            continue

        name = str(meta.get("name", "")).strip()
        if not name:
            result.error("NAME_MISSING", "frontmatter must define name", rel)
        else:
            declared[name] += 1
            expected = path.parent.name if path.name == "SKILL.md" else path.stem
            if name != expected:
                result.error("NAME_PATH_MISMATCH", f"name '{name}' != path name '{expected}'", rel)

        if path.name == "SKILL.md":
            validate_skill_frontmatter(meta, rel, result)

        duplicates = consecutive_duplicate_paragraphs(body) + adjacent_duplicate_sentences(body)
        for duplicate in dict.fromkeys(duplicates):
            result.error("DUPLICATE_RULE", f"consecutive duplicated rule: {duplicate[:120]}", rel)

        allowed = allowed_tools(meta)
        for tool in WEB_TOOLS:
            if re.search(rf"\b{re.escape(tool)}\b", body) and tool not in allowed:
                result.error(
                    "TOOL_NOT_ALLOWED",
                    f"body instructs use of {tool}, but frontmatter does not allow it",
                    rel,
                )

        for script in sorted(set(SCRIPT_REF_RE.findall(body))):
            if not (SCRIPTS_DIR / script).exists():
                result.error("SCRIPT_NOT_FOUND", f"referenced scripts/{script} does not exist", rel)

        if path.name == "SKILL.md" and path.parent.name in MECHANICAL_SKILLS:
            for segment in dict.fromkeys(updated_mutation_instructions(body)):
                result.error(
                    "UPDATED_FIELD_MUTATION",
                    f"mechanical skill instructs mutation of `updated:`: {segment[:120]}",
                    rel,
                )

        for match in SLASH_REF_RE.finditer(body):
            ref = match.group(0)[1:]
            if ref in TOP_LEVEL_PATH_WORDS or ref in skill_names or ref in agents:
                continue
            if looks_like_command(body, match):
                result.error(
                    "UNKNOWN_SKILL_COMMAND",
                    f"/{ref} is referenced as a command but matches no skill or subagent",
                    rel,
                )

        for cmd in PY_COMMAND_RE.finditer(body):
            script, tail = cmd.group(1), cmd.group(2)
            spath = SCRIPTS_DIR / script
            if not spath.exists():
                continue
            known = script_options(spath)
            for flag in FLAG_RE.findall(tail):
                if flag not in known:
                    result.warning("CLI_FLAG_UNKNOWN", f"{script} is documented with unknown flag {flag}", rel)

    for name, count in declared.items():
        if count > 1:
            result.error("DUPLICATE_NAME", f"name '{name}' declared {count} times")

    agents_path = CODE_ROOT / "AGENTS.md"
    agents_md = agents_path.read_text(encoding="utf-8-sig", errors="replace") if agents_path.exists() else ""
    readme_path = CODE_ROOT / "README.md"
    readme = readme_path.read_text(encoding="utf-8-sig", errors="replace") if readme_path.exists() else ""
    for name in sorted(skill_names):
        if f"/{name}" not in agents_md and name != "conventions":
            result.error("SKILL_NOT_IN_AGENTS", f"/{name} is not documented in AGENTS.md")
        if f"/{name}" not in readme and name not in {"conventions", "doctor"}:
            result.warning("SKILL_NOT_IN_README", f"/{name} is not mentioned in README.md")

    result.meta.update(skills=len(skill_files), agents=len(agent_files))
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
