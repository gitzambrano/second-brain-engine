#!/usr/bin/env python3
"""Audita contratos globais dos scripts Python executáveis.

Todo CLI em `scripts/*.py` deve ter um caminho útil sem argumentos. O checker
também valida shims de `scripts/lib/` e compara os CLIs públicos com o catálogo
`SCRIPTS.md`, para que scripts novos ou removidos não fiquem invisíveis.
"""
from __future__ import annotations

import argparse
import ast
import re
from pathlib import Path

from repo_paths import CODE_ROOT, SCRIPTS_DIR
from sanity_common import CheckResult

HELPER_MODULES: set[str] = set()
SHIM_IMPORT = "from lib."
CATALOG_RE = re.compile(r"\*\*`([A-Za-z0-9_.-]+\.py)`\*\*")


def is_executable_script(path: Path, tree: ast.AST) -> bool:
    if path.name in HELPER_MODULES:
        return False
    try:
        first = path.read_text(encoding="utf-8-sig").splitlines()[0]
    except (OSError, IndexError):
        first = ""
    if first.startswith("#!"):
        return True
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and isinstance(node.left, ast.Name) and node.left.id == "__name__":
            return True
    return False


def _literal(node: ast.AST | None):
    try:
        return ast.literal_eval(node) if node is not None else None
    except (ValueError, TypeError):
        return None


def audit_file(path: Path, result: CheckResult) -> bool:
    """Audita um arquivo e retorna se ele é um CLI executável."""
    try:
        source = path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError) as exc:
        result.error("SCRIPT_PARSE_ERROR", str(exc), path.relative_to(CODE_ROOT))
        return False
    if not is_executable_script(path, tree):
        return False

    subparsers: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        func = node.value.func
        if isinstance(func, ast.Attribute) and func.attr == "add_parser":
            for target in node.targets:
                if isinstance(target, ast.Name):
                    subparsers.add(target.id)

    required: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Attribute)
            or node.func.attr != "add_argument"
            or not node.args
        ):
            continue
        receiver = node.func.value
        if isinstance(receiver, ast.Name) and receiver.id in subparsers:
            continue
        name = _literal(node.args[0])
        if not isinstance(name, str) or name.startswith("-"):
            continue
        kwargs = {kw.arg: _literal(kw.value) for kw in node.keywords if kw.arg}
        if kwargs.get("nargs") in {"?", "*"} or "default" in kwargs:
            continue
        required.append((name, getattr(node, "lineno", 0)))
    for name, line in required:
        result.error(
            "CLI_REQUIRED_POSITIONAL",
            f"positional '{name}' is mandatory; no-argument execution must choose a useful global/default mode",
            path.relative_to(CODE_ROOT), line=line,
        )

    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute):
            if isinstance(node.value.value, ast.Name) and node.value.value.id == "sys" and node.value.attr == "argv":
                idx = _literal(node.slice)
                if isinstance(idx, int) and idx >= 1:
                    result.warning(
                        "CLI_RAW_ARGV",
                        f"direct sys.argv[{idx}] access; confirm no-arg path is guarded",
                        path.relative_to(CODE_ROOT), line=getattr(node, "lineno", None),
                    )
                    break
    return True


def audit_shim(path: Path, result: CheckResult) -> None:
    """Shim de módulo com CLI deve encaminhar `main()` do módulo em `lib/`."""
    source = path.read_text(encoding="utf-8-sig")
    if SHIM_IMPORT not in source or len(source.splitlines()) > 12:
        return
    lib = SCRIPTS_DIR / "lib" / path.name
    if not lib.is_file():
        return
    try:
        lib_tree = ast.parse(lib.read_text(encoding="utf-8-sig"), filename=str(lib))
    except (OSError, SyntaxError):
        return
    has_main = any(isinstance(node, ast.FunctionDef) and node.name == "main" for node in lib_tree.body)
    if has_main and "__main__" not in source:
        result.error(
            "SHIM_DROPS_CLI",
            f"shim re-exports lib.{path.stem} but never runs its main()",
            path.relative_to(CODE_ROOT),
        )


def audit_catalog(executables: set[str], result: CheckResult) -> None:
    catalog_path = CODE_ROOT / "docs" / "SCRIPTS.md"
    if not catalog_path.is_file():
        catalog_path = SCRIPTS_DIR / "SCRIPTS.md"
    if not catalog_path.is_file():
        catalog_path = CODE_ROOT / "SCRIPTS.md"
    if not catalog_path.is_file():
        result.warning("SCRIPT_CATALOG_MISSING", "SCRIPTS.md is absent")
        return
    documented = set(CATALOG_RE.findall(catalog_path.read_text(encoding="utf-8-sig")))
    top_level = {p.name for p in SCRIPTS_DIR.glob("*.py")}

    for name in sorted(documented - top_level):
        result.warning(
            "SCRIPT_DOC_STALE",
            f"SCRIPTS.md mentions missing scripts/{name}",
            catalog_path.relative_to(CODE_ROOT),
        )

    for name in sorted(executables - documented):
        path = SCRIPTS_DIR / name
        source = path.read_text(encoding="utf-8-sig", errors="replace")
        if SHIM_IMPORT in source and len(source.splitlines()) <= 12:
            continue
        result.warning(
            "SCRIPT_NOT_DOCUMENTED",
            f"executable scripts/{name} is not listed in SCRIPTS.md",
            path.relative_to(CODE_ROOT),
        )


def audit(paths: list[Path] | None = None) -> CheckResult:
    result = CheckResult("script-defaults")
    targets = paths or sorted(SCRIPTS_DIR.glob("*.py"))
    executables: set[str] = set()
    for path in targets:
        if audit_file(path, result):
            executables.add(path.name)
        audit_shim(path, result)
    if paths is None:
        audit_catalog(executables, result)
    result.meta["scripts_scanned"] = len(targets)
    result.meta["executables"] = len(executables)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("path", nargs="?", help="optional single Python script; default audits scripts/*.py")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on-warning", action="store_true")
    args = ap.parse_args()
    paths = [Path(args.path).resolve()] if args.path else None
    result = audit(paths)
    result.print(args.json)
    return result.exit_code(args.fail_on_warning)


if __name__ == "__main__":
    raise SystemExit(main())
