#!/usr/bin/env python3
"""
Renderiza os essays públicos com o mesmo pipeline do export HTML.

O export já resolve a tipografia do essay: `html_preprocess.transform_markdown`
converte as convenções de blockquote do corpus em caixas tipadas, veredictos,
pull-quotes e cards, e `essay_template.html` monta a capa, a assinatura, os
filetes de capítulo, os ornamentos, a medida justificada e as notas de rodapé.
Reimplementar qualquer parte disso para o site significaria manter dois
renderizadores que divergem.

Então este módulo chama o `prepare_for_pandoc` do próprio export e o template
dele, e só então sobrepõe o site:

    * um override de tema — paleta, fundo e fonte do site;
    * o cromo do site — volta para o Atlas, sumário flutuante, essays relacionados;
    * imagens compartilhadas em vez de data URIs, para a página ficar em dezenas
      de kilobytes.

Só essays autorizados com `visibility: public` podem ser renderizados.

Default sem argumentos: renderizar todo essay público em SITE_ROOT/essays.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from export_essay_html import PANDOC_FROM, TEMPLATE_PATH, body_has_math, prepare_for_pandoc
from repo_paths import ASSETS_DIR, SITE_ROOT, SITE_SRC_DIR
from site_common import (
    collect_public,
    plain_text,
    public_body_for_index,
    public_connections,
    reading_minutes,
    sanitize_private_wikilinks,
    title_html,
    title_plain,
)

IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
REMOTE_RE = re.compile(r"^(https?://|data:)", re.I)
ALLOWED_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}


def rewrite_images(markdown: str, source: Path) -> str:
    """Copy referenced local images into the site and rewrite their links.

    An image is published only if it resolves inside DATA_ROOT/wiki/assets and
    has a web-safe extension. Anything else degrades to its alt text rather than
    leaking a private path.
    """
    destdir = SITE_ROOT / "assets" / "media"
    destdir.mkdir(parents=True, exist_ok=True)

    def replace(match: re.Match[str]) -> str:
        alt, raw = match.group(1), match.group(2).strip()
        if REMOTE_RE.match(raw):
            return match.group(0)

        clean = raw.split(" ", 1)[0].strip("<>")
        candidate = (source.parent / clean).resolve()
        if not candidate.exists():
            candidate = (ASSETS_DIR / Path(clean).name).resolve()

        placeholder = alt or "[imagem omitida]"
        if not candidate.is_file():
            return placeholder
        try:
            candidate.relative_to(ASSETS_DIR.resolve())
        except ValueError:
            return placeholder
        if candidate.suffix.lower() not in ALLOWED_IMAGE_SUFFIXES:
            return placeholder

        dest = destdir / candidate.name
        payload = candidate.read_bytes()
        if dest.exists() and dest.read_bytes() != payload:
            digest = hashlib.sha256(payload).hexdigest()[:12]
            dest = destdir / f"{candidate.stem}-{digest}{candidate.suffix}"
        shutil.copy2(candidate, dest)
        write_webp_sibling(dest)
        return f"![{alt}](../assets/media/{dest.name})"

    return IMAGE_RE.sub(replace, markdown)


# Ganho mínimo para valer a pena guardar um segundo arquivo. Abaixo disto o
# WebP só acrescenta bytes ao repositório sem acelerar nada para o leitor.
WEBP_MIN_GAIN = 0.15
WEBP_SOURCES = {".png", ".jpg", ".jpeg"}


def write_webp_sibling(dest: Path) -> Path | None:
    """Grava um WebP ao lado do original, quando compensa.

    O PNG continua sendo o arquivo servido no `<img>`: é ele que garante figura
    técnica sem perda e navegador antigo funcionando. O WebP entra como
    `<source>` alternativo, que o navegador escolhe se souber ler — economia
    sem trocar o formato de ninguém.
    """
    if dest.suffix.lower() not in WEBP_SOURCES:
        return None
    try:
        from PIL import Image
    except ImportError:
        return None

    alvo = dest.with_suffix(".webp")
    try:
        with Image.open(dest) as imagem:
            # PNG de figura técnica é linha e texto: perda ali vira artefato em
            # cima de eixo e legenda. JPEG já é fotográfico e já perdeu antes.
            if dest.suffix.lower() == ".png":
                imagem.save(alvo, "WEBP", lossless=True, method=6)
            else:
                imagem.convert("RGB").save(alvo, "WEBP", quality=82, method=6)
    except Exception:
        alvo.unlink(missing_ok=True)
        return None

    if alvo.stat().st_size > dest.stat().st_size * (1 - WEBP_MIN_GAIN):
        alvo.unlink(missing_ok=True)
        return None
    return alvo


IMG_TAG_RE = re.compile(r'<img\b[^>]*\bsrc="(\.\./assets/media/[^"]+)"[^>]*>')
CONTENT_RE = re.compile(
    r'(<main\b[^>]*\bclass="[^"]*\bcontent\b[^"]*"[^>]*>)(.*?)(</main>)',
    re.I | re.S,
)
ORNAMENT_DIV_RE = re.compile(r'<div class="ornament">.*?</div>\s*', re.I | re.S)


def wrap_pictures(html_text: str) -> str:
    """Envolve cada `<img>` local num `<picture>` quando há WebP ao lado.

    Sem `<picture>` o WebP gerado não serviria para nada: ninguém pediria por
    ele. O `<img>` permanece intacto como fallback, então um navegador que não
    conheça WebP — ou um WebP que não exista — continua vendo a mesma imagem.
    """
    def substitui(match: re.Match[str]) -> str:
        src = match.group(1)
        sibling = SITE_ROOT / "assets" / "media" / (Path(src).stem + ".webp")
        if not sibling.is_file():
            return match.group(0)
        webp = src.rsplit(".", 1)[0] + ".webp"
        return (
            f'<picture><source srcset="{webp}" type="image/webp">'
            f"{match.group(0)}</picture>"
        )

    return IMG_TAG_RE.sub(substitui, html_text)


def strip_content_ornaments(html_text: str) -> str:
    """Omit authored chapter ornaments from the public reading projection.

    The canonical reader already marks chapter transitions with the chapter
    kicker and its rule. Source Markdown and standalone exports retain the
    authored ornament; only the public HTML body drops the duplicate cue.
    """
    def replace(match: re.Match[str]) -> str:
        return match.group(1) + ORNAMENT_DIV_RE.sub("", match.group(2)) + match.group(3)

    return CONTENT_RE.sub(replace, html_text)


def pandoc(markdown: str, title: str, subtitle: str, author: str,
           summary: str, status: str, minutes: int) -> str:
    """Run the export's own Pandoc invocation, minus the offline embedding.

    MathJax entra só em essay que tem fórmula. O export standalone já fazia
    essa distinção; a projeção pública não, e mandava um renderizador
    matemático de megabytes para quem foi ler um ensaio de filosofia.
    """
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "essay.md"
        source.write_text(markdown, encoding="utf-8")
        cmd = [
            "pandoc", str(source),
            "--standalone",
            f"--template={TEMPLATE_PATH}",
            "--highlight-style=pygments",
            *(["--mathjax=../assets/mathjax/tex-svg.js"] if body_has_math(markdown) else []),
            "-V", f"title={title_plain(title)}",
            "-V", f"titlehtml={title_html(title)}",
            "-V", f"subtitle={subtitle}",
            "-V", f"author={author}",
            "-V", f"summary={summary}",
            *(["-V", f"status={status}"] if status else []),
            # O tempo de leitura vai PRONTO para o template, e vem calculado
            # sobre o MESMO texto que o catálogo mede — não sobre o markdown
            # que o pandoc recebe. Medir aqui dava número parecido mas não
            # igual, e o leitor via 76 na página e 73 no catálogo.
            "-V", f"minutes={minutes}",
            "-f", PANDOC_FROM,
            "-t", "html5",
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
        if proc.returncode:
            raise SystemExit("Pandoc failed:\n" + proc.stderr)
        return proc.stdout


def asset_version(name: str) -> str:
    """Content fingerprint, so a redeploy can never serve a stale script."""
    source = SITE_SRC_DIR / name
    if not source.exists():
        return "0"
    return hashlib.sha256(source.read_bytes()).hexdigest()[:8]


FAVICON_RE = re.compile(r'<link rel="(?:icon|apple-touch-icon)"[^>]*>')


def favicon_link() -> str:
    """The Atlas icon, read from the index instead of copied.

    The two surfaces are one site; a second literal would be a second thing to
    keep in sync. Without any icon the browser asks for /favicon.ico on every
    essay page and gets a 404, and the tab opens with no identity at all.
    """
    index = (SITE_SRC_DIR / "index.html").read_text(encoding="utf-8")
    # A página do essay vive em `essays/`, um nível abaixo do índice: o mesmo
    # literal de ícone só serve depois de subir um diretório.
    return "".join(FAVICON_RE.findall(index)).replace('href="assets/', 'href="../assets/')


def site_chrome(essay, related) -> str:
    """Nav back to the Atlas, a floating summary, and public connections."""
    related_html = "".join(
        f'<a class="sb-related-card" href="{html.escape(r.slug)}.html">'
        f"<strong>{html.escape(r.title)}</strong>"
        f"<span>{html.escape(r.summary)}</span></a>"
        for r in related
    )
    related_block = (
        f'<section class="sb-related"><h2>Continue explorando</h2>'
        f'<div class="sb-related-grid">{related_html}</div></section>'
        if related else ""
    )
    tags = "".join(f'<span class="sb-tag">{html.escape(t)}</span>' for t in essay.tags)
    theme_v = asset_version("theme.js")
    essay_v = asset_version("essay.js")

    return f"""
