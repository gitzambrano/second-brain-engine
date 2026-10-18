"""console_encoding.py - Força codificação UTF-8 em stdout e stderr no Windows.

Reconfigura sys.stdout e sys.stderr para UTF-8 com errors="replace", evitando que
caracteres especiais, acentuações e emojis quebrem a execução em terminais cp1252/Windows.

Escopo:
    Módulo utilitário importado no início dos scripts executáveis CLI.

Entradas (Inputs):
    Nenhuma; modifica descritores de stdout/stderr em tempo de execução.

Saídas (Outputs):
    Garante que impressões em console não disparem UnicodeEncodeError.
"""

import sys

for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            # Stream redirecionado para algo que não aceita reconfiguração;
            # seguir sem UTF-8 é melhor do que abortar na importação.
            pass
