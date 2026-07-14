/* GreenDial shared nav — injects the top-right hamburger menu into any page's
 * header. index.html ships its own richer hamburger (view switching, admin);
 * this script bails if one is already present. Styles are gdnav- prefixed so
 * they can't collide with per-page CSS. */
(function () {
  if (document.getElementById('hamburger-btn') || document.getElementById('gdnav-btn')) return;
  var header = document.querySelector('.header') || document.querySelector('header');
  if (!header) return;

  var css = [
    '#gdnav-wrap { position: absolute; top: calc(8px + env(safe-area-inset-top, 0px));',
    '  right: calc(12px + env(safe-area-inset-right, 0px)); z-index: 60; }',
    '#gdnav-btn { width: 40px; height: 40px; padding: 0; border: 1px solid rgba(255,255,255,0.15);',
    '  border-radius: 10px; background: rgba(255,255,255,0.06); color: rgba(255,255,255,0.85);',
    '  font-size: 18px; line-height: 1; cursor: pointer; transition: background 0.2s; }',
    '#gdnav-btn:hover { background: rgba(255,255,255,0.14); color: #fff; }',
    '#gdnav-menu { position: absolute; top: calc(100% + 8px); right: 0; width: 250px;',
    '  max-width: calc(100vw - 16px); background: #2a2a4e; border-radius: 12px;',
    '  box-shadow: 0 12px 48px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.08);',
    '  display: none; z-index: 2100; padding: 8px; max-height: min(85dvh, 640px);',
    '  overflow-y: auto; -webkit-overflow-scrolling: touch; box-sizing: border-box; text-align: left; }',
    '#gdnav-menu.show { display: block; }',
    '.gdnav-item { display: flex; align-items: center; gap: 10px; width: 100%;',
    '  padding: 12px; min-height: 46px; border-radius: 8px; color: #eee !important;',
    '  font-size: 14px; text-decoration: none; box-sizing: border-box; white-space: nowrap; }',
    '.gdnav-item:hover, .gdnav-item:active { background: rgba(255,255,255,0.08); color: #fff !important; }',
    '.gdnav-item.active { background: rgba(16,185,129,0.2); color: #10b981 !important; }',
    '.gdnav-divider { height: 1px; background: rgba(255,255,255,0.1); margin: 6px 4px; }'
  ].join('\n');
  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  // [href, default label, data-i18n key (label includes emoji), extra emoji prefix]
  var LINKS = [
    ['/', '💬 Chat', 'app.nav.chat'],
    ['/?view=stickers', '🏷️ Board', 'app.nav.board'],
    ['/?view=history', '📜 History', 'app.nav.history'],
    ['/?view=feedback', '📣 Feedback', 'app.nav.feedback'],
    ['/?view=getstarted', '🚀 Get Started', 'app.nav.getstarted'],
    null,
    ['/about', 'ℹ️ About', 'app.nav.about'],
    ['/docs', '📄 Docs', 'app.nav.docs'],
    ['/arazzo', 'How It Works', 'common.nav.how_it_works', '🧭'],
    ['/sponsor', '💚 Sponsor', null],
    ['/privacy', '🔒 Privacy', 'app.mbn.privacy']
  ];

  var wrap = document.createElement('div');
  wrap.id = 'gdnav-wrap';
  var btn = document.createElement('button');
  btn.type = 'button';
  btn.id = 'gdnav-btn';
  btn.setAttribute('aria-label', 'Menu');
  btn.setAttribute('aria-haspopup', 'true');
  btn.setAttribute('aria-expanded', 'false');
  btn.textContent = '☰';
  var menu = document.createElement('div');
  menu.id = 'gdnav-menu';
  menu.setAttribute('role', 'menu');

  var here = location.pathname.replace(/\/+$/, '') || '/';
  LINKS.forEach(function (link) {
    if (!link) {
      var d = document.createElement('div');
      d.className = 'gdnav-divider';
      menu.appendChild(d);
      return;
    }
    var a = document.createElement('a');
    a.className = 'gdnav-item';
    a.href = link[0];
    if (link[3]) {
      var em = document.createElement('span');
      em.setAttribute('aria-hidden', 'true');
      em.textContent = link[3];
      a.appendChild(em);
    }
    var label = document.createElement('span');
    label.textContent = link[1];
    if (link[2]) label.setAttribute('data-i18n', link[2]);
    a.appendChild(label);
    if (link[0].split('?')[0].replace(/\/+$/, '') === here && link[0].indexOf('?') === -1 && here !== '/') {
      a.classList.add('active');
    }
    menu.appendChild(a);
  });

  wrap.appendChild(btn);
  wrap.appendChild(menu);
  // Pin to the header's top-right corner; reserve a gutter so wrapped header
  // rows can't slide under the button.
  if (getComputedStyle(header).position === 'static') header.style.position = 'relative';
  header.style.paddingRight = 'calc(62px + env(safe-area-inset-right, 0px))';
  header.appendChild(wrap);

  function setOpen(open) {
    if (open) {
      // Anchor below the button but clamp to the viewport — on narrow screens
      // the header can wrap and leave the button far from the right edge.
      var r = btn.getBoundingClientRect();
      var w = Math.min(250, window.innerWidth - 16);
      var right = Math.max(8, Math.round(window.innerWidth - r.right));
      menu.style.position = 'fixed';
      menu.style.top = Math.round(r.bottom + 8) + 'px';
      menu.style.right = Math.min(right, window.innerWidth - w - 8) + 'px';
    }
    menu.classList.toggle('show', open);
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  }
  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    setOpen(!menu.classList.contains('show'));
  });
  document.addEventListener('click', function (e) {
    if (!wrap.contains(e.target)) setOpen(false);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') setOpen(false);
  });
  // Menu is fixed-position; on pages without a sticky header the button
  // scrolls away from it, so just close.
  window.addEventListener('scroll', function () { setOpen(false); }, { passive: true });
})();
