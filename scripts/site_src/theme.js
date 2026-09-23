// Controle de tema compartilhado. O valor inicial é aplicado por um trecho
// inline no <head> de cada página, para a primeira pintura já sair na paleta
// certa. Um único controlador percorre claro → sépia → escuro e persiste a escolha.
(function () {
  var root = document.documentElement;
  var THEMES = ['light', 'sepia', 'dark'];
  var NAMES = { light: 'claro', sepia: 'sépia', dark: 'escuro' };
  var COLORS = { light: '#ffffff', sepia: '#fbf8f1', dark: '#090909' };
  var CONTROL_SELECTOR = '#themeToggle,#sbTheme,#reader-theme,#sb-theme';

  /* Compatibilidade com HTML público já gerado. O ícone é um SVG geométrico:
     três setores exatos de 120 graus, divisórias radiais e contorno preto. */
  var compatStyle = document.createElement('style');
  compatStyle.id = 'sb-three-theme-base';
  compatStyle.textContent = `
:root[data-theme="sepia"]{
  --bg:#fbf8f1;--bg-soft:#fdfaf4;--panel:#fffdf8;--panel-2:#f3ede3;
  --surface:#fffaf3;--surface2:#f3ede3;--border:#ded5c8;
  --text:#39342f;--text-strong:#26211c;--text-bright:#26211c;
  --muted:#746b62;--faint:#7d7165;--text-dim:#746b62;
  --line:rgba(74,62,48,.15);--line-strong:rgba(74,62,48,.28);
  --accent:#785b38;--accent-soft:rgba(117,87,47,.10);--accent-dim:#604626;
  --gold:#785b38;--gold-dim:#604626;--rust:#8e4636;--rust-bright:#9c4838;--amber:#865a27;
  --callout-note:#746b62;--note-bg:#f3ede3;--callout-abstract:#77572f;
  --callout-info:#596b78;--callout-todo:#865a27;--callout-success:#486f50;
  --callout-question:#77572f;--callout-warning:#8c5f2a;--callout-failure:#8e4636;
  --callout-danger:#98493e;--callout-bug:#8f4337;--callout-example:#6e536f;
  --callout-quote:#746b62;--quote-bg:#f3ede3;--box-bg:#fffaf3;
  --tab-mix:4%;--verdict-mix:6%;--box-verdict-bg:#f3ede3;--th-bg:#eee5d8;
  --sb-bg:#fbf8f1;--sb-surface:#fffdf8;--sb-surface-soft:#fdfaf4;
  --sb-text:#26211c;--sb-muted:#746b62;--sb-line:rgba(74,62,48,.15);
  --sb-line-strong:rgba(74,62,48,.28);--sb-primary:#785b38;
  --sb-primary-soft:rgba(117,87,47,.10);--sb-shadow:0 20px 56px rgba(73,54,32,.12);
}
:root[data-theme="sepia"] .masthead{background:#fbf8f1!important;color:var(--text)!important;border-bottom-color:var(--border)!important}
:root[data-theme="sepia"] .masthead .hero-title{color:var(--text-bright)!important}
.theme-disc{width:14px!important;height:14px!important;display:block!important;flex:none!important;box-sizing:border-box!important;border:0!important;border-radius:50%!important;background:center/100% 100% no-repeat url("data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2014%2014%22%3E%3Cpath%20d%3D%22M7%207L7%201A6%206%200%200%201%2012.196%2010Z%22%20fill%3D%22%23fff%22%2F%3E%3Cpath%20d%3D%22M7%207L12.196%2010A6%206%200%200%201%201.804%2010Z%22%20fill%3D%22%23d6bc8b%22%2F%3E%3Cpath%20d%3D%22M7%207L1.804%2010A6%206%200%200%201%207%201Z%22%20fill%3D%22%23111%22%2F%3E%3Cpath%20d%3D%22M7%207L7%201M7%207L12.196%2010M7%207L1.804%2010%22%20fill%3D%22none%22%20stroke%3D%22%23111%22%20stroke-width%3D%221.25%22%20stroke-linecap%3D%22butt%22%2F%3E%3Ccircle%20cx%3D%227%22%20cy%3D%227%22%20r%3D%226%22%20fill%3D%22none%22%20stroke%3D%22%23111%22%20stroke-width%3D%221.5%22%2F%3E%3C%2Fsvg%3E")!important;box-shadow:none!important;font-size:0!important;line-height:1!important}
.theme-disc::after{content:none!important}
`;
  document.head.appendChild(compatStyle);

  function normalize(theme) {
    return THEMES.indexOf(theme) < 0 ? 'light' : theme;
  }
  function nextTheme(theme) {
    var at = THEMES.indexOf(normalize(theme));
    return THEMES[(at + 1) % THEMES.length];
  }
  function controls() {
    return [].slice.call(document.querySelectorAll(CONTROL_SELECTOR));
  }
  function ensureDisc(button) {
    if (!button.querySelector('.theme-disc')) {
      button.innerHTML = '<span class="theme-disc" aria-hidden="true"></span>';
    }
  }
  function updateControl(button, theme) {
    ensureDisc(button);
    var next = nextTheme(theme);
    button.removeAttribute('aria-pressed');
    button.setAttribute('aria-label', 'Mudar para tema ' + NAMES[next]);
    button.setAttribute('title', 'Tema ' + NAMES[theme] + ' · próximo: ' + NAMES[next]);
  }
  function apply(theme, persist) {
    theme = normalize(theme);
    root.dataset.theme = theme;
    controls().forEach(function (button) { updateControl(button, theme); });
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', COLORS[theme]);
    if (persist) {
      try { localStorage.setItem('sb-theme', theme); } catch (e) { /* private mode */ }
    }
    try {
      document.dispatchEvent(new CustomEvent('sb-theme-change', { detail: { theme: theme } }));
    } catch (e) { /* old browser */ }
  }

  var initialTheme = root.dataset.theme || 'light';
  try {
    var savedTheme = localStorage.getItem('sb-theme');
    if (savedTheme) initialTheme = savedTheme;
  } catch (e) { /* private mode */ }
  apply(initialTheme, false);

  /* Capture phase is intentional. Older exported essays still contain a legacy
     dark↔light handler. Letting both handlers run makes one click advance twice
     and appear to do nothing. This shared controller owns the theme click. */
  document.addEventListener('click', function (event) {
    var button = event.target.closest(CONTROL_SELECTOR);
    if (!button) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    apply(nextTheme(root.dataset.theme), true);
  }, true);

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
