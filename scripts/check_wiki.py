#!/usr/bin/env python3
"""
check_wiki.py - Lint unificado da wiki, em dois níveis:

- Por essay: issues {severity, code, message} (CRITICAL|ERROR|WARNING|INFO)
  cobrindo frontmatter obrigatório, H1+byline, Sumário/Referências/Conexões,
  tipografia, travessões (máx. 2), bullets residuais, HTML/símbolos
  residuais, idioma, wikilinks mortos e fora de Conexões.
- De corpus: órfãos, wiki/index.md, manifesto de sources, estrutura de
  wiki/sources/**, plan/plano.md, insights — pulados com aviso quando o
  escopo é um essay único.

Somente-leitura: a correção mecânica é do fix_lint.py. Regra completa de
cada checagem em conventions/SKILL.md.

Lê:
    wiki/{essays,concepts,entities,insights}/*.md, wiki/sources/manifest.md,
    wiki/index.md, plan/plano.md

Gera:
    stdout (relatório) + output/comprehensive_lint_output.txt no escopo corpus;
    --json para parse programático. Com --strict, CRITICAL/ERROR retornam 1.

Uso:
    python scripts/check_wiki.py                       # corpus inteiro (default)
    python scripts/check_wiki.py --all                 # idem, explícito
    python scripts/check_wiki.py xadrez-computacional  # essay único (posicional)
    python scripts/check_wiki.py --file <slug>         # alias de compatibilidade
    python scripts/check_wiki.py --json                # saída JSON

Flags:
    slug        essay alvo (posicional, opcional)
    --file/-f   caminho do essay (alternativa ao slug)
    --all       força corpus inteiro
    --json      saída JSON para parse programático
    --strict    bloqueia CI em CRITICAL/ERROR
"""

import argparse
import json
import re
import subprocess
import sys
from math import ceil
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import console_encoding  # noqa: F401  (UTF-8 no console; ver o módulo)
import yaml

# ---------------------------------------------------------------------------
# Configuração de caminhos
# ---------------------------------------------------------------------------
from repo_paths import CODE_ROOT, DATA_ROOT, OUTPUT_DIR, PLAN_DIR, WIKI_ROOT

ROOT_DIR = CODE_ROOT
ESSAYS_DIR = WIKI_ROOT / "essays"
CONCEPTS_DIR = WIKI_ROOT / "concepts"
ENTITIES_DIR = WIKI_ROOT / "entities"
SOURCES_DIR = WIKI_ROOT / "sources"
INSIGHTS_DIR = WIKI_ROOT / "insights"
HANDOUTS_DIR = WIKI_ROOT / "handouts"

CALLOUT_TYPES = {
    "note", "info", "example", "abstract", "todo", "warning", "success",
    "question", "failure", "danger", "bug", "quote",
}
CALLOUT_ALIASES = {"tldr", "summary", "hint", "important", "caution", "cite"}
CALLOUT_HEADER_RE = re.compile(
    r"^(?:>\s*)+\[!([A-Za-z0-9_-]+)\](?:[+-])?(?:\s+(.*))?$"
)
CALLOUT_HEADING_RE = re.compile(r"^(?:>\s*)+#{2,3}\s+")
FIGURE_RE = re.compile(r"!\[[^\]]*\]\(([^\s\)]+)(?:\s+[^\)]*)?\)")


def normalize_url(url: str) -> str:
    """Normalize URLs only enough to detect duplicate bibliography entries."""
    parsed = urlsplit(url.rstrip(".,;"))
    query = "&".join(
        part for part in parsed.query.split("&")
        if part and not part.lower().startswith(("utm_", "fbclid="))
    )
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), query, ""))


def check_callout_contracts(body: str, add) -> None:
    """Validate native Obsidian callout syntax without rewriting source text."""
    active_h2 = "(antes do primeiro H2)"
    abstract_counts: dict[str, int] = {}
    callout_count = 0
    for lineno, line in enumerate(strip_fences(body).splitlines(), start=1):
        h2 = re.match(r"^##\s+(.+)$", line)
        if h2:
            active_h2 = h2.group(1).strip()
        if CALLOUT_HEADING_RE.match(line):
            add("ERROR", "CALLOUT_HEADING_LEVEL",
                f"linha {lineno}: ##/### dentro de callout quebra o Sumário; use ####")
        match = CALLOUT_HEADER_RE.match(line)
        if not match:
            continue
        callout_count += 1
        kind, title = match.group(1).casefold(), (match.group(2) or "").strip()
        if kind in CALLOUT_ALIASES:
            add("ERROR", "CALLOUT_ALIAS", f"linha {lineno}: alias [!{kind}] proibido")
        elif kind not in CALLOUT_TYPES:
            add("ERROR", "CALLOUT_TYPE", f"linha {lineno}: tipo [!{kind}] não permitido")
        if kind == "warning" and not re.search(r"\d", title):
            add("ERROR", "CALLOUT_WARNING_TITLE",
                f"linha {lineno}: [!warning] exige número-chave no título")
        if kind == "todo" and not title:
            add("ERROR", "CALLOUT_TODO_TITLE",
                f"linha {lineno}: [!todo] exige o nome da entidade no título")
        if kind == "abstract":
            abstract_counts[active_h2] = abstract_counts.get(active_h2, 0) + 1
        if kind == "note" and re.search(r"\b(mapa conceitual|definição formal|framework)\b", title, re.I):
            add("WARNING", "CALLOUT_NOTE_SHOULD_ABSTRACT",
                f"linha {lineno}: título '{title}' sugere [!abstract], não [!note]")
    limit = max(6, ceil(len(re.findall(r"\b\w+\b", body)) / 1000 * 6))
    if callout_count > limit:
        add("WARNING", "CALLOUT_DENSITY",
            f"{callout_count} callouts para o tamanho do essay (máximo recomendado: {limit})")
    for section, count in abstract_counts.items():
        if count > 1:
            add("WARNING", "CALLOUT_ABSTRACT_PER_SECTION",
                f"seção '{section}' tem {count} callouts [!abstract] (máximo recomendado: 1)")


def check_figure_contracts(body: str, slug: str, add) -> None:
    """Check figure filename, ordering and adjacent Markdown captions."""
    lines = strip_fences(body).splitlines()
    numbers: list[int] = []
    name_re = re.compile(rf"^{re.escape(slug)}_fig(\d+)\.[A-Za-z0-9]+$")
    for index, line in enumerate(lines):
        match = FIGURE_RE.search(line)
        if not match:
            continue
        target = match.group(1).strip("<>")
        if target.startswith(("http://", "https://", "data:")):
            continue
        filename = Path(target).name
        name_match = name_re.fullmatch(filename)
        if not name_match:
            add("WARNING", "FIGURE_FILENAME",
                f"linha {index + 1}: figura deve se chamar {slug}_figN.ext, recebeu {filename}")
            continue
        number = int(name_match.group(1))
        numbers.append(number)
        caption_index = index + 1
        while caption_index < len(lines) and not lines[caption_index].strip():
            caption_index += 1
        caption = lines[caption_index].strip() if caption_index < len(lines) else ""
        caption_match = re.fullmatch(r"\*Figura\s+(\d+)\..+\*", caption)
        if not caption_match:
            add("WARNING", "FIGURE_CAPTION_MISSING",
                f"linha {index + 1}: figura {number} sem legenda '*Figura {number}. ...*'")
        elif int(caption_match.group(1)) != number:
            add("WARNING", "FIGURE_CAPTION_NUMBER",
                f"linha {index + 1}: arquivo fig{number} diverge da legenda Figura {caption_match.group(1)}")
    if numbers and sorted(numbers) != list(range(1, len(numbers) + 1)):
        add("WARNING", "FIGURE_SEQUENCE",
            f"numeração de figuras não sequencial: {sorted(numbers)}")


def check_prose_signals(body: str, add) -> None:
    """Surface editorial signals conservatively; never change prose automatically."""
    prose = strip_fences(body).split("## Referências", 1)[0]
    patterns = (
        ("WARNING", "METADISCOURSE", r"\b(nesta seção|neste ensaio|veremos|examinaremos|percorreremos|a seguir)\b"),
        ("WARNING", "VAGUE_AUTHORITY", r"\b(estudos mostram|especialistas afirmam|a literatura indica)\b"),
        ("WARNING", "ANTHROPOMORPHIZATION", r"\b(modelo|llm|equação|teoria)\s+(sabe|quer|tenta|entende|acredita|percebe)\b"),
        ("INFO", "PROMOTIONAL_LANGUAGE", r"\b(revolucionário|extraordinário|fundamental|crucial|impressionante|dramático)\b"),
        ("INFO", "VAGUE_UNCERTAINTY", r"\b(possivelmente|potencialmente|de certa forma|em grande medida|pode-se dizer)\b"),
    )
    for severity, code, pattern in patterns:
        found = re.findall(pattern, prose, re.I)
        if found:
            add(severity, code, f"{len(found)} ocorrência(s) de sinal editorial: {found[:3]}")


def check_reference_contracts(entries: list[str], add) -> None:
    """Validate bibliography details not covered by the citation-link checker."""
    numbers = [int(match.group(1)) for entry in entries if (match := re.match(r"^\[(\d+)\]", entry))]
    if numbers and numbers != list(range(1, len(numbers) + 1)):
        add("WARNING", "REF_SEQUENCE", f"numeração de referências não sequencial: {numbers}")
    seen: dict[str, int] = {}
    for entry in entries:
        number = re.match(r"^\[(\d+)\]", entry)
        label = number.group(1) if number else "?"
        if not re.search(r"\*[^*]+\*", entry):
            add("WARNING", "REF_TITLE_NOT_ITALIC", f"entrada [{label}] sem título em itálico")
        links = re.findall(r"\[Link\]\((https?://[^)]+)\)", entry)
        link = links[-1] if links else None
        if link and not re.search(r"\[Link\]\(https?://[^)]+\)\s*$", entry):
            add("WARNING", "REF_LINK_NOT_FINAL", f"entrada [{label}] não termina no [Link](url)")
        local_urls: set[str] = set()
        for raw_url in re.findall(r"https?://[^\s)]+", entry):
            normalized = normalize_url(raw_url)
            if normalized in local_urls:
                continue
            local_urls.add(normalized)
            if normalized in seen:
                add("WARNING", "REF_DUPLICATE_URL",
                    f"entrada [{label}] repete URL normalizada da entrada [{seen[normalized]}]")
            else:
                seen[normalized] = int(label) if label.isdigit() else 0
            if any(token in normalized for token in ("wikipedia.org", "/readme", "github.com")) and "acesso em" not in entry.casefold():
                add("WARNING", "REF_MUTABLE_NO_ACCESS_DATE",
                    f"entrada [{label}] usa fonte mutável sem data de acesso")


