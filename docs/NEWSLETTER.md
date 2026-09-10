# Newsletter — Kit

A newsletter é uma projeção do Second Brain. O site continua sendo a publicação canônica; o e-mail apenas anuncia um novo essay e aponta para ele.

## Publicar

No front matter de um essay público, `newsletter_issue` é a **única** autorização de envio:

```yaml
visibility: public
newsletter_issue: 1
```

O comportamento padrão é **não enviar** (ausência de `newsletter_issue:`). Adicione `newsletter_issue: 1` para autorizar o anúncio por e-mail da primeira edição.

Campos opcionais de customização do e-mail:

```yaml
newsletter_subject: "Novo essay — Título"
newsletter_summary: "Resumo específico para o e-mail."
newsletter_preview: "Texto curto exibido pelo cliente de e-mail."
```

`newsletter_issue` evita reenvio acidental quando o essay é editado. Só aumente para `2`, `3`, etc. se quiser deliberadamente anunciar uma nova edição do mesmo essay. Não existe `newsletter: true` — o número da edição é a única chave que habilita e rastreia o envio.

### Gatilho de envio

O envio é deliberado e independente de `status:`.

Um essay entra na fila de newsletter somente quando satisfaz ao mesmo tempo:

1. está publicamente autorizado (`visibility: public`, ou `publish: true` legado);
2. contém `newsletter_issue: N` (inteiro positivo `1`, `2`, ...);
3. sua identidade `slug:newsletter_issue` ainda não existia no manifesto anterior;
4. o deploy do GitHub Pages em `main` terminou com sucesso.

Trocar `status: draft` → `revisao` → `finalizado` não envia e-mail. `status:` mede estado editorial; `visibility:` controla publicação pública; `newsletter_issue:` controla anúncio por e-mail. Assim um essay pode estar público e em revisão sem gerar newsletter, e pode ser anunciado depois simplesmente adicionando `newsletter_issue: 1`.

Não há comando extra de publicação: `seal_publication.py` gera automaticamente `site/.github/newsletter-manifest.json`. O manifesto contém apenas metadados públicos e nunca entra no artefato do GitHub Pages.

## E-mail

Padrão gerado automaticamente:

- Assunto: `Novo essay — <título>`
- Preheader: resumo truncado do essay
- Cabeçalho: `Second Brain`
- Título do essay
- Resumo
- Tempo estimado de leitura
- CTA: `Ler o essay completo →`
- Assinatura: `Gustavo Zambrano · Second Brain`

O corpo completo permanece no site. O broadcast é privado no Kit (`public: false`) para não criar uma segunda versão pública do artigo.

## GitHub → Kit

O workflow `.github/workflows/newsletter.yml` do `second-brain-site` só roda depois de um deploy Pages bem-sucedido em `main`.

Configuração no repositório do site:

- Secret `KIT_API_KEY` — API key v4 do Kit.
- Variable `KIT_NEWSLETTER_ENABLED` — `true` habilita envio; qualquer outro valor mantém dry-run.
- Variable `SITE_BASE_URL` — opcional; padrão `https://gitzambrano.github.io/second-brain-site`.
- Variable `KIT_EMAIL_TEMPLATE_ID` — opcional; usa o template padrão da conta quando ausente.

Proteções:

- primeiro deploy cria baseline e não envia nada;
- rerun não duplica broadcast;
- edição comum do essay não reenvia;
- envio real exige `KIT_NEWSLETTER_ENABLED=true` e `KIT_API_KEY`;
- o broadcast só é criado depois de o Pages terminar com sucesso.

## Formulário de assinatura

O Atlas usa o Form Inline do Kit com UID `4fd36350af` dentro de um diálogo compacto aberto pelo botão `Assinar` no header:

```html
<script async data-uid="4fd36350af" src="https://gustavo-jose-zambrano.kit.com/4fd36350af/index.js"></script>
```

O embed é público. A API key nunca vai para HTML ou JavaScript do site. Em telas muito estreitas, o texto `Second Brain` da marca é ocultado e o ícone permanece, preservando `Grafo`, `Assinar` e o seletor de tema no header.
