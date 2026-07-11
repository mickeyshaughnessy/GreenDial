/**
 * GreenDial UI style runtime.
 *
 * Depends on themes/catalog.js (GD_THEME_CATALOG).
 *
 * Usage on each page:
 *   <html data-gd-page="app">  (or about|docs|stickers|unprompted)
 *   early FOUC script + link skins.css
 *   <script src="/themes/catalog.js"></script>
 *   <script src="/themes/apply.js"></script>
 *   GDThemes.init({ page: 'app', getSessionToken, getUserId, onChange });
 */
(function (global) {
  'use strict';

  const STORAGE_KEY = 'gd_ui_style';
  const cat = () => global.GD_THEME_CATALOG;

  const GDThemes = {
    page: 'app',
    preference: 'page_default', // page_default | theme id
    resolved: 'emerald_protocol',
    _api: '',
    _getUserId: null,
    _getToken: null,
    _onChange: null,

    init(opts) {
      opts = opts || {};
      this.page = opts.page || document.documentElement.getAttribute('data-gd-page') || 'app';
      this._api = opts.api || '';
      this._getUserId = opts.getUserId || null;
      this._getToken = opts.getToken || null;
      this._onChange = opts.onChange || null;

      try {
        const saved = localStorage.getItem(STORAGE_KEY);
        if (saved) this.preference = saved;
      } catch (e) {}

      this.apply();
      return this;
    },

    /** Sync preference from server settings object (when user logs in). */
    hydrateFromSettings(settings) {
      if (!settings) return;
      const v = settings.ui_style;
      if (typeof v === 'string' && v) {
        this.preference = v;
        try { localStorage.setItem(STORAGE_KEY, v); } catch (e) {}
        this.apply();
      }
    },

    resolve() {
      const c = cat();
      if (!c) return 'emerald_protocol';
      if (this.preference === 'page_default' || !this.preference) {
        return c.pageDefaultId(this.page);
      }
      // Full-menu picks apply even if exclusive to another page
      if (c.byId(this.preference)) return this.preference;
      return c.pageDefaultId(this.page);
    },

    apply() {
      this.resolved = this.resolve();
      const root = document.documentElement;
      root.setAttribute('data-gd-theme', this.resolved);
      root.setAttribute('data-gd-page', this.page);
      try { localStorage.setItem('gd_ui_style_resolved', this.resolved); } catch (e) {}

      const meta = cat() && cat().byId(this.resolved);
      const themeColor = (meta && meta.themeColor) || '#1a1a2e';
      let m = document.querySelector('meta[name="theme-color"]');
      if (!m) {
        m = document.createElement('meta');
        m.setAttribute('name', 'theme-color');
        document.head.appendChild(m);
      }
      m.setAttribute('content', themeColor);

      // Refresh any mounted pickers
      document.querySelectorAll('[data-gd-style-picker]').forEach((el) => {
        this.renderPicker(el, el.getAttribute('data-gd-style-picker') || 'full');
      });
      document.querySelectorAll('[data-gd-style-select]').forEach((el) => {
        this.renderSelect(el);
      });

      if (typeof this._onChange === 'function') {
        try { this._onChange(this.preference, this.resolved); } catch (e) {}
      }
      return this.resolved;
    },

    async setPreference(id) {
      this.preference = id || 'page_default';
      try { localStorage.setItem(STORAGE_KEY, this.preference); } catch (e) {}
      this.apply();

      // Persist to account when signed in
      const uid = this._getUserId && this._getUserId();
      if (uid) {
        try {
          await fetch((this._api || '') + '/settings/' + encodeURIComponent(uid), {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ui_style: this.preference }),
          });
        } catch (e) {}
      }
      return this.resolved;
    },

    swatchHtml(theme) {
      const sw = (theme && theme.swatches) || ['#333', '#666', '#999', '#ccc'];
      return '<div class="gd-style-swatches">' +
        sw.map((c) => '<span style="background:' + c + '"></span>').join('') +
        '</div>';
    },

    optionHtml(theme, selectedId, badge) {
      const sel = theme.id === selectedId ? ' selected' : '';
      const badgeHtml = badge
        ? '<span class="gd-style-badge">' + escapeHtml(badge) + '</span>'
        : '';
      return (
        '<button type="button" class="gd-style-option' + sel + '" data-style-id="' +
        escapeHtml(theme.id) + '" onclick="GDThemes.setPreference(\'' +
        escapeHtml(theme.id) + '\')">' +
        this.swatchHtml(theme) +
        '<div class="gd-style-name">' + escapeHtml(theme.name) + '</div>' +
        (theme.category
          ? '<div class="gd-style-meta">' + escapeHtml(theme.category) + '</div>'
          : '') +
        badgeHtml +
        '<div class="gd-style-blurb">' + escapeHtml(theme.blurb || '') + '</div>' +
        '</button>'
      );
    },

    /**
     * mode: 'page' | 'full'
     * - page: page_default + this page's pool (~10)
     * - full: page_default + all themes, grouped
     */
    renderPicker(container, mode) {
      if (!container || !cat()) return;
      mode = mode || 'full';
      const c = cat();
      const pref = this.preference;
      // Highlight the preference (not resolved random) for selection chrome
      const selectedForUi = pref;

      let html = '';
      const pageDefault = c.byId('page_default');
      html += this.optionHtml(
        pageDefault,
        selectedForUi,
        this.preference === 'page_default' ? 'active · ' + (c.byId(this.resolved) || {}).name : 'auto'
      );

      if (mode === 'page') {
        html += '<div class="gd-style-section-title" style="grid-column:1/-1">On this page</div>';
        c.poolForPage(this.page).forEach((t) => {
          html += this.optionHtml(t, selectedForUi, null);
        });
      } else {
        html += '<div class="gd-style-section-title" style="grid-column:1/-1">Always available</div>';
        c.SHARED.forEach((t) => {
          html += this.optionHtml(t, selectedForUi, 'shared');
        });
        Object.keys(c.BY_PAGE).forEach((p) => {
          const label = c.PAGE_LABELS[p] || p;
          html +=
            '<div class="gd-style-section-title" style="grid-column:1/-1">' +
            escapeHtml(label) + ' exclusive</div>';
          c.BY_PAGE[p].forEach((t) => {
            html += this.optionHtml(t, selectedForUi, label);
          });
        });
      }

      container.innerHTML = html;
      // Make grid span correctly for section titles
      container.classList.add('gd-style-picker');
    },

    renderSelect(selectEl) {
      if (!selectEl || !cat()) return;
      const c = cat();
      const pref = this.preference;
      const mode = selectEl.getAttribute('data-gd-style-select') || 'page';
      let opts = [{ id: 'page_default', name: 'Page default (semi-random)' }];
      if (mode === 'full') {
        opts = opts.concat(c.allThemes());
      } else {
        opts = opts.concat(c.poolForPage(this.page));
      }
      selectEl.innerHTML = opts
        .map(
          (t) =>
            '<option value="' +
            escapeHtml(t.id) +
            '"' +
            (t.id === pref ? ' selected' : '') +
            '>' +
            escapeHtml(t.name) +
            '</option>'
        )
        .join('');
      selectEl.onchange = () => this.setPreference(selectEl.value);
    },

    /** Mount full picker into a settings panel group. */
    mountFullPicker(parentEl) {
      if (!parentEl) return;
      let box = parentEl.querySelector('[data-gd-style-picker="full"]');
      if (!box) {
        box = document.createElement('div');
        box.setAttribute('data-gd-style-picker', 'full');
        parentEl.appendChild(box);
      }
      this.renderPicker(box, 'full');
    },

    currentLabel() {
      const c = cat();
      if (!c) return '';
      if (this.preference === 'page_default') {
        const r = c.byId(this.resolved);
        return 'Page default → ' + (r ? r.name : this.resolved);
      }
      const t = c.byId(this.preference);
      return t ? t.name : this.preference;
    },
  };

  function escapeHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  global.GDThemes = GDThemes;
})(typeof window !== 'undefined' ? window : globalThis);
