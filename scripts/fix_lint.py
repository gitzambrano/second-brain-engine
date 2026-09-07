#!/usr/bin/env python3
"""
fix_lint.py - Único fixer mecânico da wiki: aplica correções inequívocas
sem perguntar. Escreve apenas em essays/concepts/entities/insights - nunca
em AGENTS.md, README.md, .agents/** ou wiki/sources/**. Correções de prosa
nunca tocam frontmatter nem blocos de código.

Correções: linha em branco após heading; ':' dentro de [[wikilink]] -> '—';
espaços duplos em prosa; '&amp;' residual; 3+ linhas em branco -> 1;
`## Referências` no formato antigo -> padrão AIAA [N] (renumera, normaliza
itálico, move link para o fim).

Lê:
    wiki/{essays,concepts,entities,insights}/*.md

Gera:
    arquivos corrigidos in place (com --dry-run, só relatório)

Uso:
    python scripts/fix_lint.py                    # corpus inteiro (default)
    python scripts/fix_lint.py --all              # idem, explícito
    python scripts/fix_lint.py meu-essay          # essay único (slug posicional)
    python scripts/fix_lint.py --file meu-essay   # alias de compatibilidade
    python scripts/fix_lint.py --dry-run          # simula, sem escrever

Flags:
    slug        essay alvo (posicional, opcional)
    --file/-f   caminho do essay (alternativa ao slug)
    --all       força corpus inteiro
    --dry-run   lista o que mudaria, não escreve
"""

import argparse
import re
import sys
from pathlib import Path

import console_encoding  # noqa: F401  (UTF-8 no console; ver o módulo)
from check_references import (
    ANY_MD_LINK_RE,
    ITALIC_RE,
    TAIL_LINK_RE,
    UNDERSCORE_ITALIC_RE,
    URL_PAT,
    citation_and_note,
    load,
    parse_entries,
    try_fix_quoted_title,
)

# Primitivos de parsing de bibliografia continuam em check_references.py, que é
# somente-leitura: são a base da validação. A REESCRITA vive aqui, porque este é
# o único script que escreve em arquivo (ver docstring de check_references.py).
from check_wiki import heading_anchor
from repo_paths import CODE_ROOT, DATA_ROOT, WIKI_ROOT

ROOT_DIR = CODE_ROOT
ESSAYS_DIR = WIKI_ROOT / "essays"
CONCEPTS_DIR = WIKI_ROOT / "concepts"
ENTITIES_DIR = WIKI_ROOT / "entities"
INSIGHTS_DIR = WIKI_ROOT / "insights"

# Same set of directories check_wiki.py treats as "wiki content" -- sources are
# original/immutable documents and are excluded on purpose.
DIRS = [ESSAYS_DIR, CONCEPTS_DIR, ENTITIES_DIR, INSIGHTS_DIR]

FENCE_RE = re.compile(r"^```.*$")


def load_file_content(path):
    # utf-8-sig strips a BOM on read if one happens to be present, but...
    with open(path, "r", encoding="utf-8-sig") as f:
        return f.read()


def save_file_content(path, content):
    # ...we always write plain utf-8, so this script never introduces a BOM
    # that wasn't already there. Injecting a BOM can break YAML frontmatter
    # parsers and Pandoc.
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def split_frontmatter(content):
    """Devolve (frontmatter_com_delimitadores, corpo). O frontmatter é '' se não houver."""
    if content.startswith("---\n"):
        end = content.find("\n---", 4)
        if end != -1:
            end_of_block = content.find("\n", end + 1)
            end_of_block = end_of_block + 1 if end_of_block != -1 else len(content)
            return content[:end_of_block], content[end_of_block:]
    return "", content


def apply_outside_fences(body, fn):
    """Aplica fn(trecho) só aos trechos de `body` FORA de bloco de código cercado,
    deixando as cercas — e o conteúdo delas — intactas.
    """
    lines = body.split("\n")
    out_segments = []
    buffer = []
    in_fence = False
    for line in lines:
        if FENCE_RE.match(line.strip()):
            out_segments.append(fn("\n".join(buffer)) if not in_fence else "\n".join(buffer))
            out_segments.append(line)
            buffer = []
            in_fence = not in_fence
            continue
        buffer.append(line)
    out_segments.append(fn("\n".join(buffer)) if not in_fence else "\n".join(buffer))
    return "\n".join(out_segments)


