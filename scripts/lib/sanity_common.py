#!/usr/bin/env python3
"""sanity_common.py - Modelo compartilhado de resultados dos checadores de sanidade.

Define a estrutura unificada CheckResult para todos os checadores de qualidade do repositório:
- Vocabulário canônico de severidades: ERROR, WARNING, INFO, SKIP.
- Padronização de mensagens de erro, caminhos de arquivo, linhas e contexto.
- Exportação consistente em formato texto para console e JSON estruturado.

Escopo:
    Módulo de biblioteca base para check_repo, check_wiki, check_env e demais validadores.

Entradas (Inputs):
    Chamadas de registro de resultados em tempo de execução dos checadores.

Saídas (Outputs):
    Impressão formatada em console e dicionário serializável para JSON.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def _safe_print(*args, **kwargs) -> None:
    """Print with UTF-8 fallback on Windows cp1252 terminals."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        # Encode to UTF-8 bytes, decode back replacing unmappable chars.
        text = " ".join(str(a) for a in args)
        safe = text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
            sys.stdout.encoding or "utf-8", errors="replace"
        )
        print(safe, **{k: v for k, v in kwargs.items() if k != "end"})

SEVERITIES = ("ERROR", "WARNING", "INFO", "SKIP")


# --- Navegador headless ------------------------------------------------------
# Três checadores e o gerador de capa precisavam da mesma resposta: existe um
# Chromium utilizável nesta máquina? Cada um tinha sua cópia da busca, e a do
# build_cover não tinha nenhuma — só um `except ImportError`, que não cobre o
# caso mais comum em CI, o de pacote instalado e browser não baixado.

CHROMIUM_ABSENT = "chromium-absent"
CHROMIUM_MANAGED = "chromium-managed"
CHROMIUM_SYSTEM = "chromium-system"
PLAYWRIGHT_ABSENT = "playwright-absent"


def resolve_chromium():
    """Descobre um Chromium utilizável. Retorna (estado, executável|None, texto).

    Estados possíveis, nesta ordem de preferência:

    - `PLAYWRIGHT_ABSENT`: o pacote `playwright` não está instalado;
    - `CHROMIUM_MANAGED`: o browser que o `playwright install` baixou;
    - `CHROMIUM_SYSTEM`: um Chromium/Chrome do sistema, quando o gerenciado
      não foi baixado — é o caso de quem tem o navegador mas nunca rodou
      `python -m playwright install chromium`;
    - `CHROMIUM_ABSENT`: pacote presente, nenhum executável em lugar nenhum.

    Nunca levanta: quem chama decide se a ausência é SKIP ou FAIL.
    """
    import importlib.util
    import shutil

    if importlib.util.find_spec("playwright") is None:
        return PLAYWRIGHT_ABSENT, None, "pacote playwright não instalado"

    from playwright.sync_api import sync_playwright

    try:
        with sync_playwright() as p:
            managed = Path(p.chromium.executable_path)
    except Exception as exc:  # driver quebrado, instalação parcial
        return PLAYWRIGHT_ABSENT, None, f"playwright indisponível: {exc}"

    if managed.exists():
        return CHROMIUM_MANAGED, str(managed), f"chromium do playwright em {managed}"

    names = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")
    system = next((shutil.which(x) for x in names if shutil.which(x)), None)
    if system:
        return CHROMIUM_SYSTEM, system, f"chromium do sistema em {system}"

    return (
        CHROMIUM_ABSENT,
        None,
        "playwright instalado mas sem browser; rode: python -m playwright install chromium",
    )


def text_contains(haystack_norm: str, needle_norm: str) -> bool:
    """Presence test tolerant of typographic letter-spacing.

    The PDF template tracks section headings and the byline ("S U M A R I O"),
    so text extraction returns a space between every glyph and a plain substring
    test reports the heading as missing. Falling back to a space-free comparison
    keeps the check honest without weakening it: absent text is still absent.
    """
    if not needle_norm:
        return True
    if needle_norm in haystack_norm:
        return True
    return needle_norm.replace(" ", "") in haystack_norm.replace(" ", "")


@dataclass(slots=True)
class Issue:
    code: str
    severity: str
    message: str
    path: str | None = None
    line: int | None = None
    details: Any = None

    def __post_init__(self) -> None:
        self.severity = self.severity.upper()
        if self.severity not in SEVERITIES:
            raise ValueError(f"invalid severity: {self.severity}")


@dataclass
class CheckResult:
    check: str
    issues: list[Issue] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def add(self, code: str, severity: str, message: str, path: str | Path | None = None,
            line: int | None = None, details: Any = None) -> None:
        self.issues.append(Issue(code, severity, message, str(path) if path else None, line, details))

    def error(self, code: str, message: str, path: str | Path | None = None, **kw: Any) -> None:
        self.add(code, "ERROR", message, path, **kw)

    def warning(self, code: str, message: str, path: str | Path | None = None, **kw: Any) -> None:
        self.add(code, "WARNING", message, path, **kw)

    def info(self, code: str, message: str, path: str | Path | None = None, **kw: Any) -> None:
        self.add(code, "INFO", message, path, **kw)

    def skip(self, code: str, message: str, path: str | Path | None = None, **kw: Any) -> None:
        self.add(code, "SKIP", message, path, **kw)

    def count(self, severity: str) -> int:
        return sum(i.severity == severity.upper() for i in self.issues)

    @property
    def status(self) -> str:
        if self.count("ERROR"):
            return "fail"
        if self.count("WARNING"):
            return "warn"
        if self.issues and all(i.severity == "SKIP" for i in self.issues):
            return "skip"
        return "pass"

    def exit_code(self, fail_on_warning: bool = False) -> int:
        if self.count("ERROR") or (fail_on_warning and self.count("WARNING")):
            return 1
        return 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "status": self.status,
            "errors": self.count("ERROR"),
            "warnings": self.count("WARNING"),
            "info": self.count("INFO"),
            "skipped": self.count("SKIP"),
            "issues": [asdict(i) for i in self.issues],
            "meta": self.meta,
        }

    def print(self, json_mode: bool = False) -> None:
        if json_mode:
            _safe_print(json.dumps(self.to_dict(), ensure_ascii=False, indent=2))
            return
        _safe_print(f"{self.check}: {self.status.upper()} — {self.count('ERROR')} error(s), "
              f"{self.count('WARNING')} warning(s), {self.count('SKIP')} skip(s)")
        for issue in self.issues:
            where = f" [{issue.path}" if issue.path else ""
            if issue.line is not None:
                where += f":{issue.line}"
            if where:
                where += "]"
            _safe_print(f"  {issue.severity:<7} {issue.code}{where}: {issue.message}")


def main() -> int:
    print("severities: ERROR WARNING INFO SKIP")
    print("exit codes: 0=clean/warnings-only, 1=blocking issue, 2=checker execution/configuration failure")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
