---
name: essay
description: >
  Escreve um essay, white paper ou estudo novo a partir de outline aprovado em
  plan/drafts/. Use para autoria original; se não houver outline, acione
  /outline. Texto autoral pronto é /import; fonte de terceiro é /digest.
metadata:
  second-brain-role: "author"
  second-brain-mode: "write"
  second-brain-scope: "essay"
  second-brain-approval: "conditional"
  second-brain-closure: "single-essay"
allowed-tools: Bash Read Write Edit Glob Grep WebSearch WebFetch AskUserQuestion
---
# Essay

Cria prosa original a partir de um esboço aprovado. O Usuário define a tese e a direção; o agente pesquisa, estrutura a evidência e redige segundo `conventions/SKILL.md`.

## 1. Pré-condição: esboço aprovado

O brief é `plan/drafts/<slug>.md`.

- **Existe draft:** leia tese, tipo, domínio, capítulos e bullets; não reproponha a estrutura.
- **Não existe:** acione `/outline` e volte apenas quando o esboço estiver aprovado, inclusive aprovação implícita prevista naquela skill.
- **Essay já pronto do autor:** use `/import`, não `/essay`.
- **Sessão parcial:** mantenha o draft e registre `escritos:` no frontmatter. Apague-o somente quando todos os capítulos estiverem incorporados ao essay.

## 2. Pesquisar antes de redigir

1. Busque conteúdo relacionado na wiki com `qmd query`; use `python scripts/find_text.py "tema" --ignore-case` como fallback.
2. Confirme e complete as conexões candidatas do outline.
3. Pesquise fontes externas por capítulo com `WebSearch`/`WebFetch`. Verifique dados, obras, autores, normas e referências antes de usá-los.
4. Parafraseie fontes de terceiros; não reproduza trechos longos.

## 3. Redigir

Escreva `wiki/essays/<slug>.md` em Português do Brasil. Siga integralmente `conventions/SKILL.md`, especialmente frontmatter, estrutura do essay, links, referências, prosa e imagens.

### Domínio filosófico

- Defenda uma tese; não transforme o essay em catálogo neutro de posições.
- Nomeie correntes, pensadores e obras relevantes.
- Trate objeções fortes e responda a elas quando fizer parte da tese.
- Use experimentos mentais quando clarificarem o argumento.
- Apoie afirmações históricas ou interpretativas em fontes verificadas.

### Domínio técnico/engenharia

Exija as quatro camadas quando forem pertinentes:

1. **Mecanismo físico:** explique por que o fenômeno ocorre e como responde aos parâmetros.
2. **Desenvolvimento matemático:** apresente as equações relevantes e derive os passos que carregam a física.
3. **Aplicação concreta:** inclua exemplo numérico ou ordem de grandeza.
4. **Representação visual:** gere plot, gráfico ou diagrama quando a relação quantitativa ficar mais clara visualmente. Siga rigorosamente a paridade bilíngue (<slug>_fig<N>.svg e <slug>_fig<N>_en.svg) e renderização Retina 2x via scripts/svg_to_png.py conforme /diagram e conventions/SKILL.md.

Use normas, papers e livros-texto específicos. Não substitua intuição física por fórmula nem fórmula por descrição qualitativa.

### Domínio misto

Combine as duas abordagens na proporção exigida pela tese.

## 4. Criar páginas de apoio quando necessário

Conceito ou entidade central sem página própria pode gerar `wiki/concepts/` ou `wiki/entities/`.

Antes de criar:

```bash
python scripts/check_title.py "Título"
```

Crie página de apoio apenas quando ela tiver valor além daquele essay. A relação com o essay fica em `## Conexões`, não como remissão interna no corpo.

## 5. Validar e reconstruir derivados

Use o `## Fechamento padrão de essay único` de `conventions/SKILL.md` e confira referências:

```bash
python scripts/check_references.py --file <slug>
python scripts/build_index.py
python scripts/build_references.py
```

Não edite `wiki/index.*` nem `wiki/references.*` manualmente.

Registre:

```markdown
## [YYYY-MM-DD] essay | Título do Essay
Tese: <uma frase>.
Tipo: <tipo>. Conecta com: [[slug|Página]], ...
```

Se o essay veio de `plan/plano.md`, conclua o item via `/plan done`.

## 6. Encerrar

Depois do essay pronto, ofereça `/pdf`, `/html` ou `/handout` conforme o uso. Não gere automaticamente.

## Limites

- Não invente citação, dado ou referência.
- Não escreva sem outline aprovado.
- Não use `/essay` para ingerir texto pronto ou resumir fonte.
- Não duplique regras de formatação aqui; `conventions/SKILL.md` é a fonte normativa.
