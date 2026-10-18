#!/usr/bin/env python3
"""sync_skills.py - Espelha .agents/ nos formatos que cada harness lê.

Mantém a integridade entre a fonte única e os mirrors para Claude Code e Codex:
- .agents/skills/** e .agents/agents/** são a fonte única canônica.
- .claude/skills/ e .claude/agents/ recebem cópias idênticas (removendo órfãos).
- .codex/agents/*.toml são adaptadores derivados do formato Markdown.

Escopo:
    Sincronizador mecânico de agentes e skills em CODE_ROOT.
    Nunca edite os espelhos à mão; toda modificação deve ser feita em .agents/.

Entradas (Inputs):
    Diretório .agents/ (skills e agentes).
    Argumentos CLI opcionais:
        --check    Verifica se há descompasso (drift) sem escrever em disco (exit 1 se houver)
        --quiet    Modo silencioso para hooks de sessão (reporta apenas se houver alterações)

Saídas (Outputs):
    Espelhos atualizados em .claude/ e adaptadores em .codex/.
    Stdout: Lista de arquivos sincronizados ou aviso de conformidade.
    Exit code: 0 em sucesso (ou sem drift), 1 se drift for detectado com --check.

Uso:
    python scripts/sync_skills.py                             # sincroniza todos os espelhos
    python scripts/sync_skills.py --check                     # verifica drift sem alterar
    python scripts/sync_skills.py --quiet                     # modo hook de sessão
"""
from __future__ import annotations

import argparse
import filecmp
import re
import shutil
import sys
from pathlib import Path

from repo_paths import CODE_ROOT

REPO_ROOT = CODE_ROOT

PAIRS = [
    (REPO_ROOT / ".agents" / "skills", REPO_ROOT / ".claude" / "skills"),
    (REPO_ROOT / ".agents" / "agents", REPO_ROOT / ".claude" / "agents"),
]

AGENTS_DIR = REPO_ROOT / ".agents" / "agents"
CODEX_DIR = REPO_ROOT / ".codex" / "agents"

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n(.*)$", re.DOTALL)
KEY_RE = re.compile(r"^([A-Za-z_][\w-]*):\s*(.*)$")


def _frontmatter(text: str) -> tuple[dict, str]:
    """Frontmatter minimalista: `chave: valor`, com bloco dobrado (`>`).

    Deliberadamente sem PyYAML: este script roda no hook `SessionStart` de toda
    sessão, e uma dependência opcional ali vira sessão que abre com erro numa
    máquina recém-clonada.
    """
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    meta: dict[str, str] = {}
    key = None
    for line in match.group(1).splitlines():
        header = KEY_RE.match(line)
        if header:
            key, value = header.group(1), header.group(2).strip()
            meta[key] = "" if value in (">", "|", ">-", "|-") else value
        elif key and line.strip():
            meta[key] = (meta[key] + " " + line.strip()).strip()
    return meta, match.group(2)


def codex_toml(md_path: Path) -> str:
    """O adaptador do Codex, derivado do agent canônico.

    Outro formato, mesma fonte: o corpo do `.md` vira `developer_instructions`
    e o frontmatter vira `name`/`description`. A aspa simples entra quando a
    descrição já contém aspas duplas — TOML básico não escapa isso aqui.
    """
    meta, body = _frontmatter(md_path.read_text(encoding="utf-8"))
    name = meta.get("name", md_path.stem)
    description = " ".join(str(meta.get("description", "")).split())
    quote = "'" if '"' in description else '"'
    corpo = body.strip("\n").rstrip()
    return (
        'name = "' + name + '"\n'
        + "description = " + quote + description + quote + "\n"
        + 'developer_instructions = """\n' + corpo + '"""\n'
    )