def fix_blank_line_before_heading(segment):
    """Garante linha em branco ANTES de um heading Markdown.

    Complemento de `fix_heading_spacing`, que só cuidava da linha DEPOIS. Sem a
    linha antes, o Pandoc lê `## Título` colado no parágrafo anterior como
    continuação preguiçosa do parágrafo, e o heading **desaparece** do HTML e do
    PDF, sem erro nenhum: o texto vira uma frase solta no meio da prosa e todo
    link do Sumário que apontava para ele fica órfão. O Obsidian e o GitHub
    renderizam mesmo assim, o que faz o defeito passar despercebido na edição.
    """
    lines = segment.split("\n")
    out = []
    for line in lines:
        if re.match(r"^#{1,6} ", line) and out and out[-1].strip() != "":
            out.append("")
        out.append(line)
    return "\n".join(out)


def fix_heading_spacing(segment):
    """Garante uma linha em branco depois de cada heading."""
    lines = segment.split("\n")
    new_lines = []
    for i, line in enumerate(lines):
        new_lines.append(line)
        if re.match(r"^#{1,6} ", line):
            if i + 1 < len(lines):
                next_line = lines[i + 1]
                if next_line.strip() != "" and not next_line.strip().startswith("#"):
                    new_lines.append("")
    return "\n".join(new_lines)


def fix_wikilinks_colons(segment):
    """Troca `:` por travessão dentro de [[wikilink]] — o Windows não aceita
    dois-pontos em nome de arquivo. Preserva `[[#Seção]]`, que aponta para uma
    âncora do próprio arquivo e não para um nome de arquivo.
    """
    def repl(match):
        raw_link = match.group(1)
        # `[[#Heading]]` referencia seção do próprio arquivo, não um arquivo: o
        # `:` ali é legítimo (o veto a `:` existe porque o Windows não aceita
        # dois-pontos em nome de arquivo). Trocar por travessão reescrevia o
        # título da seção e quebrava o link.
        if raw_link.startswith("#"):
            return match.group(0)
        if "|" in raw_link:
            target, display = raw_link.split("|", 1)
        else:
            target, display = raw_link, None

        if ": " in target:
            target = target.replace(": ", " — ")
        elif ":" in target:
            target = target.replace(":", " — ")

        if display:
            if ": " in display:
                display = display.replace(": ", " — ")
            elif ":" in display:
                display = display.replace(":", " — ")
            return f"[[{target.strip()}|{display.strip()}]]"
        return f"[[{target.strip()}]]"

    return re.sub(r"\[\[([^\]]+)\]\]", repl, segment)


def fix_double_spaces(segment):
    """Remove espaços duplos em linhas de prosa.

    Exceções:
    - Início de linha (indentação pode ser intencional).
    - Linhas de tabela Markdown (| ... |).
    - Linhas que parecem ser código inline.
    """
    lines = segment.split("\n")
    new_lines = []
    for line in lines:
        if line.startswith("|") or not line.strip():
            new_lines.append(line)
            continue
        # Preserva indentação inicial, reduz duplos espaços apenas no meio
        leading = len(line) - len(line.lstrip(" "))
        indent = line[:leading]
        rest = line[leading:]
        rest = re.sub(r"  +", " ", rest)
        new_lines.append(indent + rest)
    return "\n".join(new_lines)


def fix_excess_blank_lines(text):
    """Colapsa 3 ou mais linhas em branco consecutivas para 2."""
    return re.sub(r"\n{4,}", "\n\n\n", text)


def fix_ampersand_entity(segment):
    """`&amp;` residual (de import HTML/PDF) -> `&`. Nunca mexe em `&` que já
    está sozinho, só no entity codificado por engano."""
    return segment.replace("&amp;", "&")


