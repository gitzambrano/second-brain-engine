#!/usr/bin/env python3
"""
Núcleo compartilhado dos podcasts de essay.

Cada essay pode ter um podcast de áudio. O original vive em
``DATA_ROOT/wiki/podcasts/<slug>.m4a|mp3`` (grande, só em disco). O site recebe
uma cópia recodificada e enxuta em ``SITE_ROOT/assets/podcasts/<slug>.m4a``,
somente para essays ``public``.

Este módulo reúne o que build, checkers, fixer, ingestão e geração precisam
dividir: localizar o ffmpeg, inspecionar áudio, validar integridade, casar nome
de arquivo com essay, recodificar para o site e sincronizar a pasta publicada.

Não há ffprobe garantido no ambiente (o ``imageio-ffmpeg`` traz só o ffmpeg),
então a inspeção lê a saída de ``ffmpeg -i``. Se um ffprobe existir ele não é
necessário.

Módulo de biblioteca: sem CLI.
"""
from __future__ import annotations

import difflib
import functools
import glob
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from repo_paths import ESSAYS_DIR, LOCAL_DIR, PODCASTS_DIR, SITE_ROOT

PODCAST_EXTS = (".m4a", ".mp3")
SITE_PODCASTS_REL = "assets/podcasts"

# Parâmetros da cópia publicada. Mude ENCODE_VERSION ao mexer em qualquer um:
# o cache de recodificação é invalidado por ela.
ENCODE_VERSION = 3
SITE_BITRATE_K = 64
SITE_CHANNELS = 2
SITE_SAMPLE_RATE = 44100
SITE_ARTIST = "Second Brain"

MIN_DURATION_S = 60
MAX_DURATION_S = 3 * 3600
# Plausibilidade de tamanho: bytes por segundo entre ~16 kbps e ~640 kbps.
MIN_BYTES_PER_S = 2_000
MAX_BYTES_PER_S = 80_000

CONTAINERS = {".m4a": "mp4", ".mp3": "mp3"}
ALLOWED_CODECS = {"aac", "mp3"}

CACHE_DIR = LOCAL_DIR / "podcasts"


# --- ffmpeg -----------------------------------------------------------------

@functools.lru_cache(maxsize=1)
def find_ffmpeg() -> str | None:
    """Caminho do ffmpeg: env, PATH, imageio-ffmpeg, instalações comuns."""
    env = os.environ.get("FFMPEG_BIN")
    if env and Path(env).is_file():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and Path(exe).is_file():
            return exe
    except Exception:  # noqa: BLE001 - dependência opcional
        pass
    local = os.environ.get("LOCALAPPDATA")
    if local:
        for pattern in (
            f"{local}/Microsoft/WinGet/Packages/*ffmpeg*/**/ffmpeg.exe",
            f"{local}/Microsoft/WinGet/Links/ffmpeg.exe",
        ):
            hits = sorted(glob.glob(pattern, recursive=True))
            if hits:
                return hits[0]
    return None


def require_ffmpeg() -> str:
    exe = find_ffmpeg()
    if not exe:
        raise SystemExit(
            "ffmpeg não encontrado. Instale o ffmpeg ou rode "
            "`python -m pip install imageio-ffmpeg`."
        )
    return exe


def _run(args: list[str], timeout: int = 3600) -> subprocess.CompletedProcess:
    return subprocess.run(
        args, capture_output=True, text=True, encoding="utf-8",
        errors="replace", timeout=timeout,
    )


# --- inspeção ---------------------------------------------------------------

@dataclass
class AudioStream:
    codec: str
    sample_rate: int | None = None
    channels: int | None = None
    bitrate_kbps: int | None = None


@dataclass
class Probe:
    ok: bool
    error: str = ""
    container: str = ""
    duration: float | None = None
    size: int = 0
    audio: list[AudioStream] = field(default_factory=list)

    @property
    def minutes(self) -> int:
        return max(1, round((self.duration or 0) / 60))


