# Invariante de GitHub Actions — NÃO VIOLAR

- `second-brain-engine`: **NO GITHUB ACTIONS. ZERO.** Não criar `.github/workflows/` nem qualquer workflow de CI, lint, testes, build, QA, sync, cron, documentação ou automação.
- `second-brain-data`: **NO GITHUB ACTIONS. ZERO.** A mesma proibição é absoluta.
- A **única GitHub Action permitida em todo o ecossistema Second Brain** vive em `second-brain-site` e existe somente para o **gate mínimo de privacidade antes da publicação + deploy no GitHub Pages**.
- O workflow do site não deve virar CI geral. Testes, lint, QA, build, checks editoriais, newsletter e demais automações devem rodar localmente pelos scripts do engine, nunca como GitHub Actions.
- Se uma tarefa sugerir criar uma Action em `second-brain-engine` ou `second-brain-data`, a solução está errada: não crie. Se encontrar uma Action nesses repositórios, remova-a.

@AGENTS.md
