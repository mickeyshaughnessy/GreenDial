#!/usr/bin/env python3
"""
Pulls every translatable English string out of about.html, docs.html, and
index.html into i18n/strings.json — the source-of-truth dictionary that
translate_i18n.py sends to the LLM to produce i18n/zh.json and i18n/ja.json.

Run this after adding/editing any data-i18n / data-i18n-html / data-i18n-attr-*
attribute, or any t('key', 'fallback') call, in the English HTML. It is safe
to re-run any time — it always rebuilds strings.json from what's currently in
the HTML/JS source, which is the single source of truth for English text.
"""
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILES = ["about.html", "docs.html", "index.html"]
OUT = ROOT / "i18n" / "strings.json"

KEY = r"[a-zA-Z0-9_.]+"

# data-i18n="key">plain text<
RE_SIMPLE = re.compile(
    r'data-i18n="(' + KEY + r')"[^>]*>([^<]+)<'
)

# <tag ...data-i18n-html="key"...>inner html (may include nested tags)</tag>
RE_HTML = re.compile(
    r'<(\w+)([^>]*)data-i18n-html="(' + KEY + r')"([^>]*)>(.*?)</\1>',
    re.DOTALL,
)

# a tag carrying one or more data-i18n-attr-<attr>="key"
RE_ATTR_TAG = re.compile(r'<[a-zA-Z][^>]*data-i18n-attr-[a-zA-Z-]+="' + KEY + r'"[^>]*>')
RE_ATTR_PAIR = re.compile(r'data-i18n-attr-([a-zA-Z-]+)="(' + KEY + r')"')

# t('key', 'fallback') or t("key", "fallback") calls in <script> blocks
RE_T_CALL = re.compile(
    r"""t\(\s*(['"])(""" + KEY + r""")\1\s*,\s*(['"])((?:\\.|(?!\3).)*)\3\s*\)"""
)


def unescape_js(s):
    return s.replace("\\'", "'").replace('\\"', '"')


def extract_attr_value(tag_text, attr_name):
    m = re.search(attr_name + r'="([^"]*)"', tag_text)
    return m.group(1) if m else None


def extract_file(path, strings, warnings):
    text = path.read_text(encoding="utf-8")

    # data-i18n and data-i18n-attr-* are applied via textContent/setAttribute,
    # neither of which decodes HTML entities — so the stored source string
    # must already be plain decoded text (e.g. "&" not "&amp;").
    # data-i18n-html is applied via innerHTML, which *does* parse entities,
    # so that value is kept as raw HTML source, entities and all.
    for m in RE_SIMPLE.finditer(text):
        key, value = m.group(1), html.unescape(m.group(2).strip())
        add(strings, warnings, path.name, key, value)

    for m in RE_HTML.finditer(text):
        key, value = m.group(3), m.group(5).strip()
        add(strings, warnings, path.name, key, value)

    for tag_match in RE_ATTR_TAG.finditer(text):
        tag_text = tag_match.group(0)
        for pair in RE_ATTR_PAIR.finditer(tag_text):
            attr_name, key = pair.group(1), pair.group(2)
            value = extract_attr_value(tag_text, attr_name)
            if value is not None:
                add(strings, warnings, path.name, key, html.unescape(value))

    for m in RE_T_CALL.finditer(text):
        key, value = m.group(2), unescape_js(m.group(4))
        add(strings, warnings, path.name, key, value)


def add(strings, warnings, filename, key, value):
    if not value:
        warnings.append(f"{filename}: empty value for key '{key}'")
        return
    if key in strings and strings[key] != value:
        warnings.append(
            f"{filename}: key '{key}' value mismatch:\n"
            f"    existing: {strings[key]!r}\n"
            f"    new:      {value!r}"
        )
        return
    strings[key] = value


def main():
    strings = {}
    warnings = []
    for fname in FILES:
        extract_file(ROOT / fname, strings, warnings)

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps(strings, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(strings)} keys to {OUT.relative_to(ROOT)}")
    if warnings:
        print(f"\n{len(warnings)} warning(s):", file=sys.stderr)
        for w in warnings:
            print(f"  - {w}", file=sys.stderr)


if __name__ == "__main__":
    main()