_INPUT_RE = re.compile(r"Input #0, (.+?), from ")
_DURATION_RE = re.compile(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)")
_AUDIO_RE = re.compile(r"Stream #\d+:\d+[^\n]*?: Audio: ([A-Za-z0-9_]+)([^\n]*)")
_HZ_RE = re.compile(r"(\d+) Hz")
_KBS_RE = re.compile(r"(\d+) kb/s")
_LAYOUT_RE = re.compile(r"\b(mono|stereo|(\d)\.(\d)(?:\([a-z]+\))?|(\d+) channels)\b")


def parse_probe_output(text: str, size: int = 0) -> Probe:
    """Interpreta a saída de ``ffmpeg -i`` (separada para ser testável)."""
    head = _INPUT_RE.search(text)
    if not head:
        tail = " ".join(text.strip().splitlines()[-2:])[:300]
        return Probe(False, tail or "formato não reconhecido", size=size)
    probe = Probe(True, container=head.group(1), size=size)
    dur = _DURATION_RE.search(text)
    if dur:
        h, m, s = dur.groups()
        probe.duration = int(h) * 3600 + int(m) * 60 + float(s)
    for match in _AUDIO_RE.finditer(text):
        rest = match.group(2)
        stream = AudioStream(match.group(1).lower())
        hz = _HZ_RE.search(rest)
        if hz:
            stream.sample_rate = int(hz.group(1))
        kbs = _KBS_RE.search(rest)
        if kbs:
            stream.bitrate_kbps = int(kbs.group(1))
        layout = _LAYOUT_RE.search(rest)
        if layout:
            word = layout.group(1)
            if word == "mono":
                stream.channels = 1
            elif word == "stereo":
                stream.channels = 2
            elif layout.group(4):
                stream.channels = int(layout.group(4))
            else:
                stream.channels = int(layout.group(2)) + int(layout.group(3))
        probe.audio.append(stream)
    return probe


def probe(path: Path) -> Probe:
    path = Path(path)
    try:
        size = path.stat().st_size
    except OSError as exc:
        return Probe(False, str(exc))
    exe = find_ffmpeg()
    if not exe:
        return Probe(False, "ffmpeg indisponível", size=size)
    proc = _run([exe, "-hide_banner", "-nostdin", "-i", str(path)], timeout=120)
    return parse_probe_output(proc.stdout + "\n" + proc.stderr, size)


def mp4_top_level_boxes(path: Path) -> list[str]:
    """Tipos das caixas de nível superior de um MP4/M4A, na ordem do arquivo."""
    boxes: list[str] = []
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        end = fh.tell()
        pos = 0
        while pos + 8 <= end:
            fh.seek(pos)
            header = fh.read(8)
            if len(header) < 8:
                break
            size, kind = struct.unpack(">I4s", header)
            if size == 1:
                big = fh.read(8)
                if len(big) < 8:
                    break
                size = struct.unpack(">Q", big)[0]
            elif size == 0:
                size = end - pos
            if size < 8:
                break
            boxes.append(kind.decode("latin-1"))
            pos += size
    return boxes


def is_faststart(path: Path) -> bool:
    boxes = mp4_top_level_boxes(path)
    return "moov" in boxes and "mdat" in boxes and boxes.index("moov") < boxes.index("mdat")


