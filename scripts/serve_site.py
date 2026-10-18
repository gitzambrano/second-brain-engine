#!/usr/bin/env python3
"""serve_site.py - Servidor HTTP local leve para inspeção do site público gerado.

Inicia um servidor HTTP local simples (http.server) servindo os arquivos compilados
em SITE_ROOT, permitindo inspecionar o Atlas no navegador antes do deploy público.

Escopo:
    Utilitário read-only de desenvolvimento e inspeção local. Não altera arquivos.

Entradas (Inputs):
    Arquivos compilados em SITE_ROOT.
    Argumentos CLI opcionais:
        --port PORT    Porta TCP para o servidor HTTP (padrão: 8000)

Saídas (Outputs):
    Stdout: URL local de acesso (ex: http://127.0.0.1:8000) e log de requisições.
    Exit code: 0 ao encerrar (Ctrl+C).

Uso:
    python scripts/serve_site.py                  # serve em http://127.0.0.1:8000
    python scripts/serve_site.py --port 8080      # serve na porta 8080
"""
from __future__ import annotations

import argparse
import http.server
import socketserver
from functools import partial

from repo_paths import SITE_ROOT


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()

    if not SITE_ROOT.is_dir():
        raise SystemExit(f"SITE_ROOT not found: {SITE_ROOT}")

    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(SITE_ROOT))
    with socketserver.ThreadingTCPServer(("127.0.0.1", args.port), handler) as server:
        server.allow_reuse_address = True
        print(f"Serving {SITE_ROOT} at http://127.0.0.1:{args.port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
