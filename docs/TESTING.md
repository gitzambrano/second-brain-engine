# 🧪 Testing and Repository Quality Gates

> Testes automatizados e quality gates do **`second-brain-engine`**.

O engine não versiona corpus pessoal. Testes usam `tests/fixtures/mini-brain/` sob `tmp_path`; nunca grave no `data/` ativo. Scripts e testes resolvem caminhos por `scripts/repo_paths.py`:

```text
CODE_ROOT   → engine público
DATA_ROOT   → data/ ou SECOND_BRAIN_DATA_ROOT
SITE_ROOT   → site/ ou SECOND_BRAIN_SITE_ROOT
```

---

## 🚦 Quality Gates

| Comando | Finalidade |
| :--- | :--- |
| `python scripts/check_repo.py` | diagnóstico completo |
| `python scripts/check_repo.py --quick` | contratos rápidos e isolamento |
| `python scripts/check_repo.py --wiki` | wiki, frescor e publicação |
| `python scripts/check_repo.py --exports` | exports e paridade documental |
| `python scripts/check_repo.py --site` | privacidade, browser audit e budget do site |
| `python scripts/check_repo.py --architecture` | três Gits, paths e cadeia `.agents/` → mirrors/adapters |
| `python -m pytest -q -m browser` | auditoria em Chromium: home, essay e mapas; claro, escuro e mobile |

Grupos dependentes de corpus ou ferramentas ausentes devem retornar `SKIP`, não acessar dados privados.

### Contratos de scripts e agentes

```bash
python scripts/check_script_defaults.py
python scripts/check_skills.py
python scripts/sync_skills.py --check
python -m pytest tests/test_agent_sync_contract.py
```

- Scripts executáveis devem ter default seguro e útil.
- `.agents/` é a fonte editável; `.claude/skills/` e `.claude/agents/` são mirrors gerados.
- Drift de mirror é erro; corrija em `.agents/` e rode `python scripts/sync_skills.py`.

---

## 🛡️ Privacidade do Site

```bash
python scripts/build_site.py --check
python scripts/check_site_privacy.py
```

`tests/test_site_privacy.py` deve garantir:

- `private`: metadata permitida no catálogo/mapa; corpo e link de leitura proibidos.
- `hidden`: metadata, slug, nó, corpo e links não podem aparecer na saída pública.
- caminhos para `data/` e corpos não autorizados nunca podem vazar.

**Nunca enfraqueça ou desative esse gate.**

---

## 🏃 Pytest

Suíte rápida/core:

```bash
python -m pytest -q -m "not html and not pdf and not slow and not browser"
```

Marcadores úteis:

```bash
python -m pytest -m "not slow"
python -m pytest -m html
python -m pytest -m pdf
python -m pytest -m browser
```

`browser` exige Chromium e Pandoc. Rode `python -m pytest -q` sem filtro apenas em ambiente completo.

---

## 📦 Dependências

| Ferramenta | Necessária para |
| :--- | :--- |
| **PyYAML + pytest** | suíte básica |
| **Playwright + Chromium** | testes `browser` e validação visual |
| **Pandoc** | HTML e construção do site nos testes de browser |
| **LuaLaTeX** | PDF |

Instalação do Chromium: `python -m playwright install chromium`.

---

## 🐛 Regressão de Bugs Mecânicos

Bug mecânico determinístico: adicione regressão ao `mini-brain`, confirme falha antes do fix e passagem depois, então rode o gate aplicável.

Nunca use essays reais do repositório privado como fixture.