def decode_check(path: Path) -> tuple[bool, str]:
    """Decodifica o arquivo inteiro; é o único teste que pega corrupção no meio."""
    exe = require_ffmpeg()
    proc = _run([exe, "-v", "error", "-nostdin", "-i", str(path), "-f", "null", "-"])
    message = (proc.stderr or "").strip()
    return (proc.returncode == 0 and not message), message[:400]


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_json(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass  # cache é otimização; nunca derruba o fluxo


def cached_decode_check(path: Path, use_cache: bool = True) -> tuple[bool, str]:
    """``decode_check`` com cache por tamanho + mtime (não repete a cada checagem)."""
    path = Path(path)
    stat = path.stat()
    key = str(path.resolve())
    cache_file = CACHE_DIR / "decode-cache.json"
    cache = _load_json(cache_file) if use_cache else {}
    hit = cache.get(key)
    if hit and hit.get("size") == stat.st_size and hit.get("mtime_ns") == stat.st_mtime_ns:
        return bool(hit["ok"]), str(hit.get("message", ""))
    ok, message = decode_check(path)
    if use_cache:
        cache[key] = {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
                      "ok": ok, "message": message}
        _save_json(cache_file, cache)
    return ok, message


@dataclass
class Finding:
    code: str
    severity: str  # ERROR | WARNING | INFO
    message: str


def integrity_findings(path: Path, deep: bool = True, use_cache: bool = True) -> list[Finding]:
    """Todas as falhas de integridade de um original, sem lançar."""
    path = Path(path)
    out: list[Finding] = []
    ext = path.suffix.lower()
    if ext not in PODCAST_EXTS:
        out.append(Finding("PODCAST_BAD_EXTENSION", "ERROR",
                           f"extensão {ext or '(nenhuma)'} não aceita; use .m4a ou .mp3"))
        return out
    info = probe(path)
    if info.size == 0:
        out.append(Finding("PODCAST_EMPTY", "ERROR", "arquivo vazio"))
        return out
    if not info.ok:
        out.append(Finding("PODCAST_UNREADABLE", "ERROR", f"não decodifica: {info.error}"))
        return out
    wanted = CONTAINERS[ext]
    if wanted not in info.container.split(","):
        out.append(Finding(
            "PODCAST_EXT_MISMATCH", "ERROR",
            f"extensão {ext} mas o contêiner real é '{info.container}'"))
    if len(info.audio) != 1:
        out.append(Finding("PODCAST_STREAMS", "ERROR",
                           f"esperado exatamente 1 stream de áudio, encontrado {len(info.audio)}"))
    elif info.audio[0].codec not in ALLOWED_CODECS:
        out.append(Finding("PODCAST_CODEC", "ERROR",
                           f"codec '{info.audio[0].codec}' não aceito (aac ou mp3)"))
    if info.duration is None:
        out.append(Finding("PODCAST_NO_DURATION", "ERROR", "duração indeterminada"))
    else:
        if info.duration <= MIN_DURATION_S:
            out.append(Finding("PODCAST_TOO_SHORT", "ERROR",
                               f"duração {info.duration:.0f}s; mínimo {MIN_DURATION_S}s"))
        elif info.duration >= MAX_DURATION_S:
            out.append(Finding("PODCAST_TOO_LONG", "ERROR",
                               f"duração {info.duration / 60:.0f} min; máximo {MAX_DURATION_S // 60} min"))
        rate = info.size / max(info.duration, 1)
        if not (MIN_BYTES_PER_S <= rate <= MAX_BYTES_PER_S):
            out.append(Finding("PODCAST_SIZE_IMPLAUSIBLE", "ERROR",
                               f"{info.size} bytes para {info.duration:.0f}s ({rate / 1000:.1f} kB/s)"))
    if ext == ".m4a" and not out:
        boxes = mp4_top_level_boxes(path)
        if "moov" not in boxes or "mdat" not in boxes:
            out.append(Finding("PODCAST_NO_MOOV", "ERROR", "estrutura MP4 incompleta (moov/mdat)"))
    if deep and not any(f.severity == "ERROR" for f in out):
        ok, message = cached_decode_check(path, use_cache)
        if not ok:
            out.append(Finding("PODCAST_DECODE_ERRORS", "ERROR",
                               f"decodificação completa falhou: {message or 'erro desconhecido'}"))
    return out


# --- essays e nomes ---------------------------------------------------------

@dataclass(frozen=True)
class EssayRef:
    slug: str
    title: str
    visibility: str
    summary: str = ""

    @property
    def public(self) -> bool:
        return self.visibility == "public"


def load_essays() -> dict[str, EssayRef]:
    """Todos os essays, inclusive ocultos (um podcast pode apontar para eles)."""
    import visibility
    from site_common import H1_RE, parse, title_plain

    essays: dict[str, EssayRef] = {}
    if not ESSAYS_DIR.is_dir():
        return essays
    for path in sorted(ESSAYS_DIR.glob("*.md")):
        meta, body = parse(path)
        heading = H1_RE.search(body)
        title = title_plain(heading.group(1).strip()) if heading else path.stem
        essays[path.stem] = EssayRef(
            path.stem, title, visibility.of(meta), str(meta.get("summary") or ""))
    return essays


def list_podcast_files(directory: Path | None = None) -> list[Path]:
    directory = Path(directory or PODCASTS_DIR)
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.iterdir()
                  if p.is_file() and p.suffix.lower() in PODCAST_EXTS)


