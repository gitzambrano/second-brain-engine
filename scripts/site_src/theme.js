// Controle de tema compartilhado. O valor inicial é aplicado por um trecho
// inline no <head> de cada página, para a primeira pintura já sair na paleta
// certa. Este arquivo também aplica um pequeno reparo pós-montagem no formulário
// do Kit, que injeta estilos próprios depois do CSS do site.
(function () {
  var root = document.documentElement;

  function apply(theme, persist) {
    root.dataset.theme = theme;
    var button = document.getElementById('themeToggle');
    if (button) {
      button.setAttribute('aria-pressed', String(theme === 'light'));
      button.setAttribute(
        'aria-label', theme === 'light' ? 'Mudar para tema escuro' : 'Mudar para tema claro'
      );
    }
    if (persist) {
      try { localStorage.setItem('sb-theme', theme); } catch (e) { /* private mode */ }
    }
  }

  apply(root.dataset.theme || 'light', false);

  document.getElementById('themeToggle')?.addEventListener('click', function () {
    apply(root.dataset.theme === 'dark' ? 'light' : 'dark', true);
  });

  /* O Kit monta o formulário de forma assíncrona e pode aplicar largura própria
     ao submit depois do CSS do Atlas. Normalize o DOM quando ele aparecer e,
     por fim, iguale a largura física do botão à do campo de e-mail. */
  function important(el, property, value) {
    if (el) el.style.setProperty(property, value, 'important');
  }

  function normalizeSubscribeMount(mount) {
    if (!mount) return;

    mount.querySelectorAll('.formkit-guarantee,[data-element="guarantee"]').forEach(function (el) {
      el.remove();
    });

    mount.querySelectorAll('.formkit-fields').forEach(function (fields) {
      important(fields, 'display', 'grid');
      important(fields, 'grid-template-columns', 'minmax(0,1fr)');
      important(fields, 'align-items', 'stretch');
      important(fields, 'width', '100%');
      important(fields, 'max-width', '100%');
      important(fields, 'box-sizing', 'border-box');
    });

    mount.querySelectorAll('.formkit-fields > *,.formkit-field,.formkit-input,[data-element="submit"],.formkit-submit').forEach(function (el) {
      important(el, 'box-sizing', 'border-box');
      important(el, 'width', '100%');
      important(el, 'max-width', '100%');
      important(el, 'min-width', '0');
      important(el, 'margin-left', '0');
      important(el, 'margin-right', '0');
      important(el, 'align-self', 'stretch');
      important(el, 'justify-self', 'stretch');
    });

    var input = mount.querySelector('.formkit-input');
    if (input) { input.placeholder = 'E-mail'; input.setAttribute('aria-label', 'E-mail'); }
    mount.querySelectorAll('.formkit-powered-by-convertkit-container').forEach(function (el) { el.remove(); });
    var submit = mount.querySelector('.formkit-submit');
    if (!input || !submit) return;

    var width = input.getBoundingClientRect().width;
    if (width > 0) {
      var submitWrapper = submit.closest('[data-element="submit"]');
      [submitWrapper, submit].forEach(function (el) {
        if (!el) return;
        important(el, 'width', width + 'px');
        important(el, 'max-width', width + 'px');
      });
    }
  }

  function normalizeSubscribeForms() {
    normalizeSubscribeMount(document.getElementById('kitEmbedMount'));
    normalizeSubscribeMount(document.getElementById('sbKitEmbedMount'));
  }

  if ('MutationObserver' in window) {
    new MutationObserver(function () {
      requestAnimationFrame(normalizeSubscribeForms);
    }).observe(document.documentElement, { childList: true, subtree: true });
  }

  if ('ResizeObserver' in window) {
    var resizeObserver = new ResizeObserver(function () {
      requestAnimationFrame(normalizeSubscribeForms);
    });
    [document.getElementById('kitEmbedMount'), document.getElementById('sbKitEmbedMount')].forEach(function (mount) {
      if (mount) resizeObserver.observe(mount);
    });
  }

  requestAnimationFrame(normalizeSubscribeForms);
})();
