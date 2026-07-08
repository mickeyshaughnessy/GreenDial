// GreenDial i18n runtime.
// English is the default and lives directly in each page's HTML — no
// translation file is loaded or applied for 'en'. For 'zh'/'ja', this
// fetches the pre-generated /i18n/<lang>.json dictionary (built ahead of
// time by scripts/translate_i18n.py from i18n/strings.json) and rewrites
// every tagged element in place. There is no live translation call on the
// request path, so switching language is just a cached JSON fetch.
(function () {
  var SUPPORTED = ['en', 'zh', 'ja'];
  var STORAGE_KEY = 'gd_lang';
  var LABELS = { en: 'T', zh: '中', ja: '日' };
  var NAMES = { en: 'English', zh: '中文', ja: '日本語' };

  function getLang() {
    var saved = null;
    try { saved = localStorage.getItem(STORAGE_KEY); } catch (e) {}
    return SUPPORTED.indexOf(saved) !== -1 ? saved : 'en';
  }

  function applyDict(dict) {
    document.querySelectorAll('[data-i18n]').forEach(function (el) {
      var key = el.getAttribute('data-i18n');
      if (dict[key]) el.textContent = dict[key];
    });
    document.querySelectorAll('[data-i18n-html]').forEach(function (el) {
      var key = el.getAttribute('data-i18n-html');
      if (dict[key]) el.innerHTML = dict[key];
    });
    Array.prototype.slice.call(document.querySelectorAll('*')).forEach(function (el) {
      for (var i = 0; i < el.attributes.length; i++) {
        var attr = el.attributes[i];
        if (attr.name.indexOf('data-i18n-attr-') === 0) {
          var targetAttr = attr.name.slice('data-i18n-attr-'.length);
          var key = attr.value;
          if (dict[key]) el.setAttribute(targetAttr, dict[key]);
        }
      }
    });
  }

  function setActiveButtons(lang) {
    document.querySelectorAll('.lang-btn').forEach(function (btn) {
      btn.classList.toggle('active', btn.getAttribute('data-lang') === lang);
    });
  }

  function reveal() {
    document.documentElement.classList.remove('i18n-loading');
  }

  var cache = window.__gdI18nCache = window.__gdI18nCache || {};

  function notifyChange(lang) {
    if (typeof window.onGdLanguageChange === 'function') window.onGdLanguageChange(lang);
  }

  function loadAndApply(lang, persist) {
    document.documentElement.setAttribute('lang', lang === 'en' ? 'en' : lang);
    setActiveButtons(lang);
    if (persist) {
      try { localStorage.setItem(STORAGE_KEY, lang); } catch (e) {}
    }
    if (lang === 'en') {
      reveal();
      notifyChange(lang);
      return;
    }
    if (cache[lang]) {
      applyDict(cache[lang]);
      reveal();
      notifyChange(lang);
      return;
    }
    fetch('/i18n/' + lang + '.json', { cache: 'force-cache' })
      .then(function (r) { return r.json(); })
      .then(function (dict) {
        cache[lang] = dict;
        applyDict(dict);
      })
      .catch(function (err) {
        console.error('i18n: failed to load', lang, err);
      })
      .finally(function () { reveal(); notifyChange(lang); });
  }

  window.setLanguage = function (lang) {
    if (SUPPORTED.indexOf(lang) === -1) return;
    loadAndApply(lang, true);
  };

  // t(key, fallback): for JS-rendered strings (innerHTML templates built at
  // runtime, e.g. the Settings/Identity/Activities panels) that data-i18n
  // can't reach because they don't exist in the DOM until after login.
  window.t = function (key, fallback) {
    var lang = getLang();
    if (lang === 'en') return fallback;
    var dict = cache[lang];
    return (dict && dict[key]) || fallback;
  };

  window.gdCurrentLang = getLang;
  window.gdI18nLabels = LABELS;
  window.gdI18nNames = NAMES;

  // Hide content until translation is applied for non-English visitors, to
  // avoid a flash of English text. Runs as soon as this script executes.
  var initialLang = getLang();
  if (initialLang !== 'en') {
    document.documentElement.classList.add('i18n-loading');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { loadAndApply(initialLang, false); });
  } else {
    loadAndApply(initialLang, false);
  }
})();
