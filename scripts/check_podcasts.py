#!/usr/bin/env python3
"""
Checagens mecânicas dos podcasts de essay.

Três frentes, todas read-only:

    originais   ``DATA_ROOT/wiki/podcasts/``: o nome é o slug de um essay, o
                essay existe, o áudio é íntegro (ffmpeg decodifica, um stream,
                aac/mp3, duração e tamanho plausíveis, extensão = contêiner,
                decodificação completa com cache por tamanho+mtime)
    publicado   ``SITE_ROOT/assets/podcasts/``: cada cópia pertence a um essay
                público, todo essay público com original tem cópia e player,
                nenhum player sem áudio, cópia mono ~48 kbps com faststart
    vazamento   nada de e-mail de conta nem nome de perfil local no engine
                versionado nem em ``site/``

Nome errado vem com sugestão por similaridade; ``fix_podcasts.py`` renomeia os
casos inequívocos.

Default sem argumentos: auditar originais, site e vazamentos.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess

import console_encoding  # noqa: F401  (UTF-8 no console; ver o módulo)
from repo_paths import CODE_ROOT, LOCAL_DIR, PODCASTS_DIR, SITE_ROOT

import podcast_common as pc  # isort: skip
from sanity_common import CheckResult

EMAIL_RE = re.compile(rb"[A-Za-z0-9._%+-]+@gmail\.com", re.I)
TEXT_SUFFIXES = {
    ".py", ".md", ".json", ".toml", ".yml", ".yaml", ".txt", ".html", ".css",
    ".js", ".cfg", ".ini", ".sh", ".bat", ".lua", ".svg", ".xml", ".csv",
}
MAX_SCAN_BYTES = 4_000_000
PLAYER_MARK = "data-sb-podcast"


def profiles_dir():
    from pathlib import Path

    raw = os.environ.get("NOTEBOOKLM_PROFILES_DIR")
    return Path(raw).expanduser() if raw else LOCAL_DIR / "notebooklm" / "profiles"


def profile_names() -> list[str]:
    """Nomes das pastas de perfil locais, lidos em runtime (nada embutido aqui)."""
    base = profiles_dir()
    if not base.is_dir():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir() and len(p.name) >= 4)


def tracked_engine_files() -> list:
    """Arquivos versionados ou prestes a sê-lo (não ignorados) do engine."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(CODE_ROOT), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if proc.returncode:
        return []
    return [CODE_ROOT / p for p in proc.stdout.split("\0") if p]


def scan_text_for_leaks(data: bytes, names: list[str]) -> list[str]:
    hits = [m.group(0).decode("latin-1") for m in EMAIL_RE.finditer(data)]
    lowered = data.lower()
    for name in names:
        if re.search(rb"(?<![a-z0-9])" + re.escape(name.lower().encode()) + rb"(?![a-z0-9])", lowered):
            hits.append(f"perfil '{name}'")
    return sorted(set(hits))


def audit_leaks(result: CheckResult, engine_files=None, site_root=None) -> None:
    names = profile_names()
    files = tracked_engine_files() if engine_files is None else list(engine_files)
    scanned = 0
    for path in files:
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            if path.stat().st_size > MAX_SCAN_BYTES:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        scanned += 1
        for hit in scan_text_for_leaks(data, names):
            try:
                shown = path.relative_to(CODE_ROOT)
            except ValueError:
                shown = path
            result.error("ACCOUNT_LEAK_ENGINE", f"{hit} em arquivo versionado do engine", shown)
    root = site_root if site_root is not None else SITE_ROOT
    if root.is_dir():
        for path in sorted(root.rglob("*")):
            if not path.is_file() or ".git" in path.relative_to(root).parts:
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES | {".m4a", ".mp3"}:
                continue
            try:
                if path.stat().st_size > 40_000_000:
                    continue
                data = path.read_bytes()
            except OSError:
                continue
            scanned += 1
            for hit in scan_text_for_leaks(data, names if path.suffix.lower() in TEXT_SUFFIXES else []):
                result.error("ACCOUNT_LEAK_SITE", f"{hit} em {path.relative_to(root).as_posix()}", path)
    result.meta["leak_scanned_files"] = scanned
    result.meta["leak_profile_names"] = len(names)


