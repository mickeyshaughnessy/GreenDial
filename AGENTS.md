# AGENTS.md

Instructions for AI coding agents (and humans) working on GreenDial deploys and translations. See `CLAUDE.md` for general stack/architecture notes — this file covers the deploy mechanics and the i18n pipeline in more depth.

## Deploy process

Production runs on a DigitalOcean (DO) droplet at `root@143.110.131.237`, deployed via `deploy.sh`.

**Always `git push origin main` before running `deploy.sh`.** The script does `git fetch && git reset --hard origin/main` on the server — any local commits you haven't pushed will simply not exist on the server, and any server-side drift gets discarded. There is no separate staging step.

```bash
git push origin main
bash deploy.sh
```

What `deploy.sh` actually does:
1. SSHes in, `git reset --hard origin/main` in `/root/GreenDial` (the server-side clone).
2. Copies a *subset* of files into `/var/www/greendial` (the nginx webroot): `index.html`, `stickers.html`, `api_server.py`, `handlers.py`, `manifest.json`, `sw.js`, `icons/*.png`. These are the files nginx can serve directly as static assets without going through Flask.
3. Every other route — `/about`, `/docs`, `/arazzo`, `/i18n/<file>`, all `/api`-style endpoints — is **not** copied to the webroot. nginx's `try_files` falls through to the Flask app (`@flask` upstream on `:8012`), which serves those directly from `/root/GreenDial` (its working directory) via `send_from_directory(...)` routes in `api_server.py`. This is why `about.html`, `docs.html`, and the `i18n/` directory don't need entries in `deploy.sh`'s `cp` list — pushing them to `origin/main` and running `git reset --hard` on the server is sufficient; Flask picks up the new files immediately from disk.
4. Syncs `config.py` (gitignored, never touched by git reset) separately via `scp`.
5. Restarts `greendial.service`.

If you add a new static HTML page and want nginx to serve it directly (slightly faster, bypasses Flask), add a `cp` line to `deploy.sh`. If you're fine with the Flask-fallback path (true for every low-traffic page today), you don't need to touch `deploy.sh` at all.

## i18n (translations)

GreenDial ships in English (default), Simplified Chinese, and Japanese. The three language buttons ("T" / "中" / "日") live next to Sign In in `index.html`'s header and in the top nav of `about.html`/`docs.html`.

**How it works:** all translation happens ahead of time and is committed to the repo — there is no live translation call on the request path. `i18n/i18n.js` is a small runtime that, based on the visitor's saved language (`localStorage.gd_lang`), fetches a pre-built `/i18n/<lang>.json` dictionary and rewrites tagged DOM elements in place. Switching languages is just a cached JSON fetch, not an LLM call.

**Files:**
- `i18n/strings.json` — the English source-of-truth dictionary (`key: "English text"`), auto-extracted from the HTML/JS — do not hand-edit it.
- `i18n/zh.json`, `i18n/ja.json` — pre-generated translations, committed to the repo. These are what actually get served to visitors.
- `i18n/i18n.js` — runtime: applies `data-i18n` (textContent), `data-i18n-html` (innerHTML, for strings with inline tags like `<strong>`/`<code>`/`<a>`), and `data-i18n-attr-<attr>` (e.g. `data-i18n-attr-placeholder`) to the DOM. Also exposes `window.t(key, fallback)` for strings built in JS template literals (e.g. the Settings/Identity/Activities panels, which don't exist in the DOM until after login) and `window.setLanguage(lang)` for the button handlers.
- `scripts/extract_strings.py` — scans `about.html`, `docs.html`, `index.html` for every `data-i18n`/`data-i18n-html`/`data-i18n-attr-*` attribute and every `t('key', 'fallback')` call, and rebuilds `i18n/strings.json` from what it finds. Safe to re-run anytime; it always reflects current English source.
- `scripts/translate_i18n.py` — calls OpenRouter (same `config.py` credentials as the app) to translate `i18n/strings.json` into `i18n/zh.json` and `i18n/ja.json`, in batches, preserving HTML tags/placeholders/brand names. **Incremental by default** — only translates keys that are new or missing, so editing one FAQ answer doesn't re-translate the other 400 strings. Use `--force` to retranslate everything (e.g. after a wording-style change).

**Whenever you change English UI text** (edit a `data-i18n`/`data-i18n-html` value, add a new tagged element, or add/change a `t('key', 'fallback')` call), the translated files go stale until you regenerate them:

```bash
python3 scripts/extract_strings.py      # rebuild i18n/strings.json from the HTML/JS
python3 scripts/translate_i18n.py       # fill in zh.json/ja.json for new/changed keys only
```

Then commit `i18n/strings.json`, `i18n/zh.json`, and `i18n/ja.json` alongside the HTML change, push, and deploy as usual. Do not commit an HTML change that adds/edits `data-i18n*` content without also regenerating and committing the translation files — otherwise zh/ja visitors silently fall back to whatever English text was last translated (or see nothing, if the key is brand new).

**Scope note:** live AI chat replies (Doc and the specialist agents) are intentionally left in English regardless of the selected UI language — they're generated fresh per conversation and can't be pre-cached the way static UI text can. Only the app chrome, onboarding, settings, and the About/Docs pages are translated. `docs.html`'s code blocks (curl/JSON examples) are also left in English on purpose, since they're API syntax, not prose.
