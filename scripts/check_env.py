#!/usr/bin/env python3
"""check_env.py - Diagnostica as dependências de runtime usadas pelo repositório e exports.

Audita a presença e versões das dependências de sistema e pacotes Python:
1. Python e módulos essenciais (PyYAML, PyMuPDF, BeautifulSoup4, html5lib).
2. Motores externos de exportação (Pandoc, LuaLaTeX).
3. Ambiente de testes e automação de navegador (Playwright, navegadores Chromium).

Escopo:
    Diagnóstico read-only do ambiente local de execução.
    Default sem argumentos roda diagnóstico completo. Motores de export ausentes geram
    avisos (WARNING) por padrão para permitir clones mínimos; --strict promove avisos a erro.

Entradas (Inputs):
    Argumentos CLI opcionais:
        --core      Verifica apenas dependências do núcleo (Python e PyYAML)
        --strict    Promove ferramentas de export e navegador ausentes a erro
        --json      Emite diagnóstico formatado em JSON

Saídas (Outputs):
    Stdout: Relatório formatado com status de cada dependência e ferramenta.
    JSON: {"check": "environment", "status": "pass"|"warn"|"fail", "errors": [...], "warnings": [...]}
    Exit code: 0 em sucesso/aviso, 1 em dependência obrigatória ausente.

Uso:
    python scripts/check_env.py           # diagnóstico completo
    python scripts/check_env.py --core    # apenas dependências fundamentais
    python scripts/check_env.py --strict  # exige todas as ferramentas externas
    python scripts/check_env.py --json    # saída estruturada em JSON
"""
from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

import repo_paths  # noqa: F401  (põe lib/ no sys.path)
from sanity_common import CheckResult


def audit(core_only: bool = False, strict: bool = False) -> CheckResult:
    result = CheckResult("environment")
    result.info("PYTHON", sys.version.split()[0])
    modules = {"yaml": "PyYAML"} if core_only else {
        "yaml": "PyYAML",
        "pymupdf": "PyMuPDF",
        "bs4": "BeautifulSoup4",
        "html5lib": "html5lib",
    }
    for module, label in modules.items():
        if importlib.util.find_spec(module) is None:
            sev = "ERROR" if module in {"yaml"} else ("ERROR" if strict else "WARNING")
            result.add("MODULE_MISSING", sev, f"{label} ({module}) is not importable")
        else:
            result.info("MODULE_OK", f"{label} available")
    if core_only:
        return result

    for exe, label in (("pandoc", "Pandoc"), ("lualatex", "LuaLaTeX")):
        path = shutil.which(exe)
        if path:
            result.info("EXECUTABLE_OK", f"{label}: {path}")
        else:
            result.add("EXECUTABLE_MISSING", "ERROR" if strict else "WARNING", f"{label} not found")

    # ffmpeg: recodifica e valida os podcasts. O fallback é o pacote
    # `imageio-ffmpeg` (`python -m pip install imageio-ffmpeg`).
    import podcast_common

    ffmpeg = podcast_common.find_ffmpeg()
    if ffmpeg:
        result.info("EXECUTABLE_OK", f"ffmpeg: {ffmpeg}")
    else:
        result.add("EXECUTABLE_MISSING", "ERROR" if strict else "WARNING",
                   "ffmpeg not found (podcasts); install ffmpeg or `pip install imageio-ffmpeg`")

    if importlib.util.find_spec("playwright") is None:
        result.add("PLAYWRIGHT_MISSING", "ERROR" if strict else "WARNING", "Playwright Python package not installed")
    else:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                browser_path = Path(p.chromium.executable_path)
            browser_names = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
            system_browser = next((shutil.which(x) for x in browser_names if shutil.which(x)), None)
            if browser_path.exists():
                result.info("CHROMIUM_OK", str(browser_path))
            elif system_browser:
                result.info("CHROMIUM_OK", f"system browser fallback: {system_browser}")
            else:
                result.add(
                    "CHROMIUM_MISSING",
                    "ERROR" if strict else "WARNING",
                    "no Playwright-managed or system Chromium/Chrome found",
                )
        except Exception as exc:  # environment probe only
            result.add("PLAYWRIGHT_PROBE_FAILED", "ERROR" if strict else "WARNING", str(exc))
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--core", action="store_true", help="check only Python/core dependencies")
    ap.add_argument("--strict", action="store_true", help="treat optional export dependencies as blocking")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = audit(args.core, args.strict)
    result.print(args.json)
    return result.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