def fix_hr_needs_blank_line(text):
    """Garante linha em branco depois de uma régua `---`.

    Sem ela, o Pandoc não lê `---` como régua: com `yaml_metadata_block` ligado
    (o caso do nosso export), `---` seguido de texto abre um bloco YAML, e o
    primeiro `:` da prosa aborta o export; com a extensão desligada, `---`
    seguido de texto vira cabeçalho de tabela e o capítulo inteiro é engolido
    dentro de um `<td>`, sem erro nenhum. Os dois modos de falha têm a mesma
    origem, e é aqui que ela se corrige.
    """
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        if (
            line.strip() == "---"
            and i > 0
            and i + 1 < len(lines)
            and lines[i + 1].strip() != ""
        ):
            out.append("")
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def _chave_rotulo(texto):
    """Chave de casamento entre item do Sumário e heading.

    Os dois lados divergem em detalhes que não mudam o texto renderizado: o
    Sumário costuma trazer ênfase que o heading não tem (`Vácuo *Eterno*` vs.
    `Vácuo Eterno`) e o heading costuma trazer link que o Sumário resolve para
    texto puro. Normalizar ambos evita deixar o anchor sem conserto.
    """
    t = re.sub(r"\[([^\]]*)\]\([^\)]*\)", lambda m: m.group(1), texto)
    t = t.replace("*", "").replace("_", "")
    # Pontuação de separação some: o mesmo título aparece como
    # "Introdução: O Xadrez" e "Introdução — O Xadrez" conforme quem
    # escreveu, e os dois devem casar com o mesmo heading.
    t = re.sub(r"[:—–-]+", " ", t)
    return re.sub(r"\s+", " ", t).strip().lower()


def fix_sumario_anchors(text):
    """Reescreve os anchors do `## Sumário` para o valor real do heading.

    O anchor é gerado pelo renderizador a partir do texto do heading (regra
    `gfm_auto_identifiers`), e escrevê-lo à mão erra em dois pontos recorrentes:
    o travessão, que some e deixa DOIS espaços (`Tradicional — Ernst` ->
    `tradicional--ernst`, não `-ernst`), e o link embutido, cuja URL não entra
    no anchor. O texto visível de cada item do Sumário é preservado; só o alvo
    do link muda.

    Casa item do Sumário com heading pela ordem em que aparecem, ignorando
    Sumário/Referências/Conexões, e só reescreve quando o alvo atual difere.
    """
    m = re.search(r"(?m)^## Sumário\s*$", text)
    if not m:
        return text
    rest = text[m.end():]
    nxt = re.search(r"(?m)^(---|## )", rest)
    bloco = rest[: nxt.start()] if nxt else rest
    inicio, fim = m.end(), m.end() + len(bloco)

    reais = [
        h.strip()
        for h in re.findall(r"(?m)^#{2,6} (.+)$", text)
        if h.strip() not in ("Sumário", "Referências", "Conexões")
    ]
    # Índices para achar o heading certo a partir do que o Sumário escreveu:
    # pelo slug antigo (forma `[texto](#slug)`) ou pelo texto do rótulo.
    por_slug = {heading_anchor(h): h for h in reais}
    por_texto = {}
    for h in reais:
        por_texto.setdefault(_chave_rotulo(h), h)

    def _monta(heading, rotulo):
        if rotulo.strip() == heading.strip():
            return "[[#%s]]" % heading
        return "[[#%s|%s]]" % (heading, rotulo)

    def troca(mm):
        rotulo, alvo = mm.group(1), mm.group(2)
        heading = por_slug.get(alvo) or por_texto.get(_chave_rotulo(rotulo))
        if heading is None:
            return mm.group(0)
        return _monta(heading, rotulo)

    # Migra a forma antiga `[texto](#slug)` para a forma nativa do Obsidian.
    novo_bloco = re.sub(r"\[([^\]]+)\]\(#([^\)]+)\)", troca, bloco)

    # E conserta a forma nova que aponte para um heading inexistente, quando o
    # rótulo ainda permite identificar de qual seção se tratava.
    def troca_wl(mm):
        alvo, display = mm.group(1).strip(), mm.group(2)
        if alvo in {h.strip() for h in reais}:
            return mm.group(0)
        # Tenta o ALVO antes do display: o display costuma ser uma versão
        # encurtada do título (sem o "Seção 1 —" da frente), e não casa.
        heading = por_texto.get(_chave_rotulo(alvo))
        if heading is None and display:
            heading = por_texto.get(_chave_rotulo(display))
        if heading is None:
            return mm.group(0)
        return _monta(heading, display or heading)

    novo_bloco = re.sub(r"\[\[#([^\]\|]+)(?:\|([^\]]+))?\]\]", troca_wl, novo_bloco)
    return text[:inicio] + novo_bloco + text[fim:]


