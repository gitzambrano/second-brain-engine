#!/usr/bin/env python3
"""
Gera o podcast de um essay no NotebookLM por automação de navegador.

Python puro + Playwright: zero tokens de LLM. O fluxo abre o NotebookLM com um
perfil de navegador local, cria um caderno, cola o texto do essay como fonte,
personaliza o Resumo em áudio (português do Brasil, formato mais longo, prompt de
``.agents/skills/podcast/prompt.md``), espera a geração, baixa o áudio e o
entrega a ``ingest_podcast.py``.

Contas = pastas. Cada subpasta de ``--profiles-dir`` é um perfil persistente do
Chrome e um candidato de conta; o rodízio segue a ordem alfabética das pastas.
O script nunca digita senha: sessão deslogada é reportada, e ``--login PASTA``
abre uma janela para o próprio Usuário entrar.

Estado em runtime (cooldowns, última conta, depuração) fica em
``.local/notebooklm/`` e nunca entra em nenhum repositório.

    python scripts/notebooklm_podcast.py <essay>        # gera
    python scripts/notebooklm_podcast.py --login <pasta>  # login manual, janela visível

Default sem argumentos: listar os essays públicos sem podcast, do mais recente
ao mais antigo, e o estado dos perfis. Não abre navegador.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import console_encoding  # noqa: F401  (UTF-8 no console; ver o módulo)
from repo_paths import LOCAL_DIR, SKILLS_DIR

import human_input as hi  # isort: skip

import podcast_common as pc  # isort: skip

NOTEBOOKLM_URL = "https://notebooklm.google.com"
STATE_DIR = LOCAL_DIR / "notebooklm"
DEFAULT_PROFILES_DIR = STATE_DIR / "profiles"
STATE_FILE = STATE_DIR / "state.json"
DEBUG_DIR = STATE_DIR / "debug"
PROMPT_FILE = SKILLS_DIR / "podcast" / "prompt.md"

QUOTA_COOLDOWN_H = 12
GENERATION_TIMEOUT_MIN = 30
POLL_SECONDS = (20, 35)

QUOTA_RE = re.compile(
    r"limite (di[aá]rio|de uso|de gera[cç][aã]o)|atingiu o limite|limite atingido|volte amanh[aã]|"
    r"daily (limit|quota)|reached (the|your)[^.]{0,40}limit|usage limit|try again (tomorrow|later)|"
    r"cota (di[aá]ria|excedida)|quota",
    re.I,
)
FAILED_RE = re.compile(
    r"n[aã]o foi poss[ií]vel gerar|falha ao gerar|erro ao gerar|couldn.t (generate|create)|"
    r"generation failed|failed to generate|something went wrong|algo deu errado",
    re.I,
)


# --- erros com destino -------------------------------------------------------

class FlowError(RuntimeError):
    """Falha do fluxo; carrega o passo para o relatório."""


class ProfileInUse(FlowError):
    pass


class NotLoggedIn(FlowError):
    pass


class QuotaExceeded(FlowError):
    pass


# --- configuração e estado ---------------------------------------------------

def resolve_profiles_dir(cli: str | None) -> Path:
    raw = cli or os.environ.get("NOTEBOOKLM_PROFILES_DIR")
    return Path(raw).expanduser().resolve() if raw else DEFAULT_PROFILES_DIR


def list_accounts(profiles_dir: Path) -> list[str]:
    """Pastas imediatas, em ordem alfabética; a pasta é a conta."""
    if not profiles_dir.is_dir():
        return []
    return sorted(p.name for p in profiles_dir.iterdir() if p.is_dir() and not p.name.startswith("."))


def load_state(path: Path = STATE_FILE) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("accounts", {})
            return data
    except (OSError, ValueError):
        pass
    return {"accounts": {}, "last_account": None}


def save_state(state: dict, path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def in_cooldown(state: dict, account: str, now: datetime | None = None) -> bool:
    until = state.get("accounts", {}).get(account, {}).get("cooldown_until")
    if not until:
        return False
    try:
        return datetime.fromisoformat(until) > (now or _now())
    except ValueError:
        return False


def rotation_order(accounts: list[str], state: dict, forced: str | None = None,
                   now: datetime | None = None) -> list[str]:
    """Contas a tentar, em ordem: a seguinte à última usada, sem as em cooldown."""
    if forced:
        if forced not in accounts:
            raise SystemExit(f"conta '{forced}' não existe; pastas: {', '.join(accounts) or '(nenhuma)'}")
        return [forced]
    last = state.get("last_account")
    start = (accounts.index(last) + 1) % len(accounts) if last in accounts else 0
    ordered = accounts[start:] + accounts[:start]
    return [a for a in ordered if not in_cooldown(state, a, now)]


def mark_account(state: dict, account: str, status: str, cooldown_hours: float = 0) -> None:
    entry = state.setdefault("accounts", {}).setdefault(account, {})
    entry["last_status"] = status
    entry["last_attempt"] = _now().isoformat(timespec="seconds")
    if status == "ok":
        entry["last_used"] = entry["last_attempt"]
        entry.pop("cooldown_until", None)
        state["last_account"] = account
    if cooldown_hours:
        entry["cooldown_until"] = (_now() + timedelta(hours=cooldown_hours)).isoformat(timespec="seconds")


def load_prompt() -> str:
    if not PROMPT_FILE.is_file():
        raise SystemExit(f"prompt ausente: {PROMPT_FILE}")
    return PROMPT_FILE.read_text(encoding="utf-8").rstrip("\n")


SECTION_DROP = re.compile(r"(?ms)^##\s+(?:Sumário|Conex[õo]es)\s*\n.*?(?=^##\s+|\Z)")


def build_source_text(essay_path: Path) -> str:
    """Corpo do essay sem frontmatter, sem Sumário e sem Conexões."""
    from site_common import parse

    _meta, body = parse(essay_path)
    body = SECTION_DROP.sub("", body)
    return re.sub(r"\n{3,}", "\n\n", body).strip() + "\n"


def candidates_without_podcast() -> list[pc.EssayRef]:
    """Essays públicos sem podcast, do mais recente (created) ao mais antigo."""
    from site_common import parse

    essays = pc.load_essays()
    rows = []
    for slug, ref in essays.items():
        if not ref.public or pc.source_for(slug):
            continue
        meta, _ = parse(pc.ESSAYS_DIR / f"{slug}.md")
        rows.append((str(meta.get("created") or ""), ref))
    rows.sort(key=lambda r: (r[0], r[1].slug), reverse=True)
    return [ref for _created, ref in rows]


# --- perfis em uso -----------------------------------------------------------

LOCK_NAMES = ("SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile")


def profile_in_use(profile: Path) -> bool:
    """Há um Chrome com este perfil aberto? (Windows: linha de comando do processo.)"""
    if os.name != "nt":
        lock = profile / "SingletonLock"
        if not lock.is_symlink():
            return False
        try:
            pid = int(os.readlink(lock).rsplit("-", 1)[-1])
            os.kill(pid, 0)
            return True
        except (OSError, ValueError):
            return False
    needle = str(profile).replace("/", "\\").rstrip("\\").lower()
    script = (
        "Get-CimInstance Win32_Process -Filter \"name='chrome.exe'\" | "
        "ForEach-Object { $_.CommandLine }"
    )
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                             capture_output=True, text=True, timeout=30,
                             encoding="utf-8", errors="replace").stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return any(needle in line.lower().replace("/", "\\") for line in out.splitlines())


def clear_stale_locks(profile: Path) -> None:
    """Remove travas deixadas por um Chrome morto; só chamar quando não está em uso."""
    for name in LOCK_NAMES:
        target = profile / name
        try:
            if target.exists() or target.is_symlink():
                target.unlink()
        except OSError:
            pass


# --- depuração ---------------------------------------------------------------

def dump_debug(page, tag: str) -> Path | None:
    """Captura de tela + HTML em `.local/`: pode conter dados da conta, nunca vai a repositório."""
    try:
        folder = DEBUG_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-{tag}"
        folder.mkdir(parents=True, exist_ok=True)
        try:
            page.screenshot(path=str(folder / "page.png"), full_page=True)
        except Exception:  # noqa: BLE001
            pass
        (folder / "page.html").write_text(page.content(), encoding="utf-8")
        (folder / "url.txt").write_text(page.url, encoding="utf-8")
        return folder
    except Exception:  # noqa: BLE001
        return None


# --- helpers de UI (texto/role, pt-BR e en) ----------------------------------

def rx(*words: str) -> re.Pattern:
    return re.compile("|".join(words), re.I)


class Ui:
    def __init__(self, page, log=print):
        self.page = page
        self.log = log

    def _locators(self, pattern: re.Pattern, roles):
        for role in roles:
            yield self.page.get_by_role(role, name=pattern)
        yield self.page.get_by_text(pattern)

    def find(self, pattern: re.Pattern, roles=("button", "menuitem", "tab", "link", "option"),
             timeout: float = 15.0):
        deadline = time.time() + timeout
        while True:
            for loc in self._locators(pattern, roles):
                try:
                    count = min(loc.count(), 6)
                except Exception:  # noqa: BLE001
                    continue
                for i in range(count):
                    item = loc.nth(i)
                    try:
                        if item.is_visible():
                            return item
                    except Exception:  # noqa: BLE001
                        continue
            if time.time() >= deadline:
                return None
            time.sleep(0.4)

    def click(self, pattern: re.Pattern, step: str, roles=("button", "menuitem", "tab", "link", "option"),
              timeout: float = 15.0):
        item = self.find(pattern, roles, timeout)
        if item is None:
            raise FlowError(f"{step}: elemento não encontrado ({pattern.pattern[:60]})")
        hi.human_click(self.page, item)
        hi.pause(0.4, 1.1)
        self.check_notices()
        return item

    def visible_text(self) -> str:
        try:
            return self.page.inner_text("body", timeout=5000)
        except Exception:  # noqa: BLE001
            return ""

    def check_notices(self) -> None:
        """Quota, falha e logout aparecem como texto; qualquer passo pode revelá-los."""
        if "accounts.google.com" in self.page.url:
            raise NotLoggedIn("a sessão está deslogada (redirecionou para o login do Google)")
        text = self.visible_text()
        if QUOTA_RE.search(text) and not re.search(r"limite de caracteres|character limit", text, re.I):
            snippet = QUOTA_RE.search(text).group(0)
            raise QuotaExceeded(f"limite/cota do NotebookLM detectado: '{snippet}'")


# --- fluxo -------------------------------------------------------------------

def open_context(pw, profile: Path, headed: bool):
    kwargs = dict(
        headless=not headed, locale="pt-BR", viewport={"width": 1440, "height": 900},
        accept_downloads=True,
        args=["--disable-blink-features=AutomationControlled", "--lang=pt-BR"],
    )
    try:
        return pw.chromium.launch_persistent_context(str(profile), channel="chrome", **kwargs)
    except Exception as exc:  # noqa: BLE001 - Chrome ausente: cai para o Chromium do Playwright
        if "Executable doesn't exist" in str(exc) or "chrome" in str(exc).lower() and "not found" in str(exc).lower():
            return pw.chromium.launch_persistent_context(str(profile), **kwargs)
        raise


def ensure_logged_in(ui: Ui) -> None:
    page = ui.page
    page.goto(NOTEBOOKLM_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)
    if "accounts.google.com" in page.url or ui.find(rx(r"^Fazer login$", r"^Sign in$"), ("link", "button"), 2):
        raise NotLoggedIn("a sessão está deslogada")
    ui.check_notices()


def create_notebook(ui: Ui) -> None:
    ui.click(rx(r"Criar (novo|notebook|caderno)", r"Novo (notebook|caderno)",
                r"Create (new|notebook)", r"^New notebook"),
             "criar caderno")
    ui.page.wait_for_timeout(2500)


def add_pasted_text(ui: Ui, text: str) -> None:
    page = ui.page
    ui.click(rx(r"Texto copiado", r"Colar texto", r"Copied text", r"Paste text"), "fonte: colar texto")
    box = None
    for _ in range(20):
        for sel in ("textarea", "[contenteditable='true']", "div[role='textbox']"):
            loc = page.locator(sel)
            for i in range(loc.count()):
                if loc.nth(i).is_visible():
                    box = loc.nth(i)
                    break
            if box:
                break
        if box:
            break
        time.sleep(0.5)
    if box is None:
        raise FlowError("fonte: campo de texto não encontrado")
    hi.human_type(page, box, text, timeout=30000)
    hi.pause(0.5, 1.2)
    ui.click(rx(r"^Inserir$", r"^Insert$", r"^Adicionar$", r"^Add$", r"Inserir"), "fonte: confirmar texto")
    page.wait_for_timeout(8000)


def set_notebook_title(ui: Ui, title: str) -> None:
    try:
        field = ui.page.get_by_role("textbox", name=rx(r"t[ií]tulo", r"title", r"sem t[ií]tulo", r"untitled")).first
        if field.is_visible():
            hi.human_type(ui.page, field, title, clear_first=True)
            ui.page.keyboard.press("Enter")
            hi.pause(0.4, 0.9)
    except Exception:  # noqa: BLE001
        pass


def customize_audio(ui: Ui, prompt: str, allow_truncated: bool) -> None:
    page = ui.page
    # O cartão "Resumo em áudio" tem um botão de personalizar (lápis).
    ui.click(rx(r"Personalizar", r"Customi[sz]e"), "áudio: personalizar", timeout=40)
    page.wait_for_timeout(1500)

    # Idioma: português (Brasil).
    lang = ui.find(rx(r"Idioma", r"Language", r"Escolha o idioma", r"Choose language"),
                   ("combobox", "button", "listbox"), 5)
    if lang is not None:
        hi.human_click(page, lang)
        hi.pause(0.4, 0.9)
        ui.click(rx(r"Portugu[eê]s \(Brasil\)", r"Portuguese \(Brazil\)", r"Portugu[eê]s.*Brasil"),
                 "áudio: idioma pt-BR", roles=("option", "menuitem", "button"), timeout=10)

    # Duração: a mais longa disponível.
    longest = ui.find(rx(r"^Longo$", r"^Long$", r"Mais longo", r"Longest"),
                      ("radio", "button", "tab", "option"), 4)
    if longest is not None:
        hi.human_click(page, longest)
        hi.pause(0.4, 0.9)
    else:
        print("  aviso: opção de duração 'longa' não encontrada; segue com o padrão do NotebookLM")

    # Prompt.
    area = ui.find(rx(r"Sobre o que", r"What should", r"o que os apresentadores", r"focus"), ("textbox",), 6)
    if area is None:
        loc = page.locator("textarea")
        area = loc.last if loc.count() else None
    if area is None:
        raise FlowError("áudio: campo de prompt não encontrado")
    hi.human_type(page, area, prompt, clear_first=True, timeout=30000)
    hi.pause(0.5, 1.0)
    try:
        written = area.input_value()
    except Exception:  # noqa: BLE001
        written = area.inner_text()
    maxlen = None
    try:
        maxlen = area.get_attribute("maxlength")
    except Exception:  # noqa: BLE001
        pass
    if len(written.strip()) < len(prompt.strip()) - 2 or (maxlen and int(maxlen) < len(prompt)):
        msg = (f"PROMPT TRUNCADO: o NotebookLM aceitou {len(written)} de {len(prompt)} caracteres"
               f"{f' (maxlength={maxlen})' if maxlen else ''}")
        if not allow_truncated:
            raise FlowError(msg + "; encurte .agents/skills/podcast/prompt.md ou use --allow-truncated-prompt")
        print("  aviso: " + msg)
    ui.click(rx(r"^Gerar$", r"^Generate$", r"Gerar"), "áudio: gerar", timeout=10)


GENERATING_RE = re.compile(r"gerando|generating|criando|creating", re.I)


def wait_for_audio(ui: Ui, timeout_min: int) -> None:
    page = ui.page
    deadline = time.time() + timeout_min * 60
    seen_generating = False
    while time.time() < deadline:
        text = ui.visible_text()
        ui.check_notices()
        if FAILED_RE.search(text):
            raise FlowError("o NotebookLM reportou falha na geração do áudio")
        generating = bool(GENERATING_RE.search(text))
        seen_generating = seen_generating or generating
        play = ui.find(rx(r"^Reproduzir", r"^Play", r"Reproduzir (resumo|[áa]udio)"), ("button",), 1.5)
        more = ui.find(rx(r"Mais op[cç][oõ]es", r"^Mais$", r"More options", r"^More$"), ("button",), 1.0)
        if not generating and (play is not None or (seen_generating and more is not None)):
            return
        # Ociosidade humana: rolagem e movimentos suaves entre as verificações.
        hi.human_scroll(page, random.choice((-120, 120, 200)), steps=4)
        hi.move_to(page, random.uniform(300, 1100), random.uniform(250, 700))
        time.sleep(random.uniform(*POLL_SECONDS))
    raise FlowError(f"tempo esgotado ({timeout_min} min) esperando o áudio")


def download_audio(ui: Ui, dest_dir: Path) -> Path:
    page = ui.page
    ui.click(rx(r"Mais op[cç][oõ]es", r"^Mais$", r"More options", r"^More$"), "áudio: menu", ("button",), timeout=15)
    with page.expect_download(timeout=10 * 60 * 1000) as info:
        ui.click(rx(r"Fazer download", r"^Baixar", r"^Download"), "áudio: baixar", ("menuitem", "button"), timeout=10)
    download = info.value
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / (download.suggested_filename or "podcast.m4a")
    download.save_as(str(target))
    return target


def normalize_download(path: Path) -> Path:
    """Garante .m4a/.mp3 com stream de áudio único; converte o que vier em outro formato."""
    if path.suffix.lower() in pc.PODCAST_EXTS:
        return path
    exe = pc.require_ffmpeg()
    out = path.with_suffix(".m4a")
    proc = subprocess.run(
        [exe, "-y", "-hide_banner", "-loglevel", "error", "-i", str(path), "-vn", "-map", "0:a:0",
         "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if proc.returncode or not out.is_file():
        raise FlowError(f"não foi possível converter o download ({path.suffix}): {proc.stderr.strip()[:200]}")
    path.unlink(missing_ok=True)
    return out


def delete_notebook(ui: Ui, title: str) -> None:
    """Apaga só o caderno criado agora, localizado pelo título exato."""
    page = ui.page
    page.goto(NOTEBOOKLM_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(4000)
    card = page.get_by_text(title, exact=True).first
    if not card.is_visible():
        print("  aviso: caderno não localizado para exclusão; nada foi apagado")
        return
    box = card.bounding_box()
    hi.move_to(page, box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    ui.click(rx(r"Mais", r"More"), "excluir: menu do caderno", ("button",), timeout=8)
    ui.click(rx(r"Excluir", r"Delete"), "excluir: item", ("menuitem", "button"), timeout=8)
    ui.click(rx(r"^Excluir$", r"^Delete$", r"Confirmar"), "excluir: confirmar", ("button",), timeout=8)


@dataclass
class Result:
    ok: bool
    path: Path | None = None
    message: str = ""


def generate_once(account: str, profile: Path, essay: pc.EssayRef, args) -> Path:
    from playwright.sync_api import sync_playwright

    if profile_in_use(profile):
        raise ProfileInUse(f"o perfil '{account}' está em uso por outro Chrome")
    clear_stale_locks(profile)
    source = build_source_text(pc.ESSAYS_DIR / f"{essay.slug}.md")
    prompt = load_prompt()
    title = f"{essay.title} [{essay.slug[:24]}]"
    with sync_playwright() as pw:
        ctx = open_context(pw, profile, args.headed)
        try:
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            hi.set_current_mouse_pos(200, 200)
            ui = Ui(page)
            try:
                ensure_logged_in(ui)
                create_notebook(ui)
                add_pasted_text(ui, source)
                set_notebook_title(ui, title)
                customize_audio(ui, prompt, args.allow_truncated_prompt)
                wait_for_audio(ui, args.timeout)
                downloaded = download_audio(ui, STATE_DIR / "downloads")
                if args.delete_notebook:
                    try:
                        delete_notebook(ui, title)
                    except FlowError as exc:
                        print(f"  aviso: exclusão do caderno falhou ({exc})")
            except FlowError:
                folder = dump_debug(page, "falha")
                if folder:
                    print(f"  depuração salva em {folder}")
                raise
        finally:
            ctx.close()
    return normalize_download(downloaded)


def run_login(account: str, profiles_dir: Path) -> int:
    """Janela visível para o Usuário entrar; o script não toca em credenciais."""
    from playwright.sync_api import sync_playwright

    profile = profiles_dir / account
    profile.mkdir(parents=True, exist_ok=True)
    if profile_in_use(profile):
        print(f"o perfil '{account}' está em uso por outro Chrome; feche-o antes")
        return 1
    clear_stale_locks(profile)
    print(f"Entre na conta na janela que vai abrir e feche a janela quando o NotebookLM carregar ({account}).")
    with sync_playwright() as pw:
        ctx = open_context(pw, profile, headed=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(NOTEBOOKLM_URL)
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:  # noqa: BLE001
            pass
        ctx.close()
    return 0


def report_default(profiles_dir: Path) -> int:
    accounts = list_accounts(profiles_dir)
    state = load_state()
    print(f"perfis: {profiles_dir}")
    if not accounts:
        print("  nenhum perfil (uma subpasta por conta). Use --profiles-dir ou NOTEBOOKLM_PROFILES_DIR.")
    for name in accounts:
        entry = state["accounts"].get(name, {})
        if in_cooldown(state, name):
            flag = "cooldown até " + entry["cooldown_until"]
        else:
            flag = entry.get("last_status", "nunca usado")
        print(f"  {name}: {flag}")
    print("essays públicos sem podcast (mais recentes primeiro):")
    for ref in candidates_without_podcast()[:15]:
        print(f"  {ref.slug}")
    print("gerar: python scripts/notebooklm_podcast.py <essay>")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("essay", nargs="?", help="slug (ou título) do essay; omita para listar candidatos")
    ap.add_argument("--profiles-dir", help="pasta com um perfil de navegador por subpasta "
                                           "(env NOTEBOOKLM_PROFILES_DIR; padrão .local/notebooklm/profiles)")
    ap.add_argument("--account", help="forçar uma pasta de perfil em vez do rodízio")
    ap.add_argument("--headed", action="store_true", help="mostrar o navegador (padrão: headless)")
    ap.add_argument("--delete-notebook", action="store_true", help="apagar o caderno criado ao final")
    ap.add_argument("--timeout", type=int, default=GENERATION_TIMEOUT_MIN, help="minutos de espera pela geração")
    ap.add_argument("--force", action="store_true", help="gerar mesmo que o essay já tenha podcast")
    ap.add_argument("--allow-truncated-prompt", action="store_true",
                    help="seguir mesmo se o NotebookLM truncar o prompt")
    ap.add_argument("--login", metavar="PASTA", help="abrir janela para login manual do perfil e sair")
    ap.add_argument("--dry-run", action="store_true", help="resolver essay, contas e prompt sem abrir o navegador")
    args = ap.parse_args()

    profiles_dir = resolve_profiles_dir(args.profiles_dir)
    if args.login:
        return run_login(args.login, profiles_dir)
    if not args.essay:
        return report_default(profiles_dir)

    essays = pc.load_essays()
    slug = args.essay if args.essay in essays else None
    if slug is None:
        match, ranking = pc.resolve_essay(args.essay, essays)
        if match is None:
            print("essay não identificado. Candidatos:", file=sys.stderr)
            for score, ref in ranking:
                print(f"  {score:.2f}  {ref.slug}", file=sys.stderr)
            return 2
        slug = match.slug
    essay = essays[slug]
    if pc.source_for(slug) and not args.force:
        print(f"'{slug}' já tem podcast; use --force para gerar outro", file=sys.stderr)
        return 1
    if not essay.public:
        print(f"aviso: o essay é {essay.visibility}; o podcast ficará só em disco (não será publicado)")

    accounts = list_accounts(profiles_dir)
    if not accounts:
        print(f"nenhum perfil em {profiles_dir}. Crie uma subpasta por conta ou use --profiles-dir.", file=sys.stderr)
        return 1
    state = load_state()
    order = rotation_order(accounts, state, args.account)
    if not order:
        print("todas as contas estão em cooldown; veja o estado sem argumentos", file=sys.stderr)
        return 1
    if args.dry_run:
        print(f"essay: {slug}\ncontas, em ordem: {', '.join(order)}\n"
              f"fonte: {len(build_source_text(pc.ESSAYS_DIR / f'{slug}.md'))} caracteres; "
              f"prompt: {len(load_prompt())} caracteres")
        return 0

    last_error = "nenhuma conta tentada"
    for account in order:
        print(f"conta: {account}")
        try:
            audio = generate_once(account, profiles_dir / account, essay, args)
        except ProfileInUse as exc:
            print(f"  {exc}; próxima conta")
            mark_account(state, account, "em uso")
            last_error = str(exc)
        except NotLoggedIn as exc:
            print(f"  {exc}. Entre manualmente: python scripts/notebooklm_podcast.py --login {account}")
            mark_account(state, account, "deslogada")
            last_error = str(exc)
        except QuotaExceeded as exc:
            print(f"  {exc}; cooldown de {QUOTA_COOLDOWN_H} h e próxima conta")
            mark_account(state, account, "cota", QUOTA_COOLDOWN_H)
            last_error = str(exc)
        except FlowError as exc:
            mark_account(state, account, "falha")
            save_state(state)
            print(f"falha: {exc}", file=sys.stderr)
            return 1
        else:
            mark_account(state, account, "ok")
            save_state(state)
            import ingest_podcast

            code, message = ingest_podcast.ingest(audio, slug, force=args.force)
            print(message, file=sys.stderr if code else sys.stdout)
            return code
        save_state(state)
    print(f"nenhuma conta conseguiu gerar: {last_error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