<header class="sb-bar">
  <a class="sb-brand" href="../index.html"><span class="sb-mark" aria-hidden="true"></span>Second Brain</a>
  <nav class="sb-nav">
    <a href="../index.html">Essays</a>
    <a href="../graph.html">Grafo</a>
    <button class="sb-subscribe" type="button" id="sbSubscribe" aria-haspopup="dialog"
            aria-controls="sbSubscribeDialog">Assinar</button>
    <button type="button" id="sbTheme" aria-label="Alternar tema" aria-pressed="false">◐</button>
  </nav>
</header>
<dialog class="sb-subscribe-dialog" id="sbSubscribeDialog" aria-labelledby="sbSubscribeTitle">
  <div class="sb-subscribe-dialog-head">
    <p class="sb-subscribe-eyebrow">Ensaios · Second Brain</p>
    <h2 id="sbSubscribeTitle">Novos ensaios por e-mail.</h2>
    <p>Só quando houver publicação nova.</p>
    <form method="dialog"><button class="sb-subscribe-close" type="submit" aria-label="Fechar">×</button></form>
  </div>
  <div class="sb-subscribe-embed" aria-label="Assinar a newsletter do Second Brain">
    <div id="sbKitEmbedMount" data-uid="4fd36350af"
         data-src="https://gustavo-jose-zambrano.kit.com/4fd36350af/index.js"></div>
  </div>
  <p class="sb-subscribe-note"><strong>Importante:</strong> confira também a pasta de <strong>Spam</strong> e confirme o e-mail.</p>