def fix_ascii_double_quotes(segment):
    """Aspas retas (") viram tipográficas (“ ”) na prosa.

    Só aspas duplas. O apóstrofo reto (') fica como está: na wiki ele aparece
    exclusivamente dentro de título de obra em inglês (*The Emperor's New Mind*,
    *Bramwell's Helicopter Dynamics*), string bibliográfica que deve casar com a
    fonte, e como linha (prime) em LaTeX (`x'`, `\\theta''`).

    Trechos mascarados antes da troca: código inline, math `$...$`/`$$...$$`,
    alvo de link markdown, tag HTML. Math é o caso crítico — 21 dos 35 essays
    têm `$...$`, e trocar aspas ali quebra o LaTeX na exportação a PDF.
    """
    masked = []

    def mask(m):
        masked.append(m.group(0))
        return f"\x00{len(masked) - 1}\x00"

    protected = re.compile(
        r"\$\$.*?\$\$"          # math display
        r"|\$[^$\n]+\$"          # math inline
        r"|`[^`\n]*`"            # código inline
        r"|\]\([^)\n]*\)"        # alvo de link markdown
        r"|<[^>\n]+>",           # tag HTML
        re.DOTALL,
    )
    segment = protected.sub(mask, segment)

    # Abre se vier depois de início/espaço/abertura; senão fecha.
    def troca(m):
        anterior = m.string[m.start() - 1] if m.start() > 0 else ""
        abre = anterior == "" or anterior in " \t\n([{—–-*_>"
        return "“" if abre else "”"

    segment = re.sub(r'"', troca, segment)
    return re.sub(r"\x00(\d+)\x00", lambda m: masked[int(m.group(1))], segment)


# Legenda de figura (## Tratamento de imagens em conventions): toda figura
# leva `*Figura N. ...*` logo abaixo. Num mosaico, a legenda vem depois da
# ultima imagem do grupo. Isto so AVISA — escrever legenda e trabalho editorial,
# nao correcao mecanica.
FIGURA_IMG_RE = re.compile(r"^\s*!\[")
FIGURA_CAPTION_RE = re.compile(r"^\s*[*_]{0,2}(figura\b|fig\.|tira\b)", re.IGNORECASE)


def figuras_sem_legenda(body):
    """[(linha, alt)] de cada bloco de figura sem legenda logo abaixo."""
    linhas = body.split("\n")
    achados = []
    i = 0
    while i < len(linhas):
        if not FIGURA_IMG_RE.match(linhas[i]):
            i += 1
            continue
        inicio = i
        while i < len(linhas) and (FIGURA_IMG_RE.match(linhas[i]) or not linhas[i].strip()):
            i += 1
        seguinte = linhas[i] if i < len(linhas) else ""
        if not FIGURA_CAPTION_RE.match(seguinte):
            alt = re.match(r"^\s*!\[([^\]|]*)", linhas[inicio])
            achados.append((inicio + 1, (alt.group(1) if alt else "")[:60]))
    return achados


def fix_content(content):
    """Aplica todas as correções mecânicas ao conteúdo, na ordem.

    O frontmatter sai fora antes e volta intacto no fim; as correções de prosa
    passam por `apply_outside_fences`, então bloco de código nunca é reescrito.
    """
    frontmatter, body = split_frontmatter(content)
    body = apply_outside_fences(body, fix_hr_needs_blank_line)
    body = fix_sumario_anchors(body)
    body = apply_outside_fences(body, fix_blank_line_before_heading)
    body = apply_outside_fences(body, fix_heading_spacing)
    body = apply_outside_fences(body, fix_wikilinks_colons)
    body = apply_outside_fences(body, fix_double_spaces)
    body = apply_outside_fences(body, fix_ascii_double_quotes)
    body = apply_outside_fences(body, fix_ampersand_entity)
    body = fix_excess_blank_lines(body)
    return frontmatter + body


