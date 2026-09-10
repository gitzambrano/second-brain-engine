#!/usr/bin/env python3
"""
Audita a geometria de paginação e layout dos PDFs, via PyMuPDF.

Checa estouro de margem à direita e à esquerda, título órfão e páginas
anormalmente vazias. O default sem argumentos audita cada ``output/pdf/*.pdf``
e falha em defeito de layout bloqueante; use ``--report-only`` para o antigo
comportamento de sempre sair zero.
"""
from __future__ import annotations

import argparse
import json
import re
import sys

import console_encoding  # noqa: F401
import pymupdf as fitz
from repo_paths import PDF_DIR

TOP_MM, BOTTOM_MM, LEFT_MM, RIGHT_MM = 17.0, 19.0, 19.0, 19.0
MM = 72.0 / 25.4
FOLGA_MARGEM_PT = 3.0
CORPO_MAX = 13.0
VAZIO_LIMITE_PT = 170.0
TITULO_CAPITULO_PT = (17.0, 19.5)
FIGURA_TOPO_MIN_PT = 120.0
FIGURA_TOPO_MAX_Y_PT = 200.0

# Glifos editoriais desenhados em corpo grande não são títulos. Em particular,
# os quotes premium usam aspas curvas grandes; classificá-las só pelo tamanho da
# fonte produz falsos TITULO_ORFAO. A auditoria continua usando a posição desses
# glifos para medir a ocupação visual da página, mas nunca os usa como a última
# linha semântica ao decidir se existe um título órfão.
ORNAMENTO_PURO_RE = re.compile(r"^[\s“”‘’\"'«»‹›]+$")


def eh_ornamento_puro(texto):
    return bool(texto) and bool(ORNAMENTO_PURO_RE.fullmatch(texto))


def linhas_da_pagina(page):
    out = []
    for bloco in page.get_text("dict")["blocks"]:
        if bloco.get("type") != 0:
            continue
        for linha in bloco["lines"]:
            txt = "".join(span["text"] for span in linha["spans"]).strip()
            if txt:
                size = max(span["size"] for span in linha["spans"])
                out.append((linha["bbox"][3], size, txt))
    return sorted(out, key=lambda row: row[0])


def caixas_de_texto(page):
    out = []
    for bloco in page.get_text("dict")["blocks"]:
        if bloco.get("type") != 0:
            continue
        for linha in bloco["lines"]:
            txt = "".join(span["text"] for span in linha["spans"]).strip()
            if txt:
                out.append((linha["bbox"], txt))
    return out


def desenhos_da_pagina(page):
    fundo = 0.0
    for drawing in page.get_drawings():
        fundo = max(fundo, drawing["rect"].y1)
    for image in page.get_image_info():
        fundo = max(fundo, image["bbox"][3])
    return fundo


def primeira_pagina_de_corpo(doc):
    for index, page in enumerate(doc):
        for _, size, _ in linhas_da_pagina(page):
            if TITULO_CAPITULO_PT[0] <= size <= TITULO_CAPITULO_PT[1]:
                return index + 1
    return 3


def figura_grande_no_topo(page):
    """Há conteúdo gráfico de tamanho editorial começando no topo da página?

    O export pode compor uma figura como uma única imagem grande ou como um
    mosaico de painéis. A regra antiga exigia uma imagem individual >200 pt e
    confundia páginas legitimamente encurtadas antes de mosaicos/figuras de
    ~195 pt com PAGINA_VAZADA. 120 pt ainda exclui ícones e pequenos ornamentos,
    mas reconhece um painel que, junto de legenda/margens, pode precisar ser
    empurrado integralmente para a página seguinte.
    """
    for image in page.get_image_info():
        y0, y1 = image["bbox"][1], image["bbox"][3]
        if y0 < FIGURA_TOPO_MAX_Y_PT and y1 - y0 >= FIGURA_TOPO_MIN_PT:
            return True
    for drawing in page.get_drawings():
        rect = drawing["rect"]
        if rect.y0 < FIGURA_TOPO_MAX_Y_PT and rect.y1 - rect.y0 >= FIGURA_TOPO_MIN_PT:
            return True
    return False


