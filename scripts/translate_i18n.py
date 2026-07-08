#!/usr/bin/env python3
"""
Builds i18n/zh.json and i18n/ja.json from i18n/strings.json via OpenRouter.

This is an offline, ahead-of-time step — it is never called on the request
path. Run it whenever i18n/strings.json changes (i.e. whenever English UI
text changes) so the pre-translated JSON files stay in sync and can be
committed to the repo. See AGENTS.md for the full workflow.

Usage:
    python3 scripts/translate_i18n.py              # translate only new/changed keys
    python3 scripts/translate_i18n.py --force       # retranslate everything
    python3 scripts/translate_i18n.py --lang zh     # just one language
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config  # noqa: E402
import utils  # noqa: E402

STRINGS_PATH = ROOT / "i18n" / "strings.json"
BATCH_SIZE = 25

LANG_NAMES = {"zh": "Simplified Chinese (Mandarin)", "ja": "Japanese"}

SYSTEM_PROMPT = """You are translating UI text for GreenDial, a free AI health companion web app, from English into {lang_name}.

Rules:
- Translate naturally and concisely, matching the tone of a clean, friendly health app.
- Keep any HTML tags exactly as-is (e.g. <strong>, <code>, <a href="...">, <em>, <br>) — translate only the visible text between them, never the tag names or attributes.
- Keep placeholders, curly-brace variables, numbers, URLs, and code-like tokens (e.g. user_id, POST /bounty, X-API-Key) unchanged.
- Keep product/proper names untranslated: "GreenDial", "Doc" (the AI coordinator's name), "Cross AI", "UB".
- "Universal Bounty (UB)" — translate "Universal Bounty" but always keep the "(UB)" abbreviation suffix exactly as-is.
- Preserve emoji exactly where they appear.
- Never use a straight double-quote character (") inside a translated string's text — it breaks JSON parsing. If the English text quotes a phrase (e.g. try "Help me sleep better"), render it with curly/typographic quotes appropriate to the target language (e.g. Chinese "…" or 「…」, Japanese 「…」) instead of straight double quotes, or rephrase without quotes. Straight single quotes/apostrophes are fine.
- Return ONLY a single valid JSON object mapping each input key to its translated string, valid enough to pass through a strict JSON parser unmodified. No markdown code fences, no commentary, no extra keys.
"""


def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def strip_code_fence(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def translate_batch(pairs, lang_code):
    lang_name = LANG_NAMES[lang_code]
    prompt = "Translate these UI strings:\n\n" + json.dumps(pairs, indent=2, ensure_ascii=False)
    raw = utils.completion(
        prompt,
        system_prompt=SYSTEM_PROMPT.format(lang_name=lang_name),
        temperature=0.2,
        max_tokens=4000,
    )
    cleaned = strip_code_fence(raw)
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"  ! JSON parse failed for batch of {len(pairs)} keys: {e}", file=sys.stderr)
        print(f"  ! Raw response: {raw[:500]}", file=sys.stderr)
        return {}
    return {k: v for k, v in result.items() if k in pairs}


def translate_lang(lang_code, source, force):
    out_path = ROOT / "i18n" / f"{lang_code}.json"
    existing = {}
    if out_path.exists() and not force:
        existing = json.loads(out_path.read_text(encoding="utf-8"))

    missing_keys = [k for k in source if force or k not in existing or not existing.get(k)]
    if not missing_keys:
        print(f"[{lang_code}] up to date ({len(existing)} keys), nothing to do")
        return

    print(f"[{lang_code}] translating {len(missing_keys)} of {len(source)} keys...")
    result = dict(existing)
    for batch in chunked(missing_keys, BATCH_SIZE):
        pairs = {k: source[k] for k in batch}
        translated = translate_batch(pairs, lang_code)
        result.update(translated)
        missed = set(batch) - set(translated)
        if missed:
            print(f"  ! {len(missed)} key(s) missing from response, will retry next run: {sorted(missed)[:5]}...")
        out_path.write_text(
            json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(f"  ...{len(result)}/{len(source)} keys saved to {out_path.relative_to(ROOT)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="retranslate every key, not just missing ones")
    ap.add_argument("--lang", choices=["zh", "ja"], help="only translate this language")
    args = ap.parse_args()

    if not config.OPENROUTER_API_KEY:
        print("No OPENROUTER_API_KEY configured in config.py", file=sys.stderr)
        sys.exit(1)

    source = json.loads(STRINGS_PATH.read_text(encoding="utf-8"))
    langs = [args.lang] if args.lang else ["zh", "ja"]
    for lang_code in langs:
        translate_lang(lang_code, source, args.force)


if __name__ == "__main__":
    main()