def source_for(slug: str, directory: Path | None = None) -> Path | None:
    directory = Path(directory or PODCASTS_DIR)
    for ext in PODCAST_EXTS:
        candidate = directory / f"{slug}{ext}"
        if candidate.is_file():
            return candidate
    return None


def normalize(text: str) -> str:
    """Caixa, acento, sublinhado e pontuação descartados; sobram palavras."""
    from unidecode import unidecode

    return " ".join(re.findall(r"[a-z0-9]+", unidecode(text).lower()))


_SEGMENT_SPLIT = re.compile(r"\s+[—–-]\s+|[:?!]\s+|\s*[—–]\s*")


def _candidates(essay: EssayRef) -> list[str]:
    """Formas pelas quais um nome de arquivo pode legitimamente citar o essay."""
    forms = {normalize(essay.slug), normalize(essay.title)}
    for segment in _SEGMENT_SPLIT.split(essay.title):
        if len(segment.split()) >= 2:
            forms.add(normalize(segment))
    return [f for f in forms if f]


def match_score(query: str, essay: EssayRef) -> float:
    """Similaridade 0..1 entre um nome de arquivo e um essay.

    1.0 exige igualdade exata (normalizada) com o slug, o título ou um
    segmento do título (antes/depois de travessão ou dois-pontos).
    """
    q = normalize(query)
    if not q:
        return 0.0
    best = 0.0
    for form in _candidates(essay):
        if q == form:
            return 1.0
        best = max(best, difflib.SequenceMatcher(None, q, form).ratio())
    return best


# Confiança alta o bastante para agir sem perguntar.
AUTO_MIN_SCORE = 0.93
AUTO_MIN_MARGIN = 0.08


def rank_matches(query: str, essays: dict[str, EssayRef], limit: int = 5):
    scored = sorted(((match_score(query, e), e) for e in essays.values()),
                    key=lambda t: (-t[0], t[1].slug))
    return scored[:limit]


def best_match(query: str, essays: dict[str, EssayRef]):
    """Devolve ``(essay | None, ranking)``; ``essay`` só quando inequívoco."""
    ranking = rank_matches(query, essays)
    if not ranking:
        return None, ranking
    top_score, top = ranking[0]
    second = ranking[1][0] if len(ranking) > 1 else 0.0
    if top_score >= AUTO_MIN_SCORE and top_score - second >= AUTO_MIN_MARGIN:
        return top, ranking
    return None, ranking


def resolve_essay(query: str, essays: dict[str, EssayRef], min_substring: int = 5):
    """Resolve um slug, título ou trecho; ``(essay | None, ranking)``.

    Ordem: slug exato; trecho (normalizado) contido em exatamente um slug ou
    título; por fim a similaridade de ``best_match``.
    """
    if query in essays:
        return essays[query], []
    q = normalize(query)
    if len(q) >= min_substring:
        hits = [e for e in essays.values()
                if q in normalize(e.slug) or q in normalize(e.title)]
        if len(hits) == 1:
            return hits[0], []
    return best_match(query, essays)


