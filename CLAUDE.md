# Invariante de GitHub Actions — NÃO VIOLAR

- `second-brain-engine`: **NO GITHUB ACTIONS. ZERO.** Não criar `.github/workflows/` nem qualquer workflow de CI, lint, testes, build, QA, sync, cron, documentação ou automação.
- `second-brain-data`: **NO GITHUB ACTIONS. ZERO.** A mesma proibição é absoluta.
- Os **únicos dois GitHub Actions permitidos em todo o ecossistema Second Brain** vivem exclusivamente em `second-brain-site`:
  1. `pages.yml`: gate mínimo de privacidade antes da publicação + deploy no GitHub Pages.
  2. `newsletter.yml`: broadcast da newsletter para o Kit após deploy bem-sucedido.
- O site não deve ter outros workflows (zero CI geral, testes, lint, QA, builds editoriais, sync ou automações adicionais). Testes, lint, QA, build, checks editoriais e demais automações devem rodar localmente pelos scripts do engine, nunca como GitHub Actions.
- Se uma tarefa sugerir criar uma Action em `second-brain-engine` ou `second-brain-data`, a solução está errada: não crie. Se encontrar uma Action nesses repositórios, remova-a.

@AGENTS.md
