import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from check_wiki import check_callout_prose_duplication, check_consecutive_duplicate_prose  # noqa: E402


def test_callout_prose_duplication_detected_preceding_paragraph():
    body = (
        "## Capítulo 1\n\n"
        "O princípio de correspondência de Bohr estabelece que os resultados quânticos convergem para os clássicos quando os números quânticos se tornam muito grandes.\n\n"
        "> [!abstract] Princípio de Correspondência\n"
        "> O princípio de correspondência de Bohr estabelece que os resultados quânticos convergem para os clássicos quando os números quânticos se tornam muito grandes.\n\n"
        "A evolução contínua da mecânica ondulatória permitiu consolidar este entendimento no limite macroscópico dos sistemas físicos.\n\n"
        "## Referências\n\n"
        "[1] Bohr, N., *Atomic Theory*, 1934. [Link](https://example.com)\n"
    )
    issues = []
    check_callout_prose_duplication(body, lambda sev, code, msg: issues.append((sev, code, msg)))
    codes = [code for _, code, _ in issues]
    assert "CALLOUT_PROSE_DUPLICATION" in codes
    assert any("repete o parágrafo adjacente" in msg or "repete sentença" in msg for _, _, msg in issues)


def test_callout_prose_duplication_detected_following_paragraph():
    body = (
        "## Capítulo 1\n\n"
        "A formulação moderna do modelo padrão apoia-se em simetrias de calibre e no mecanismo de quebra espontânea no vácuo.\n\n"
        "> [!note] Implicação Fundamental\n"
        "> A quebra de simetria eletrofraca concede massa aos bósons vetoriais intermediários enquanto preserva o fóton desprovido de massa de repouso.\n\n"
        "A quebra de simetria eletrofraca concede massa aos bósons vetoriais intermediários enquanto preserva o fóton desprovido de massa de repouso. Esse mecanismo foi comprovado no CERN.\n\n"
        "## Referências\n\n"
        "[1] Weinberg, S., *Model of Leptons*, 1967. [Link](https://example.com)\n"
    )
    issues = []
    check_callout_prose_duplication(body, lambda sev, code, msg: issues.append((sev, code, msg)))
    codes = [code for _, code, _ in issues]
    assert "CALLOUT_PROSE_DUPLICATION" in codes


def test_callout_prose_no_false_positive_on_legitimate_distinct_summary():
    body = (
        "## Capítulo 1\n\n"
        "O experimento da fenda dupla evidencia o comportamento ondulatório de partículas individuais, desafiando a ontologia mecanicista clássica do século dezenove.\n\n"
        "> [!abstract] Tese Central\n"
        "> A interferência quântica demonstra que amplitudes de probabilidade governam a dinâmica microscópica, refutando trajetórias newtonianas pré-determinadas.\n\n"
        "Ao examinar a função de onda no espaço de Hilbert, nota-se que a superposição linear preserva a coerência temporal do estado até a ocorrência de uma medição irreversível.\n\n"
        "## Referências\n\n"
        "[1] Feynman, R., *Lectures on Physics*, 1965. [Link](https://example.com)\n"
    )
    issues = []
    check_callout_prose_duplication(body, lambda sev, code, msg: issues.append((sev, code, msg)))
    assert len(issues) == 0


def test_consecutive_duplicate_prose_detected():
    body = (
        "## Capítulo 1\n\n"
        "A teoria da relatividade geral reformulou a gravitação como uma manifestação geométrica direta da curvatura do espaço-tempo provocada por energia.\n\n"
        "A teoria da relatividade geral reformulou a gravitação como uma manifestação geométrica direta da curvatura do espaço-tempo provocada por energia.\n\n"
        "Outro aspecto importante diz respeito à dilatação gravitacional do tempo observada em campos de intensidade elevada.\n\n"
        "## Referências\n\n"
        "[1] Einstein, A., *Relativity*, 1916. [Link](https://example.com)\n"
    )
    issues = []
    check_consecutive_duplicate_prose(body, lambda sev, code, msg: issues.append((sev, code, msg)))
    codes = [code for _, code, _ in issues]
    assert "CONSECUTIVE_DUPLICATE_PROSE" in codes


def test_consecutive_duplicate_prose_no_false_positives_on_lists_or_math():
    body = (
        "## Capítulo 1\n\n"
        "1. Para pá retangular com torção linear e corte na raiz sob escoamento não constante no disco.\n"
        "2. Para pá retangular com torção linear e sem corte na raiz sob escoamento não constante no disco.\n\n"
        "$$x = \\int_0^1 f(r) dr$$\n\n"
        "$$x = \\int_0^1 f(r) dr$$\n\n"
        "- Item primeiro com texto descritivo detalhado sobre um conceito relevante da formulação aerodinâmica.\n"
        "- Item segundo com texto descritivo detalhado sobre um conceito relevante da formulação aerodinâmica.\n\n"
        "## Referências\n\n"
        "[1] Johnson, W., *Helicopter Theory*, 1980. [Link](https://example.com)\n"
    )
    issues = []
    check_consecutive_duplicate_prose(body, lambda sev, code, msg: issues.append((sev, code, msg)))
    assert len(issues) == 0
