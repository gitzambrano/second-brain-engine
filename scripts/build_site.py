#!/usr/bin/env python3
"""
Compila o Jardim Digital público em SITE_ROOT a partir da allowlist de publicação.

O site é uma projeção de mão única. O catálogo e o mapa cobrem a base inteira;
só um essay autorizado com ``visibility: public`` (ou o legado ``publish:
true``) tem o texto renderizado e linkado. A busca é de catálogo — filtra os
cartões da capa por título, resumo e tags, nunca pelo corpo. Nada mais do
repositório privado de dados é copiado, nunca.

Default sem argumentos: reconstruir o site inteiro.
    --manifest   imprime o que seria publicado, não escreve nada
    --check      confere um site existente contra a allowlist atual
    --no-render  pula a renderização do Pandoc (só estrutura e índice)
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
import sys
import time
import urllib.request
from datetime import date
from pathlib import Path

import build_public_map
from repo_paths import CODE_ROOT, OUTPUT_DIR, SITE_ROOT, SITE_SRC_DIR
from site_common import (
    CODE_SPAN,
    MATH_SPAN,
    WORDS_PER_MINUTE,
    collect_all,
    collect_public,
    plain_text,
    public_body_for_index,
    reading_minutes,
)

# Reexportados por compatibilidade: o cálculo mudou de casa para `site_common`,
# mas testes e leitores continuam procurando estes nomes aqui.
__all__ = ["MATH_SPAN", "CODE_SPAN", "WORDS_PER_MINUTE", "reading_minutes"]

GENERATED_ROOT_FILES = {
    "index.html", "graph.html", "sphere.html", "404.html",
    "search-index.json", "site-manifest.json",
}
GENERATED_DIRS = {"essays", "assets"}
FRONTEND_ASSETS = ("site.css", "theme.js", "site.js", "essay.js")

# O ícone do Atlas, assado por `build_favicons.py` a partir da arte-mestra em
# `site_src/brand/`. Copiado como está: são binários versionados, não gerados
# no build — assar exige Pillow e a arte de 1024px, e nenhum dos dois deveria
# ser pré-requisito para publicar.
BRAND_ASSETS = (
    "favicon.ico",
    "icon-16.png",
    "icon-32.png",
    "icon-32-dark.png",
    "icon-light-192.png",
    "icon-dark-192.png",
    "icon-light-512.png",
    "icon-dark-512.png",
    "apple-touch-icon.png",
)

# The essay template loads MathJax from a local asset so the reader never
# depends on a third-party CDN (blocked on some mobile networks/ad-blockers,
# which left equations as raw LaTeX). The source is the same single copy shared
# by the graph/HTML readers; it is fetched at build time, not at read time.
MATHJAX_URL = "https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg-full.js"
MATHJAX_SHARED_CACHE = OUTPUT_DIR / "graph" / "_mathjax_cache.js"
MATHJAX_DEST = "assets/mathjax/tex-svg.js"


def ensure_site_mathjax(root: Path) -> bool:
    """Serve a local MathJax bundle under SITE_ROOT/assets/mathjax/tex-svg.js.

    Reuses the shared graph/HTML reader cache when present, otherwise downloads
    from the CDN. Returns False (with a warning) only when neither is available,
    in which case equations fall back to raw LaTeX — same tolerated behaviour as
    the standalone HTML export.
    """
    if (root / MATHJAX_DEST).exists() and (root / MATHJAX_DEST).stat().st_size > 100_000:
        return True
    try:
        if MATHJAX_SHARED_CACHE.exists() and MATHJAX_SHARED_CACHE.stat().st_size > 100_000:
            src = MATHJAX_SHARED_CACHE.read_text(encoding="utf-8", errors="replace")
        else:
            with urllib.request.urlopen(MATHJAX_URL, timeout=60) as resp:
                src = resp.read().decode("utf-8", errors="replace")
            MATHJAX_SHARED_CACHE.parent.mkdir(parents=True, exist_ok=True)
            MATHJAX_SHARED_CACHE.write_text(src, encoding="utf-8")
    except Exception as e:  # noqa: BLE001 - offline build degrades gracefully
        print(f"  aviso: MathJax local indisponível ({e}); fórmulas ficarão como LaTeX cru.")
        return False
    dest = root / MATHJAX_DEST
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(src, encoding="utf-8")
    return True

# Fields that would turn a map node into readable body content or into a pointer
# at the private repository. `htmlFile` is the read link and is checked on its own.
GRAPH_PRIVATE_FIELDS = ("file", "body", "text", "path")


def require_site_root(root: Path) -> None:
    """Refuse to write anywhere that is not a marked site checkout."""
    if not root.is_dir():
        raise SystemExit(f"SITE_ROOT does not exist: {root}")
    if not (root / ".second-brain-site").exists():
        raise SystemExit(f"refusing to write without .second-brain-site marker: {root}")


def _unlink(path: Path, attempts: int = 5) -> None:
    """Delete a file, retrying briefly through a sync tool's transient lock."""
    for attempt in range(attempts):
        try:
            if path.exists():
                path.unlink()
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.3)


