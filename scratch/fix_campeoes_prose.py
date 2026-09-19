import re
from pathlib import Path

path = Path("substack/posts/campeoes-por-acaso-por-que-atletas-de-elite-sao-anomalias-estatisticas.md")
text = path.read_text(encoding="utf-8")

# 1. Ajustar os 4 pontos e vírgulas
text = text.replace(
    "O campeão pode ensinar o que fez; não pode concluir, apenas a partir do próprio sucesso, que aquilo que fez foi suficiente para produzir o resultado.",
    "O campeão pode ensinar o que fez, mas não pode concluir, apenas a partir do próprio sucesso, que aquilo que fez foi suficiente para produzir o resultado."
)

text = text.replace(
    "crianças quase um ano mais velhas tendem a ser maiores, mais fortes e mais coordenadas; por isso, são selecionadas com maior frequência",
    "crianças quase um ano mais velhas tendem a ser maiores, mais fortes e mais coordenadas. Por isso, são selecionadas com maior frequência"
)

text = text.replace(
    "o que estimulou o desenvolvimento de uma capacidade aeróbica extraordinária desde a infância; seus pés têm proporções excepcionais para a corrida (tornozelos finos, panturrilhas leves); e sua resposta ao treinamento está no percentil extremo",
    "o que estimulou o desenvolvimento de uma capacidade aeróbica extraordinária desde a infância. Seus pés têm proporções excepcionais para a corrida (tornozelos finos, panturrilhas leves), e sua resposta ao treinamento está no percentil extremo"
)

text = text.replace(
    "vitória é uma conquista; não é prova de que todas as condições que a tornaram possível foram merecidas.",
    "vitória é uma conquista, mas não é prova de que todas as condições que a tornaram possível foram merecidas."
)

# 2. Eliminar travessões (—) no corpo
# Separar frontmatter
parts = text.split("---", 2)
if len(parts) >= 3:
    fm = parts[1]
    body = parts[2]
    # Substituir em body
    body = body.replace(" — ", ", ").replace("—", "-")
    text = "---" + fm + "---\n" + body

path.write_text(text, encoding="utf-8")
print("[OK] Prose and typography fixed!")
