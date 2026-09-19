import fitz
from pathlib import Path
import shutil

artifact_dir = Path(r"C:\Users\gusta\.gemini\antigravity\brain\b0f26ea5-e871-4fb6-a877-37f5bb7170b2")
out_dir = Path("substack/screenshots")
out_dir.mkdir(parents=True, exist_ok=True)

targets = [
    ("data/output/pdf/quando-a-distancia-colapsou-por-que-a-aviacao-importa.pdf", "Barreiras Epidemiológicas", "pdf_quando_distancia_page.png"),
    ("data/output/pdf/a-historia-da-aviacao-como-um-jogo-estrategico.pdf", "Radar e Detecção", "pdf_historia_aviacao_mermaid_page.png"),
    ("data/output/pdf/a-historia-da-aviacao-como-um-jogo-estrategico.pdf", "Bloqueio de Coordenação", "pdf_historia_aviacao_callout_page.png"),
    ("data/output/pdf/validacao-estocastica-de-dinamica-de-voo-de-hume-ao-p-value.pdf", "Estrutura de Hipóteses do TOST", "pdf_validacao_tost_page.png"),
]

for pdf_path_str, needle, out_name in targets:
    p = Path(pdf_path_str)
    if not p.exists():
        print("Not found:", p)
        continue
    doc = fitz.open(p)
    found = False
    for page_idx, page in enumerate(doc):
        text = page.get_text()
        if needle.lower() in text.lower():
            pix = page.get_pixmap(dpi=150)
            dest = out_dir / out_name
            pix.save(str(dest))
            shutil.copy2(dest, artifact_dir / dest.name)
            print(f"Rendered {p.name} page {page_idx+1} to {dest.name}")
            found = True
            break
    if not found:
        print(f"Needle '{needle}' not found in {p.name}")