def _empty(directory: Path) -> None:
    """Remove everything inside a directory, keeping the directory itself.

    The checkout usually lives in a syncing folder (OneDrive/Dropbox) that holds
    a handle on directories it is watching, so `rmtree` fails on the folder even
    after its contents are gone. Emptying is equivalent here — the build
    repopulates the directory immediately — and never trips on that handle.
    """
    if not directory.is_dir():
        return
    for child in sorted(directory.iterdir(), key=lambda p: len(p.parts), reverse=True):
        if child.is_dir():
            _empty(child)
            try:
                child.rmdir()
            except OSError:
                pass
        else:
            _unlink(child)


# O que legitimamente vive no checkout do site sem ser produto do build. Tudo
# o mais na raiz é removido: limpar só a lista do que sabemos gerar deixava
# sobreviver o que não sabemos — um `old-page.html` de um build antigo, um
# `backup.pdf` largado ali, o `debug.json` de uma investigação. Cada um desses
# seria publicado em todo deploy seguinte, indefinidamente, porque nada nunca
# olhava para eles.
SITE_ADMIN_FILES = {
    ".gitignore",
    ".nojekyll",          # impede o Jekyll do Pages de comer pasta com underscore
    ".second-brain-site",  # marcador que autoriza escrever aqui
    "README.md",
}
SITE_ADMIN_DIRS = {".git", ".github"}


def _keep_covers(root: Path) -> dict[str, bytes]:
    """Guarda os PNG de capa antes da limpeza, para poder devolvê-los.

    Assar a capa exige navegador headless, e o build tem de funcionar sem um.
    A saída sem navegador é manter a capa anterior — o que só é possível se ela
    sobreviver ao `clean()`, que esvazia `assets/` inteiro.
    """
    assets = root / "assets"
    if not assets.is_dir():
        return {}
    return {p.name: p.read_bytes() for p in assets.glob("cover-*.png")}