def sync_codex(check_only: bool = False):
    """Retorna (escritos, sobrando) como nomes de arquivo em CODEX_DIR."""
    if not AGENTS_DIR.is_dir():
        return [], []
    esperados = {f"{p.stem}.toml": codex_toml(p) for p in sorted(AGENTS_DIR.glob("*.md"))}
    atuais = {p.name for p in CODEX_DIR.glob("*.toml")} if CODEX_DIR.is_dir() else set()

    escritos = sorted(
        nome for nome, conteudo in esperados.items()
        if nome not in atuais
        or (CODEX_DIR / nome).read_text(encoding="utf-8") != conteudo
    )
    sobrando = sorted(atuais - set(esperados))

    if check_only:
        return escritos, sobrando

    if escritos or sobrando:
        CODEX_DIR.mkdir(parents=True, exist_ok=True)
    for nome in escritos:
        (CODEX_DIR / nome).write_text(esperados[nome], encoding="utf-8")
    for nome in sobrando:
        (CODEX_DIR / nome).unlink()
    return escritos, sobrando


def relative_files(root: Path) -> set[Path]:
    """Todos os arquivos sob `root`, como caminhos relativos a ele."""
    if not root.is_dir():
        return set()
    return {p.relative_to(root) for p in root.rglob("*") if p.is_file()}


def sync_pair(source: Path, dest: Path, check_only: bool = False):
    """Retorna (copiados, removidos) como listas de caminhos relativos a `dest`."""
    if not source.is_dir():
        return [], []

    src_files = relative_files(source)
    dest_files = relative_files(dest)

    to_copy = sorted(
        rel
        for rel in src_files
        if rel not in dest_files
        or not filecmp.cmp(source / rel, dest / rel, shallow=False)
    )
    to_remove = sorted(dest_files - src_files)

    if check_only:
        return to_copy, to_remove

    for rel in to_copy:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source / rel, target)

    for rel in to_remove:
        (dest / rel).unlink()

    if dest.is_dir():
        for path in sorted(dest.rglob("*"), key=lambda p: len(p.parts), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()

    return to_copy, to_remove


def sync(check_only: bool = False):
    """Roda todos os pares fonte/espelho. Retorna lista de (source, dest, copiados, removidos)."""
    results = []
    for source, dest in PAIRS:
        copied, removed = sync_pair(source, dest, check_only=check_only)
        results.append((source, dest, copied, removed))
    escritos, sobrando = sync_codex(check_only=check_only)
    results.append((AGENTS_DIR, CODEX_DIR,
                    [Path(n) for n in escritos], [Path(n) for n in sobrando]))
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="não escreve nada; sai com código 1 se houver dessincronia",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="silencia a saída quando já está sincronizado",
    )
    args = parser.parse_args()

    results = sync(check_only=args.check)
    any_drift = any(copied or removed for _, _, copied, removed in results)

    def label(source, dest):
        return f"{source.relative_to(REPO_ROOT)} -> {dest.relative_to(REPO_ROOT)}"

    if args.check:
        if any_drift:
            for source, dest, copied, removed in results:
                if not (copied or removed):
                    continue
                print(
                    f"DRIFT ({label(source, dest)}): {len(copied)} arquivo(s) "
                    f"desatualizado(s), {len(removed)} sobrando"
                )
                for rel in copied:
                    print(f"  desatualizado: {rel.as_posix()}")
                for rel in removed:
                    print(f"  sobrando:      {rel.as_posix()}")
            print("Rode: python scripts/sync_skills.py")
            sys.exit(1)
        if not args.quiet:
            print("skills e agents sincronizados")
        return

    if any_drift:
        for source, dest, copied, removed in results:
            if not (copied or removed):
                continue
            print(
                f"sincronizado ({label(source, dest)}): {len(copied)} copiado(s), "
                f"{len(removed)} removido(s)"
            )
            for rel in copied:
                print(f"  copiado:  {rel.as_posix()}")
            for rel in removed:
                print(f"  removido: {rel.as_posix()}")
    elif not args.quiet:
        print("skills e agents já sincronizados")


if __name__ == "__main__":
    main()
