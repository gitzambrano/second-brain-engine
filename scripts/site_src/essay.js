/* Site chrome for an exported essay: floating summary, reading progress and
   the theme toggle. The essay body itself is rendered by the export pipeline
   and is not touched here. */
(function () {
  'use strict';

  var root = document.documentElement;

  /* --- Essay legibility ---------------------------------------------------- */
  /* Keep this tiny runtime override in sync with essay_template.html. Public
     essays embed the template CSS at build time but load this file externally,
     so these rules also repair already-published pages before the next rebuild. */
  var legibilityStyle = document.createElement('style');
  legibilityStyle.id = 'sb-essay-legibility-fixes';
  legibilityStyle.textContent = [
    '.content h5{font-family:var(--font-display);font-size:1rem;font-weight:700;margin:1.55rem 0 .5rem;color:color-mix(in srgb,var(--text-bright) 58%,var(--text-dim));}',
    'mjx-container:not([display="true"]){vertical-align:-.5em;font-size:90%;}',
    '@media (max-width:640px){mjx-container[display="true"]{font-size:90%;}}'
  ].join('\n');
  document.head.appendChild(legibilityStyle);

  /* --- Image captions ------------------------------------------------------ */
  /* The template's historical CSS treated every direct <em> in the paragraph
     after an image as a caption and made it block-level. A normal paragraph
     such as "... o modelo subestima o <em>sink rate</em> principalmente ..."
     was therefore split in three pieces. Classify captions from the DOM
     instead: a caption is a paragraph whose only non-whitespace child is EM,
     or one with an explicit Fig./Figura prefix. */
  var captionStyle = document.createElement('style');
  captionStyle.id = 'sb-image-caption-fix';
  captionStyle.textContent = [
    '.content p:has(> img) + p > em,.content p:has(> picture) + p > em{display:inline;text-align:inherit;font-size:inherit;color:inherit;line-height:inherit;margin-bottom:0;}',
    '.content > p:has(> picture:only-child) + p:not(.sb-image-caption){text-align:start!important;font-size:inherit!important;color:inherit!important;margin-bottom:1.25rem!important;}',
    '@media (min-width:901px){.content > p:has(> picture:only-child) + p:not(.sb-image-caption){text-align:justify!important;}}',
    '.content p.sb-image-caption{text-align:center;font-size:.84em;color:var(--text-dim);line-height:1.5;margin-bottom:2rem;}',
    '.content p.sb-image-caption > em{display:inline;font-size:inherit;color:inherit;line-height:inherit;margin:0;}'
  ].join('\n');
  document.head.appendChild(captionStyle);

  function isImageCaption(paragraph) {
    var nodes = [].slice.call(paragraph.childNodes).filter(function (node) {
      return !(node.nodeType === 3 && !node.textContent.trim());
    });
    var pureEmphasis = nodes.length === 1 && nodes[0].nodeType === 1 && nodes[0].tagName === 'EM';
    var explicitCaption = /^(fig(?:ura)?\.?\s*\d+\b|tira\b)/i.test(paragraph.textContent.trim());
    return pureEmphasis || explicitCaption;
  }

  [].slice.call(document.querySelectorAll('.content p')).forEach(function (paragraph) {
    var previous = paragraph.previousElementSibling;
    if (!previous || previous.tagName !== 'P') return;
    if (!previous.querySelector(':scope > img, :scope > picture')) return;
    if (isImageCaption(paragraph)) paragraph.classList.add('sb-image-caption');
  });

  /* --- Theme --------------------------------------------------------------- */
  var themeButton = document.getElementById('sbTheme');
  function applyTheme(theme, persist) {
    root.dataset.theme = theme;
    if (themeButton) themeButton.setAttribute('aria-pressed', String(theme === 'light'));
    if (persist) {
      try { localStorage.setItem('sb-theme', theme); } catch (e) { /* private mode */ }
    }
  }
  applyTheme(root.dataset.theme || 'dark', false);
  if (themeButton) {
    themeButton.addEventListener('click', function () {
      applyTheme(root.dataset.theme === 'dark' ? 'light' : 'dark', true);
    });
  }

  /* --- Newsletter --------------------------------------------------------- */
  var subscribe = document.getElementById('sbSubscribe');
  var subscribeDialog = document.getElementById('sbSubscribeDialog');
  var kitMount = document.getElementById('sbKitEmbedMount');
  function loadKit() {
    if (!kitMount || kitMount.dataset.loaded) return;
    var script = document.createElement('script');
    script.async = true;
    script.dataset.uid = kitMount.dataset.uid;
    script.src = kitMount.dataset.src;
    kitMount.dataset.loaded = '1';
    kitMount.appendChild(script);
  }
  if (subscribe && subscribeDialog && typeof subscribeDialog.showModal === 'function') {
    subscribe.addEventListener('click', function () { loadKit(); subscribeDialog.showModal(); });
    subscribeDialog.addEventListener('click', function (event) {
      if (event.target === subscribeDialog) subscribeDialog.close();
    });
  }

  /* --- Summary ------------------------------------------------------------- */
  var list = document.getElementById('sbTocList');
  var panel = document.getElementById('sbToc');
  var fab = document.getElementById('sbTocFab');
  if (!list || !panel || !fab) return;

  var used = {};
  function slugify(text) {
    var base = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '')
      .toLowerCase().replace(/[^a-z0-9\s-]/g, '').trim().replace(/[\s-]+/g, '-') || 'secao';
    var seen = used[base] || 0;
    used[base] = seen + 1;
    return seen ? base + '-' + (seen + 1) : base;
  }

  function cleanHeadingText(heading) {
    var clone = heading.cloneNode(true);
    var kicker = clone.querySelector('.sb-kicker');
    var kickerText = kicker ? kicker.textContent.trim() : '';
    if (kicker) kicker.remove();
    var selfnum = clone.querySelector('.sb-selfnum');
    var selfnumText = selfnum ? selfnum.textContent.trim() : '';
    if (selfnum) selfnum.remove();
    var hlink = clone.querySelector('.hlink');
    if (hlink) hlink.remove();

    var baseText = clone.textContent.replace(/\s+/g, ' ').trim();

    if (kickerText) {
      if (!baseText.toLowerCase().startsWith(kickerText.toLowerCase())) {
        return kickerText + ' — ' + baseText;
      }
    } else if (selfnumText) {
      if (!baseText.startsWith(selfnumText)) {
        return selfnumText + ' ' + baseText;
      }
    }
    return baseText;
  }

  var headings = [].slice.call(document.querySelectorAll('.content h2:not(#sumário):not(#sumario), .content h3'));
  if (!headings.length) {
    headings = [].slice.call(document.querySelectorAll('h2:not(#sumário):not(#sumario), h3'));
  }
  headings.forEach(function (heading) {
    if (!heading.id) heading.id = slugify(heading.textContent);
    var link = document.createElement('a');
    link.href = '#' + heading.id;
    link.textContent = cleanHeadingText(heading);
    if (heading.tagName === 'H3') link.className = 'h3';
    list.appendChild(link);
  });

  var links = [].slice.call(list.querySelectorAll('a'));
  if (headings.length && 'IntersectionObserver' in window) {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (!entry.isIntersecting) return;
        links.forEach(function (a) {
          a.classList.toggle('active', a.getAttribute('href') === '#' + entry.target.id);
        });
        var active = links.find(function (a) {
          return a.getAttribute('href') === '#' + entry.target.id;
        });
        if (active && !panel.hidden) {
          active.scrollIntoView({block:'nearest', behavior:'smooth'});
        }
      });
    }, { rootMargin: '-15% 0px -75% 0px' });
    headings.forEach(function (h) { observer.observe(h); });
  }

  function setOpen(open) {
    panel.hidden = !open;
    fab.setAttribute('aria-expanded', String(open));
    try { localStorage.setItem('sb-toc-open', open ? '1' : '0'); } catch (e) { /* private */ }
  }

  // Always starts closed: an open panel lands on top of the title, and the
  // first thing a reader wants is the essay, not its index.
  setOpen(false);

  fab.addEventListener('click', function () { setOpen(panel.hidden); });
  var close = document.getElementById('sbTocClose');
  if (close) close.addEventListener('click', function () { setOpen(false); });

  // Following a link means the reader is done choosing; keep it open on desktop.
  panel.addEventListener('click', function (event) {
    if (event.target.closest('a') && window.innerWidth < 1280) setOpen(false);
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && !panel.hidden) setOpen(false);
  });

  /* --- Reading progress ---------------------------------------------------- */
  var fill = document.getElementById('sbProgressFill');
  if (fill) {
    addEventListener('scroll', function () {
      var max = document.documentElement.scrollHeight - innerHeight;
      fill.style.width = (max > 0 ? (scrollY / max) * 100 : 0) + '%';
    }, { passive: true });
  }
})();