def build_title_to_slug():
    """Mapa H1 -> slug e conjunto de slugs, para migrar wikilink por título
    para a forma canônica `[[slug|Título]]` (Obsidian resolve só por slug)."""
    title_to_slug = {}
    all_slugs = set()
    for d in DIRS:
        if not d.exists():
            continue
        for f in d.glob("*.md"):
            all_slugs.add(f.stem)
            m = re.search(r"(?m)^# (.+)", load_file_content(f))
            if m:
                title_to_slug[m.group(1).strip()] = f.stem
    return title_to_slug, all_slugs


BARE_WIKILINK_RE = re.compile(r"\[\[([^\]\|#]+)(\|([^\]]+))?\]\]")


def fix_bare_title_wikilinks(body, title_to_slug, all_slugs):
    """`[[Título]]` ou `[[Título|Display]]` -> `[[slug|Display]]` quando o
    alvo não é já um slug mas casa com o H1 de uma página existente."""
    def repl(m):
        target = m.group(1).strip()
        display = m.group(3).strip() if m.group(3) else target
        if target in all_slugs:
            return m.group(0)
        slug = title_to_slug.get(target)
        if slug is None:
            return m.group(0)
        return f"[[{slug}|{display}]]"

    return BARE_WIKILINK_RE.sub(repl, body)


def resolve_essay(slug: str) -> Path:
    """Resolve um slug para o arquivo do essay, aceitando também um caminho direto."""
    p = Path(slug)
    if p.exists():
        return p.resolve()
    for ext in ("", ".md"):
        candidate = ESSAYS_DIR / (slug + ext)
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Essay '{slug}' não encontrado em {ESSAYS_DIR} nem como caminho direto")


def build_parser():
    p = argparse.ArgumentParser(
        description="Aplica correções mecânicas e inequívocas à formatação da wiki."
    )
    p.add_argument(
        "slug", nargs="?", default=None,
        help="Corrige apenas este essay (slug, nome do arquivo, ou caminho completo)."
    )
    p.add_argument(
        "--file", "-f", dest="file_slug", metavar="SLUG", default=None,
        help="Alias de compatibilidade para o slug posicional.",
    )
    p.add_argument(
        "--all", action="store_true",
        help="Corpus inteiro, explícito (comportamento padrão sem argumento).",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Não escreve nada — só lista os arquivos que seriam alterados e o que mudaria.",
    )
    return p


# Regex exclusivos da reescrita, vindos junto das funções que os usam.
BLOCKQUOTE_RE = re.compile(r"^>\s+(.+)$")
BOLD_NUMBERED_RE = re.compile(r"^\*\*\[(\d+)\]\*\*\s+(.+)$")
CANONICAL_LINK_RE = re.compile(r"\[[Ll]ink\]\((?P<url>" + URL_PAT + r")\)")
ITALIC_WRAPPED_LINK_RE = re.compile(r"\*\[(?P<title>[^\]]+)\]\((?P<url>" + URL_PAT + r")\)\*")
LINKED_TITLE_RE = re.compile(r"\[(?P<title>\*[^*\n]+\*)\]\((?P<url>" + URL_PAT + r")\)")
QUOTE_CHARS = "\"'“”‘’"
# Título entre aspas retas ou tipográficas *duplas* — nunca aspas simples: uma
# aspa simples span captura contrações/genitivos ("d'Alembert's") como se
# fossem um título inteiro, risco que dobrar em "duplas apenas" evita.


# ---------------------------------------------------------------------------
# Migração de `## Referências` para o padrão AIAA
#
# Veio de check_references.py junto com o antigo `--fix-format`: aquele script
# valida, este corrige, e a fronteira entre os dois é a permissão de escrever.
# ---------------------------------------------------------------------------

LINK_ANCHOR = "Link"


