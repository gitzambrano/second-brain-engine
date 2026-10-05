"""Podcasts de essay: player, cópias publicadas, nomes, integridade e orçamento.

Tudo roda sobre corpus sintético em `tmp_path`; os testes que precisam de áudio
geram um tom com o ffmpeg e são pulados quando ele não existe.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import ROOT, SCRIPTS

sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SCRIPTS / "lib"))

import podcast_common as pc  # noqa: E402

FFMPEG = pc.find_ffmpeg()
needs_ffmpeg = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg indisponível")
needs_pandoc = pytest.mark.skipif(shutil.which("pandoc") is None, reason="pandoc indisponível")


def essay(path: Path, title: str, visibility: str, body: str = "Texto do ensaio.") -> None:
    path.write_text(
        "---\ntags: [Teste]\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
        f"summary: resumo de {title}\nstatus: draft\nvisibility: {visibility}\n---\n"
        f"# {title}\n\n> Estudo\n> Autor Teste · Janeiro de 2026\n\n## 1. Parte\n\n{body}\n",
        encoding="utf-8",
    )


def make_audio(path: Path, seconds: int = 75, channels: int = 2) -> Path:
    codec = ["-c:a", "libmp3lame"] if path.suffix == ".mp3" else ["-c:a", "aac"]
    subprocess.run(
        [FFMPEG, "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
         "-ac", str(channels), *codec, "-b:a", "96k", str(path)],
        check=True, capture_output=True,
    )
    return path


class World:
    def __init__(self, tmp_path: Path):
        self.data = tmp_path / "data"
        self.site = tmp_path / "site"
        self.local = tmp_path / "local"
        self.essays = self.data / "wiki" / "essays"
        self.podcasts = self.data / "wiki" / "podcasts"
        self.essays.mkdir(parents=True)
        self.podcasts.mkdir(parents=True)
        self.site.mkdir()
        (self.site / ".second-brain-site").write_text("marker", encoding="utf-8")
        self.env = os.environ.copy()
        self.env.update(SECOND_BRAIN_DATA_ROOT=str(self.data), SECOND_BRAIN_SITE_ROOT=str(self.site),
                        SECOND_BRAIN_LOCAL_DIR=str(self.local))
        self.env.pop("NOTEBOOKLM_PROFILES_DIR", None)

    def run(self, script: str, *args: str, timeout: int = 300):
        return subprocess.run([sys.executable, str(SCRIPTS / script), *args], cwd=ROOT, env=self.env,
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              timeout=timeout)

    def build(self):
        proc = self.run("build_site.py", "--no-render")
        assert proc.returncode == 0, proc.stdout + proc.stderr
        return proc

    def render(self, slug: str) -> str:
        proc = self.run("render_public_essay.py", slug)
        assert proc.returncode == 0, proc.stdout + proc.stderr
        return (self.site / "essays" / f"{slug}.html").read_text(encoding="utf-8")


@pytest.fixture
def world(tmp_path):
    w = World(tmp_path)
    essay(w.essays / "ensaio-publico.md", "Ensaio Público", "public")
    essay(w.essays / "ensaio-sem-audio.md", "Ensaio Sem Áudio", "public")
    essay(w.essays / "ensaio-privado.md", "Ensaio Privado", "private")
    essay(w.essays / "ensaio-oculto.md", "Ensaio Oculto", "hidden")
    return w


# --- player ------------------------------------------------------------------

@needs_ffmpeg
@needs_pandoc
def test_player_only_when_audio_exists_and_essay_is_public(world):
    for slug in ("ensaio-publico", "ensaio-privado", "ensaio-oculto"):
        make_audio(world.podcasts / f"{slug}.m4a")
    world.build()

    published = sorted(p.name for p in (world.site / "assets" / "podcasts").iterdir())
    assert published == ["ensaio-publico.m4a"]  # privado e oculto nunca saem

    page = world.render("ensaio-publico")
    assert "data-sb-podcast" in page
    assert "Ouça um podcast gerado por IA sobre este ensaio" in page
    assert "· 1 min" in page
    assert '<audio preload="none"' in page
    assert 'download="ensaio-publico.m4a"' in page
    assert page.index('class="byline"') < page.index("data-sb-podcast")  # logo abaixo da assinatura
    assert "wiki/podcasts" not in page and "data/wiki" not in page

    assert "data-sb-podcast" not in world.render("ensaio-sem-audio")  # sem áudio, sem player


@needs_ffmpeg
def test_published_copy_is_mono_faststart_and_stripped(world):
    make_audio(world.podcasts / "ensaio-publico.m4a", channels=2)
    world.build()
    out = world.site / "assets" / "podcasts" / "ensaio-publico.m4a"

    assert pc.published_findings(out) == []
    info = pc.probe(out)
    assert info.audio[0].channels == 1 and info.audio[0].codec == "aac"
    assert pc.is_faststart(out)
    meta = subprocess.run([FFMPEG, "-hide_banner", "-i", str(out)], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stderr
    assert "Second Brain" in meta and "encoder" not in meta.lower()


@needs_ffmpeg
def test_encode_is_cached_and_stale_copies_are_removed(world):
    make_audio(world.podcasts / "ensaio-publico.m4a")
    world.build()
    out = world.site / "assets" / "podcasts" / "ensaio-publico.m4a"
    first = out.stat().st_mtime_ns
    world.build()
    assert out.stat().st_mtime_ns == first  # sem recodificar

    # Essay deixa de ser público: a cópia some do site.
    essay(world.essays / "ensaio-publico.md", "Ensaio Público", "private")
    world.build()
    assert not (world.site / "assets" / "podcasts").exists()

    # Volta a ser público: reaparece. Original some: a cópia some junto.
    essay(world.essays / "ensaio-publico.md", "Ensaio Público", "public")
    world.build()
    assert out.is_file()
    (world.podcasts / "ensaio-publico.m4a").unlink()
    world.build()
    assert not out.exists()


@needs_ffmpeg
def test_check_podcasts_flags_leaked_audio_of_non_public_essay(world):
    make_audio(world.podcasts / "ensaio-publico.m4a")
    world.build()
    stray = world.site / "assets" / "podcasts" / "ensaio-privado.m4a"
    shutil.copy(world.site / "assets" / "podcasts" / "ensaio-publico.m4a", stray)
    proc = world.run("check_podcasts.py", "--no-leaks")
    assert proc.returncode == 1
    assert "SITE_PODCAST_NOT_PUBLIC" in proc.stdout

    privacy = world.run("check_site_privacy.py")
    assert privacy.returncode == 1 and "podcast of unauthorized essay" in privacy.stdout


@needs_ffmpeg
@needs_pandoc
def test_check_podcasts_passes_on_consistent_site_and_flags_missing_player(world):
    make_audio(world.podcasts / "ensaio-publico.m4a")
    world.build()
    world.render("ensaio-publico")
    world.render("ensaio-sem-audio")
    proc = world.run("check_podcasts.py", "--no-leaks")
    assert proc.returncode == 0, proc.stdout
    (world.site / "essays" / "ensaio-publico.html").write_text("<html></html>", encoding="utf-8")
    assert "SITE_PLAYER_MISSING" in world.run("check_podcasts.py", "--no-leaks").stdout


# --- nomes -------------------------------------------------------------------

@needs_ffmpeg
def test_fixer_renames_unambiguous_and_leaves_ambiguous(world):
    make_audio(world.podcasts / "Ensaio_Público.m4a")
    make_audio(world.podcasts / "Algo_completamente_diferente.m4a")
    check = world.run("check_podcasts.py", "--no-leaks")
    assert check.returncode == 1 and "PODCAST_BAD_NAME" in check.stdout
    assert "ensaio-publico" in check.stdout  # sugestão

    fix = world.run("fix_podcasts.py")
    assert fix.returncode == 2  # sobrou um ambíguo/órfão
    assert (world.podcasts / "ensaio-publico.m4a").is_file()
    assert not (world.podcasts / "Ensaio_Público.m4a").exists()
    assert (world.podcasts / "Algo_completamente_diferente.m4a").is_file()  # intocado


def test_matching_is_exact_on_title_segments_and_conservative_otherwise():
    essays = {
        "singularidade": pc.EssayRef("singularidade", "Singularidade Tecnológica — A Derivada que Engana",
                                     "public"),
        "outro": pc.EssayRef("outro", "Um Tema Completamente Distinto", "public"),
    }
    match, _ = pc.best_match("Singularidade_Tecnológica", essays)
    assert match and match.slug == "singularidade"
    match, ranking = pc.best_match("A_ilusão_matemática_da_singularidade_tecnológica", essays)
    assert match is None and ranking[0][1].slug == "singularidade"  # sugere, mas não age


@needs_ffmpeg
def test_ingest_moves_validates_and_refuses_ambiguity(world, tmp_path):
    src = make_audio(tmp_path / "Ensaio_Público.m4a")
    proc = world.run("ingest_podcast.py", str(src))
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (world.podcasts / "ensaio-publico.m4a").is_file() and not src.exists()

    other = make_audio(tmp_path / "x.m4a")
    proc = world.run("ingest_podcast.py", str(other))
    assert proc.returncode == 2 and "ambíguo" in proc.stderr and other.exists()
    proc = world.run("ingest_podcast.py", str(other), "Sem Áudio")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert (world.podcasts / "ensaio-sem-audio.m4a").is_file()


# --- integridade -------------------------------------------------------------

def test_parse_probe_output_reads_ffmpeg_banner():
    banner = (
        "Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'a.m4a':\n"
        "  Duration: 00:16:45.82, start: 0.0, bitrate: 257 kb/s\n"
        "  Stream #0:0[0x1](und): Audio: aac (LC) (mp4a / 0x6134706D), 44100 Hz, stereo, fltp, 256 kb/s (default)\n"
    )
    info = pc.parse_probe_output(banner, 1000)
    assert info.ok and info.duration == pytest.approx(1005.82)
    assert [s.codec for s in info.audio] == ["aac"] and info.audio[0].channels == 2
    assert not pc.parse_probe_output("a.m4a: Invalid data found when processing input").ok


@needs_ffmpeg
def test_integrity_failures(world, tmp_path):
    good = make_audio(world.podcasts / "ensaio-publico.m4a")
    assert pc.integrity_findings(good, use_cache=False) == []

    truncated = tmp_path / "cortado.m4a"
    truncated.write_bytes(good.read_bytes()[: good.stat().st_size // 2])
    assert {f.code for f in pc.integrity_findings(truncated, use_cache=False)} & {
        "PODCAST_UNREADABLE", "PODCAST_NO_MOOV", "PODCAST_DECODE_ERRORS"}

    garbage = tmp_path / "lixo.m4a"
    garbage.write_bytes(b"isto nao e audio" * 5000)
    assert pc.integrity_findings(garbage, use_cache=False)[0].code == "PODCAST_UNREADABLE"

    short = make_audio(tmp_path / "curto.m4a", seconds=20)
    assert "PODCAST_TOO_SHORT" in {f.code for f in pc.integrity_findings(short, use_cache=False)}

    fake = make_audio(tmp_path / "falso.mp3")
    renamed = tmp_path / "falso.m4a"
    fake.rename(renamed)
    assert "PODCAST_EXT_MISMATCH" in {f.code for f in pc.integrity_findings(renamed, use_cache=False)}

    empty = tmp_path / "vazio.m4a"
    empty.write_bytes(b"")
    assert pc.integrity_findings(empty)[0].code == "PODCAST_EMPTY"


@needs_ffmpeg
def test_check_podcasts_caches_decode_by_size_and_mtime(world):
    make_audio(world.podcasts / "ensaio-publico.m4a")
    world.build()
    ok = world.run("check_podcasts.py", "--no-leaks")
    assert ok.returncode == 0, ok.stdout
    cache_file = world.local / "podcasts" / "decode-cache.json"
    cache = json.loads(cache_file.read_text(encoding="utf-8"))
    assert len(cache) == 1 and next(iter(cache.values()))["ok"] is True

    # Plantar um veredito falso no cache prova que o segundo passe o reutiliza.
    key = next(iter(cache))
    cache[key]["ok"] = False
    cache[key]["message"] = "do cache"
    cache_file.write_text(json.dumps(cache), encoding="utf-8")
    again = world.run("check_podcasts.py", "--no-leaks")
    assert again.returncode == 1 and "do cache" in again.stdout


@needs_ffmpeg
def test_private_podcast_is_info_and_orphan_is_error(world):
    make_audio(world.podcasts / "ensaio-privado.m4a")
    make_audio(world.podcasts / "zzzz-sem-essay-algum.m4a")
    proc = world.run("check_podcasts.py", "--no-leaks")
    assert "PODCAST_NOT_PUBLISHED" in proc.stdout
    assert "PODCAST_ORPHAN" in proc.stdout and proc.returncode == 1


# --- orçamento ---------------------------------------------------------------

def sparse(path: Path, mb: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fh:
        fh.truncate(mb * 1024 * 1024)


def test_budget_splits_podcasts_from_site_total(tmp_path):
    import check_site_budget as budget

    site = tmp_path / "site"
    for n in range(3):  # 3 x 24 MB = 72 MB: acima dos 40 MB do site, dentro dos 500 MB de áudio
        sparse(site / "assets" / "podcasts" / f"e{n}.m4a", 24)
    result = budget.audit(site)
    assert result.count("ERROR") == 0, result.to_dict()
    assert result.meta["podcasts_mb"] == pytest.approx(72, abs=0.1)

    sparse(site / "assets" / "podcasts" / "grande.m4a", 26)
    assert "OVER_BUDGET" in {i.code for i in budget.audit(site).issues}  # 25 MB por arquivo

    other = tmp_path / "site2"
    for n in range(45):  # 45 MB de mídia comum estoura os 40 MB do site
        sparse(other / "assets" / "media" / f"m{n}.png", 1)
    assert "SITE_OVER_BUDGET" in {i.code for i in budget.audit(other).issues}


# --- vazamento de conta ------------------------------------------------------

def test_leak_scan_finds_emails_and_profile_names_without_hardcoding(tmp_path, monkeypatch):
    import check_podcasts as cp
    from sanity_common import CheckResult

    profiles = tmp_path / "perfis"
    (profiles / "conta-alfa").mkdir(parents=True)
    monkeypatch.setenv("NOTEBOOKLM_PROFILES_DIR", str(profiles))
    site = tmp_path / "site"
    site.mkdir()
    clean = tmp_path / "limpo.py"
    clean.write_text("print('nada aqui')\n", encoding="utf-8")
    dirty = tmp_path / "sujo.md"
    dirty.write_text("usar a conta " + "conta-alfa" + " hoje\n", encoding="utf-8")
    mail = tmp_path / "mail.txt"
    mail.write_text("alguem" + "@" + "gmail.com", encoding="utf-8")
    (site / "index.html").write_text("<p>contato " + "x" + "@" + "gmail.com</p>", encoding="utf-8")

    result = CheckResult("t")
    cp.audit_leaks(result, engine_files=[clean], site_root=site)
    assert [i.code for i in result.issues] == ["ACCOUNT_LEAK_SITE"]

    result = CheckResult("t")
    cp.audit_leaks(result, engine_files=[clean, dirty, mail], site_root=tmp_path / "ausente")
    assert [i.code for i in result.issues] == ["ACCOUNT_LEAK_ENGINE"] * 2


# --- NotebookLM: rodízio, estado e fonte -------------------------------------

def test_rotation_state_and_source_text(tmp_path):
    import notebooklm_podcast as nb

    accounts = ["a", "b", "c"]
    state = {"accounts": {}, "last_account": None}
    assert nb.rotation_order(accounts, state) == ["a", "b", "c"]
    nb.mark_account(state, "a", "ok")
    assert nb.rotation_order(accounts, state) == ["b", "c", "a"]
    nb.mark_account(state, "b", "cota", cooldown_hours=12)
    assert nb.rotation_order(accounts, state) == ["c", "a"]
    assert nb.rotation_order(accounts, state, forced="b") == ["b"]
    with pytest.raises(SystemExit):
        nb.rotation_order(accounts, state, forced="z")

    nb.save_state(state, tmp_path / "s.json")
    assert nb.load_state(tmp_path / "s.json")["last_account"] == "a"

    profiles = tmp_path / "p"
    for name in ("zeta", "alfa", "meio"):
        (profiles / name).mkdir(parents=True)
    (profiles / "arquivo.txt").write_text("x", encoding="utf-8")
    assert nb.list_accounts(profiles) == ["alfa", "meio", "zeta"]

    md = tmp_path / "e.md"
    md.write_text("---\ntags: [x]\n---\n# T\n\n## Sumário\n\n- a\n\n## 1. Corpo\n\nTexto.\n\n"
                  "## Conexões\n\n- [[outro]]\n", encoding="utf-8")
    text = nb.build_source_text(md)
    assert "tags:" not in text and "Sumário" not in text and "Conexões" not in text
    assert "Texto." in text and text.startswith("# T")

    prompt = nb.load_prompt()
    assert prompt.startswith("Gere uma conversa entre os apresentadores")
    assert "FIDELIDADE ABSOLUTA" in prompt and prompt.rstrip().endswith("arquitetura lógica do ensaio.")


def test_notebooklm_default_runs_without_browser(tmp_path):
    env = os.environ.copy()
    env["SECOND_BRAIN_LOCAL_DIR"] = str(tmp_path / "local")
    env["SECOND_BRAIN_DATA_ROOT"] = str(tmp_path / "data")
    env.pop("NOTEBOOKLM_PROFILES_DIR", None)
    proc = subprocess.run([sys.executable, str(SCRIPTS / "notebooklm_podcast.py")], cwd=ROOT, env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    assert proc.returncode == 0, proc.stderr
    assert "perfis:" in proc.stdout


def test_logged_out_detection_covers_trynow_landing():
    import notebooklm_podcast as nb

    class FakeText:
        def __init__(self, n):
            self.n = n

        def count(self):
            return self.n

    class FakePage:
        def __init__(self, url, landing=False):
            self.url, self.landing = url, landing

        def get_by_text(self, _pattern):
            return FakeText(1 if self.landing else 0)

    assert nb.Ui(FakePage("https://notebook.google.com/trynow")).logged_out()
    assert nb.Ui(FakePage("https://accounts.google.com/signin")).logged_out()
    assert nb.Ui(FakePage("https://notebook.google.com/", landing=True)).logged_out()
    assert not nb.Ui(FakePage("https://notebook.google.com/notebook/abc")).logged_out()