# --- recodificação e sincronização com o site -------------------------------

def site_podcasts_dir(site_root: Path | None = None) -> Path:
    return Path(site_root or SITE_ROOT) / SITE_PODCASTS_REL


def encode_for_site(src: Path, dst: Path, title: str) -> None:
    """AAC-LC estéreo 64 kbps, faststart, sem metadados herdados.

    ``-map_metadata -1`` descarta tudo do original (o NotebookLM e o
    gerenciador de perfis podem deixar tags); só título e artista públicos
    são escritos. ``bitexact`` tira a tag do encoder e deixa a saída
    determinística, então recodificar o mesmo original não muda o selo.
    """
    exe = require_ffmpeg()
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_name(dst.stem + ".part.m4a")
    cmd = [
        exe, "-y", "-hide_banner", "-loglevel", "error", "-nostdin",
        "-i", str(src),
        "-map", "0:a:0", "-vn", "-sn", "-dn",
        "-map_metadata", "-1", "-map_chapters", "-1",
        "-fflags", "+bitexact", "-flags:a", "+bitexact",
        "-c:a", "aac", "-profile:a", "aac_low",
        "-b:a", f"{SITE_BITRATE_K}k", "-ac", str(SITE_CHANNELS), "-ar", str(SITE_SAMPLE_RATE),
        "-metadata", f"title={title}",
        "-metadata", f"artist={SITE_ARTIST}",
        "-movflags", "+faststart",
        "-f", "mp4", str(tmp),
    ]
    proc = _run(cmd)
    if proc.returncode or not tmp.is_file() or tmp.stat().st_size == 0:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg falhou ao recodificar {src.name}: {proc.stderr.strip()[:400]}")
    os.replace(tmp, dst)


def _source_key(src: Path, title: str) -> dict:
    stat = src.stat()
    return {"size": stat.st_size, "mtime_ns": stat.st_mtime_ns,
            "title": title, "version": ENCODE_VERSION,
            "bitrate": SITE_BITRATE_K, "rate": SITE_SAMPLE_RATE}


def sync_site_podcasts(
    essays: list[EssayRef],
    site_root: Path | None = None,
    podcasts_dir: Path | None = None,
    log: Callable[[str], None] = print,
    encoder: Callable[[Path, Path, str], None] | None = None,
) -> dict[str, Path]:
    """Deixa ``assets/podcasts`` exatamente igual ao conjunto publicável.

    Publicável = essay ``public`` com original em disco. Cópias de essays que
    deixaram de ser públicos, ou cujo original sumiu, são removidas. A
    recodificação só roda quando o original (tamanho, mtime, título) ou os
    parâmetros mudaram. Devolve ``slug -> arquivo publicado``.
    """
    encoder = encoder or encode_for_site
    out_dir = site_podcasts_dir(site_root)
    cache_file = CACHE_DIR / "encode-cache.json"
    cache = _load_json(cache_file)
    wanted: dict[str, Path] = {}

    for essay in essays:
        if not essay.public:
            continue
        src = source_for(essay.slug, podcasts_dir)
        if src is None:
            continue
        dst = out_dir / f"{essay.slug}.m4a"
        key = _source_key(src, essay.title)
        if dst.is_file() and dst.stat().st_size > 0 and cache.get(essay.slug) == key:
            log(f"  podcast: {essay.slug} (cache)")
        else:
            bad = [f for f in integrity_findings(src, deep=False) if f.severity == "ERROR"]
            if bad:
                raise SystemExit(f"podcast inválido, não publicado: {src.name}: {bad[0].message}")
            log(f"  podcast: recodificando {essay.slug} …")
            encoder(src, dst, essay.title)
            cache[essay.slug] = key
        wanted[essay.slug] = dst

    if out_dir.is_dir():
        for stale in sorted(out_dir.iterdir()):
            if stale.is_file() and stale.name in {p.name for p in wanted.values()}:
                continue
            log(f"  podcast: removendo {stale.name} (não publicável)")
            if stale.is_dir():
                shutil.rmtree(stale, ignore_errors=True)
            else:
                stale.unlink(missing_ok=True)
        if not any(out_dir.iterdir()):
            try:
                out_dir.rmdir()
            except OSError:
                pass
    cache = {slug: entry for slug, entry in cache.items() if slug in wanted}
    _save_json(cache_file, cache)
    return wanted