def classify_updated_diff(diff: str) -> str | None:
    """Classify a Git patch without guessing whether a small edit is substantive."""
    body_changes = 0
    updated_changed = False
    in_frontmatter = False
    for line in diff.splitlines():
        if line.startswith(("+++", "---", "@@")):
            continue
        if not line.startswith(("+", "-")):
            continue
        text = line[1:]
        if text.strip() == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            updated_changed = updated_changed or text.startswith("updated:")
        elif text.strip():
            body_changes += 1
    if body_changes >= 12 and not updated_changed:
        return "BODY_CHANGED_UPDATED_UNCHANGED"
    if body_changes == 0 and updated_changed:
        return "UPDATED_CHANGED_WITHOUT_BODY"
    return None


def check_updated_against_git(filepath: Path, add) -> None:
    """Warn only for clear metadata/body mismatches in the latest data revision."""
    try:
        relative = filepath.resolve().relative_to(DATA_ROOT.resolve()).as_posix()
        proc = subprocess.run(
            ["git", "-C", str(DATA_ROOT), "diff", "--unified=0", "HEAD^", "HEAD", "--", relative],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
    except (OSError, ValueError):
        return
    if proc.returncode:
        return
    state = classify_updated_diff(proc.stdout)
    if state == "BODY_CHANGED_UPDATED_UNCHANGED":
        add("WARNING", "UPDATED_STALE_AFTER_BODY_CHANGE",
            "a revisão Git mais recente mudou substancialmente o corpo sem alterar updated:")
    elif state == "UPDATED_CHANGED_WITHOUT_BODY":
        add("WARNING", "UPDATED_WITHOUT_BODY_CHANGE",
            "a revisão Git mais recente alterou updated: sem mudança no corpo")

# categorias/pastas incluídas no lint (sources fica de fora: documentos
# originais imutáveis, nunca editados por nenhuma skill)
DIRS = {
    "essays": ESSAYS_DIR,
    "concepts": CONCEPTS_DIR,
    "entities": ENTITIES_DIR,
    "insights": INSIGHTS_DIR,
}

# ---------------------------------------------------------------------------
# Vocabulário controlado
# ---------------------------------------------------------------------------

VALID_TYPES = {"Ensaio", "White Paper", "Brainstorm", "Estudo", "Análise"}
# `revisao` substituiu `maduro`. A migração do corpus está feita, e a grafia
# antiga saiu do vocabulário: manter duas palavras para o mesmo estado só
# garante que metade dos scripts vá esquecer uma delas.
VALID_STATUS = {"draft", "revisao", "finalizado"}
MATURIDADES_VALIDAS = ("solta", "germinando", "madura", "absorvida")
PLAN_SECOES = ["Tarefas", "Fontes para Ingerir", "Revisões", "Estudos", "Essays Futuros"]

SOURCE_TYPE_TO_FOLDER = {
    "Ensaio Completo Importado": "ensaio-importado",
    "Web Clipping": "web-clipping",
    "Artigo Acadêmico": "artigo-academico",
    "Livro": "livro",
    "Documentação Técnica": "documentacao-tecnica",
    "Transcrição": "transcricao",
    "Ideias": "ideias",
    "Outro": "outro",
}
# Valores que registram "examinei e não virou essay": grafias aceitas para
# `Virou:` numa fonte do tipo Ensaio Completo Importado.
MANIFEST_VIROU_NONE = {"none", "nenhum", "nenhuma", "-", "—"}

UTILITY_SOURCE_FOLDERS = {"resumos"}

# `summary:` é o resumo de uma linha usado por build_index.py. O corpus
# consolidou um padrão descritivo de arco argumentativo: mediana ~375
# caracteres, máximo observado 462 (distribuição dos essays antigos).
# Acima do teto vira parágrafo e quebra o layout de wiki/index.md;
# abaixo do piso não descreve o arco do essay.
SUMMARY_MAX_CHARS = 530
SUMMARY_MIN_CHARS = 200

# Heurística de idioma: palavras funcionais que só existem em inglês vs. em
# português. Não é um detector de idioma robusto, é um sinal barato para
# pegar parágrafos/páginas esquecidos em inglês (comum ao colar de uma fonte
# em raw/ sem terminar a tradução).
ENGLISH_ONLY_WORDS = {
    "the", "and", "with", "this", "that", "these", "those", "from", "have",
    "has", "been", "were", "was", "which", "their", "there", "where", "when",
    "because", "however", "therefore", "although", "between", "through",
    "into", "onto", "about", "should", "would", "could", "cannot",
    "doesn't", "isn't", "aren't", "wasn't", "weren't", "don't", "does",
    "did", "than",
}
PORTUGUESE_ONLY_WORDS = {
    "não", "com", "para", "uma", "isso", "está", "então", "porque", "entre",
    "sobre", "quando", "onde", "porém", "contudo", "embora", "através",
    "seus", "suas", "já", "também", "mais", "menos", "muito",
}

# ---------------------------------------------------------------------------
# Helpers compartilhados (única implementação — antes duplicada entre os dois
# scripts de lint que este arquivo unifica)
# ---------------------------------------------------------------------------

FENCE_RE = re.compile(r"^```")


def load(path: Path) -> str:
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def split_frontmatter(content: str):
    """Retorna (fm_text, body_text). fm_text é '' se não houver frontmatter."""
    if content.startswith("---\n"):
        end = content.find("\n---", 4)
        if end != -1:
            eob = content.find("\n", end + 1)
            eob = eob + 1 if eob != -1 else len(content)
            return content[:eob], content[eob:]
    return "", content


def strip_fences(text: str) -> str:
    """Esvazia o interior de blocos ```...```, preservando a contagem de
    linhas (delimitadores viram linha em branco).

    As regras de prosa (heading, label de capítulo, símbolo residual, HTML,
    wikilink) não valem dentro de código: um comentário Python `# nota` na
    coluna zero não é heading, e `np.array([[1.0]])` não é wikilink.
    """
    lines, out, in_fence = text.splitlines(), [], False
    for line in lines:
        if FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            out.append("")
        else:
            out.append("" if in_fence else line)
    return "\n".join(out)


def get_h1(content: str):
    m = re.search(r"(?m)^# (.+)$", content)
    return m.group(1).strip() if m else None


MD_LINK_IN_HEADING_RE = re.compile(r"\[([^\]]*)\]\([^\)]*\)")


def heading_anchor(heading_text: str) -> str:
    r"""Converte texto de heading no anchor que Pandoc/GitHub/Obsidian geram.

    Replica `gfm_auto_identifiers`, a regra usada pelo Obsidian e pelos dois
    exportadores (que passam `+gfm_auto_identifiers` ao Pandoc justamente para
    casar com o Sumário). Os quatro pontos que já causaram anchor quebrado:

    1. o anchor vem do texto RENDERIZADO: link vira o texto-âncora, e marcador
       de ênfase (`*`, `_`) desaparece — `(_Pitch-Flap_)` vira `pitch-flap`;
    2. dentro de math, porém, `_` é subscrito e SOBREVIVE: `$K_{att}$` vira
       `k_att` e `$\delta_3$` vira `delta_3`. Só `$`, `\`, `{` e `}` saem;
    3. tudo que não for letra/número/espaço/hífen/underscore é removido;
    4. **cada** espaço vira um hífen, sem colapsar runs — `Tradicional — Ernst`
       perde o travessão e deixa dois espaços, gerando `tradicional--ernst`.
    """
    s = MD_LINK_IN_HEADING_RE.sub(lambda m: m.group(1), heading_text)
    s = re.sub(r"\$([^$]*)\$", lambda m: re.sub(r"[^\w\s]", "", m.group(1)), s)
    s = s.lower()
    s = s.replace("*", "")
    s = re.sub(r"(?<!\w)_+|_+(?!\w)", "", s)
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s", "-", s.strip())
    return s


def anchor_key(anchor: str) -> str:
    """Forma canônica para comparar anchor de Sumário com heading real.

    Duas convenções convivem no corpus, ambas navegáveis, e a diferença entre
    elas não é defeito:

    - `## Ideia 1 — IA` perde o travessão na renderização e deixa dois
      espaços, que o GitHub mapeia a dois hífens (`ideia-1--ia`) e o Obsidian
      a um só (`ideia-1-ia`).
    - `_` aparece tanto como ênfase Markdown (`_Teetering_`, que não sobrevive
      à renderização) quanto como subscrito LaTeX (`$I_{xz}$`, que o Sumário
      escreve `i_xz`). Distinguir os dois casos exigiria parsear math;
      igualar os dois lados resolve sem ambiguidade.
    """
    return anchor


def detect_english_paragraphs(content: str, exclude_referencias: bool = True):
    """Parágrafos possivelmente em inglês (não traduzidos).

    Exceções (não são bug, são conteúdo esperado no idioma original):
    - `## Referências`: título de obra estrangeira fica no original, não é
      "parágrafo esquecido de traduzir".
    - Bloco de citação inteiro em blockquote (`> "quote" — Autor`): epígrafe
      ou citação direta, prática acadêmica padrão.

    Retorna lista de snippets (str) — quem chama decide severidade/code.
    """
    body = re.sub(r"^---.*?---\n", "", content, count=1, flags=re.DOTALL)
    if exclude_referencias:
        body = re.split(r"(?m)^## Referências\s*$", body)[0]
    body = re.sub(r"```.*?```", "", body, flags=re.DOTALL)
    body = re.sub(r"\[([^\]]*)\]\([^\)]*\)", r"\1", body)
    # Título de obra fica no idioma original por convenção bibliográfica, então
    # não conta como prosa a traduzir: `Em *Why Is There Something Rather Than
    # Nothing?*, Carroll argumenta...` é uma frase em português. Sem isto, uma
    # única citação de livro inglês numa frase portuguesa dispara o alerta.
    body = re.sub(r"\*\*?([^*\n]+)\*\*?", " ", body)
    body = re.sub(r"(?<!\w)_([^_\n]+)_(?!\w)", " ", body)

    hits = []
    for para in body.split("\n\n"):
        quote_lines = [ln for ln in para.splitlines() if ln.strip()]
        if quote_lines and all(ln.strip().startswith(">") for ln in quote_lines):
            continue
        words = re.findall(r"[A-Za-zÀ-ÿ']+", para.lower())
        if len(words) < 12:
            continue
        en_hits = sum(1 for w in words if w in ENGLISH_ONLY_WORDS)
        pt_hits = sum(1 for w in words if w in PORTUGUESE_ONLY_WORDS)
        if en_hits >= 3 and en_hits > pt_hits * 2:
            hits.append(para.strip().replace("\n", " ")[:100])
    return hits


# Símbolo residual de import HTML/PDF mal decodificado. Deliberadamente NÃO
# inclui "&" sozinho: "Horwitz & Horwitz" é nome próprio legítimo, e um "&"
# solto não indica entidade HTML corrompida — só a entidade codificada
# (`&amp;`, `&nbsp;`) ou caractere de substituição indicam.
RESIDUAL_SYMS = [
    ("◆", "diamond ◆"),
    ("�", "replacement char �"),
    (" ", "non-breaking space (NBSP)"),
    ("&nbsp;", "&nbsp;"),
    ("&amp;", "&amp;"),
    ("&lt;", "&lt;"),
    ("&gt;", "&gt;"),
    ("&quot;", "&quot;"),
    ("&#39;", "&#39;"),
]


def detect_residual_symbols(lines_clean):
    """Retorna [(desc, [linenos])] para cada símbolo residual encontrado."""
    found = []
    for sym, desc in RESIDUAL_SYMS:
        occurrences = [i + 1 for i, ln in enumerate(lines_clean) if sym in ln]
        if occurrences:
            found.append((desc, occurrences))
    return found


HTML_TAG_RE = re.compile(
    r"</?(?:div|span|p|br|hr|img|a|h[1-6]|ul|ol|li|table|tr|td|th|"
    r"thead|tbody|iframe|button|input|label|form|select|option)"
    r"(?:\s|/|>)[^>]*>|class=|style=",
    re.IGNORECASE,
)

# Remissão a outro essay no corpo: "no ensaio *Título*", "o essay *Título*".
# Essay é documento autocontido (ver `## Regra de links` em conventions/SKILL.md):
# a relação entre páginas vive em `## Conexões`, não na prosa.
CROSS_ESSAY_RE = re.compile(
    r"(?i)\b(?:essays?|ensaios?|white\s?papers?)\s+\*([^*\n]{4,120})\*"
    r"|\bno\s+ensaio\s+(?:sobre|irmão)\b"
    r"|\boutro\s+ensaio\b"
    r"|\bno\s+ensaio\s+[“\"]"
)


# ---------------------------------------------------------------------------
# Checagem por essay
# ---------------------------------------------------------------------------

def check_essay(filepath: Path) -> dict:
    """
    Retorna dict {name, issues}: cada issue é {severity, code, message}.
    severity: CRITICAL | ERROR | WARNING | INFO
    """
    issues = []

    def add(severity, code, msg):
        issues.append({"severity": severity, "code": code, "message": msg})

    content = load(filepath)
    fm_text, body = split_frontmatter(content)
    lines = content.splitlines()
    # Mesmo alinhamento de linhas que `lines`, mas com o interior das fences
    # em branco: comentário Python `# x` não é heading, aspas ASCII lá dentro
    # são obrigatórias, etc.
    lines_clean = strip_fences(content).splitlines()
    name = filepath.name

    # -----------------------------------------------------------------------
    # 1. Frontmatter
    # -----------------------------------------------------------------------
    # -----------------------------------------------------------------------
    # 0. Caracteres de controle
    # -----------------------------------------------------------------------
    # Erro de escape em script de edição (`\f`, `\a`, `\b` em string Python não
    # crua) injeta bytes de controle invisíveis no meio da prosa ou da
    # matemática. Não aparecem em nenhuma leitura casual, passam pelo Obsidian
    # e só se manifestam quando o LuaLaTeX aborta o PDF com "Text line contains
    # an invalid character". Aqui viram CRITICAL, porque quebram exportação.
    # A varredura é sobre `content` cru, e não sobre `lines`: str.splitlines()
    # do Python trata \x0b, \x0c, \x1c-\x1e e  como quebra de linha e os
    # consome, de modo que um form feed injetado no meio do texto simplesmente
    # desaparece antes de qualquer checagem por linha.
    controle = [
        (content.count("\n", 0, pos) + 1, ord(ch))
        for pos, ch in enumerate(content)
        if ord(ch) < 32 and ch not in "\n\t"
    ]
    if controle:
        onde = ", ".join(
            f"linha {ln} (0x{cp:02X})" for ln, cp in controle[:6]
        )
        resto = f" e mais {len(controle) - 6}" if len(controle) > 6 else ""
        add("CRITICAL", "CONTROL_CHAR",
            f"{len(controle)} caractere(s) de controle invisível(is) na prosa: "
            f"{onde}{resto} — quebram a exportação para PDF")

    if not fm_text:
        add("CRITICAL", "NO_FRONTMATTER", "Sem YAML frontmatter")
        return {"name": name, "issues": issues}

    try:
        fm_data = yaml.safe_load(fm_text.strip("---\n")) or {}
    except Exception as e:
        add("CRITICAL", "BAD_FRONTMATTER", f"YAML inválido: {e}")
        return {"name": name, "issues": issues}

    for field in ("tags", "sources", "created", "updated"):
        if field not in fm_data:
            add("ERROR", "FM_MISSING_FIELD", f"Frontmatter sem campo '{field}'")
        elif field in ("tags", "sources") and not isinstance(fm_data[field], list):
            add("ERROR", "FM_BAD_TYPE", f"Campo '{field}' deve ser lista")

    summary = fm_data.get("summary")
    if summary is None:
        add("ERROR", "FM_NO_SUMMARY",
            "Frontmatter sem campo 'summary' — wiki/index.md sai sem resumo desta entrada")
    elif not isinstance(summary, str) or not summary.strip():
        add("ERROR", "FM_BAD_SUMMARY", "Campo 'summary' vazio ou não é texto")
    elif len(summary.strip()) > SUMMARY_MAX_CHARS:
        add("WARNING", "FM_LONG_SUMMARY",
            f"'summary' com {len(summary.strip())} caracteres "
            f"(máximo {SUMMARY_MAX_CHARS}) — é um resumo de uma linha, não um parágrafo")
    elif len(summary.strip()) < SUMMARY_MIN_CHARS:
        add("WARNING", "FM_SHORT_SUMMARY",
            f"'summary' com {len(summary.strip())} caracteres "
            f"(mínimo {SUMMARY_MIN_CHARS}) — deve descrever o arco do argumento, não só o tema")

    status = fm_data.get("status")
    if status is None:
        add("ERROR", "FM_NO_STATUS",
            f"Frontmatter sem campo 'status' (esperado: {sorted(VALID_STATUS)})")
    elif status not in VALID_STATUS:
        add("ERROR", "FM_BAD_STATUS",
            f"'status: {status}' inválido (esperado: {sorted(VALID_STATUS)})")

    # -----------------------------------------------------------------------
    # 2. H1 + byline
    # -----------------------------------------------------------------------
    h1_match = re.search(r"^# (.+)$", content, re.MULTILINE)
    if not h1_match:
        add("CRITICAL", "NO_H1", "Sem título H1 (# Título)")
        return {"name": name, "issues": issues}

    title = h1_match.group(1).strip()
    h1_idx = next((i for i, ln in enumerate(lines) if ln.strip() == f"# {title}"), None)

    if h1_idx is not None:
        if h1_idx + 1 < len(lines) and lines[h1_idx + 1].strip() != "":
            add("ERROR", "NO_BLANK_AFTER_H1",
                f"Linha {h1_idx+2}: falta linha em branco entre H1 e byline")

        byline_lines = []
        idx = h1_idx + 2
        while idx < len(lines) and lines[idx].strip().startswith(">"):
            byline_lines.append(lines[idx].strip())
            idx += 1

        if len(byline_lines) < 2:
            add("ERROR", "BYLINE_MISSING",
                f"Byline ausente ou incompleta ({len(byline_lines)} linha(s) de blockquote encontrada(s))")
        else:
            bl1, bl2 = byline_lines[0], byline_lines[1]

            m1 = re.match(r"^>\s*(Ensaio|White Paper|Brainstorm|Estudo|Análise)\s*$", bl1)
            m2 = re.match(r"^>\s*Gustavo Zambrano\s*·\s*([A-Za-zÀ-ÿ]+ de \d{4})$", bl2)

            if not m1:
                add("ERROR", "BYLINE_LINE1",
                    f"Byline linha 1 formato inválido: '{bl1}' "
                    f"(esperado: '> [Tipo]', Tipo ∈ {sorted(VALID_TYPES)})")
            if not m2:
                add("ERROR", "BYLINE_LINE2",
                    f"Byline linha 2 formato inválido: '{bl2}' "
                    "(esperado: '> Gustavo Zambrano · Mês de Ano', ex: 'Junho de 2026')")
            if "[[" in bl1 or "[[" in bl2:
                add("ERROR", "BYLINE_WIKILINK",
                    "Byline contém [[wikilinks]] — deve ser texto puro")
            if ":" in bl1 or ":" in bl2:
                add("ERROR", "BYLINE_COLON",
                    "Byline contém ':' — Obsidian interpreta como separador de bloco")

            for bad_char, desc in [("&", "&"), ("%", "%"), ("#", "#")]:
                if bad_char in bl1 or bad_char in bl2:
                    add("WARNING", "BYLINE_LATEX_CHAR",
                        f"Byline contém '{bad_char}' ({desc}) — pode quebrar exportação LaTeX; use 'e'/'e'/'\\{bad_char}'")

    for bad_char in ("&", "%"):
        if bad_char in title:
            add("WARNING", "TITLE_LATEX_CHAR",
                f"Título H1 contém '{bad_char}' — verifique o escape no export_essay_pdf.py")

    # -----------------------------------------------------------------------
    # 3. Espaçamento de headings
    # -----------------------------------------------------------------------
    heading_spacing_errors = []
    for i, line in enumerate(lines_clean):
        if re.match(r"^#{1,6} ", line):
            if i == h1_idx:
                continue
            next_i = i + 1
            if next_i < len(lines):
                nxt = lines[next_i].strip()
                if nxt and not nxt.startswith("#"):
                    heading_spacing_errors.append(i + 1)
    if heading_spacing_errors:
        add("ERROR", "HEADING_SPACING",
            f"{len(heading_spacing_errors)} heading(s) sem linha em branco após: "
            f"linhas {heading_spacing_errors[:5]}"
            + ("..." if len(heading_spacing_errors) > 5 else ""))

    # -----------------------------------------------------------------------
    # 4. ## Sumário — presença e âncoras
    # -----------------------------------------------------------------------
    if "## Sumário" not in content:
        add("ERROR", "NO_SUMARIO", "Seção '## Sumário' ausente")
    else:
        if not re.search(r"## Sumário\s*\n.*?\n---", content, re.DOTALL):
            add("ERROR", "SUMARIO_NO_HR",
                "'## Sumário' deve terminar com '---' (separador horizontal)")

        sum_block = re.search(r"## Sumário\s*\n(.*?)\n---", content, re.DOTALL)
        if sum_block:
            # Sumário/Referências/Conexões entram na lista de anchors válidos:
            # um link do Sumário para `#referências` navega, e acusá-lo de
            # quebrado só porque a seção é estrutural era falso-positivo.
            real_headings = [
                m.group(1).strip()
                for m in re.finditer(r"^#{2,6} (.+)$", content, re.MULTILINE)
                if m.group(1).strip()
            ]
            real_anchors = {anchor_key(heading_anchor(h)) for h in real_headings}

            bloco = sum_block.group(1)

            # Forma canônica, nativa do Obsidian: `[[#Texto Do Heading]]` (ou com
            # `|Display`). Confere pelo texto do heading, não pelo slug.
            reais_txt = {h.strip() for h in real_headings}
            for alvo in re.findall(r"\[\[#([^\]\|]+)(?:\|[^\]]+)?\]\]", bloco):
                if alvo.strip() not in reais_txt:
                    add("WARNING", "SUMARIO_BROKEN_ANCHOR",
                        f"Sumário aponta para '#{alvo.strip()}', que não é um heading "
                        f"deste essay (headings: {sorted(reais_txt)[:3]}...)")

            # Forma antiga `[texto](#slug)`: ainda validada, mas sinalizada — ela
            # navega no PDF/HTML e NÃO navega no Obsidian.
            for display, anchor in re.findall(r"\[([^\]]+)\]\(#([^\)]+)\)", bloco):
                if anchor_key(anchor) not in real_anchors:
                    add("WARNING", "SUMARIO_BROKEN_ANCHOR",
                        f"Sumário link '#{anchor}' não bate com nenhum heading real "
                        f"(esperados: {sorted(real_anchors)[:4]}...)")
                else:
                    add("WARNING", "SUMARIO_ANCHOR_NAO_OBSIDIAN",
                        f"Sumário usa '[{display[:30]}](#{anchor[:30]})', que não navega no "
                        f"Obsidian; a forma canônica é [[#Texto Do Heading]]")

    # -----------------------------------------------------------------------
    # 5. ## Referências (só existência/heading — conteúdo é check_references.py)
    # -----------------------------------------------------------------------
    if not re.search(r"^## Referências$", content, re.MULTILINE):
        variants = [
            (r"^## Referências Bibliográficas", "usa '## Referências Bibliográficas'"),
            (r"^### Referências", "usa ### em vez de ##"),
            (r"^# Referências", "usa # (H1) em vez de ##"),
        ]
        msg = "Seção '## Referências' ausente"
        for pat, desc in variants:
            if re.search(pat, content, re.MULTILINE):
                msg = f"Referências mal formatada: {desc} — use exatamente '## Referências'"
                break
        add("ERROR", "NO_REFERENCIAS", msg)
    else:
        ref_match = re.search(
            r"^## Referências$\n(.*?)(?=^## |\Z)", content, re.MULTILINE | re.DOTALL
        )
        ref_block = ref_match.group(1) if ref_match else ""
        ref_entries = re.findall(r"^\[\d+\].*$", ref_block, re.MULTILINE)

        body_before_ref = content.split("## Referências")[0]
        body_ext_links = re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", body_before_ref)
        if not ref_entries and len(body_ext_links) >= 5:
            add("ERROR", "EMPTY_REFERENCIAS",
                f"'## Referências' está vazia, mas o corpo tem {len(body_ext_links)} "
                f"link(s) externo(s) — bibliografia provavelmente nunca foi construída")

        bold_entries = [e for e in ref_entries if "**" in e]
        if bold_entries:
            add("WARNING", "REF_BOLD_AUTHOR",
                f"{len(bold_entries)} entrada(s) em '## Referências' com **negrito** "
                f"— convenção não usa negrito, só itálico no título: "
                f"{[e[:40] for e in bold_entries[:3]]}")

        author_as_title = re.compile(
            r"\*[A-ZÀ-Ú][a-zà-úãõçêé]+(?:,|\s&|\set al\.)[^*]{0,60}\(\d{4}\)[^*]*\*"
        )
        title_bug_entries = [e for e in ref_entries if author_as_title.search(e)]
        if title_bug_entries:
            add("ERROR", "REF_TITLE_IS_AUTHOR",
                f"{len(title_bug_entries)} entrada(s) com 'Autor (Ano)' dentro do "
                f"itálico — ou o título real nunca foi preenchido (itálico = só "
                f"autor+ano), ou autor/ano foram incorretamente colados dentro do "
                f"itálico do título. Confira manualmente (WebFetch/DOI) antes de "
                f"aceitar: {[e[:50] for e in title_bug_entries[:3]]}")

        embedded_author = re.compile(
            r"\*[^*]+ — [A-ZÀ-Ú][\wÀ-ú.]*(?: [A-ZÀ-Ú][\wÀ-ú.]*){0,3}(?: \(\d{4}\))?\*"
        )
        embedded_entries = [e for e in ref_entries if embedded_author.search(e)]
        if embedded_entries:
            add("WARNING", "REF_EMBEDDED_AUTHOR_IN_TITLE",
                f"{len(embedded_entries)} entrada(s) parecem ter autor/ano ou "
                f"subtítulo inventado colado dentro do itálico do título (padrão "
                f"'*Título — Nome (Ano)*') — confirme o título real da página/obra "
                f"(WebFetch) e mova autor/ano para fora do itálico: "
                f"{[e[:60] for e in embedded_entries[:3]]}")

        container_only = re.compile(
            r"^\[\d+\]\s+[A-ZÀ-Ú][a-zà-úãõçêé]+.{0,80}\(\d{4}\)\.\s*\*[^*]+\*\.\s*(?:doi|https?|$)",
        )
        for e in ref_entries:
            if container_only.search(e) and not author_as_title.search(e):
                add("WARNING", "REF_MISSING_TITLE",
                    f"Entrada sem título aparente, só autor+ano+container: {e[:70]}")

        # Chamadas de citação [N] no corpo x entradas listadas. Corpo sem
        # fences e sem links (markdown/wikilink) para não pegar o "[texto]"
        # de um link; aceita listas do tipo "[1, 3]". Só é chamada de
        # citação o número dentro do alcance plausível da bibliografia
        # (até max(listed)+2): [64]/[255] num essay cuja bibliografia vai
        # a [15] é notação (casas do tabuleiro, índice de vetor), não citação.
        cite_body = strip_fences(body_before_ref)
        cite_body = re.sub(r"\[\[#(?:refer[eê]ncias|references)\|([^\]]*)\]\]", r"\1", cite_body, flags=re.IGNORECASE)
        cite_body = re.sub(r"\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\]\(#(?:refer[eê]ncias|references)\)", r"[\1]", cite_body, flags=re.IGNORECASE)
        cite_body = re.sub(r"\[([^\]]*)\]\([^\)]*\)", "", cite_body)
        cite_body = re.sub(r"\[\[(?:[^\]]*)\]\]", "", cite_body)
        cited = set()
        for m in re.finditer(r"\[(\d{1,3}(?:\s*,\s*\d{1,3})*)\]", cite_body):
            for part in m.group(1).split(","):
                cited.add(int(part.strip()))
        listed = {
            int(m.group(1))
            for m in (re.match(r"^\[(\d+)\]", e) for e in ref_entries)
            if m
        }
        limit = (max(listed) + 2) if listed else 50
        missing = sorted(n for n in cited - listed if 1 <= n <= limit)
        for n in missing:
            add("WARNING", "CITE_MISSING_REF",
                f"Chamada [{n}] no corpo sem entrada correspondente em '## Referências'")
        for n in sorted(listed - cited):
            add("INFO", "REF_NEVER_CITED",
                f"Entrada [{n}] em '## Referências' nunca é citada no corpo")
        check_reference_contracts(ref_entries, add)

    # -----------------------------------------------------------------------
    # 5a. Contratos mecânicos de callouts, figuras e prosa editorial
    # -----------------------------------------------------------------------
    check_callout_contracts(body, add)
    check_figure_contracts(body, filepath.stem, add)
    check_prose_signals(body, add)
    check_updated_against_git(filepath, add)

    # -----------------------------------------------------------------------
    # 5b. Numeração de capítulos (H2) e subseções (H3)
    #     Essays ou numeram todos os capítulos, ou nenhum; a sequência não
    #     salta (1,2,3… / I,II,III…); H3 "N.M" exige pai N e M sequencial.
    # -----------------------------------------------------------------------
    ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}

    def roman_to_int(s):
        total, prev = 0, 0
        for ch in reversed(s.upper()):
            val = ROMAN_VALUES.get(ch, 0)
            total = total - val if val < prev else total + val
            prev = max(prev, val)
        return total

    # "7. Conclusão" -> ("7", resto); "Seção 9 — X" -> ("9", resto);
    # "Capítulo II: X" -> ("II", resto); "Introdução" -> (None, texto).
    # O número só vale seguido de separador/espaço/fim — evita ler o "I"
    # inicial de "Introdução" como romano.
    NUM_HEADING_RE = re.compile(
        r"^(?:(?:se[çc][aã]o|cap[íi]tulo|parte)\s*)?"
        r"((?:[IVXLC]+|\d+)(?:[.:\-—–]|\s|$))?\s*(.*)$",
        re.IGNORECASE,
    )

    def heading_number(text):
        m = NUM_HEADING_RE.match(text.strip())
        if not m or not m.group(1):
            return None, None
        tok = m.group(1).rstrip(".:—–- ").strip()
        num = int(tok) if tok.isdigit() else roman_to_int(tok)
        return num, tok

    num_body = strip_fences(content).split("## Conexões")[0]
    seq_items = []  # (kind, line_no, text, num, tok, sub)
    for ln_no, ln in enumerate(num_body.splitlines(), 1):
        m2 = re.match(r"^## (?!#)(.+)$", ln)
        m3 = re.match(r"^### (?!#)(.+)$", ln)
        if m2:
            txt = m2.group(1).strip()
            if txt.lower() in ("sumário", "referências"):
                continue
            n, tok = heading_number(txt)
            seq_items.append(("h2", ln_no, txt, n, tok, None))
        elif m3:
            txt = m3.group(1).strip()
            ms = re.match(r"^(\d+)\.(\d+)(?:[.:\-—–]|\s|$)\s*(.*)$", txt)
            if ms:
                seq_items.append(("h3", ln_no, txt, int(ms.group(1)), "arabic", int(ms.group(2))))
            else:
                seq_items.append(("h3", ln_no, txt, None, None, None))

    # Seções semânticas (Introdução, Conclusão, Resumo Executivo…) são
    # deliberadamente sem número — não contam como "capítulo sem número".
    SEM_HEADING_RE = re.compile(
        r"^(?:se[çc][aã]o|cap[íi]tulo|parte)?\s*(?:\d+|[IVXLC]+)?\s*[.:\-—–]?\s*"
        r"(introdu[çc][aã]o|conclus[aã]o|resumo(?:\s+executivo)?|pref[áa]cio|"
        r"pr[óo]logo|ep[íi]logo|posf[áa]cio|p[óo]s-?escrito|agradecimentos|"
        r"ap[êe]ndice|anexos?)\b",
        re.IGNORECASE,
    )

    h2_all = [it for it in seq_items if it[0] == "h2"]
    h2_content = [it for it in h2_all if not SEM_HEADING_RE.match(it[2])]
    h2_numbered = [it for it in h2_content if it[3] is not None]
    h3_numbered = [it for it in seq_items if it[0] == "h3" and it[3] is not None]

    if h2_content and h2_numbered and len(h2_numbered) < len(h2_content):
        unnum = [f"linha {it[1]}: '{it[2][:40]}'" for it in h2_content if it[3] is None]
        add("WARNING", "NUMBERING_MIXED",
            f"{len(unnum)} capítulo(s) H2 sem número em essay numerado: {unnum[:3]}")

    if h2_numbered:
        expected = 1
        for it in h2_all:
            if it[3] is None:
                continue
            if it[3] != expected:
                add("WARNING", "NUMBERING_SEQUENCE",
                    f"linha {it[1]}: capítulo '{it[2][:44]}' usa '{it[4]}', "
                    f"esperado '{expected}' — sequência quebrada ou salto")
                expected = it[3]  # re-sincroniza: um aviso por quebra
            expected += 1

        cur_parent = None
        expected_sub = 1
        for it in seq_items:
            if it[0] == "h2":
                cur_parent = it[3]
                expected_sub = 1
                continue
            if it[3] is None:
                continue  # H3 sem número: legítimo, salvo misto abaixo
            if cur_parent is None:
                add("WARNING", "NUMBERING_H3_SEM_PAI",
                    f"linha {it[1]}: subseção '{it[2][:40]}' numerada antes de "
                    f"qualquer capítulo H2 numerado")
                continue
            if it[3] != cur_parent:
                add("WARNING", "NUMBERING_H3_PAI",
                    f"linha {it[1]}: subseção '{it[2][:36]}' usa '{it[3]}.{it[5]}' "
                    f"mas o capítulo corrente é {cur_parent}")
                expected_sub = it[5] + 1
                continue
            if it[5] != expected_sub:
                add("WARNING", "NUMBERING_H3_SEQUENCE",
                    f"linha {it[1]}: subseção '{it[2][:36]}' usa '{it[3]}.{it[5]}', "
                    f"esperado '{cur_parent}.{expected_sub}'")
                expected_sub = it[5]
            expected_sub += 1

        if h3_numbered and len(h3_numbered) < sum(1 for it in seq_items if it[0] == "h3"):
            unnum = [
                f"linha {it[1]}: '{it[2][:40]}'"
                for it in seq_items if it[0] == "h3" and it[3] is None
            ]
            add("WARNING", "NUMBERING_MIXED",
                f"{len(unnum)} subseção(ões) H3 sem número em essay com "
                f"subseções numeradas: {unnum[:3]}")

    # -----------------------------------------------------------------------
    # 6. ## Conexões — presente e última H2
    # -----------------------------------------------------------------------
    if not re.search(r"^## Conexões$", content, re.MULTILINE):
        add("ERROR", "NO_CONEXOES", "Seção '## Conexões' ausente")
    else:
        after_conex = content.split("## Conexões")[-1]
        if re.search(r"^## [^#]", after_conex, re.MULTILINE):
            add("ERROR", "CONEXOES_NOT_LAST",
                "'## Conexões' não é a última seção H2 do essay")

    # -----------------------------------------------------------------------
    # 7. Wikilinks fora de Conexões
    # -----------------------------------------------------------------------
    body_before_conex = strip_fences(content).split("## Conexões")[0]
    # `[[#Heading]]` é link para seção do próprio arquivo, não para outra
    # página: é a forma que o `## Sumário` usa, e a única que o Obsidian
    # resolve. A regra "só link externo no corpo" existe para o essay ser
    # autocontido no PDF, e o export converte esses em âncora normal, então
    # eles não violam nada.
    wikilinks_in_body = [
        w for w in re.findall(r"\[\[([^\]]+)\]\]", body_before_conex)
        if not w.startswith("#")
    ]

    # Todo `[[#Heading]]` do corpo é validado, não só os do `## Sumário`. Links
    # de seção aparecem também em índices internos e em referências cruzadas no
    # meio do texto, e por muito tempo ninguém os checou: foi exatamente aí que
    # 20 links quebrados sobreviveram a várias passadas de lint.
    todos_headings = {
        m.group(1).strip() for m in re.finditer(r"(?m)^#{2,6} (.+)$", content)
    }
    for alvo in re.findall(r"\[\[#([^\]\|]+)(?:\|[^\]]+)?\]\]", strip_fences(content)):
        if alvo.strip() not in todos_headings:
            add("WARNING", "HEADING_LINK_QUEBRADO",
                f"'[[#{alvo.strip()[:50]}]]' não corresponde a nenhum heading deste essay")
    if wikilinks_in_body:
        add("ERROR", "WIKILINKS_IN_BODY",
            f"{len(wikilinks_in_body)} [[wikilink(s)]] fora de Conexões: "
            f"{wikilinks_in_body[:3]}")

    # -----------------------------------------------------------------------
    # 8. Links externos (mínimo 10)
    # -----------------------------------------------------------------------
    ext_links = re.findall(r"\[([^\]]+)\]\((https?://[^\)]+)\)", content)
    if len(ext_links) < 10:
        # WARNING, não ERROR: o mínimo de 10 é alvo editorial, e um white paper
        # curto e muito técnico pode legitimamente não ter 10 fontes externas
        # que valha a pena linkar. Quem decide é o Usuário, via `/linkify`.
        add("WARNING", "FEW_EXT_LINKS",
            f"Apenas {len(ext_links)} link(s) externos (mínimo recomendado: 10)")

    # -----------------------------------------------------------------------
    # 9. Aspas ASCII suspeitas na prosa
    # -----------------------------------------------------------------------
    prose_body = re.sub(r"^---.*?---\n", "", content, count=1, flags=re.DOTALL)
    prose_body = strip_fences(prose_body)
    prose_body = re.sub(r"`[^`]+`", "", prose_body)
    prose_body = re.sub(r"\[[^\]]+\]\([^\)]+\)", "", prose_body)

    ascii_double = len(re.findall(r'"', prose_body))
    ascii_single = len(re.findall(r"'", prose_body))
    if ascii_double > 3:
        add("WARNING", "ASCII_QUOTES",
            f"{ascii_double} aspas duplas ASCII (\") na prosa — considere aspas tipográficas "
            "(“...”) ou verifique se não quebram LaTeX")
    if ascii_single > 5:
        add("INFO", "ASCII_APOSTROPHES",
            f"{ascii_single} apóstrofos/aspas simples ASCII (') na prosa — ok se for contrações, "
            "verifique se intencional")

    # -----------------------------------------------------------------------
    # 10. Espaços duplos
    # -----------------------------------------------------------------------
    double_spaces = [
        i + 1 for i, line in enumerate(lines_clean)
        if "  " in line and not line.startswith("```") and not line.startswith("|")
    ]
    if double_spaces:
        add("WARNING", "DOUBLE_SPACES",
            f"Espaços duplos em {len(double_spaces)} linha(s): {double_spaces[:5]}"
            + ("..." if len(double_spaces) > 5 else ""))

    # -----------------------------------------------------------------------
    # 11. Linhas em branco excessivas (>=3 consecutivas)
    # -----------------------------------------------------------------------
    blank_runs = re.findall(r"\n{4,}", content)
    if blank_runs:
        add("WARNING", "EXCESS_BLANK_LINES",
            f"{len(blank_runs)} trecho(s) com >=3 linhas em branco consecutivas")

    # -----------------------------------------------------------------------
    # 12. Travessões (—) — max 2 por essay
    # -----------------------------------------------------------------------
    # Conta só a prosa. `## Referências` e `## Conexões` são estruturais: o
    # formato AIAA exige `—` antes da nota de cada entrada, e cada linha de
    # Conexões usa `—` antes da descrição. Nenhum dos dois é escolha de estilo.
    prose_for_dashes = re.split(r"(?m)^## Refer[êe]ncias\s*$", content)[0]
    prose_for_dashes = re.split(r"(?m)^## Conex[õo]es\s*$", prose_for_dashes)[0]
    em_dash_count = prose_for_dashes.count("—")
    em_dashes_in_wikilinks = len(re.findall(r"\[\[[^\]]+—[^\]]+\]\]", prose_for_dashes))
    effective_dashes = em_dash_count - em_dashes_in_wikilinks
    if effective_dashes > 2:
        add("INFO", "TOO_MANY_EM_DASHES",
            f"{effective_dashes} travessão(ões) (—) na prosa "
            "(máximo recomendado: 2; prefira vírgula, dois-pontos ou parênteses)")

    # -----------------------------------------------------------------------
    # 13. Bullets no corpo argumentativo (só Sumário/Referências/tabelas)
    # -----------------------------------------------------------------------
    body_for_bullets = content
    for section in ("## Sumário", "## Referências", "## Conexões"):
        parts_s = body_for_bullets.split(section, 1)
        if len(parts_s) == 2:
            next_section = re.search(r"\n## ", parts_s[1])
            if next_section:
                body_for_bullets = parts_s[0] + parts_s[1][next_section.start():]
            else:
                body_for_bullets = parts_s[0]

    body_for_bullets_clean = strip_fences(body_for_bullets)
    bullet_lines = [
        (i + 1, ln)
        for i, ln in enumerate(body_for_bullets_clean.splitlines())
        if re.match(r"^\s*[-*]\s+\S", ln)
    ]
    if bullet_lines:
        add("WARNING", "BULLETS_IN_BODY",
            f"{len(bullet_lines)} linha(s) com bullet fora de Sumário/Referências — "
            f"use prosa argumentativa: linhas {[b[0] for b in bullet_lines[:5]]}"
            + ("..." if len(bullet_lines) > 5 else ""))

    # -----------------------------------------------------------------------
    # 13.5 Remissão a outro essay no corpo
    # -----------------------------------------------------------------------
    xref_body = re.sub(r"^---.*?---\n", "", content, count=1, flags=re.DOTALL)
    xref_body = strip_fences(xref_body)
    xref_body = re.split(
        r"(?m)^## (?:Refer[e\u00ea]ncias|Conex[o\u00f5]es)\s*$", xref_body)[0]
    xrefs = [m.group(0).strip() for m in CROSS_ESSAY_RE.finditer(xref_body)]
    if xrefs:
        add("WARNING", "CROSS_ESSAY_REFERENCE",
            f"{len(xrefs)} remiss\u00e3o(\u00f5es) a outro essay no corpo \u2014 o essay \u00e9 autocontido "
            f"e a rela\u00e7\u00e3o entre p\u00e1ginas vive em ## Conex\u00f5es: {xrefs[:3]}")

    # -----------------------------------------------------------------------
    # 13.6 Estilo de prosa mecanizavel (## Estilo de prosa em conventions)
    # -----------------------------------------------------------------------
    # Base limpa: sem frontmatter, sem codigo, sem matematica, sem tabela e sem
    # URL. Sem isso a barra de uma URL e o hifen dentro de `$...$` viram falso
    # positivo.
    est = re.sub(r"^---.*?---\n", "", content, count=1, flags=re.DOTALL)
    est = strip_fences(est)
    est = re.split(r"(?m)^## (?:Refer[eê]ncias|Conex[oõ]es)\s*$", est)[0]
    est = re.sub(r"`[^`\n]*`", "", est)
    est = re.sub(r"\$\$.*?\$\$", "", est, flags=re.DOTALL)
    est = re.sub(r"\$[^$\n]*\$", "", est)
    est = re.sub(r"\[([^\]]*)\]\([^\)]*\)", r"\1", est)
    est = re.sub(r"(?m)^\|.*$", "", est)

    # "Sem ponto e virgula": divida em frases autonomas.
    n_pv = est.count(";")
    if n_pv:
        add("INFO", "SEMICOLON",
            f"{n_pv} ponto(s) e vírgula na prosa — a convenção pede frases "
            "autônomas; trabalho de /polish")

    # "Por exemplo" e "ou seja" por extenso, sem abreviacao latina solta.
    lat = re.findall(r"(?i)\b(?:e\.g\.|i\.e\.)", est)
    if lat:
        add("WARNING", "LATIN_ABBREV",
            f"{len(lat)} abreviação(ões) latina(s) {sorted(set(lat))} — escreva "
            "“por exemplo”, “ou seja”")

    # "Remissoes completas": Capitulo 3, nao Cap. 3. `Fig. 1` no inicio de linha
    # fica de fora: e o formato de legenda que pdf_boxes.lua estiliza.
    cross = [m.group(0) for m in re.finditer(
        r"(?im)(?<![\n*])\b(?:cap|sec|seç|tab|eq)\.\s*\d+", est)]
    if cross:
        add("WARNING", "ABBREV_CROSSREF",
            f"{len(cross)} remissão(ões) abreviada(s) {cross[:3]} — escreva "
            "“Capítulo 3”, “Seção 2” por extenso")

    # "Intervalos numericos por extenso": 5 a 30, nao 5-30.
    faixa = re.findall(r"(?<![\d\-–])\d{1,4}\s?[-–]\s?\d{1,4}(?![\d\-–])", est)
    if faixa:
        add("INFO", "NUMERIC_RANGE_HYPHEN",
            f"{len(faixa)} intervalo(s) numérico(s) com hífen {faixa[:3]} — a "
            "convenção pede “5 a 30”")

    # "Sem barras obliquas": escreva "e" ou "ou" por extenso.
    barras = re.findall(r"(?<=[a-zà-ú])\s?/\s?(?=[a-zà-ú])", est)
    if barras:
        add("INFO", "SLASH_IN_PROSE",
            f"{len(barras)} barra(s) oblíqua(s) entre palavras — escreva “e” ou "
            "“ou” por extenso")

    # "Sem simbolos de atalho": ~ vira "aproximadamente".
    til = re.findall(r"~\s?\d", est)
    if til:
        add("WARNING", "TILDE_APPROX",
            f"{len(til)} uso(s) de ~ como “aproximadamente” — escreva por extenso")

    # -----------------------------------------------------------------------
    # 13.7 Imagens (## Tratamento de imagens em conventions)
    # -----------------------------------------------------------------------
    # ERROR porque quebram o export em silêncio: o Pandoc não acha o arquivo e o
    # PDF sai sem a figura, sem aviso alto.
    for alvo in re.findall(r"!\[[^\]]*\]\(([^\)]+)\)", content):
        alvo_limpo = alvo.split()[0].strip("<>")
        if alvo_limpo.startswith("data:"):
            add("ERROR", "IMAGE_BASE64",
                "imagem embutida em base64 — extraia para wiki/assets/")
        elif re.match(r"^([A-Za-z]:[\\/]|/)", alvo_limpo):
            add("ERROR", "IMAGE_ABSOLUTE_PATH",
                f"imagem em caminho absoluto ({alvo_limpo[:50]}) — use relativo")
        elif not alvo_limpo.startswith("http"):
            if not (filepath.parent / alvo_limpo).exists():
                add("ERROR", "IMAGE_MISSING",
                    f"imagem inexistente: {alvo_limpo[:60]}")

    # -----------------------------------------------------------------------
    # 13.8 Wikilink sem título visível (## Compatibilidade com Obsidian)
    # -----------------------------------------------------------------------
    conex_txt = content.split("## Conexões")[-1] if "## Conexões" in content else ""
    sem_pipe = [w for w in re.findall(r"\[\[([^\]]+)\]\]", conex_txt)
                if "|" not in w and not w.startswith("#")]
    if sem_pipe:
        add("WARNING", "WIKILINK_NO_PIPE",
            f"{len(sem_pipe)} wikilink(s) sem título visível {sem_pipe[:3]} — o "
            "formato é [[nome-do-arquivo|Título Da Página]]")

    # -----------------------------------------------------------------------
    # 13.9 Nome de arquivo (## Nomenclatura de páginas)
    # -----------------------------------------------------------------------
    if not re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", filepath.stem):
        add("WARNING", "FILENAME_NOT_KEBAB",
            f"nome de arquivo fora do kebab-case: {filepath.stem}")

    # -----------------------------------------------------------------------
    # 14. HTML residual
    # -----------------------------------------------------------------------
    html_tags = HTML_TAG_RE.findall(strip_fences(content))
    if html_tags:
        add("ERROR", "HTML_RESIDUAL",
            f"{len(html_tags)} tag(s) HTML residuais: {html_tags[:3]}")

    # -----------------------------------------------------------------------
    # 15. Símbolos residuais
    # -----------------------------------------------------------------------
    for desc, occurrences in detect_residual_symbols(lines_clean):
        add("ERROR", "RESIDUAL_SYMBOL",
            f"Símbolo residual '{desc}' em {len(occurrences)} linha(s): {occurrences[:5]}")

    # -----------------------------------------------------------------------
    # 16. Idioma — parágrafos possivelmente em inglês
    # -----------------------------------------------------------------------
    for snippet in detect_english_paragraphs(content):
        add("WARNING", "ENGLISH_PARAGRAPH",
            f"Parágrafo possivelmente em inglês: \"{snippet}...\"")

    # -----------------------------------------------------------------------
    # 17. Loose chapter labels (ex: "01 — Introdução" como linha solta)
    # -----------------------------------------------------------------------
    # Separador tem que ser traço (-, –, —), nunca ponto: "1. Texto" é item de
    # lista ordenada Markdown padrão (## Estilo de prosa permite lista quando
    # a numeração é passo-a-passo de um argumento), não o resíduo de import de
    # PDF que esta regra tenta pegar. Incluir "." aqui gerava aviso em toda
    # lista numerada do corpus — ruído puro, sem nenhum caso real capturado.
    #
    # Também exclui linha com sinal de LaTeX (`\comando`, `$`, `&` de tabela
    # de matriz): dentro de um bloco `$$...$$`/`\begin{cases}` (que
    # strip_fences não esvazia — só cobre ``` ```), uma linha de sistema
    # linear como "1 - \lambda_A \lambda_B \rho & \text{se } x = 0" também
    # começa com dígito+traço, mas é matemática, não capítulo órfão.
    LATEX_TOKEN_RE = re.compile(r"\\[a-zA-Z]|\$|&")
    for i, line in enumerate(lines_clean):
        stripped = line.strip()
        if re.match(r"^\d+\s*[-–—]\s*\S", stripped) and not LATEX_TOKEN_RE.search(stripped):
            add("WARNING", "LOOSE_CHAPTER_LABEL",
                f"Possível label de capítulo solto (linha {i+1}): '{stripped}'")

    return {"name": name, "issues": issues}