def auditar(pdf_path):
    doc = fitz.open(pdf_path)
    achados = []
    inicio = primeira_pagina_de_corpo(doc)
    try:
        for index, page in enumerate(doc):
            page_number = index + 1
            if page_number < inicio:
                continue
            fim_mancha = page.rect.height - BOTTOM_MM * MM
            linhas = [
                line
                for line in linhas_da_pagina(page)
                if line[0] < fim_mancha + 2
            ]
            if not linhas:
                continue
            right_limit = page.rect.width - RIGHT_MM * MM
            for bbox, txt in caixas_de_texto(page):
                if bbox[2] > right_limit + FOLGA_MARGEM_PT:
                    achados.append(
                        {
                            "pagina": page_number,
                            "tipo": "VAZA_MARGEM",
                            "severity": "WARNING",
                            "detalhe": "+%.0fpt: %s" % (bbox[2] - right_limit, txt[:60]),
                        }
                    )
                elif bbox[0] < LEFT_MM * MM - FOLGA_MARGEM_PT:
                    achados.append(
                        {
                            "pagina": page_number,
                            "tipo": "VAZA_MARGEM",
                            "severity": "WARNING",
                            "detalhe": "-%.0fpt: %s"
                            % (LEFT_MM * MM - bbox[0], txt[:60]),
                        }
                    )

            linhas_sem_ornamento = [
                line for line in linhas if not eh_ornamento_puro(line[2])
            ]
            if not linhas_sem_ornamento:
                continue

            # A linha semântica decide TITULO_ORFAO; a linha visual mais baixa
            # continua contando para calcular quanto da página ficou ocupada.
            _, ultimo_tam, ultimo_txt = linhas_sem_ornamento[-1]
            fundo = max(linhas[-1][0], desenhos_da_pagina(page))
            sobra = fim_mancha - fundo
            ultima = page_number == doc.page_count
            if not ultima and ultimo_tam > CORPO_MAX:
                achados.append(
                    {
                        "pagina": page_number,
                        "tipo": "TITULO_ORFAO",
                        "severity": "WARNING",
                        "detalhe": "%.1fpt: %s" % (ultimo_tam, ultimo_txt[:70]),
                    }
                )
            elif not ultima and sobra > VAZIO_LIMITE_PT:
                tipo = (
                    "FIGURA_EMPURRADA"
                    if figura_grande_no_topo(doc[index + 1])
                    else "PAGINA_VAZADA"
                )
                severity = "INFO" if tipo == "FIGURA_EMPURRADA" else "WARNING"
                achados.append(
                    {
                        "pagina": page_number,
                        "tipo": tipo,
                        "severity": severity,
                        "detalhe": "%.0fpt vazios apos: %s" % (sobra, ultimo_txt[:60]),
                    }
                )
        return achados
    finally:
        doc.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slug", nargs="?")
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="never fail on findings (legacy behavior)",
    )
    args = parser.parse_args()
    targets = sorted(PDF_DIR.glob(f"{args.slug or '*'}.pdf")) if PDF_DIR.exists() else []
    if not targets:
        if args.json:
            print("{}")
        else:
            print(f"SKIP: nenhum PDF em {PDF_DIR}")
        return 0

    report = {path.stem: auditar(path) for path in targets}
    report = {key: value for key, value in report.items() if value}
    if args.json:
        # Preserve the historical JSON contract: slug -> list[issue].
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        for slug, findings in sorted(report.items(), key=lambda item: -len(item[1])):
            print(f"\n{slug}  ({len(findings)})")
            for finding in findings:
                print(
                    "   p.%-4d %-16s %-5s %s"
                    % (
                        finding["pagina"],
                        finding["tipo"],
                        finding["severity"],
                        finding["detalhe"],
                    )
                )
        total = sum(map(len, report.values()))
        blocking_count = sum(
            finding["severity"] == "ERROR"
            for findings in report.values()
            for finding in findings
        )
        print(
            f"\n{len(targets)} PDF(s) auditado(s), {total} achado(s), "
            f"{blocking_count} bloqueante(s)"
        )
    blocking = any(
        finding["severity"] == "ERROR"
        for findings in report.values()
        for finding in findings
    )
    return 0 if args.report_only or not blocking else 1


if __name__ == "__main__":
    sys.exit(main())