def published_minutes(slug: str, site_root: Path | None = None) -> int | None:
    """Duração em minutos da cópia publicada, ou None se não houver."""
    path = site_podcasts_dir(site_root) / f"{slug}.m4a"
    if not path.is_file():
        return None
    info = probe(path)
    if not info.ok or info.duration is None:
        return None
    return info.minutes


def published_findings(path: Path) -> list[Finding]:
    """A cópia publicada cumpre o contrato do site? (estéreo, ~64 kbps, faststart)"""
    out: list[Finding] = []
    info = probe(path)
    if not info.ok:
        return [Finding("SITE_PODCAST_UNREADABLE", "ERROR", f"não decodifica: {info.error}")]
    if len(info.audio) != 1 or info.audio[0].codec != "aac":
        out.append(Finding("SITE_PODCAST_CODEC", "ERROR", "a cópia publicada deve ter um stream aac"))
        return out
    stream = info.audio[0]
    if stream.channels != SITE_CHANNELS:
        out.append(Finding("SITE_PODCAST_NOT_STEREO" if SITE_CHANNELS == 2 else "SITE_PODCAST_NOT_MONO",
                           "WARNING" if stream.channels in (1, 2) else "ERROR",
                           f"{stream.channels} canais; esperado {SITE_CHANNELS} (estéreo)"))
    if stream.bitrate_kbps is not None and not (SITE_BITRATE_K * 0.5 <= stream.bitrate_kbps <= SITE_BITRATE_K * 1.6):
        out.append(Finding("SITE_PODCAST_BITRATE", "WARNING",
                           f"{stream.bitrate_kbps} kb/s; esperado ~{SITE_BITRATE_K}"))
    if not is_faststart(path):
        out.append(Finding("SITE_PODCAST_NOT_FASTSTART", "ERROR",
                           "moov depois de mdat; o player não consegue buscar sem baixar tudo"))
    return out


def file_sha1(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as fh:
        while block := fh.read(chunk):
            h.update(block)
    return h.hexdigest()


def make_temp_dir(prefix: str = "sb-podcast-") -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix))


# --- renomeação e ingestão --------------------------------------------------

@dataclass
class RenamePlan:
    path: Path
    status: str  # ok | rename | ambiguous | orphan
    target: Path | None = None
    slug: str | None = None
    ranking: list = field(default_factory=list)


def plan_renames(directory: Path | None = None) -> list[RenamePlan]:
    essays = load_essays()
    plans: list[RenamePlan] = []
    for path in list_podcast_files(directory):
        if path.stem in essays:
            plans.append(RenamePlan(path, "ok", slug=path.stem))
            continue
        match, ranking = best_match(path.stem, essays)
        if match is None:
            status = "ambiguous" if ranking and ranking[0][0] >= 0.5 else "orphan"
            plans.append(RenamePlan(path, status, ranking=ranking))
            continue
        target = path.with_name(f"{match.slug}{path.suffix.lower()}")
        plans.append(RenamePlan(path, "rename", target=target, slug=match.slug, ranking=ranking))
    return plans


def apply_renames(plans: list[RenamePlan]) -> list[RenamePlan]:
    """Aplica só os renames inequívocos; devolve os que não puderam ser feitos."""
    skipped: list[RenamePlan] = []
    for plan in plans:
        if plan.status != "rename":
            continue
        if plan.target.exists():
            plan.status = "ambiguous"
            skipped.append(plan)
            continue
        plan.path.rename(plan.target)
    return skipped