def canonicalize_entry_lines(section):
    """Normaliza variantes de escrita para o formato `[N] ...`, uma por linha.

    O corpus acumulou quatro estilos de bibliografia. Dois deles são
    deterministicamente conversíveis e entram aqui:

    - `**[1]** Citação.` seguida da nota num parágrafo próprio: o negrito sai e
      a nota volta para a mesma linha, depois de ` — `.
    - `> Citação` em blockquote, uma por linha e sem numeração: vira `[N]` na
      ordem em que já estava.

    O que sobra (link envolvendo só o título, ou entrada sem título em itálico)
    depende de saber qual pedaço do texto é o título da obra, e isso não é
    decidível sem ler a fonte — fica para `/linkify`.
    """
    out = []
    pending_bold = None      # entrada `**[N]**` esperando a nota do parágrafo seguinte
    blockquote_number = 0

    for raw in section.splitlines():
        line = raw.strip()

        if not line or line == "---":
            continue

        m = BOLD_NUMBERED_RE.match(line)
        if m:
            if pending_bold:
                out.append(pending_bold)
            pending_bold = f"[{m.group(1)}] {m.group(2)}"
            continue

        m = BLOCKQUOTE_RE.match(line)
        if m:
            blockquote_number += 1
            out.append(f"[{blockquote_number}] {m.group(1)}")
            continue

        if pending_bold:
            # Parágrafo solto logo após uma entrada `**[N]**` é a nota dela.
            out.append(f"{pending_bold} — {line}")
            pending_bold = None
            continue

        out.append(line)

    if pending_bold:
        out.append(pending_bold)

    return "\n".join(out)


def convert_underscore_italics(text):
    """`_Título_` -> `*Título*`. Não mexe em `nome_var`/`x_1` (ver UNDERSCORE_ITALIC_RE)."""
    return UNDERSCORE_ITALIC_RE.sub(lambda m: f"*{m.group(1)}*", text)


def normalize_italics(text):
    """`*"Título."*` -> `*Título*`. Só mexe no que já está em itálico.

    Nunca toca em `**negrito**` (ver `ITALIC_RE`) e nunca consome espaço fora
    dos delimitadores: o texto entre um itálico e o próximo é copiado intacto.
    """
    out = []
    pos = 0
    for m in ITALIC_RE.finditer(text):
        inner = m.group(1).strip().strip(QUOTE_CHARS).strip()
        if not inner:
            continue
        had_terminal_period = inner.endswith(".")
        out.append(text[pos : m.start()])
        out.append(f"*{inner.rstrip('.').strip()}*")
        pos = m.end()
        # No formato antigo o ponto que separava título e container morava
        # dentro do itálico. Tirá-lo sem repor nada deixaria
        # "*Título* Oxford University Press" sem separador algum, então a
        # vírgula do padrão AIAA entra no lugar — mas só quando o que vem a
        # seguir é mesmo um container, e não pontuação que já separa.
        if had_terminal_period and re.match(r"\s+[^\s,.;:—)\]]", text[pos:]):
            out.append(",")
    out.append(text[pos:])
    return "".join(out)


def mover_link_para_o_fim(entrada):
    """Desmarca todo link do texto e devolve a URL da obra como `[Link]` no fim.

    Cobre todos os arranjos que o corpus acumulou — link envolvendo a citação
    inteira, envolvendo o título (`[*T*](u)` ou `*[T](u)*`), pendurado no
    container (`*Título*, [Physical Review Letters](u), 59(22)`) ou já num
    âncora `[link]` no meio da linha. Em todos, o texto do link permanece como
    texto e a URL vai para o fim.

    A URL nunca é inventada: entrada sem link nenhum sai sem link, e é o
    `REFERENCIA_SEM_LINK` que reporta isso.
    """
    url = None

    # O âncora explícito, quando existe, é a URL da obra — tem prioridade
    # sobre um link de glossário que apareça antes dele na mesma entrada.
    m = CANONICAL_LINK_RE.search(entrada)
    if m:
        url = m.group("url")
        entrada = CANONICAL_LINK_RE.sub("", entrada)

    # `*[Título](url)*` -> `*Título*`; `[*Título*](url)` -> `*Título*`.
    # O itálico tem que sobreviver ao desembrulho: é ele que marca o título.
    def desembrulhar(regex, texto, formatar):
        nonlocal url
        mm = regex.search(texto)
        if not mm:
            return texto
        if url is None:
            url = mm.group("url")
        return texto[: mm.start()] + formatar(mm.group("title")) + texto[mm.end() :]

    entrada = desembrulhar(ITALIC_WRAPPED_LINK_RE, entrada, lambda t: f"*{t}*")
    entrada = desembrulhar(LINKED_TITLE_RE, entrada, lambda t: t)

    # Qualquer link restante vira texto puro; o primeiro deles serve de URL da
    # obra se nenhum candidato melhor apareceu antes.
    def sem_marcacao(mm):
        nonlocal url
        if url is None:
            url = mm.group("url")
        return mm.group("text")

    entrada = ANY_MD_LINK_RE.sub(sem_marcacao, entrada)

    entrada = re.sub(r"\s{2,}", " ", entrada).strip()
    entrada = re.sub(r"\s+([,.;:])", r"\1", entrada)
    # Título que já termina em `?` ou `!` não leva ponto depois do itálico:
    # `*Is Our Universe Likely to Decay?*. 2006.` vira `*...?* 2006.`
    entrada = re.sub(r"([?!]\*)\.", r"\1", entrada)
    return entrada, url


