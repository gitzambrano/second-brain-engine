#!/usr/bin/env python3
"""
Converte arquivos Mermaid .mmd em PNG via Mermaid CLI (mmdc).

O default sem argumentos descobre todo ``*.mmd`` sob wiki/assets e plan e
converte todos. Se não existir nenhum, o lote completo é um sucesso vazio.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from repo_paths import ASSETS_DIR, PLAN_DIR


def find_mmdc():
    if sys.platform == "win32":
        npm_dir = os.environ.get("APPDATA", "")
        candidates = ["mmdc.cmd", "mmdc"]
        if npm_dir:
            candidates = [
                os.path.join(npm_dir, "npm", "mmdc.cmd"),
                os.path.join(npm_dir, "npm", "mmdc"),
                *candidates,
            ]
    else:
        candidates = ["mmdc"]
    for command in candidates:
        try:
            result = subprocess.run(
                [command, "--version"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode == 0:
                return command
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            pass
    return None


def find_browser():
    cache_dir = Path.home() / ".cache" / "puppeteer"
    if cache_dir.exists():
        for exe in cache_dir.rglob("chrome-headless-shell*"):
            if exe.is_file() and (exe.suffix in (".exe", "") or os.access(exe, os.X_OK)):
                return str(exe)
    candidates = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def convert(src, dst, width=1400, scale=2, bg="white"):
    command = find_mmdc()
    if not command:
        print("ERRO: mmdc não encontrado. Instale @mermaid-js/mermaid-cli.")
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        command,
        "-i",
        str(src),
        "-o",
        str(dst),
        "--backgroundColor",
        bg,
        "--width",
        str(width),
        "--scale",
        str(scale),
    ]
    browser = find_browser()
    temp_config = None
    if browser:
        import json
        import tempfile
        cfg = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump({"executablePath": browser, "args": ["--no-sandbox", "--disable-setuid-sandbox"]}, cfg)
        cfg.close()
        temp_config = Path(cfg.name)
        cmd.extend(["-p", str(temp_config)])
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=120,
        )
    finally:
        if temp_config and temp_config.exists():
            try:
                temp_config.unlink()
            except OSError:
                pass
    if result.returncode == 0 and dst.exists():
        print(f"OK: {dst} ({dst.stat().st_size // 1024} KB)")
        return True
    stderr = (result.stderr or b"").decode("utf-8", errors="replace")
    print("ERRO: mmdc falhou.\n" + stderr[:400])
    return False


def discover():
    files = []
    for root in (ASSETS_DIR, PLAN_DIR):
        if root.exists():
            files.extend(sorted(root.rglob("*.mmd")))
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "src",
        nargs="?",
        help="input .mmd; omit to convert all discovered diagrams",
    )
    parser.add_argument("dst", nargs="?", help="output .png")
    parser.add_argument("--assets", action="store_true")
    parser.add_argument("--width", type=int, default=1400)
    parser.add_argument("--scale", type=int, default=2)
    parser.add_argument("--bg", default="white")
    args = parser.parse_args()

    if not args.src:
        sources = discover()
        if not sources:
            print("Nenhum .mmd encontrado em wiki/assets/ ou plan/ — batch completo vazio.")
            return 0
        failures = 0
        for src in sources:
            dst = ASSETS_DIR / src.with_suffix(".png").name
            failures += 0 if convert(src, dst, args.width, args.scale, args.bg) else 1
        print(f"Batch Mermaid: {len(sources) - failures} OK, {failures} falha(s).")
        return 1 if failures else 0

    src = Path(args.src)
    if not src.exists():
        print(f"ERRO: arquivo não encontrado: {src}")
        return 1
    if args.dst:
        dst = Path(args.dst)
    elif args.assets:
        dst = ASSETS_DIR / src.with_suffix(".png").name
    else:
        dst = src.with_suffix(".png")
    return 0 if convert(src, dst, args.width, args.scale, args.bg) else 1


if __name__ == "__main__":
    sys.exit(main())