# ---------------------------------------------------------------------------
# Checagens de corpus (puladas em escopo de essay único)
# ---------------------------------------------------------------------------

def build_title_map():
    """Mapa de título -> arquivo (e o inverso) para todas as categorias, e o
    conjunto de arquivos sem H1 (issue própria de páginas de apoio; essays
    já têm NO_H1 no check_essay)."""
    title_to_file, file_to_title = {}, {}
    essay_titles, all_titles, all_slugs = set(), set(), set()
    no_h1 = []

    for category, dir_path in DIRS.items():
        if not dir_path.exists():
            continue
        for file in sorted(dir_path.glob("*.md")):
            rel_path = f"{category}/{file.name}"
            content = load(file)
            title = get_h1(content)
            # O slug do arquivo é alvo VÁLIDO de wikilink, e é a forma canônica:
            # o Obsidian resolve `[[...]]` por nome de arquivo, nunca pelo H1 nem
            # por alias de frontmatter (verificado no leitor real). A convenção da
            # wiki é `[[slug-do-arquivo|Título Visível]]`. O H1 continua aceito
            # aqui só para não quebrar link antigo ainda não migrado.
            all_titles.add(file.stem)
            all_slugs.add(file.stem)
            if category == "essays":
                essay_titles.add(file.stem)
            if title:
                title_to_file[title] = rel_path
                file_to_title[rel_path] = title
                all_titles.add(title)
                if category == "essays":
                    essay_titles.add(title)
            else:
                no_h1.append((category, rel_path))

    return {
        "title_to_file": title_to_file,
        "file_to_title": file_to_title,
        "essay_titles": essay_titles,
        "all_titles": all_titles,
        "all_slugs": all_slugs,
        "no_h1": no_h1,
    }