def montar_entrada(numero, resto_da_linha):
    """`[N] Citação. — Nota. [Link](url)` — o link sempre por último.

    Só a **citação** é varrida atrás da URL da obra. Links que estejam na nota
    são de glossário (um verbete para um termo comentado ali) e continuam onde
    estão: promovê-los faria a bibliografia apontar para o lugar errado.
    """
    # O `[Link]` do fim sai primeiro, senão a divisão citação/nota o jogaria
    # dentro da nota e a função não seria idempotente.
    cauda = TAIL_LINK_RE.search(resto_da_linha)
    url_da_cauda = cauda.group("url") if cauda else None
    resto_da_linha = TAIL_LINK_RE.sub("", resto_da_linha).rstrip()

    citacao, nota = citation_and_note(resto_da_linha)
    # Ordem importa: aspas -> itálico antes de underscore -> asterisco, porque
    # try_fix_quoted_title recusa mexer se já houver _underscore_ (evita duplo
    # match improvável tipo `_"X"_`); e ambos rodam ANTES de normalize_italics,
    # que só entende `*...*`. Nunca toca em `nota` — só a citação em si.
    citacao_com_titulo = try_fix_quoted_title(citacao)
    if citacao_com_titulo is not None:
        citacao = citacao_com_titulo
    citacao = convert_underscore_italics(citacao)
    citacao, url = mover_link_para_o_fim(normalize_italics(citacao))
    url = url_da_cauda or url

    linha = f"{numero} {citacao}"
    if nota:
        linha += f" — {nota}"
    if url:
        # A palavra "Link" vem depois do ponto final, separada da prosa.
        linha = linha.rstrip()
        if not linha.endswith((".", "!", "?")):
            linha += "."
        linha = f"{linha} [{LINK_ANCHOR}]({url})"
    return linha


def rebuild_section(section):
    """Reescreve a seção no padrão AIAA. Retorna (novo_texto, n_entradas)."""
    section = canonicalize_entry_lines(section)
    entries = [e for e in parse_entries(section) if e["kind"] in ("numbered", "bullet")]
    if not entries:
        return None, 0

    lines = []
    for number, entry in enumerate(entries, start=1):
        rest = entry["rest"]
        # Entrada que é bullet E numerada (`- [1] Autor...`) chega aqui com o
        # `[1]` ainda dentro de `rest`, e a renumeração prefixaria um segundo
        # número, produzindo `[1] [1] Autor...`. O número velho é descartado:
        # quem manda é a posição na lista, calculada por `enumerate`.
        rest = re.sub(r"^\[\d+\]\s*", "", rest)
        lines.append(montar_entrada(f"[{number}]", rest))

    return "\n\n" + "\n\n".join(lines) + "\n\n", len(entries)