def audit_sources(result: CheckResult, deep: bool = True) -> dict:
    """Valida os originais; devolve ``slug -> arquivo`` dos nomes corretos."""
    files = pc.list_podcast_files()
    strays = (
        [p for p in PODCASTS_DIR.iterdir()
         if p.is_file() and p.suffix.lower() not in pc.PODCAST_EXTS and p.name != ".gitkeep"]
        if PODCASTS_DIR.is_dir() else []
    )
    for path in strays:
        result.warning("PODCAST_STRAY_FILE", "arquivo que não é .m4a/.mp3 na pasta de podcasts", path.name)
    if not files:
        result.skip("NO_PODCASTS", "nenhum podcast em wiki/podcasts")
        return {}
    if not pc.find_ffmpeg():
        result.warning("FFMPEG_MISSING", "ffmpeg ausente; integridade dos podcasts não verificada")
    essays = pc.load_essays()
    named: dict[str, list] = {}
    for path in files:
        slug = path.stem
        if slug in essays:
            named.setdefault(slug, []).append(path)
            essay = essays[slug]
            if not essay.public:
                result.info("PODCAST_NOT_PUBLISHED",
                            f"essay '{slug}' é {essay.visibility}; o podcast não será publicado", path.name)
        else:
            match, ranking = pc.best_match(slug, essays)
            hint = ", ".join(f"{e.slug} ({s:.2f})" for s, e in ranking[:3] if s >= 0.4)
            if match is not None:
                result.error("PODCAST_BAD_NAME",
                             f"nome não é slug de essay; correção inequívoca: {match.slug} "
                             f"(rode scripts/fix_podcasts.py)", path.name)
            elif hint:
                result.error("PODCAST_BAD_NAME",
                             f"nome não é slug de essay; candidatos: {hint}", path.name)
            else:
                result.error("PODCAST_ORPHAN", "nenhum essay corresponde a este podcast", path.name)
            continue
        if pc.find_ffmpeg():
            for finding in pc.integrity_findings(path, deep=deep):
                result.add(finding.code, finding.severity, finding.message, path.name)
    for slug, paths in named.items():
        if len(paths) > 1:
            result.warning("PODCAST_DUPLICATE",
                           f"'{slug}' tem mais de um original ({', '.join(p.name for p in paths)}); "
                           "o .m4a é usado", slug)
    result.meta["podcasts"] = len(files)
    return {slug: paths[0] for slug, paths in named.items()}


def audit_site(result: CheckResult, named: dict, site_root=None) -> None:
    root = site_root if site_root is not None else SITE_ROOT
    if not root.is_dir() or not (root / ".second-brain-site").exists():
        result.skip("NO_SITE", "checkout do site não inicializado; cópias publicadas não verificadas")
        return
    essays = pc.load_essays()
    public = {s for s, e in essays.items() if e.public}
    out_dir = pc.site_podcasts_dir(root)
    published = ({p.name: p for p in out_dir.iterdir() if p.is_file()} if out_dir.is_dir() else {})

    for name, path in sorted(published.items()):
        slug = path.stem
        if path.suffix != ".m4a":
            result.error("SITE_PODCAST_BAD_FILE", "só .m4a é publicado em assets/podcasts", f"assets/podcasts/{name}")
        elif slug not in essays:
            result.error("SITE_PODCAST_ORPHAN", "essay inexistente", f"assets/podcasts/{name}")
        elif slug not in public:
            result.error("SITE_PODCAST_NOT_PUBLIC",
                         f"essay '{slug}' é {essays[slug].visibility}; o áudio não pode estar no site",
                         f"assets/podcasts/{name}")
        elif slug not in named:
            result.error("SITE_PODCAST_NO_SOURCE", "o original sumiu; cópia obsoleta", f"assets/podcasts/{name}")
        elif pc.find_ffmpeg():
            for finding in pc.published_findings(path):
                result.add(finding.code, finding.severity, finding.message, f"assets/podcasts/{name}")

    pages = root / "essays"
    for slug in sorted(public):
        page = pages / f"{slug}.html"
        has_copy = f"{slug}.m4a" in published
        if slug in named and not has_copy:
            result.error("SITE_PODCAST_MISSING", f"essay público '{slug}' tem original mas não tem cópia publicada")
        if not page.is_file():
            continue
        text = page.read_text(encoding="utf-8", errors="replace")
        has_player = PLAYER_MARK in text
        if has_copy and not has_player:
            result.error("SITE_PLAYER_MISSING", "há áudio publicado mas a página não tem o player", page.name)
        if has_player and not has_copy:
            result.error("SITE_PLAYER_WITHOUT_AUDIO", "a página tem player mas não há áudio publicado", page.name)
        if has_player:
            for target in re.findall(r'(?:src|href)="([^"]*podcasts[^"]*)"', text):
                if target != f"../assets/podcasts/{slug}.m4a":
                    result.error("SITE_PLAYER_BAD_TARGET", f"o player aponta para {target[:80]}", page.name)
            if re.search(r"(?i)(?:data/|wiki/podcasts|[A-Za-z]:\\)", "".join(
                    re.findall(r'<section class="sb-podcast".*?</section>', text, re.S))):
                result.error("SITE_PLAYER_PATH_LEAK", "o player expõe um caminho local", page.name)
    result.meta["published_podcasts"] = len(published)


def audit(deep: bool = True, leaks: bool = True, leaks_only: bool = False) -> CheckResult:
    result = CheckResult("podcasts")
    if not leaks_only:
        named = audit_sources(result, deep=deep)
        audit_site(result, named)
    if leaks or leaks_only:
        audit_leaks(result)
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-on-warning", action="store_true")
    ap.add_argument("--no-deep", action="store_true",
                    help="pula a decodificação completa (mais rápido; sem cache)")
    ap.add_argument("--no-leaks", action="store_true", help="pula a varredura de vazamento de conta")
    ap.add_argument("--leaks-only", action="store_true",
                    help="só a varredura de vazamento de conta (não lê o corpus)")
    args = ap.parse_args()
    result = audit(deep=not args.no_deep, leaks=not args.no_leaks, leaks_only=args.leaks_only)
    result.print(args.json)
    return result.exit_code(args.fail_on_warning)


if __name__ == "__main__":
    raise SystemExit(main())
