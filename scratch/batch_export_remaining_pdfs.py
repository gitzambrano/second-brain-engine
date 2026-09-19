import subprocess
import sys
from pathlib import Path

essays_to_export = [
    "a-historia-da-aviacao-como-um-jogo-estrategico",
    "por-que-um-rotor-nao-e-um-giroscopio",
    "o-espaco-de-todos-os-avioes-possiveis",
    "aplicacao-de-modelos-de-ia-generativa-em-dinamica-de-voo-de-aeronaves",
    "xadrez-computacional-do-brute-force-as-redes-neurais",
    "validacao-estocastica-de-dinamica-de-voo-de-hume-ao-p-value",
]

for slug in essays_to_export:
    print(f"[*] Compilando PDF: {slug}...")
    cmd = [sys.executable, "scripts/export_essay_pdf.py", slug]
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if res.returncode == 0:
        print(f"    [OK] PDF gerado com sucesso.")
    else:
        print(f"    [ERRO] Falha na geracao:\n{res.stderr}")