def check_support_pages():
    """concepts/entities/insights: uma versão mais leve do lint de essay —
    frontmatter, H1, heading spacing, idioma, símbolos/HTML residuais."""
    corpus = []

    def add(section, severity, code, message):
        corpus.append({"section": section, "severity": severity, "code": code, "message": message})

    for category in ("concepts", "entities", "insights"):
        dir_path = DIRS[category]
        if not dir_path.exists():
            continue
        for file in sorted(dir_path.glob("*.md")):
            rel_path = f"{category}/{file.name}"
            content = load(file)
            lines = content.splitlines()
            lines_clean = strip_fences(content).splitlines()

            fm_text, _ = split_frontmatter(content)
            fm_data = {}
            if not fm_text:
                add("SUPPORT_PAGES", "ERROR", "SUPPORT_NO_FRONTMATTER",
                    f"{rel_path}: sem YAML frontmatter")
            else:
                try:
                    fm_data = yaml.safe_load(fm_text.strip("---\n")) or {}
                except Exception as e:
                    add("SUPPORT_PAGES", "ERROR", "SUPPORT_BAD_FRONTMATTER",
                        f"{rel_path}: YAML inválido: {e}")

            for field in ("tags", "sources", "created", "updated"):
                if field not in fm_data:
                    add("SUPPORT_PAGES", "ERROR", "SUPPORT_FM_MISSING_FIELD",
                        f"{rel_path}: frontmatter sem campo '{field}'")

            for i, line in enumerate(lines_clean):
                if re.match(r"^#{1,6} ", line):
                    if i + 1 < len(lines) and lines[i + 1].strip() != "" and not lines[i + 1].strip().startswith("#"):
                        add("SUPPORT_PAGES", "ERROR", "SUPPORT_HEADING_SPACING",
                            f"{rel_path}: heading '{line}' (linha {i+1}) sem linha em branco após")

            for snippet in detect_english_paragraphs(content, exclude_referencias=False):
                add("SUPPORT_PAGES", "WARNING", "SUPPORT_ENGLISH_PARAGRAPH",
                    f"{rel_path}: parágrafo possivelmente não traduzido: \"{snippet}...\"")

            for desc, occurrences in detect_residual_symbols(lines_clean):
                add("SUPPORT_PAGES", "ERROR", "SUPPORT_RESIDUAL_SYMBOL",
                    f"{rel_path}: símbolo residual '{desc}' em {len(occurrences)} linha(s): {occurrences[:5]}")

            html_tags = HTML_TAG_RE.findall(strip_fences(content))
            if html_tags:
                add("SUPPORT_PAGES", "ERROR", "SUPPORT_HTML_RESIDUAL",
                    f"{rel_path}: {len(html_tags)} tag(s) HTML residuais: {html_tags[:3]}")

    return corpus


