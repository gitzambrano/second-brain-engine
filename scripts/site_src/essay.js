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
    '.ref-cite{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif!important;}',
    '.ref-cite-group{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif!important;font-size:.78em!important;line-height:0!important;vertical-align:super!important;white-space:nowrap!important;}',
    '.ref-cite-group .ref-cite{font-size:inherit!important;line-height:inherit!important;vertical-align:baseline!important;padding:0 .04em!important;}',
    '.ref-cite-sep{font-family:inherit!important;font-size:inherit!important;line-height:inherit!important;vertical-align:baseline!important;color:var(--gold)!important;font-weight:600!important;margin-right:.12em!important;}',
    '.content h5{font-family:var(--font-display);font-size:1rem;font-weight:700;margin:1.55rem 0 .5rem;color:color-mix(in srgb,var(--text-bright) 58%,var(--text-dim));}',
    'mjx-container:not([display="true"]){vertical-align:-.5em;font-size:90%;}',
    '@media (max-width:640px){mjx-container[display="true"]{font-size:90%;}}',
    '@media print{body{padding-top:0!important;}.sb-bar,.sb-progress,.sb-toc-fab,.sb-toc,.sb-subscribe-dialog,#lupa,#lupa-fechar,#lupa-dica,#sbThemeToggle,#sbToTop,.hlink{display:none!important;}.content{max-width:none!important;}table{display:table!important;width:100%!important;max-width:100%!important;table-layout:fixed!important;overflow:visible!important;font-size:.82rem!important;}th,td{padding:.45rem .55rem!important;white-space:normal!important;overflow-wrap:anywhere!important;word-break:normal!important;}pre,pre.sourceCode{max-width:100%!important;overflow:visible!important;white-space:pre-wrap!important;overflow-wrap:anywhere!important;word-break:break-word!important;}pre code{white-space:inherit!important;overflow-wrap:anywhere!important;word-break:break-word!important;}code{overflow-wrap:anywhere!important;word-break:break-word!important;}}'
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
  /* theme.js owns the selector. Keeping one click handler avoids the legacy
     dark↔light handler in older exported bodies from advancing the theme twice. */

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
/* --- Podcast do ensaio ------------------------------------------------------ */
(function () {
  'use strict';
  var player = document.querySelector('[data-sb-podcast]');
  if (!player) return;
  var audio = player.querySelector('audio');
  var playBtn = player.querySelector('.sb-pc-play');
  var seek = player.querySelector('.sb-pc-seek');
  var timeEl = player.querySelector('.sb-pc-time');
  var speedBtn = player.querySelector('.sb-pc-speed');
  var SPEEDS = [1, 1.25, 1.5, 1.75, 2];
  var speedIndex = 0;
  var scrubbing = false;
  var title = player.getAttribute('data-title') || document.title;

  function fmt(sec) {
    if (!isFinite(sec) || sec < 0) sec = 0;
    sec = Math.floor(sec);
    var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    var ss = (s < 10 ? '0' : '') + s;
    return h ? h + ':' + (m < 10 ? '0' : '') + m + ':' + ss : m + ':' + ss;
  }
  function clampTime(t) {
    var d = audio.duration;
    return Math.max(0, isFinite(d) ? Math.min(t, d) : t);
  }
  function render() {
    var d = audio.duration, t = audio.currentTime || 0;
    var ready = isFinite(d) && d > 0;
    seek.disabled = !ready;
    if (!scrubbing) seek.value = ready ? Math.round((t / d) * 1000) : 0;
    seek.style.setProperty('--pc-fill', (seek.value / 10) + '%');
    timeEl.textContent = fmt(scrubbing && ready ? (seek.value / 1000) * d : t);
    seek.setAttribute('aria-valuetext', fmt(t) + (ready ? ' de ' + fmt(d) : ''));
  }
  function setPlaying(on) {
    player.classList.toggle('is-playing', on);
    playBtn.setAttribute('aria-label', playBtn.getAttribute(on ? 'data-label-pause' : 'data-label-play'));
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = on ? 'playing' : 'paused';
  }
  function toggle() {
    if (audio.paused) {
      var p = audio.play();
      if (p && p.catch) p.catch(function () { setPlaying(false); });
    } else {
      audio.pause();
    }
  }
  function updatePosition() {
    if (!('mediaSession' in navigator) || !navigator.mediaSession.setPositionState) return;
    var d = audio.duration;
    if (!isFinite(d) || d <= 0) return;
    try {
      navigator.mediaSession.setPositionState({
        duration: d, playbackRate: audio.playbackRate || 1,
        position: Math.min(audio.currentTime || 0, d)
      });
    } catch (e) { /* posição fora do intervalo durante o carregamento */ }
  }
  function skip(delta) {
    audio.currentTime = clampTime((audio.currentTime || 0) + delta);
    render();
    updatePosition();
  }
  function setSpeed(i) {
    speedIndex = i % SPEEDS.length;
    var rate = SPEEDS[speedIndex];
    audio.playbackRate = rate;
    var label = String(rate).replace('.', ',') + '×';
    speedBtn.textContent = label;
    speedBtn.setAttribute('aria-label', 'Velocidade de reprodução: ' + label);
  }

  // Rótulo: forma completa quando cabe numa linha; senão a curta. Nunca corta.
  var labelEl = player.querySelector('.sb-pc-label');
  function fitLabel() {
    if (!labelEl) return;
    player.removeAttribute('data-short');
    labelEl.classList.add('is-measuring');
    var overflows = labelEl.scrollWidth > labelEl.clientWidth + 1;
    labelEl.classList.remove('is-measuring');
    if (overflows) player.setAttribute('data-short', '');
  }
  fitLabel();
  if (window.ResizeObserver) new ResizeObserver(fitLabel).observe(player);
  else window.addEventListener('resize', fitLabel);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fitLabel);

  playBtn.addEventListener('click', toggle);
  player.querySelector('.sb-pc-back').addEventListener('click', function () { skip(-15); });
  player.querySelector('.sb-pc-fwd').addEventListener('click', function () { skip(15); });
  speedBtn.addEventListener('click', function () { setSpeed(speedIndex + 1); });

  seek.addEventListener('input', function () { scrubbing = true; render(); });
  seek.addEventListener('change', function () {
    var d = audio.duration;
    if (isFinite(d) && d > 0) audio.currentTime = (seek.value / 1000) * d;
    scrubbing = false;
    render();
    updatePosition();
  });
  // `preload="none"`: a duração só chega depois do primeiro play, e o slider
  // fica desabilitado até lá. Tocar em qualquer controle pede os metadados.
  player.addEventListener('pointerdown', function () {
    if (!isFinite(audio.duration) && audio.preload === 'none') audio.preload = 'metadata';
  }, { once: true });

  audio.addEventListener('play', function () { setPlaying(true); });
  audio.addEventListener('pause', function () { setPlaying(false); });
  audio.addEventListener('ended', function () { setPlaying(false); render(); });
  ['timeupdate', 'durationchange', 'loadedmetadata', 'seeked'].forEach(function (ev) {
    audio.addEventListener(ev, render);
  });
  ['durationchange', 'loadedmetadata', 'ratechange', 'seeked'].forEach(function (ev) {
    audio.addEventListener(ev, updatePosition);
  });

  // Espaço no slider alterna a reprodução em vez de rolar a página.
  player.addEventListener('keydown', function (event) {
    if (event.target === seek && event.key === ' ') { event.preventDefault(); toggle(); }
  });

  if ('mediaSession' in navigator && window.MediaMetadata) {
    var art = [
      { src: '../assets/icon-light-192.png', sizes: '192x192', type: 'image/png' },
      { src: '../assets/icon-light-512.png', sizes: '512x512', type: 'image/png' }
    ];
    navigator.mediaSession.metadata = new MediaMetadata({
      title: title, artist: 'Second Brain', album: 'Podcasts do Second Brain', artwork: art
    });
    var handlers = {
      play: function () { audio.play(); },
      pause: function () { audio.pause(); },
      seekbackward: function (d) { skip(-((d && d.seekOffset) || 15)); },
      seekforward: function (d) { skip((d && d.seekOffset) || 15); },
      seekto: function (d) {
        if (d && typeof d.seekTime === 'number') {
          audio.currentTime = clampTime(d.seekTime);
          render();
          updatePosition();
        }
      }
    };
    Object.keys(handlers).forEach(function (action) {
      try { navigator.mediaSession.setActionHandler(action, handlers[action]); } catch (e) { /* ação não suportada */ }
    });
  }
  setSpeed(0);
  render();
})();
