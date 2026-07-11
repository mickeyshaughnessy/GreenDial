# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Stack

- **Backend:** Python/Flask (`api_server.py` routes → `handlers.py` logic → `s3_storage.py` persistence)
- **Frontend:** Single-page app in `index.html` (vanilla JS, no build step)
- **Storage:** DigitalOcean Spaces (S3-compatible) via boto3 — all data is JSON, no ORM
- **LLM:** OpenRouter via the sibling `listening-ai` package (`utils.completion` / `completion_with_tools` are thin adapters). Agent/prompt definitions stay in `prompts/`.
- **Cron agent:** `agent_runner.py` runs daily via cron on the prod VM — it is NOT part of the web server
- **ListeningAI (reference):** GreenDial is the production reference host for `listening-ai`. `listening_bridge.py` configures Spaces under `greendial/listening_ai/`, mounts the portable API at `/listening`, powers plain chat completions, and runs the agentic health-tool loop through `ChatController.run_loop`.

## Dev server

```bash
# One-time: install ListeningAI from the sibling checkout
pip install -e ../ListeningAI[spaces]

python3 api_server.py   # runs on 0.0.0.0:8012
# Portable ListeningAI API: http://localhost:8012/listening/ping
```

Requires `config.py` (gitignored). Never commit `config.py` — it holds production secrets. The deploy script syncs it to the server separately.

## Tests

```bash
python3 test_integration.py   # hits production at greendial.org, not localhost
python3 test_doc_v2.py        # manual LLM smoke test
```

No pytest/unittest framework. Tests run against prod by default.

## Deploy

**Always push to GitHub before running the deploy script** — the script does `git reset --hard origin/main` on the server, so unpushed commits will be lost.

```bash
git push origin main
bash deploy.sh
```

## Architecture gotchas

- **In-memory cache:** `_cache_store` in `handlers.py` (TTL 60–300 s). Does not survive restarts.
- **In-memory sessions:** `_sessions` dict in `handlers.py`. Not persisted to S3.
- **No ORM:** Read/write user and conversation data directly via `s3_storage.py`. Treat the JSON schema as the contract.
- **Static files in prod:** Nginx serves `index.html` and the other HTML files from `/var/www/greendial/`; Flask only handles `/api` routes in prod.
- **CORS:** All origins allowed (`*`) — intentional, single-tenant deployment.

## Repo etiquette

- `main` is the production branch — commits here deploy to greendial.org.
- `config.py` must never be committed (it's gitignored and synced by `deploy.sh`).