def check_dead_wikilinks(title_map, essay_only_file=None):
    corpus = []

    def add(section, severity, code, message):
        corpus.append({"section": section, "severity": severity, "code": code, "message": message})

    all_titles = title_map["all_titles"]
    all_slugs = title_map["all_slugs"]

    if essay_only_file:
        scope = {"essays": [essay_only_file]}
    else:
        scope = {cat: sorted(d.glob("*.md")) for cat, d in DIRS.items() if d.exists()}

    dead_links = {}
    non_slug_links = {}
    for category, files in scope.items():
        for file in files:
            content = strip_fences(load(file))
            for raw_link in re.findall(r"\[\[([^\]]+)\]\]", content):
                target = raw_link.split("|")[0].strip()
                display = raw_link.split("|")[1].strip() if "|" in raw_link else target
                if target.startswith("#"):
                    continue
                if ":" in display:
                    add("DEAD_WIKILINKS", "ERROR", "WIKILINK_DISPLAY_COLON",
                        f"Wikilink display text em {category}/{file.name} tem dois-pontos: '{raw_link}'")
                if target not in all_titles:
                    dead_links.setdefault(target, set()).add(f"{category}/{file.name}")
                elif target not in all_slugs:
                    # Existe uma pagina com esse H1, mas o link usa o titulo em vez
                    # do nome de arquivo: resolve aqui (falso "vivo"), mas o Obsidian
                    # so resolve por slug e abre uma nota nova em branco.
                    non_slug_links.setdefault(target, set()).add(f"{category}/{file.name}")

    for target, sources in sorted(dead_links.items()):
        add("DEAD_WIKILINKS", "ERROR", "DEAD_WIKILINK",
            f"'{target}' referenciado em: {', '.join(sorted(sources))}")

    for target, sources in sorted(non_slug_links.items()):
        add("DEAD_WIKILINKS", "ERROR", "NON_SLUG_WIKILINK",
            f"'{target}' usa o título em vez do slug (quebra no Obsidian) em: {', '.join(sorted(sources))}")

    return corpus