def clean(root: Path) -> None:
    """Esvazia o site, preservando só o que não é produto do build.

    Allowlist, e não blacklist: arquivo desconhecido na raiz é lixo de build
    anterior até prova em contrário, e o custo de errar para o lado de apagar é
    um rebuild — enquanto o custo de errar para o outro lado é publicar.
    """
    require_site_root(root)
    for path in sorted(root.iterdir(), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir():
            if path.name in SITE_ADMIN_DIRS:
                continue
            _empty(path)
            if path.name not in GENERATED_DIRS:
                try:
                    path.rmdir()
                except OSError:
                    pass
        elif path.name not in SITE_ADMIN_FILES:
            _unlink(path)


def ensure_site_fonts(root: Path) -> str:
    """Auto-hospeda a Inter variável e devolve os blocos `@font-face`.

    `--sans` do site sempre começou em Inter, mas nada nunca a servia: a página
    caía em Segoe UI ou Roboto, onde o eixo de peso é discreto e 500, 550 e 600
    renderizam exatamente o mesmo Semibold. Não havia como pedir um negrito
    intermediário porque a fonte que o tem nunca chegava.

    Sem rede o passo é pulado e o site volta ao comportamento anterior — a
    fonte é melhoria de tipografia, não pré-requisito de build.
    """
    from fetch_fonts import SITE_CSS_URL, SITE_FONT_FAMILIES, ensure_local_fonts

    css_path = ensure_local_fonts(
        root / "assets", css_url=SITE_CSS_URL, dirname="fonts",
        required_families=SITE_FONT_FAMILIES,
    )
    if css_path is None:
        print("  fontes: SKIP (sem rede); o site usa a fonte do sistema")
        return ""
    return css_path.read_text(encoding="utf-8")


def font_face_css(blocks: str, prefix: str) -> str:
    """Reescreve `url(x.woff2)` para o caminho relativo de quem vai usar.

    O `fonts.css` do cache guarda referências relativas a si mesmo. A folha do
    catálogo é servida como `assets/site.css` (base: `assets/`), e a do essay é
    embutida em `essays/<slug>.html` (base: `essays/`). Dois prefixos, mesmos
    blocos.
    """
    if not blocks:
        return ""
    return re.sub(r"url\(([^)/][^)]*\.woff2)\)", lambda m: f"url({prefix}{m.group(1)})", blocks)


def copy_frontend(root: Path, fonts: str = "") -> dict[str, str]:
    """Copy the frontend and return a content fingerprint per asset.

    A browser that has visited before will happily keep serving the previous
    CSS and JS after a redeploy. Versioning each URL by content makes a changed
    asset a different URL, so a stale mix can never happen.
    """
    assets = root / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    fingerprints = {}
    for name in FRONTEND_ASSETS:
        source = SITE_SRC_DIR / name
        payload = source.read_bytes()
        if name == "site.css" and fonts:
            merged = font_face_css(fonts, "fonts/") + "\n" + source.read_text(encoding="utf-8")
            payload = merged.encode("utf-8")
        (assets / name).write_bytes(payload)
        # O fingerprint segue o conteúdo SERVIDO, não o do fonte: com a fonte
        # embutida os dois deixam de ser o mesmo arquivo.
        fingerprints[name] = hashlib.sha256(payload).hexdigest()[:8]

    brand = SITE_SRC_DIR / "brand"
    for name in BRAND_ASSETS:
        source = brand / name
        if source.is_file():
            (assets / name).write_bytes(source.read_bytes())
    return fingerprints


def version_assets(html_text: str, fingerprints: dict[str, str]) -> str:
    """Rewrite `assets/<name>` references to carry the content fingerprint."""
    for name, digest in fingerprints.items():
        html_text = html_text.replace(f"assets/{name}\"", f"assets/{name}?v={digest}\"")
    return html_text


def write_data(root: Path, catalogue) -> dict[str, int]:
    """Write the machine files.

    The catalogue lists every essay, because the index does. No essay
    contributes its body — not even an authorized one. The body is read here
    only to derive `minutes` (reading time) for the pages a reader can actually
    open.
    """
    # O índice é um CATÁLOGO, não um corpus. A busca da capa filtra os cartões
    # que já estão no DOM (`card.dataset.search`), então ninguém jamais baixou
    # este arquivo — e ele carregava o texto integral de todos os essays, 2,2 MB
    # servidos para nenhum leitor. Se um dia a busca virar full-text, o corpo
    # volta aqui de propósito e com o gate de privacidade acompanhando.
    allowed = {e.slug for e in catalogue if e.published}
    body_text = {
        e.slug: plain_text(public_body_for_index(e, allowed))
        for e in catalogue if e.published
    }

    search = []
    for essay in catalogue:
        entry = {
            "slug": essay.slug,
            "title": essay.title,
            "summary": essay.summary,
            "tags": list(essay.tags),
            "updated": essay.updated,
            "created": essay.created,
            "status": essay.status,
            "published": essay.published,
        }
        if essay.published:
            entry["minutes"] = reading_minutes(body_text[essay.slug])
            entry["url"] = f"essays/{essay.slug}.html"
        search.append(entry)

    def dump(name: str, data) -> None:
        (root / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    dump("search-index.json", search)
    dump("site-manifest.json", {
        "generated": date.today().isoformat(),
        "published": sorted(allowed),
        "count": len(allowed),
        "catalogue": len(catalogue),
    })
    return {slug: reading_minutes(text) for slug, text in body_text.items()}


def render_index(root: Path, catalogue, minutes: dict[str, int] | None = None,
                 fingerprints: dict[str, str] | None = None) -> None:
    """Render the catalogue: every essay, with only the authorized ones linked."""
    minutes = minutes or {}
    template = (SITE_SRC_DIR / "index.html").read_text(encoding="utf-8")
    tags = sorted({t for e in catalogue for t in e.tags}, key=str.casefold)
    tag_counts = {t: sum(1 for e in catalogue if t in e.tags) for t in tags}
    latest = sorted(catalogue, key=lambda e: e.updated or e.created, reverse=True)
    published = [e for e in catalogue if e.published]

    cards = []
    for essay in latest:
        tag_html = "".join(
            f'<span class="tag">{html.escape(t)}</span>' for t in essay.tags
        )
        # The search haystack is pre-folded so the client only lowercases input.
        searchable = html.escape(
            " ".join([essay.title, essay.summary, *essay.tags]).casefold(), quote=True
        )

        meta = [f'<span>{html.escape(essay.updated)}</span>']
        reading = minutes.get(essay.slug, 0)
        if reading:
            meta.append('<span class="dot" aria-hidden="true">·</span>'
                        f'<span>{reading} min de leitura</span>')

        badges = []
        if not essay.published:
            badges.append('<span class="badge badge-private">Privado</span>')
        if essay.status == "draft":
            badges.append('<span class="badge badge-draft">Rascunho</span>')
        elif essay.status == "revisao":
            badges.append('<span class="badge badge-review">Em revisão</span>')
        badge_html = f'<div class="badges">{"".join(badges)}</div>' if badges else ""

        # The title carries the link and stretches over the whole card (see
        # site.css); the expander is a sibling, never nested inside a link.
        if essay.published:
            title_html = (f'<a href="essays/{html.escape(essay.slug)}.html">'
                          f'{html.escape(essay.title)}</a>')
            read_html = ('<span class="read-link">Ler essay '
                         '<span aria-hidden="true">&rarr;</span></span>')
        else:
            # No link: the text is not published, and the card must not pretend.
            title_html = html.escape(essay.title)
            read_html = '<span class="read-link is-muted">Não publicado</span>'

        body = (
            f'<div class="card-head">'
            f'<div class="card-meta">{"".join(meta)}</div>{badge_html}</div>'
            f'<h3 class="card-title">{title_html}</h3>'
            f'<p class="card-summary">{html.escape(essay.summary)}</p>'
            f'<button class="card-expand" type="button" aria-expanded="false">'
            f'<span class="card-expand-text">Resumo</span>'
            f'<i aria-hidden="true">⌄</i></button>'
            f'<div class="tags">{tag_html}</div>'
            f'{read_html}'
        )

        cards.append(
            f'<article class="essay-card{"" if essay.published else " is-private"}"'
            f' data-search="{searchable}"'
            f' data-tags="{html.escape("|".join(essay.tags), quote=True)}"'
            f' data-updated="{html.escape(essay.updated, quote=True)}"'
            f' data-minutes="{reading}"'
            f' data-published="{"1" if essay.published else "0"}"'
            f' data-status="{html.escape(essay.status or "", quote=True)}"'
            f' data-title="{html.escape(essay.title, quote=True)}">'
            f'{body}</article>'
        )

    # Busiest themes first; the rest stay behind "mais temas" so the page does
    # not open with a wall of tags.
    ordered = sorted(tags, key=lambda name: (-tag_counts[name], name.casefold()))
    chips = "".join(
        f'<button class="filter-chip" type="button"'
        f' data-tag="{html.escape(name, quote=True)}">'
        f'{html.escape(name)} <span class="count">{tag_counts[name]}</span></button>'
        for name in ordered
    )
    updated = max((e.updated for e in catalogue if e.updated), default="—")

    page = (template
            .replace("{{COUNT}}", str(len(catalogue)))
            .replace("{{PUBLISHED}}", str(len(published)))
            .replace("{{TAG_COUNT}}", str(len(tags)))
            .replace("{{UPDATED}}", html.escape(updated))
            .replace("{{CARDS}}", "\n".join(cards))
            .replace("{{TAG_FILTERS}}", chips))
    (root / "index.html").write_text(
        version_assets(page, fingerprints or {}), encoding="utf-8")


def render_essays(root: Path, essays, no_render: bool = False) -> None:
    out = root / "essays"
    out.mkdir(parents=True, exist_ok=True)
    if no_render:
        return
    renderer = CODE_ROOT / "scripts" / "render_public_essay.py"
    for essay in essays:
        proc = subprocess.run(
            [sys.executable, str(renderer), essay.slug,
             "--output", str(out / f"{essay.slug}.html")],
            cwd=CODE_ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode:
            raise SystemExit(proc.stdout + "\n" + proc.stderr)


def build(root: Path, no_render: bool = False):
    catalogue = collect_all()
    essays = [e for e in catalogue if e.published]
    capas_antigas = _keep_covers(root)
    clean(root)
    fonts = ensure_site_fonts(root)
    fingerprints = copy_frontend(root, fonts)
    # MathJax ausente não é degradação aceitável quando há fórmula publicada:
    # a página vai ao ar com LaTeX cru no lugar da equação, o que num white
    # paper de rotores é o conteúdo principal virando ruído. Só é tolerável
    # quando nenhum essay autorizado tem matemática — aí o arquivo nem seria
    # baixado por ninguém.
    if not ensure_site_mathjax(root) and not no_render:
        from export_essay_html import body_has_math

        com_formula = sorted(
            e.slug for e in essays
            if body_has_math(e.path.read_text(encoding="utf-8-sig"))
        )
        if com_formula:
            raise SystemExit(
                "MathJax local indisponível e "
                f"{len(com_formula)} essay(s) publicado(s) têm fórmula "
                f"({', '.join(com_formula[:3])}"
                f"{'…' if len(com_formula) > 3 else ''}). Publicar agora "
                "colocaria LaTeX cru no lugar das equações."
            )
    minutes = write_data(root, catalogue)
    render_index(root, catalogue, minutes, fingerprints)

    # The map is produced by the wiki's own renderers, on sanitized nodes.
    nodes, edges, tag_gaps, isolated = build_public_map.build()
    build_public_map.write(root, nodes, edges, tag_gaps, isolated)

    # O retrato da capa sai do graph.html recém-escrito, e por isso vem
    # depois dele. Sem navegador headless o passo é pulado e o PNG anterior é
    # devolvido ao lugar: publicar não pode depender do Playwright estar
    # instalado. O `clean()` acima já esvaziou `assets/`, então "o anterior
    # permanece" só é verdade porque ele foi guardado antes — era uma promessa
    # falsa enquanto ninguém guardava nada.
    #
    # `--no-render` não assa capa nenhuma. Esse modo existe para checagem
    # estrutural e de privacidade — nos testes e na CI — e um build que serve
    # para isso não pode exigir Chromium. Era o que deixava o job `core`
    # vermelho numa máquina sem browser.
    # Importado aqui, e não no topo: `scripts/lib/` só entra no sys.path
    # quando `repo_paths` é carregado, e o topo deste arquivo roda antes disso.
    if no_render:
        print("  capa: pulada (--no-render é build lógico, sem navegador)")
    else:
        import build_cover

        assado = build_cover.render(root)
        if assado.ok:
            print(f"  capa: {assado.detail}")
            for nome, kb in assado.written:
                print(f"  assets/{nome} ({kb:.0f} KB)")
        else:
            devolvidas = 0
            for nome, dados in capas_antigas.items():
                (root / "assets" / nome).write_bytes(dados)
                devolvidas += 1
            recado = f" ({devolvidas} capa(s) anterior(es) devolvida(s))" if devolvidas else ""
            print(f"  capa: SKIP ({assado.reason}) — {assado.detail}{recado}")

    source = SITE_SRC_DIR / "404.html"
    if source.exists():
        (root / "404.html").write_text(
            version_assets(source.read_text(encoding="utf-8"), fingerprints),
            encoding="utf-8")
    # `render_public_essay.py` lê `assets/fonts/fonts.css` direto do site já
    # montado — por isso `ensure_site_fonts` roda antes daqui.
    render_essays(root, essays, no_render)
    return essays


def check(root: Path) -> list[str]:
    """Verify a built site still matches the current allowlist exactly."""
    require_site_root(root)
    allowed = {e.slug for e in collect_public()}
    errors: list[str] = []

    manifest = root / "site-manifest.json"
    if not manifest.exists():
        errors.append("missing site-manifest.json")
    else:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if set(payload.get("published", [])) != allowed:
            errors.append("manifest differs from current publish:true allowlist")

    # The catalogue lists every essay. Body text and a page link belong only to
    # the authorized ones.
    search = root / "search-index.json"
    if search.exists():
        for entry in json.loads(search.read_text(encoding="utf-8")):
            slug = entry.get("slug")
            if entry.get("published") and slug not in allowed:
                errors.append(f"entry marked published but not authorized: {slug}")
            if not entry.get("published"):
                if entry.get("text"):
                    errors.append(f"body text exposed for unpublished essay: {slug}")
                if entry.get("url"):
                    errors.append(f"unauthorized link in search index: {slug}")

    # O mapa contém todo nó de propósito. O que ele nunca pode conter é corpo de
    # texto, caminho privado ou porta para fora da allowlist.
    #
    # `graph.json` não é mais publicado — o payload que o navegador lê está
    # embutido nos mapas, e é ele que `check_site_privacy.audit_maps` infla e
    # audita. Este bloco continua aqui como rede: se o arquivo reaparecer num
    # deploy antigo ou por engano, ele volta a ser conferido em vez de passar.
    graph = root / "graph.json"
    if graph.exists():
        payload = json.loads(graph.read_text(encoding="utf-8"))
        for node in payload.get("nodes", []):
            node_id = node.get("id")
            slug = str(node_id or "").partition(":")[2]
            readable = bool(node.get("public"))
            if readable and slug not in allowed:
                errors.append(f"node marked public but not authorized: {node_id}")
            link = str(node.get("htmlFile") or "")
            if link and (not readable or link != f"essays/{slug}.html"):
                errors.append(f"unauthorized read link in map: {node_id} -> {link}")
            url = str(node.get("url") or "")
            if url and not url.startswith(("http://", "https://")):
                errors.append(f"non-external url in map: {node_id} -> {url}")
            for field in GRAPH_PRIVATE_FIELDS:
                if node.get(field):
                    errors.append(f"private field '{field}' in map node {node_id}")

    essays_dir = root / "essays"
    if essays_dir.exists():
        present = {p.stem for p in essays_dir.glob("*.html")}
        extra = present - allowed
        if extra:
            errors.append(f"stale/private HTML: {sorted(extra)}")
        # A page missing is as wrong as a page too many: `--no-render` empties
        # this directory, and a site checked only for what it must NOT contain
        # would pass with every essay gone.
        missing = allowed - present
        if missing:
            errors.append(f"authorized essay without a page: {sorted(missing)}")

    return errors


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="validate an existing site")
    ap.add_argument("--manifest", action="store_true", help="list what would be published")
    ap.add_argument("--no-render", action="store_true", help="skip Pandoc rendering")
    args = ap.parse_args()

    if args.manifest:
        print(json.dumps(
            [{"slug": e.slug, "title": e.title} for e in collect_public()],
            ensure_ascii=False, indent=2,
        ))
        return 0

    if args.check:
        errors = check(SITE_ROOT)
        print("site: PASS" if not errors else "site: FAIL")
        for error in errors:
            print(f"  ERROR {error}")
        return 1 if errors else 0

    essays = build(SITE_ROOT, args.no_render)
    print(f"site generated: {SITE_ROOT}")
    print(f"published essays: {len(essays)}")
    for essay in essays:
        print(f"  {essay.slug} — {essay.title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