</dialog>
<div class="sb-progress"><span id="sbProgressFill"></span></div>
<div class="sb-tags">{tags}</div>
{related_block}
<button class="sb-toc-fab" type="button" id="sbTocFab" aria-expanded="false"
        aria-controls="sbToc" title="Sumário do essay">
  <span class="sb-toc-icon" aria-hidden="true">☰</span>
  <span class="sb-toc-text">Sumário</span>
</button>
<aside class="sb-toc" id="sbToc" hidden aria-label="Sumário do essay">
  <header><strong>Sumário</strong>
    <button type="button" id="sbTocClose" aria-label="Fechar">×</button></header>
  <nav id="sbTocList"></nav>
</aside>
<script src="../assets/theme.js?v={theme_v}"></script>
<script src="../assets/essay.js?v={essay_v}"></script>
"""


def render(slug: str, output: Path) -> None:
    essays = collect_public()
    by_slug = {e.slug: e for e in essays}
    if slug not in by_slug:
        raise SystemExit(f"not public or not found: {slug}")

    essay = by_slug[slug]
    allowed = set(by_slug)

    # The export reads the file; give it one with public-safe wikilinks and
    # site-relative images, leaving its own preprocessing untouched.
    prepared = sanitize_private_wikilinks(essay.path.read_text(encoding="utf-8-sig"), allowed)
    prepared = rewrite_images(prepared, essay.path)

    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / essay.path.name
        staged.write_text(prepared, encoding="utf-8")
        body, title, subtitle, author_date, summary, status = prepare_for_pandoc(staged)

    minutos = reading_minutes(plain_text(public_body_for_index(essay, allowed)))
    page = pandoc(body, title, subtitle, author_date, summary, status, minutos)
    page = strip_content_ornaments(page)

    theme = (SITE_SRC_DIR / "essay-theme.css").read_text(encoding="utf-8")
    # A Inter auto-hospedada, quando o build a baixou. As referências do cache
    # são relativas ao próprio `fonts/`; aqui a folha é embutida na página do
    # essay, cuja base é `essays/`, então o prefixo muda.
    fonts_css = SITE_ROOT / "assets" / "fonts" / "fonts.css"
    if fonts_css.is_file():
        blocos = re.sub(
            r"url\(([^)/][^)]*\.woff2)\)",
            lambda m: f"url(../assets/fonts/{m.group(1)})",
            fonts_css.read_text(encoding="utf-8"),
        )
        theme = blocos + "\n" + theme
    related = [by_slug[s] for s in public_connections(essay, allowed) if s in by_slug]
    chrome = site_chrome(essay, related)

    early_theme = (
        '<script>(function(){'
        'var t=null;'
        'try{t=localStorage.getItem("sb-theme")}catch(e){}'
        # Sem escolha guardada, claro. Seguir o `prefers-color-scheme` abria o
        # site inteiro no escuro em qualquer aparelho com o sistema escuro.
        'if(!t)t="light";'
        'document.documentElement.dataset.theme=t'
        '})();</script>'
    )
    # O ícone do Atlas: sem ele o navegador pede /favicon.ico e leva 404 em
    # toda página de essay — e a aba abre sem identidade nenhuma.
    head = favicon_link() + early_theme + f"<style>{theme}</style>\n"
    page = page.replace("</head>", head + "</head>", 1)
    page = page.replace("</body>", chrome + "</body>", 1)
    page = wrap_pictures(page)

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(page, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("slug", nargs="?",
                    help="essay slug; omit to render every public essay")
    ap.add_argument("--output", type=Path,
                    help="explicit output file (requires an explicit slug)")
    args = ap.parse_args()

    if args.slug is None:
        if args.output:
            raise SystemExit("--output requires an explicit slug")
        slugs = [e.slug for e in collect_public()]
        if not slugs:
            print("no public essays")
            return 0
        for slug in slugs:
            out = SITE_ROOT / "essays" / f"{slug}.html"
            render(slug, out)
            print(out)
        return 0

    out = args.output or SITE_ROOT / "essays" / f"{args.slug}.html"
    render(args.slug, out)
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