def check_orphans(title_map):
    """Dois graus de orfandade.

    ORPHAN_PAGE (WARNING) — ninguém cita, em lugar nenhum. Órfão de verdade.
    ORPHAN_NO_ESSAY (INFO) — concept/entity citada só por outra concept/entity
    ou por insight, nunca por essay. Legítimo enquanto o insight não virar
    essay, ou quando um concept se apoia noutro; informativo, não defeito.
    """
    corpus = []

    def concat(*categories):
        out = []
        for c in categories:
            d = DIRS.get(c)
            if d and d.exists():
                out.extend(load(f) for f in d.glob("*.md"))
        return "".join(out)

    essay_content = concat("essays")
    outro_content = concat("concepts", "entities", "insights")

    for category in ("concepts", "entities"):
        dir_path = DIRS[category]
        if not dir_path.exists():
            continue
        for file in sorted(dir_path.glob("*.md")):
            title = get_h1(load(file))
            if not title:
                continue
            # Casa pelo slug do arquivo E pelo H1: a forma canônica é
            # `[[slug|Título]]`, mas link antigo pelo título ainda conta como
            # referência — senão a migração para slug marcaria a wiki inteira
            # como órfã.
            alvos = "|".join(re.escape(a) for a in (file.stem, title))
            pattern = re.compile(r"\[\[(?:" + alvos + r")(\|[^\]]+)?\]\]")
            if pattern.search(essay_content):
                continue
            if pattern.search(outro_content):
                corpus.append({
                    "section": "ORPHANS", "severity": "INFO", "code": "ORPHAN_NO_ESSAY",
                    "message": f"{category}: '{title}' ({category}/{file.name}) é citada só por concept/entity/insight, nunca por um essay",
                })
            else:
                corpus.append({
                    "section": "ORPHANS", "severity": "WARNING", "code": "ORPHAN_PAGE",
                    "message": f"{category}: '{title}' ({category}/{file.name}) não é referenciada por nenhuma página",
                })
    return corpus


