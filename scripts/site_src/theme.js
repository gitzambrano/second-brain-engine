// Controle de tema compartilhado. O valor inicial é aplicado por um trecho
// inline no <head> de cada página, para a primeira pintura já sair na paleta
// certa. O seletor percorre claro → sépia → escuro e persiste a escolha.
(function () {
  var root = document.documentElement;
  var THEMES = ['light', 'sepia', 'dark'];
  var NAMES = { light: 'claro', sepia: 'sépia', dark: 'escuro' };
  var COLORS = { light: '#ffffff', sepia: '#fbf8f1', dark: '#090909' };

  /* Fallback para HTML público já publicado antes do terceiro tema. Os fontes
     CSS também definem a paleta, então builds novos não dependem deste bloco. */
  var compatStyle = document.createElement('style');
  compatStyle.id = 'sb-three-theme-base';
  compatStyle.textContent = "\n:root[data-theme=\"sepia\"]{\n  --bg:#fbf8f1;--bg-soft:#fdfaf4;--panel:#fffdf8;--panel-2:#f3ede3;\n  --surface:#fffaf3;--surface2:#f3ede3;--border:#ded5c8;\n  --text:#39342f;--text-strong:#26211c;--text-bright:#26211c;\n  --muted:#746b62;--faint:#7d7165;--text-dim:#746b62;\n  --line:rgba(74,62,48,.15);--line-strong:rgba(74,62,48,.28);\n  --accent:#785b38;--accent-soft:rgba(117,87,47,.10);--accent-dim:#604626;\n  --gold:#785b38;--gold-dim:#604626;--rust:#8e4636;--rust-bright:#9c4838;--amber:#865a27;\n  --callout-note:#746b62;--note-bg:#f3ede3;--callout-abstract:#77572f;\n  --callout-info:#596b78;--callout-todo:#865a27;--callout-success:#486f50;\n  --callout-question:#77572f;--callout-warning:#8c5f2a;--callout-failure:#8e4636;\n  --callout-danger:#98493e;--callout-bug:#8f4337;--callout-example:#6e536f;\n  --callout-quote:#746b62;--quote-bg:#f3ede3;--box-bg:#fffaf3;\n  --tab-mix:4%;--verdict-mix:6%;--box-verdict-bg:#f3ede3;--th-bg:#eee5d8;\n  --sb-bg:#fbf8f1;--sb-surface:#fffdf8;--sb-surface-soft:#fdfaf4;\n  --sb-text:#26211c;--sb-muted:#746b62;--sb-line:rgba(74,62,48,.15);\n  --sb-line-strong:rgba(74,62,48,.28);--sb-primary:#785b38;\n  --sb-primary-soft:rgba(117,87,47,.10);--sb-shadow:0 20px 56px rgba(73,54,32,.12);\n}\n:root[data-theme=\"sepia\"] .masthead{background:#fbf8f1!important;color:var(--text)!important;border-bottom-color:var(--border)!important}\n:root[data-theme=\"sepia\"] .masthead .hero-title{color:var(--text-bright)!important}\n:root[data-theme=\"sepia\"] .cover-map{background-image:url(\"cover-light.png\");background-color:var(--bg);background-blend-mode:multiply}\n.theme-disc{width:19px;height:19px;display:block;flex:none;border-radius:50%;background:conic-gradient(from -90deg,#fff 0 33.333%,#d6bc8b 33.333% 66.666%,#111 66.666% 100%);border:1px solid color-mix(in srgb,var(--text) 30%,transparent);box-shadow:0 0 0 1px color-mix(in srgb,var(--bg) 45%,transparent)}\n";
  document.head.appendChild(compatStyle);

  function normalize(theme) {
    return THEMES.indexOf(theme) < 0 ? 'light' : theme;
  }
  function nextTheme(theme) {
    var at = THEMES.indexOf(normalize(theme));
    return THEMES[(at + 1) % THEMES.length];
  }
  function apply(theme, persist) {
    theme = normalize(theme);
    root.dataset.theme = theme;
    var next = nextTheme(theme);
    var button = document.getElementById('themeToggle');
    if (button) {
      button.removeAttribute('aria-pressed');
      button.setAttribute('aria-label', 'Mudar para tema ' + NAMES[next]);
      button.setAttribute('title', 'Tema ' + NAMES[theme] + ' · próximo: ' + NAMES[next]);
    }
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', COLORS[theme]);
    if (persist) {
      try { localStorage.setItem('sb-theme', theme); } catch (e) { /* private mode */ }
    }
  }

  apply(root.dataset.theme || 'light', false);

  document.getElementById('themeToggle')?.addEventListener('click', function () {
    apply(nextTheme(root.dataset.theme), true);
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