def fix_essay(path, dry_run=False):
    """Aplica a migração mecânica. Retorna n_entradas reescritas, 0 se nada mudou.

    Com dry_run=True, calcula a mudança mas não escreve — só para reporte.
    """
    content = load(path)
    m = re.search(r"(?m)^## Referências[ \t]*$", content)
    if not m:
        return 0

    rest = content[m.end():]
    next_h2 = re.search(r"(?m)^## ", rest)
    end = m.end() + (next_h2.start() if next_h2 else len(rest))
    section = content[m.end():end]

    new_section, count = rebuild_section(section)
    if new_section is None or new_section == section:
        return 0

    if not dry_run:
        path.write_text(content[: m.end()] + new_section + content[end:], encoding="utf-8")
    return count


def main():
    args = build_parser().parse_args()
    target_slug = args.file_slug or args.slug
    scope_all = args.all or not target_slug

    if scope_all:
        essay_targets = sorted(ESSAYS_DIR.glob("*.md"))
        support_dirs = [CONCEPTS_DIR, ENTITIES_DIR, INSIGHTS_DIR]
    else:
        try:
            essay_targets = [resolve_essay(target_slug)]
        except FileNotFoundError as e:
            print(f"ERRO: {e}", file=sys.stderr)
            sys.exit(1)
        support_dirs = []
        print(f"Escopo: apenas {essay_targets[0].name} — checagens de corpus "
              f"(concepts/entities/insights) puladas, mesmo padrão de check_wiki.py.")

    fixed_files_count = 0
    referencias_fixed_count = 0
    sem_legenda_count = 0
    title_to_slug, all_slugs = build_title_to_slug()

    all_targets = [("essays", f) for f in essay_targets]
    for d in support_dirs:
        if not d.exists():
            continue
        all_targets += [(d.name, f) for f in sorted(d.glob("*.md"))]

    for category, file in all_targets:
        if file.name in ("log.md", "index.md", "manifest.md", "map.md"):
            continue

        content = load_file_content(file)
        new_content = fix_content(content)
        frontmatter, body = split_frontmatter(new_content)
        body = apply_outside_fences(body, lambda seg: fix_bare_title_wikilinks(seg, title_to_slug, all_slugs))
        new_content = frontmatter + body

        if new_content != content:
            if not args.dry_run:
                save_file_content(file, new_content)
            verb = "Would fix" if args.dry_run else "Fixed"
            print(f"{verb} formatting and/or links in: {file.relative_to(DATA_ROOT)}")
            fixed_files_count += 1

        for linha, alt in figuras_sem_legenda(split_frontmatter(new_content)[1]):
            print(f"AVISO figura sem legenda: {file.relative_to(DATA_ROOT)}:{linha}"
                  f" — acrescente `*Figura N. ...*` abaixo da imagem"
                  + (f" (alt: {alt})" if alt else ""))
            sem_legenda_count += 1

        # A migração de `## Referências` para o padrão AIAA só se aplica a
        # essays — concepts/entities/insights não têm essa seção.
        if category == "essays":
            n_entries = fix_essay(file, dry_run=args.dry_run)
            if n_entries:
                referencias_fixed_count += 1
                verb = "would be rewritten" if args.dry_run else "reescritas"
                print(f"Referências {verb} (padrão AIAA): {file.relative_to(DATA_ROOT)} "
                      f"({n_entries} entrada(s))")

    if sem_legenda_count:
        print(f"\n{sem_legenda_count} figura(s) sem legenda. Legenda e decisao "
              f"editorial: o fixer avisa, não escreve.")
    action = "Dry-run completo — nada foi escrito." if args.dry_run else "Completed auto-fix."
    print(f"\n{action} {fixed_files_count} file(s) {'seriam' if args.dry_run else 'foram'} "
          f"modificado(s); {referencias_fixed_count} essay(s) "
          f"{'teriam' if args.dry_run else 'tiveram'} '## Referências' reescrita.")
    if referencias_fixed_count and not args.dry_run:
        print("Rode `python scripts/build_references.py` para regenerar o índice de referências.")
        print(
            "A migração de referências é só mecânica: entradas que continuarem sem link da "
            "própria obra saem sinalizadas como REFERENCIA_SEM_LINK e precisam de /linkify."
        )

    if not args.dry_run:
        try:
            from sync_skills import sync
            sync()
        except Exception as exc:
            print(f"Aviso: sync_skills falhou: {exc}")


if __name__ == "__main__":
    main()