def check_index(title_map, essay_only_file=None):
    corpus = []

    def add(severity, code, message):
        corpus.append({"section": "INDEX", "severity": severity, "code": code, "message": message})

    index_path = WIKI_ROOT / "index.md"
    if not index_path.exists():
        add("ERROR", "INDEX_MISSING", "wiki/index.md não existe")
        return corpus

    index_content = load(index_path)
    if get_h1(index_content) != "Índice":
        add("ERROR", "INDEX_BAD_TITLE", "index.md título deve ser '# Índice'")

    essay_stems = {file.stem for file in ESSAYS_DIR.glob("*.md")}
    index_links = re.findall(r"\]\(essays/([^\)]+?)\.md\)", index_content)
    for target in index_links:
        if target not in essay_stems:
            add("ERROR", "INDEX_DEAD_LINK", f"index.md tem link morto ou para não-essay: '{target}'")

    if re.search(r"\[\[[^\]]+\]\]", index_content):
        add("ERROR", "INDEX_LEGACY_WIKILINK",
            "index.md tem [[wikilinks]] (formato antigo) — rode `python scripts/build_index.py`")

    essay_titles_to_check = (
        {get_h1(load(essay_only_file))} if essay_only_file else sorted(title_map["essay_titles"])
    )
    for essay_title in essay_titles_to_check:
        if not essay_title or essay_title not in title_map["title_to_file"]:
            continue
        filename = title_map["title_to_file"][essay_title].split("/")[-1]
        stem = filename.replace(".md", "")
        if not re.search(r"\]\(essays/" + re.escape(stem) + r"\.md\)", index_content):
            add("ERROR", "INDEX_MISSING_ESSAY",
                f"Essay '{essay_title}' (essays/{filename}) não aparece em index.md — "
                f"rode `python scripts/build_index.py`")

    return corpus


def check_sources_manifest(essay_titles):
    corpus = []

    def add(severity, code, message):
        corpus.append({"section": "MANIFEST", "severity": severity, "code": code, "message": message})

    manifest_path = SOURCES_DIR / "manifest.md"
    manifest_entries = {}
    if not manifest_path.exists():
        add("ERROR", "MANIFEST_MISSING", "wiki/sources/manifest.md não existe")
    else:
        manifest_content = load(manifest_path)
        entry_blocks = re.split(r"(?m)^## \[(\d{4}-\d{2}-\d{2})\]\s+(.+)$", manifest_content)
        for i in range(1, len(entry_blocks), 3):
            filename, body = entry_blocks[i + 1], entry_blocks[i + 2]
            tipo_m = re.search(r"(?m)^Tipo:\s*(.+?)\.?$", body)
            tags_m = re.search(r"(?m)^Tags:\s*(.+?)\.?$", body)
            pasta_m = re.search(r"(?m)^Pasta:\s*(.+?)\.?$", body)
            virou_m = re.search(r"(?m)^Virou:\s*(.+?)\.?$", body)
            tags_raw = tags_m.group(1).strip() if tags_m else None
            if tags_raw and tags_raw.startswith("[") and tags_raw.endswith("]"):
                tags_raw = tags_raw[1:-1]
            tags = [t.strip().strip('"').strip("'") for t in tags_raw.split(",")] if tags_raw else []
            tags = [t for t in tags if t]
            manifest_entries[filename.strip()] = {
                "tipo": tipo_m.group(1).strip() if tipo_m else None,
                "tags": tags,
                "tags_present": tags_m is not None,
                "pasta": pasta_m.group(1).strip() if pasta_m else None,
                "virou": virou_m.group(1).strip() if virou_m else None,
            }

        files_on_disk = set()
        if SOURCES_DIR.exists():
            for sub in SOURCES_DIR.iterdir():
                if not sub.is_dir() or sub.name in UTILITY_SOURCE_FOLDERS:
                    continue
                for f in sub.iterdir():
                    if f.name == ".gitkeep" or f.is_dir():
                        continue
                    files_on_disk.add(f.name)
                    if f.name not in manifest_entries:
                        add("ERROR", "MANIFEST_MISSING_ENTRY",
                            f"wiki/sources/{sub.name}/{f.name} existe no disco mas não tem entrada em manifest.md")
                    if sub.name not in SOURCE_TYPE_TO_FOLDER.values():
                        add("ERROR", "MANIFEST_BAD_SUBFOLDER",
                            f"wiki/sources/{sub.name}/ não é subpasta do vocabulário controlado")

        # Raw source documents are intentionally local-only (see data/.gitignore).
        # The durable manifest may therefore outlive the local raw file in a clean clone.
        # Validation is one-way: a present raw source needs a manifest entry; the reverse
        # is not required because raw source bytes are deliberately not versioned.
        for filename, entry in manifest_entries.items():
            if entry["tipo"] == "Ensaio Completo Importado":
                # `Virou: None` é uma resposta, não uma omissão: registra que o
                # Usuário examinou a fonte e decidiu que ela não virou essay
                # nenhum. Sem esse valor, a única forma de calar o erro seria
                # apontar para um essay que não existe.
                virou = (entry["virou"] or "").strip()
                if virou.lower().strip('"').strip("'") in MANIFEST_VIROU_NONE:
                    pass
                elif not virou or "[[" not in virou:
                    add("ERROR", "MANIFEST_IMPORTED_NO_ESSAY",
                        f"source '{filename}' é Tipo: Ensaio Completo Importado mas não registra "
                        f"'Virou: [[Essay]]' nem 'Virou: None'")
                elif entry["virou"]:
                    virou_target = re.search(r"\[\[([^\]|]+)", entry["virou"])
                    if virou_target and virou_target.group(1).strip() not in essay_titles:
                        add("ERROR", "MANIFEST_VIROU_TARGET_MISSING",
                            f"source '{filename}' Virou: aponta para '{virou_target.group(1).strip()}', "
                            f"que não existe como título de essay")
            if not entry["tags_present"]:
                add("WARNING", "MANIFEST_NO_TAGS", f"source '{filename}' sem campo 'Tags:' em manifest.md")
            elif not entry["tags"]:
                add("WARNING", "MANIFEST_EMPTY_TAGS", f"source '{filename}' tem 'Tags:' vazio em manifest.md")

    for tipo, subpasta in SOURCE_TYPE_TO_FOLDER.items():
        if not (SOURCES_DIR / subpasta).exists():
            add("WARNING", "SOURCES_SUBFOLDER_MISSING",
                f"wiki/sources/{subpasta}/ (Tipo: {tipo}) não existe — crie com .gitkeep")
    if not HANDOUTS_DIR.exists():
        add("WARNING", "HANDOUTS_DIR_MISSING", "wiki/handouts/ não existe — crie com .gitkeep")

    return corpus


