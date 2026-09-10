from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def replace_one(path: Path, old: str, new: str, label: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected 1 occurrence, got {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


# Landing popup.
index = ROOT / "scripts/site_src/index.html"
replace_one(index,
    '.subscribe-dialog-note{margin:-4px 24px 24px;padding:0;color:var(--muted);font-size:11.5px;line-height:1.5}',
    '.subscribe-dialog-note{margin:-4px 24px 24px;padding:0;color:var(--muted);font-size:13.5px;line-height:1.55}',
    'landing note size')
replace_one(index,
    '.subscribe-embed .formkit-input{width:100%!important;min-height:44px!important;margin:0!important;padding:0 13px!important;',
    '.subscribe-embed .formkit-input{box-sizing:border-box!important;width:100%!important;min-height:44px!important;margin:0!important;padding:0 13px!important;',
    'landing input box sizing')
replace_one(index,
'''  <div class="subscribe-dialog-head">
    <p class="subscribe-dialog-eyebrow">Ensaios · Second Brain</p>
    <h2 id="subscribeTitle">Novos ensaios por e-mail.</h2>
    <p class="subscribe-dialog-lede">Só quando houver publicação nova.</p>
    <form method="dialog"><button class="subscribe-close" type="submit" aria-label="Fechar">×</button></form>
  </div>''',
'''  <div class="subscribe-dialog-head">
    <h2 id="subscribeTitle">Receba novos ensaios por email.</h2>
    <form method="dialog"><button class="subscribe-close" type="submit" aria-label="Fechar">×</button></form>
  </div>''',
    'landing popup heading')
replace_one(index,
    '<p class="subscribe-dialog-note"><strong>Importante:</strong> confira também a pasta de <strong>Spam</strong> e confirme o e-mail.</p>',
    '<p class="subscribe-dialog-note"><u>Confirme</u> o e-mail recebido. Verifique a <u>caixa de spam</u>. Marque o email como confiável. Você não receberá mensagens de spam.</p>',
    'landing popup note')

# Essay popup markup.
renderer = ROOT / "scripts/lib/render_public_essay.py"
replace_one(renderer,
'''  <div class="sb-subscribe-dialog-head">
    <p class="sb-subscribe-eyebrow">Ensaios · Second Brain</p>
    <h2 id="sbSubscribeTitle">Novos ensaios por e-mail.</h2>
    <p>Só quando houver publicação nova.</p>
    <form method="dialog"><button class="sb-subscribe-close" type="submit" aria-label="Fechar">×</button></form>
  </div>''',
'''  <div class="sb-subscribe-dialog-head">
    <h2 id="sbSubscribeTitle">Receba novos ensaios por email.</h2>
    <form method="dialog"><button class="sb-subscribe-close" type="submit" aria-label="Fechar">×</button></form>
  </div>''',
    'essay popup heading')
replace_one(renderer,
    '<p class="sb-subscribe-note"><strong>Importante:</strong> confira também a pasta de <strong>Spam</strong> e confirme o e-mail.</p>',
    '<p class="sb-subscribe-note"><u>Confirme</u> o e-mail recebido. Verifique a <u>caixa de spam</u>. Marque o email como confiável. Você não receberá mensagens de spam.</p>',
    'essay popup note')

# Essay popup CSS.
css = ROOT / "scripts/site_src/essay-theme.css"
replace_one(css,
    '.sb-subscribe-note{margin:-4px 24px 24px!important;padding:0;color:var(--sb-muted)!important;font:11.5px/1.5 Inter,ui-sans-serif,system-ui,sans-serif!important;}',
    '.sb-subscribe-note{margin:-4px 24px 24px!important;padding:0;color:var(--sb-muted)!important;font:13.5px/1.55 Inter,ui-sans-serif,system-ui,sans-serif!important;}',
    'essay note size')
replace_one(css,
    '.sb-subscribe-embed .formkit-input{width:100%!important;min-height:44px!important;margin:0!important;padding:0 13px!important;',
    '.sb-subscribe-embed .formkit-input{box-sizing:border-box!important;width:100%!important;min-height:44px!important;margin:0!important;padding:0 13px!important;',
    'essay input box sizing')

# Contract checks.
for path in (index, renderer):
    text = path.read_text(encoding='utf-8')
    assert 'Receba novos ensaios por email.' in text
    assert '<u>Confirme</u> o e-mail recebido.' in text
    assert '<u>caixa de spam</u>' in text
    assert 'Você não receberá mensagens de spam.' in text
    assert 'Só quando houver publicação nova.' not in text

assert 'box-sizing:border-box!important;width:100%!important;min-height:44px' in index.read_text(encoding='utf-8')
assert 'box-sizing:border-box!important;width:100%!important;min-height:44px' in css.read_text(encoding='utf-8')
print('subscribe popup source patch PASS')