def check_plano():
    corpus = []

    def add(severity, code, message):
        corpus.append({"section": "PLANO", "severity": severity, "code": code, "message": message})

    plano_path = PLAN_DIR / "plano.md"
    if not plano_path.exists():
        add("WARNING", "PLANO_MISSING", "plan/plano.md não existe ainda (normal se /plan nunca foi usado)")
        return corpus

    plano_content = load(plano_path)
    secoes_found = set()
    for part in re.split(r"(?m)^## ", plano_content)[1:]:
        heading = part.split("\n", 1)[0].strip()
        if heading in PLAN_SECOES:
            secoes_found.add(heading)
        elif heading != "Índice":
            add("ERROR", "PLANO_UNKNOWN_SECTION",
                f"plan/plano.md tem seção '## {heading}' fora do vocabulário fechado")
    for secao in PLAN_SECOES:
        if secao not in secoes_found:
            add("ERROR", "PLANO_MISSING_SECTION", f"plan/plano.md sem a seção '## {secao}'")
    for sv in re.findall(r"(?m)^- Status:\s*(.+)$", plano_content):
        if sv.strip() not in ("Pendente", "Em Andamento"):
            add("ERROR", "PLANO_BAD_STATUS",
                f"item com Status: '{sv.strip()}' fora do vocabulário (Pendente | Em Andamento)")
    return corpus


def check_insights():
    corpus = []

    def add(severity, code, message):
        corpus.append({"section": "INSIGHTS", "severity": severity, "code": code, "message": message})

    if not INSIGHTS_DIR.exists():
        return corpus
    for file in sorted(INSIGHTS_DIR.glob("*.md")):
        content = load(file)
        fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
        fm_data = {}
        if fm_match:
            try:
                fm_data = yaml.safe_load(fm_match.group(1)) or {}
            except Exception:
                pass
        maturidade = fm_data.get("maturidade")
        if maturidade not in MATURIDADES_VALIDAS:
            add("ERROR", "INSIGHT_BAD_MATURIDADE",
                f"insights/{file.name} tem 'maturidade:' inválida ou ausente ('{maturidade}')")
        conexoes_match = re.search(r"## Conexões\s*\n(.*?)(?=\n##|\Z)", content, re.DOTALL)
        if conexoes_match and not re.search(r"\[\[", conexoes_match.group(1)):
            add("WARNING", "INSIGHT_NO_CONEXOES",
                f"insights/{file.name} não tem nenhum [[wikilink]] em Conexões — candidata a órfã")
    return corpus


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser():
    p = argparse.ArgumentParser(
        description="Lint unificado da wiki (formatação de essay + estrutura/grafo)."
    )
    p.add_argument(
        "slug", nargs="?", default=None,
        help="Checa apenas este essay (slug, nome do arquivo, ou caminho completo)."
    )
    p.add_argument(
        "--file", "-f", dest="file_slug", metavar="SLUG", default=None,
        help="Alias de compatibilidade para o slug posicional.",
    )
    p.add_argument(
        "--all", action="store_true",
        help="Corpus inteiro, explícito (comportamento padrão sem argumento).",
    )
    p.add_argument("--json", action="store_true", help="Saída em JSON.")
    p.add_argument(
        "--strict", action="store_true",
        help="Retorna código 1 quando houver CRITICAL ou ERROR; útil para CI.",
    )
    return p


def resolve_essay(slug: str) -> Path:
    p = Path(slug)
    if p.exists():
        return p.resolve()
    for ext in ("", ".md"):
        candidate = ESSAYS_DIR / (slug + ext)
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Essay '{slug}' não encontrado em {ESSAYS_DIR} nem como caminho direto")


def main():
    args = build_parser().parse_args()

    target_slug = args.file_slug or args.slug
    scope_all = args.all or not target_slug

    target_essay = None
    if not scope_all and target_slug:
        try:
            target_essay = resolve_essay(target_slug)
        except FileNotFoundError as e:
            print(f"ERRO: {e}", file=sys.stderr)
            sys.exit(1)

    essay_paths = [target_essay] if target_essay else sorted(ESSAYS_DIR.glob("*.md"))
    essay_results = [check_essay(p) for p in essay_paths]

    corpus_issues = []
    corpus_skipped = False
    if target_essay is not None:
        corpus_skipped = True
        # Ainda faz sentido filtrar wikilinks mortos originados NESTE essay.
        title_map = build_title_map()
        corpus_issues.extend(check_dead_wikilinks(title_map, essay_only_file=target_essay))
        corpus_issues.extend(check_index(title_map, essay_only_file=target_essay))
    else:
        title_map = build_title_map()
        for category, rel_path in title_map["no_h1"]:
            corpus_issues.append({
                "section": "SUPPORT_PAGES", "severity": "CRITICAL", "code": "SUPPORT_NO_H1",
                "message": f"{rel_path}: sem H1 título (# Título)",
            })
        corpus_issues.extend(check_support_pages())
        corpus_issues.extend(check_dead_wikilinks(title_map))
        corpus_issues.extend(check_orphans(title_map))
        corpus_issues.extend(check_index(title_map))
        corpus_issues.extend(check_sources_manifest(title_map["essay_titles"]))
        corpus_issues.extend(check_plano())
        corpus_issues.extend(check_insights())
        try:
            from check_visibility_field import audit as audit_visibility

            _public, _invalid, visibility_errors = audit_visibility()
            for message in visibility_errors:
                corpus_issues.append({
                    "section": "VISIBILITY", "severity": "ERROR",
                    "code": "VISIBILITY_INVALID", "message": message,
                })
        except ImportError:
            corpus_issues.append({
                "section": "VISIBILITY", "severity": "WARNING",
                "code": "VISIBILITY_CHECK_UNAVAILABLE",
                "message": "check_visibility_field.py indisponível",
            })

    if args.json:
        output = {
            "essays": essay_results,
            "corpus": corpus_issues,
            "corpus_skipped": corpus_skipped,
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        all_issues = [i for r in essay_results for i in r["issues"]] + corpus_issues
        return 1 if args.strict and any(i["severity"] in {"CRITICAL", "ERROR"} for i in all_issues) else 0

    # ---- saída human-readable ----
    severity_order = {"CRITICAL": 0, "ERROR": 1, "WARNING": 2, "INFO": 3}
    ICONS = {"CRITICAL": "🔴", "ERROR": "❌", "WARNING": "⚠️ ", "INFO": "ℹ️ "}

    report_lines = []
    total_issues = 0
    clean = 0

    report_lines.append("=== ESSAY LINT ===")
    for result in essay_results:
        name = result["name"]
        issues = result["issues"]
        if not issues:
            report_lines.append(f"✅ {name}")
            clean += 1
            continue
        issues_sorted = sorted(issues, key=lambda x: severity_order.get(x["severity"], 9))
        report_lines.append(f"\n{'─'*60}")
        report_lines.append(f"📄 {name}")
        for issue in issues_sorted:
            icon = ICONS.get(issue["severity"], "•")
            report_lines.append(f"   {icon} [{issue['code']}] {issue['message']}")
        total_issues += len(issues)

    report_lines.append(f"\n{'='*60}")
    report_lines.append(
        f"Resultado essays: {clean}/{len(essay_results)} limpo(s), {total_issues} issue(s)"
    )

    if corpus_skipped:
        report_lines.append(
            "\n=== CORPUS (índice, órfãos, manifesto, plano, insights) ===\n"
            "(pulado — escopo de essay único; wikilinks mortos e index.md filtrados para este essay)"
        )
    else:
        report_lines.append("")

    by_section = {}
    for issue in corpus_issues:
        by_section.setdefault(issue["section"], []).append(issue)

    corpus_total = 0
    for section, issues in by_section.items():
        report_lines.append(f"\n--- {section} ---")
        for issue in sorted(issues, key=lambda x: severity_order.get(x["severity"], 9)):
            icon = ICONS.get(issue["severity"], "•")
            report_lines.append(f"{icon} [{issue['code']}] {issue['message']}")
            corpus_total += 1

    report_lines.append(f"\n{'='*60}")
    report_lines.append(f"Resultado corpus: {corpus_total} issue(s)")

    report_text = "\n".join(report_lines)
    print(report_text)

    if not corpus_skipped:
        output_report_path = OUTPUT_DIR / "comprehensive_lint_output.txt"
        output_report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_report_path, "w", encoding="utf-8") as f:
            f.write(report_text)
        print(f"\nRelatório completo também salvo em {output_report_path}")

    all_issues = [i for r in essay_results for i in r["issues"]] + corpus_issues
    n_critical = sum(1 for i in all_issues if i["severity"] == "CRITICAL")
    n_error = sum(1 for i in all_issues if i["severity"] == "ERROR")
    n_warning = sum(1 for i in all_issues if i["severity"] == "WARNING")
    n_info = sum(1 for i in all_issues if i["severity"] == "INFO")
    print(
        f"\nResumo: {n_critical} CRITICAL, {n_error} ERROR, {n_warning} WARNING, {n_info} INFO"
    )
    return 1 if args.strict and (n_critical or n_error) else 0


if __name__ == "__main__":
    raise SystemExit(main())
