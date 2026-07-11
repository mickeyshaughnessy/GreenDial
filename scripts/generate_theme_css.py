#!/usr/bin/env python3
"""
Generate themes/skins.css from structured theme palettes.

Run: python3 scripts/generate_theme_css.py
"""
from __future__ import annotations

import os
from textwrap import dedent

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "themes", "skins.css")

# Each theme: id, light?, fonts, palette, extras (pattern kind, radius, etc.)
THEMES = [
    # ── Shared ──────────────────────────────────────────────────────────
    {
        "id": "emerald_protocol",
        "light": False,
        "font": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif",
        "mono": "'SF Mono', Monaco, Menlo, monospace",
        "radius": "12px",
        "pattern": "mesh",
        "bg": "#1a1a2e",
        "bg2": "#12121f",
        "elevated": "#2a2a4e",
        "fg": "#eeeeee",
        "muted": "rgba(255,255,255,0.55)",
        "accent": "#10b981",
        "accent2": "#34d399",
        "danger": "#ef4444",
        "border": "rgba(255,255,255,0.12)",
        "header": "linear-gradient(135deg, rgba(16,185,129,0.18), rgba(26,26,46,0.97))",
        "btn_fg": "#ffffff",
        "glow": "rgba(16,185,129,0.35)",
        "selection": "rgba(16,185,129,0.35)",
    },
    {
        "id": "borland",
        "light": False,
        "font": "'IBM Plex Mono', 'Courier New', Courier, monospace",
        "mono": "'IBM Plex Mono', 'Courier New', monospace",
        "radius": "0px",
        "pattern": "grid",
        "bg": "#000084",
        "bg2": "#00005c",
        "elevated": "#0000aa",
        "fg": "#ffff55",
        "muted": "#aaaa55",
        "accent": "#55ffff",
        "accent2": "#ffffff",
        "danger": "#ff5555",
        "border": "#55ffff",
        "header": "linear-gradient(180deg, #0000aa 0%, #000084 100%)",
        "btn_fg": "#000084",
        "glow": "rgba(85,255,255,0.4)",
        "selection": "rgba(85,255,255,0.35)",
        "btn_bg": "#aaaaaa",
        "extra": "bevel",
    },
    {
        "id": "deep_plasma",
        "light": False,
        "font": "'Segoe UI', system-ui, sans-serif",
        "mono": "ui-monospace, monospace",
        "radius": "16px",
        "pattern": "plasma",
        "bg": "#0b0618",
        "bg2": "#05030d",
        "elevated": "#1a1030",
        "fg": "#f5e8ff",
        "muted": "rgba(240,171,252,0.65)",
        "accent": "#c084fc",
        "accent2": "#22d3ee",
        "danger": "#fb7185",
        "border": "rgba(192,132,252,0.28)",
        "header": "linear-gradient(120deg, rgba(192,132,252,0.25), rgba(34,211,238,0.12), #0b0618)",
        "btn_fg": "#0b0618",
        "glow": "rgba(34,211,238,0.45)",
        "selection": "rgba(192,132,252,0.4)",
    },
    {
        "id": "faster_than_lightspeed",
        "light": False,
        "font": "'Inter', system-ui, sans-serif",
        "mono": "'JetBrains Mono', monospace",
        "radius": "10px",
        "pattern": "starfield",
        "bg": "#020617",
        "bg2": "#000000",
        "elevated": "#0f172a",
        "fg": "#e0f2fe",
        "muted": "rgba(148,163,184,0.85)",
        "accent": "#38bdf8",
        "accent2": "#a78bfa",
        "danger": "#f43f5e",
        "border": "rgba(56,189,248,0.28)",
        "header": "linear-gradient(90deg, rgba(56,189,248,0.15), rgba(167,139,250,0.12), transparent)",
        "btn_fg": "#020617",
        "glow": "rgba(56,189,248,0.5)",
        "selection": "rgba(56,189,248,0.35)",
    },
    {
        "id": "ghost_recon",
        "light": False,
        "font": "'Roboto Condensed', 'Arial Narrow', sans-serif",
        "mono": "'Share Tech Mono', monospace",
        "radius": "4px",
        "pattern": "camo",
        "bg": "#0f1410",
        "bg2": "#0a0e0b",
        "elevated": "#1a2218",
        "fg": "#d9f99d",
        "muted": "rgba(190,242,100,0.55)",
        "accent": "#84cc16",
        "accent2": "#65a30d",
        "danger": "#ef4444",
        "border": "rgba(132,204,22,0.35)",
        "header": "linear-gradient(180deg, #1a2218, #0f1410)",
        "btn_fg": "#0f1410",
        "glow": "rgba(132,204,22,0.4)",
        "selection": "rgba(132,204,22,0.35)",
        "extra": "hud",
    },
    # ── App unique ──────────────────────────────────────────────────────
    {
        "id": "magic_the_gathering",
        "light": False,
        "font": "Georgia, 'Palatino Linotype', serif",
        "mono": "ui-monospace, monospace",
        "radius": "8px",
        "pattern": "filigree",
        "bg": "#1c1410",
        "bg2": "#120e0a",
        "elevated": "#2a1f18",
        "fg": "#f5e6c8",
        "muted": "rgba(245,230,200,0.6)",
        "accent": "#d4a017",
        "accent2": "#7c3aed",
        "danger": "#dc2626",
        "border": "rgba(212,160,23,0.4)",
        "header": "linear-gradient(135deg, rgba(124,58,237,0.35), rgba(212,160,23,0.2), #1c1410)",
        "btn_fg": "#1c1410",
        "glow": "rgba(212,160,23,0.45)",
        "selection": "rgba(124,58,237,0.4)",
        "extra": "ornate",
    },
    {
        "id": "dungeon_crawler_rpg",
        "light": False,
        "font": "'Cinzel', 'Times New Roman', serif",
        "mono": "monospace",
        "radius": "6px",
        "pattern": "stone",
        "bg": "#1a120b",
        "bg2": "#0f0b07",
        "elevated": "#2c2015",
        "fg": "#fef3c7",
        "muted": "rgba(196,165,116,0.75)",
        "accent": "#c4a574",
        "accent2": "#b45309",
        "danger": "#b91c1c",
        "border": "rgba(180,83,9,0.45)",
        "header": "linear-gradient(180deg, #3b2a1a, #1a120b)",
        "btn_fg": "#1a120b",
        "glow": "rgba(245,158,11,0.35)",
        "selection": "rgba(180,83,9,0.4)",
        "extra": "leather",
    },
    {
        "id": "graph_trotterization",
        "light": False,
        "font": "'IBM Plex Sans', system-ui, sans-serif",
        "mono": "'IBM Plex Mono', monospace",
        "radius": "14px",
        "pattern": "graph",
        "bg": "#0f172a",
        "bg2": "#020617",
        "elevated": "#1e293b",
        "fg": "#e2e8f0",
        "muted": "rgba(148,163,184,0.85)",
        "accent": "#60a5fa",
        "accent2": "#34d399",
        "danger": "#f87171",
        "border": "rgba(96,165,250,0.3)",
        "header": "linear-gradient(90deg, rgba(96,165,250,0.2), rgba(52,211,153,0.12), #0f172a)",
        "btn_fg": "#0f172a",
        "glow": "rgba(96,165,250,0.45)",
        "selection": "rgba(52,211,153,0.35)",
    },
    {
        "id": "crt_phosphor",
        "light": False,
        "font": "'VT323', 'Courier New', monospace",
        "mono": "'VT323', monospace",
        "radius": "2px",
        "pattern": "scanlines",
        "bg": "#001100",
        "bg2": "#000800",
        "elevated": "#0a2a0a",
        "fg": "#33ff66",
        "muted": "rgba(51,255,102,0.55)",
        "accent": "#33ff66",
        "accent2": "#9affb0",
        "danger": "#ff3333",
        "border": "rgba(51,255,102,0.4)",
        "header": "linear-gradient(180deg, #0a2a0a, #001100)",
        "btn_fg": "#001100",
        "glow": "rgba(51,255,102,0.55)",
        "selection": "rgba(51,255,102,0.35)",
        "extra": "crt",
    },
    {
        "id": "velvet_clinic",
        "light": False,
        "font": "'Cormorant Garamond', Georgia, serif",
        "mono": "ui-monospace, monospace",
        "radius": "18px",
        "pattern": "softglow",
        "bg": "#1a1020",
        "bg2": "#120a18",
        "elevated": "#2a1a35",
        "fg": "#faf5ff",
        "muted": "rgba(232,180,188,0.7)",
        "accent": "#e8b4bc",
        "accent2": "#9f7aea",
        "danger": "#f43f5e",
        "border": "rgba(232,180,188,0.3)",
        "header": "linear-gradient(135deg, rgba(159,122,234,0.3), rgba(232,180,188,0.15), #1a1020)",
        "btn_fg": "#1a1020",
        "glow": "rgba(232,180,188,0.4)",
        "selection": "rgba(159,122,234,0.35)",
    },
    # ── About unique ────────────────────────────────────────────────────
    {
        "id": "illuminated_manuscript",
        "light": True,
        "font": "'Palatino Linotype', Palatino, Georgia, serif",
        "mono": "monospace",
        "radius": "4px",
        "pattern": "vellum",
        "bg": "#f4ecd8",
        "bg2": "#ebe2c9",
        "elevated": "#fff8ea",
        "fg": "#1c1917",
        "muted": "#57534e",
        "accent": "#7f1d1d",
        "accent2": "#b45309",
        "danger": "#991b1b",
        "border": "rgba(127,29,29,0.25)",
        "header": "linear-gradient(180deg, #fff8ea, #f4ecd8)",
        "btn_fg": "#f4ecd8",
        "glow": "rgba(180,83,9,0.3)",
        "selection": "rgba(180,83,9,0.25)",
        "extra": "manuscript",
    },
    {
        "id": "ethos_marble",
        "light": True,
        "font": "'Source Serif 4', Georgia, serif",
        "mono": "ui-monospace, monospace",
        "radius": "10px",
        "pattern": "marble",
        "bg": "#f8faf9",
        "bg2": "#eef2f0",
        "elevated": "#ffffff",
        "fg": "#1e293b",
        "muted": "#64748b",
        "accent": "#047857",
        "accent2": "#0f766e",
        "danger": "#b91c1c",
        "border": "rgba(4,120,87,0.2)",
        "header": "linear-gradient(180deg, #ffffff, #f0fdf4)",
        "btn_fg": "#ffffff",
        "glow": "rgba(4,120,87,0.25)",
        "selection": "rgba(4,120,87,0.2)",
    },
    {
        "id": "founder_atelier",
        "light": False,
        "font": "'Work Sans', system-ui, sans-serif",
        "mono": "ui-monospace, monospace",
        "radius": "12px",
        "pattern": "sketch",
        "bg": "#1c1917",
        "bg2": "#0c0a09",
        "elevated": "#292524",
        "fg": "#fafaf9",
        "muted": "rgba(168,162,158,0.85)",
        "accent": "#d97706",
        "accent2": "#fbbf24",
        "danger": "#ef4444",
        "border": "rgba(217,119,6,0.35)",
        "header": "linear-gradient(120deg, rgba(217,119,6,0.2), #1c1917)",
        "btn_fg": "#1c1917",
        "glow": "rgba(217,119,6,0.4)",
        "selection": "rgba(217,119,6,0.3)",
    },
    {
        "id": "bounty_treasury",
        "light": False,
        "font": "Georgia, serif",
        "mono": "monospace",
        "radius": "8px",
        "pattern": "coins",
        "bg": "#052e16",
        "bg2": "#022c14",
        "elevated": "#14532d",
        "fg": "#fef3c7",
        "muted": "rgba(253,230,138,0.7)",
        "accent": "#fbbf24",
        "accent2": "#f59e0b",
        "danger": "#f87171",
        "border": "rgba(251,191,36,0.4)",
        "header": "linear-gradient(135deg, rgba(251,191,36,0.25), #052e16)",
        "btn_fg": "#052e16",
        "glow": "rgba(251,191,36,0.45)",
        "selection": "rgba(251,191,36,0.3)",
        "extra": "goldedge",
    },
    {
        "id": "quiet_library",
        "light": False,
        "font": "Georgia, 'Iowan Old Style', serif",
        "mono": "monospace",
        "radius": "6px",
        "pattern": "paper",
        "bg": "#292524",
        "bg2": "#1c1917",
        "elevated": "#3f3a36",
        "fg": "#f5f5f4",
        "muted": "rgba(168,162,158,0.8)",
        "accent": "#fbbf24",
        "accent2": "#d6d3d1",
        "danger": "#f87171",
        "border": "rgba(120,113,108,0.5)",
        "header": "linear-gradient(180deg, #3f3a36, #292524)",
        "btn_fg": "#292524",
        "glow": "rgba(251,191,36,0.3)",
        "selection": "rgba(251,191,36,0.25)",
    },
    # ── Docs unique ─────────────────────────────────────────────────────
    {
        "id": "openapi_blueprint",
        "light": False,
        "font": "'IBM Plex Sans', system-ui, sans-serif",
        "mono": "'IBM Plex Mono', monospace",
        "radius": "4px",
        "pattern": "blueprint",
        "bg": "#0c1a24",
        "bg2": "#061018",
        "elevated": "#132f42",
        "fg": "#e0f2fe",
        "muted": "rgba(125,211,252,0.7)",
        "accent": "#38bdf8",
        "accent2": "#0ea5e9",
        "danger": "#fb7185",
        "border": "rgba(56,189,248,0.35)",
        "header": "linear-gradient(180deg, #132f42, #0c1a24)",
        "btn_fg": "#0c1a24",
        "glow": "rgba(56,189,248,0.4)",
        "selection": "rgba(56,189,248,0.3)",
    },
    {
        "id": "schema_noir",
        "light": False,
        "font": "'Helvetica Neue', Helvetica, Arial, sans-serif",
        "mono": "'SF Mono', monospace",
        "radius": "0px",
        "pattern": "none",
        "bg": "#0a0a0a",
        "bg2": "#000000",
        "elevated": "#171717",
        "fg": "#fafafa",
        "muted": "#a3a3a3",
        "accent": "#fafafa",
        "accent2": "#e5e5e5",
        "danger": "#ef4444",
        "border": "#525252",
        "header": "#0a0a0a",
        "btn_fg": "#0a0a0a",
        "glow": "rgba(255,255,255,0.15)",
        "selection": "rgba(255,255,255,0.2)",
        "extra": "noir",
    },
    {
        "id": "spec_terminal",
        "light": False,
        "font": "ui-monospace, 'Cascadia Code', monospace",
        "mono": "ui-monospace, monospace",
        "radius": "6px",
        "pattern": "scanlines",
        "bg": "#111827",
        "bg2": "#030712",
        "elevated": "#1f2937",
        "fg": "#f3f4f6",
        "muted": "#9ca3af",
        "accent": "#fbbf24",
        "accent2": "#f59e0b",
        "danger": "#f87171",
        "border": "rgba(251,191,36,0.3)",
        "header": "linear-gradient(180deg, #1f2937, #111827)",
        "btn_fg": "#111827",
        "glow": "rgba(251,191,36,0.35)",
        "selection": "rgba(251,191,36,0.3)",
    },
    {
        "id": "courier_manual",
        "light": True,
        "font": "'Courier New', Courier, monospace",
        "mono": "'Courier New', monospace",
        "radius": "2px",
        "pattern": "paper",
        "bg": "#f5f0e6",
        "bg2": "#ebe4d4",
        "elevated": "#fffcf5",
        "fg": "#1f2937",
        "muted": "#57534e",
        "accent": "#991b1b",
        "accent2": "#b91c1c",
        "danger": "#7f1d1d",
        "border": "rgba(31,41,55,0.25)",
        "header": "linear-gradient(180deg, #fffcf5, #f5f0e6)",
        "btn_fg": "#f5f0e6",
        "glow": "rgba(153,27,27,0.25)",
        "selection": "rgba(153,27,27,0.15)",
        "extra": "stamp",
    },
    {
        "id": "grid_reference",
        "light": True,
        "font": "'Helvetica Neue', Helvetica, Arial, sans-serif",
        "mono": "ui-monospace, monospace",
        "radius": "0px",
        "pattern": "swiss",
        "bg": "#ffffff",
        "bg2": "#f5f5f5",
        "elevated": "#ffffff",
        "fg": "#000000",
        "muted": "#525252",
        "accent": "#2563eb",
        "accent2": "#1d4ed8",
        "danger": "#dc2626",
        "border": "#000000",
        "header": "#ffffff",
        "btn_fg": "#ffffff",
        "glow": "rgba(37,99,235,0.2)",
        "selection": "rgba(37,99,235,0.2)",
        "extra": "swiss",
    },
    # ── Stickers unique ─────────────────────────────────────────────────
    {
        "id": "scrapbook_pastel",
        "light": True,
        "font": "'Nunito', 'Segoe UI', sans-serif",
        "mono": "monospace",
        "radius": "16px",
        "pattern": "washi",
        "bg": "#fff7ed",
        "bg2": "#ffedd5",
        "elevated": "#ffffff",
        "fg": "#431407",
        "muted": "#9a3412",
        "accent": "#fb7185",
        "accent2": "#a78bfa",
        "danger": "#e11d48",
        "border": "rgba(251,113,133,0.35)",
        "header": "linear-gradient(90deg, #fecdd3, #ddd6fe, #a5f3fc)",
        "btn_fg": "#ffffff",
        "glow": "rgba(251,113,133,0.35)",
        "selection": "rgba(167,139,250,0.3)",
    },
    {
        "id": "emoji_arcade",
        "light": False,
        "font": "'Press Start 2P', system-ui, sans-serif",
        "mono": "monospace",
        "radius": "8px",
        "pattern": "arcade",
        "bg": "#1e0338",
        "bg2": "#0f021c",
        "elevated": "#3b0764",
        "fg": "#fdf4ff",
        "muted": "rgba(240,171,252,0.7)",
        "accent": "#f0abfc",
        "accent2": "#22d3ee",
        "danger": "#f43f5e",
        "border": "rgba(240,171,252,0.4)",
        "header": "linear-gradient(90deg, #86198f, #0e7490)",
        "btn_fg": "#1e0338",
        "glow": "rgba(34,211,238,0.5)",
        "selection": "rgba(240,171,252,0.35)",
        "extra": "neon",
    },
    {
        "id": "polaroid_wall",
        "light": False,
        "font": "'Comic Sans MS', 'Segoe Print', cursive",
        "mono": "monospace",
        "radius": "4px",
        "pattern": "cork",
        "bg": "#44403c",
        "bg2": "#292524",
        "elevated": "#57534e",
        "fg": "#fafaf9",
        "muted": "rgba(214,211,209,0.75)",
        "accent": "#f59e0b",
        "accent2": "#fafaf9",
        "danger": "#ef4444",
        "border": "rgba(250,250,249,0.25)",
        "header": "linear-gradient(180deg, #57534e, #44403c)",
        "btn_fg": "#292524",
        "glow": "rgba(245,158,11,0.35)",
        "selection": "rgba(245,158,11,0.3)",
    },
    {
        "id": "bubble_pop",
        "light": True,
        "font": "'Quicksand', 'Segoe UI', sans-serif",
        "mono": "monospace",
        "radius": "24px",
        "pattern": "bubbles",
        "bg": "#ecfeff",
        "bg2": "#cffafe",
        "elevated": "#ffffff",
        "fg": "#164e63",
        "muted": "#0e7490",
        "accent": "#06b6d4",
        "accent2": "#f472b6",
        "danger": "#e11d48",
        "border": "rgba(6,182,212,0.35)",
        "header": "linear-gradient(135deg, #a5f3fc, #fbcfe8)",
        "btn_fg": "#ffffff",
        "glow": "rgba(6,182,212,0.35)",
        "selection": "rgba(244,114,182,0.25)",
    },
    {
        "id": "chalk_board",
        "light": False,
        "font": "'Comic Sans MS', 'Chalkboard SE', sans-serif",
        "mono": "monospace",
        "radius": "4px",
        "pattern": "chalk",
        "bg": "#1a2e1a",
        "bg2": "#0f1a0f",
        "elevated": "#243824",
        "fg": "#f5f5f4",
        "muted": "rgba(163,163,163,0.85)",
        "accent": "#86efac",
        "accent2": "#f5f5f4",
        "danger": "#fca5a5",
        "border": "rgba(134,239,172,0.3)",
        "header": "linear-gradient(180deg, #243824, #1a2e1a)",
        "btn_fg": "#1a2e1a",
        "glow": "rgba(134,239,172,0.3)",
        "selection": "rgba(134,239,172,0.25)",
        "extra": "chalkdust",
    },
    # ── Unprompted unique ───────────────────────────────────────────────
    {
        "id": "street_interview",
        "light": False,
        "font": "'Barlow Condensed', 'Arial Narrow', sans-serif",
        "mono": "monospace",
        "radius": "6px",
        "pattern": "asphalt",
        "bg": "#18181b",
        "bg2": "#09090b",
        "elevated": "#27272a",
        "fg": "#e4e4e7",
        "muted": "#a1a1aa",
        "accent": "#facc15",
        "accent2": "#fde047",
        "danger": "#ef4444",
        "border": "rgba(250,204,21,0.4)",
        "header": "linear-gradient(90deg, #27272a, #18181b)",
        "btn_fg": "#18181b",
        "glow": "rgba(250,204,21,0.4)",
        "selection": "rgba(250,204,21,0.3)",
    },
    {
        "id": "radio_wave",
        "light": False,
        "font": "system-ui, sans-serif",
        "mono": "ui-monospace, monospace",
        "radius": "10px",
        "pattern": "waves",
        "bg": "#1c1210",
        "bg2": "#0c0807",
        "elevated": "#2c1c18",
        "fg": "#fef3c7",
        "muted": "rgba(251,146,60,0.75)",
        "accent": "#f59e0b",
        "accent2": "#fb923c",
        "danger": "#f87171",
        "border": "rgba(245,158,11,0.35)",
        "header": "linear-gradient(135deg, rgba(245,158,11,0.25), #1c1210)",
        "btn_fg": "#1c1210",
        "glow": "rgba(251,146,60,0.4)",
        "selection": "rgba(245,158,11,0.3)",
    },
    {
        "id": "field_notes",
        "light": True,
        "font": "'Caveat', 'Segoe Print', cursive",
        "mono": "'Courier New', monospace",
        "radius": "2px",
        "pattern": "graphpaper",
        "bg": "#f8fafc",
        "bg2": "#f1f5f9",
        "elevated": "#ffffff",
        "fg": "#0f172a",
        "muted": "#64748b",
        "accent": "#1d4ed8",
        "accent2": "#2563eb",
        "danger": "#b91c1c",
        "border": "rgba(29,78,216,0.25)",
        "header": "linear-gradient(180deg, #ffffff, #f8fafc)",
        "btn_fg": "#ffffff",
        "glow": "rgba(29,78,216,0.2)",
        "selection": "rgba(29,78,216,0.15)",
    },
    {
        "id": "civic_bulletin",
        "light": False,
        "font": "Georgia, serif",
        "mono": "monospace",
        "radius": "4px",
        "pattern": "notice",
        "bg": "#1e3a5f",
        "bg2": "#0f2744",
        "elevated": "#274c77",
        "fg": "#fefce8",
        "muted": "rgba(147,197,253,0.8)",
        "accent": "#93c5fd",
        "accent2": "#dc2626",
        "danger": "#fca5a5",
        "border": "rgba(147,197,253,0.35)",
        "header": "linear-gradient(180deg, #274c77, #1e3a5f)",
        "btn_fg": "#1e3a5f",
        "glow": "rgba(147,197,253,0.35)",
        "selection": "rgba(220,38,38,0.25)",
        "extra": "stamp",
    },
    {
        "id": "night_dispatch",
        "light": False,
        "font": "'Share Tech Mono', ui-monospace, monospace",
        "mono": "'Share Tech Mono', monospace",
        "radius": "6px",
        "pattern": "ticker",
        "bg": "#0b1220",
        "bg2": "#050810",
        "elevated": "#152038",
        "fg": "#e0e7ff",
        "muted": "rgba(129,140,248,0.75)",
        "accent": "#4ade80",
        "accent2": "#818cf8",
        "danger": "#f87171",
        "border": "rgba(74,222,128,0.35)",
        "header": "linear-gradient(90deg, rgba(74,222,128,0.15), rgba(129,140,248,0.15), #0b1220)",
        "btn_fg": "#0b1220",
        "glow": "rgba(74,222,128,0.4)",
        "selection": "rgba(74,222,128,0.3)",
        "extra": "hud",
    },
]


def pattern_css(t: dict) -> str:
    tid = t["id"]
    kind = t.get("pattern", "none")
    accent = t["accent"]
    accent2 = t["accent2"]
    bg = t["bg"]
    bg2 = t["bg2"]
    sel = f'html[data-gd-theme="{tid}"]'
    blocks = []

    # Always: subtle noise grain overlay
    blocks.append(f"""
{sel} body::before {{
  content: "";
  position: fixed; inset: 0; pointer-events: none; z-index: 0;
  opacity: 0.45;
}}
{sel} body > * {{ position: relative; z-index: 1; }}
/* Keep sticky chrome (header + menus) above page content */
{sel} body > .header,
{sel} body > header {{
  z-index: 1000;
}}
""")

    if kind == "mesh":
        blocks.append(f"""
{sel} body::before {{
  background:
    radial-gradient(ellipse 80% 50% at 20% -10%, {accent}33, transparent 50%),
    radial-gradient(ellipse 60% 40% at 90% 10%, {accent2}22, transparent 45%),
    radial-gradient(circle at 50% 100%, {accent}11, transparent 40%);
  opacity: 1;
}}
""")
    elif kind == "grid":
        blocks.append(f"""
{sel} body::before {{
  background-image:
    linear-gradient({accent}18 1px, transparent 1px),
    linear-gradient(90deg, {accent}18 1px, transparent 1px);
  background-size: 24px 24px;
  opacity: 0.55;
}}
""")
    elif kind == "plasma":
        blocks.append(f"""
{sel} body::before {{
  background:
    radial-gradient(ellipse 50% 40% at 30% 40%, {accent}44, transparent 60%),
    radial-gradient(ellipse 40% 50% at 70% 60%, {accent2}33, transparent 55%),
    radial-gradient(circle at 50% 50%, {accent}15, transparent 70%);
  filter: blur(0.5px);
  opacity: 1;
  animation: gd-plasma-drift 18s ease-in-out infinite alternate;
}}
@keyframes gd-plasma-drift {{
  from {{ transform: scale(1) translate(0,0); }}
  to {{ transform: scale(1.08) translate(-2%, 1%); }}
}}
""")
    elif kind == "starfield":
        blocks.append(f"""
{sel} body::before {{
  background-image:
    radial-gradient(1px 1px at 10% 20%, #fff 50%, transparent 50%),
    radial-gradient(1px 1px at 30% 65%, #fff 50%, transparent 50%),
    radial-gradient(1.5px 1.5px at 55% 15%, {accent} 50%, transparent 50%),
    radial-gradient(1px 1px at 70% 80%, #fff 50%, transparent 50%),
    radial-gradient(1px 1px at 85% 35%, {accent2} 50%, transparent 50%),
    radial-gradient(1.5px 1.5px at 15% 85%, #fff 50%, transparent 50%),
    radial-gradient(1px 1px at 45% 45%, #fff 50%, transparent 50%),
    linear-gradient(105deg, transparent 40%, {accent}08 50%, transparent 60%);
  background-size: 100% 100%, 100% 100%, 100% 100%, 100% 100%, 100% 100%, 100% 100%, 100% 100%, 200% 100%;
  opacity: 0.9;
  animation: gd-hyperspace 12s linear infinite;
}}
@keyframes gd-hyperspace {{
  from {{ background-position: 0 0, 0 0, 0 0, 0 0, 0 0, 0 0, 0 0, 0 0; }}
  to {{ background-position: 0 0, 0 0, 0 0, 0 0, 0 0, 0 0, 0 0, 200% 0; }}
}}
""")
    elif kind == "camo":
        blocks.append(f"""
{sel} body::before {{
  background-image:
    radial-gradient(ellipse 30% 25% at 20% 30%, {accent}18, transparent 60%),
    radial-gradient(ellipse 25% 30% at 70% 50%, {accent2}14, transparent 55%),
    radial-gradient(ellipse 20% 20% at 40% 80%, {accent}10, transparent 50%);
  opacity: 1;
}}
{sel} body::after {{
  content: "";
  position: fixed; inset: 0; pointer-events: none; z-index: 0;
  background: repeating-linear-gradient(
    0deg, transparent, transparent 2px, rgba(0,0,0,0.08) 2px, rgba(0,0,0,0.08) 3px
  );
  opacity: 0.35;
}}
""")
    elif kind == "filigree":
        blocks.append(f"""
{sel} body::before {{
  background:
    radial-gradient(circle at 50% 0%, {accent}22, transparent 40%),
    radial-gradient(circle at 10% 90%, {accent2}18, transparent 35%),
    radial-gradient(circle at 90% 80%, {accent}12, transparent 30%);
  opacity: 1;
}}
{sel} .header {{
  box-shadow: inset 0 -1px 0 {accent}55, 0 0 0 1px {accent}22;
}}
""")
    elif kind == "stone":
        blocks.append(f"""
{sel} body::before {{
  background-image:
    radial-gradient(ellipse at 20% 30%, rgba(0,0,0,0.25) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 70%, rgba(0,0,0,0.2) 0%, transparent 45%),
    linear-gradient(180deg, {bg2}, {bg});
  opacity: 1;
}}
""")
    elif kind == "graph":
        blocks.append(f"""
{sel} body::before {{
  background-image:
    radial-gradient(circle at 15% 25%, {accent} 2px, transparent 2.5px),
    radial-gradient(circle at 55% 40%, {accent2} 2px, transparent 2.5px),
    radial-gradient(circle at 80% 20%, {accent} 1.5px, transparent 2px),
    radial-gradient(circle at 35% 75%, {accent2} 2px, transparent 2.5px),
    radial-gradient(circle at 70% 70%, {accent} 1.5px, transparent 2px),
    linear-gradient({accent}14 1px, transparent 1px),
    linear-gradient(90deg, {accent}14 1px, transparent 1px);
  background-size: 100% 100%, 100% 100%, 100% 100%, 100% 100%, 100% 100%, 48px 48px, 48px 48px;
  opacity: 0.7;
}}
""")
    elif kind == "scanlines":
        blocks.append(f"""
{sel} body::before {{
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(0,0,0,0.18) 2px,
    rgba(0,0,0,0.18) 4px
  );
  opacity: 0.55;
}}
{sel} body {{
  text-shadow: 0 0 6px {accent}88, 0 0 1px {accent};
}}
""")
    elif kind == "softglow":
        blocks.append(f"""
{sel} body::before {{
  background:
    radial-gradient(ellipse 70% 50% at 50% -20%, {accent}33, transparent 55%),
    radial-gradient(ellipse 50% 40% at 100% 50%, {accent2}22, transparent 50%);
  opacity: 1;
}}
""")
    elif kind == "vellum":
        blocks.append(f"""
{sel} body::before {{
  background-image:
    url("data:image/svg+xml,%3Csvg viewBox='0 0 200 200' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='0.08'/%3E%3C/svg%3E");
  opacity: 0.9;
}}
{sel} h1, {sel} h2 {{
  font-variant: small-caps;
  letter-spacing: 0.04em;
}}
""")
    elif kind == "marble":
        blocks.append(f"""
{sel} body::before {{
  background:
    linear-gradient(125deg, transparent 40%, {accent}08 50%, transparent 60%),
    linear-gradient(55deg, transparent 30%, rgba(0,0,0,0.03) 50%, transparent 70%);
  opacity: 1;
}}
""")
    elif kind == "sketch":
        blocks.append(f"""
{sel} body::before {{
  background-image:
    linear-gradient({accent}10 1px, transparent 1px);
  background-size: 100% 28px;
  opacity: 0.6;
}}
""")
    elif kind == "coins":
        blocks.append(f"""
{sel} body::before {{
  background:
    radial-gradient(circle at 10% 20%, {accent}22 0 2px, transparent 3px),
    radial-gradient(circle at 90% 80%, {accent}18 0 3px, transparent 4px),
    radial-gradient(ellipse at 50% 0%, {accent}20, transparent 50%);
  opacity: 1;
}}
""")
    elif kind == "paper":
        blocks.append(f"""
{sel} body::before {{
  background-image:
    linear-gradient(rgba(0,0,0,0.03) 1px, transparent 1px);
  background-size: 100% 1.6em;
  opacity: 0.8;
}}
""")
    elif kind == "blueprint":
        blocks.append(f"""
{sel} body::before {{
  background-image:
    linear-gradient({accent}20 1px, transparent 1px),
    linear-gradient(90deg, {accent}20 1px, transparent 1px),
    linear-gradient({accent}10 1px, transparent 1px),
    linear-gradient(90deg, {accent}10 1px, transparent 1px);
  background-size: 80px 80px, 80px 80px, 16px 16px, 16px 16px;
  opacity: 0.55;
}}
""")
    elif kind == "swiss":
        blocks.append(f"""
{sel} body::before {{
  background: linear-gradient(90deg, {accent} 0 4px, transparent 4px);
  opacity: 0.15;
  width: 100%;
}}
{sel} h1, {sel} h2 {{
  text-transform: uppercase;
  letter-spacing: 0.06em;
  font-weight: 800;
}}
""")
    elif kind == "washi":
        blocks.append(f"""
{sel} body::before {{
  background:
    radial-gradient(circle at 12% 18%, {accent}33 0 40px, transparent 41px),
    radial-gradient(circle at 88% 22%, {accent2}28 0 50px, transparent 51px),
    radial-gradient(circle at 70% 85%, {accent}20 0 60px, transparent 61px);
  opacity: 0.9;
}}
""")
    elif kind == "arcade":
        blocks.append(f"""
{sel} body::before {{
  background:
    repeating-linear-gradient(90deg, {accent}11 0 2px, transparent 2px 20px),
    radial-gradient(ellipse at 50% 0%, {accent2}33, transparent 50%);
  opacity: 0.85;
}}
{sel} .logo, {sel} h1 {{
  text-shadow: 0 0 8px {accent}, 0 0 16px {accent2};
}}
""")
    elif kind == "cork":
        blocks.append(f"""
{sel} body::before {{
  background-image:
    radial-gradient(circle at 20% 30%, rgba(0,0,0,0.15) 0 8px, transparent 9px),
    radial-gradient(circle at 60% 50%, rgba(0,0,0,0.12) 0 6px, transparent 7px),
    radial-gradient(circle at 80% 20%, rgba(0,0,0,0.1) 0 10px, transparent 11px);
  opacity: 0.7;
}}
""")
    elif kind == "bubbles":
        blocks.append(f"""
{sel} body::before {{
  background-image:
    radial-gradient(circle at 20% 30%, {accent}33 0 18px, transparent 19px),
    radial-gradient(circle at 70% 20%, {accent2}28 0 28px, transparent 29px),
    radial-gradient(circle at 40% 80%, {accent}22 0 22px, transparent 23px),
    radial-gradient(circle at 85% 70%, {accent2}25 0 14px, transparent 15px);
  opacity: 0.85;
}}
""")
    elif kind == "chalk":
        blocks.append(f"""
{sel} body::before {{
  background-image:
    radial-gradient(circle at 30% 40%, rgba(255,255,255,0.04) 0 2px, transparent 3px),
    radial-gradient(circle at 70% 60%, rgba(255,255,255,0.03) 0 1px, transparent 2px);
  opacity: 1;
}}
{sel} body {{
  text-shadow: 0.5px 0.5px 0 rgba(0,0,0,0.4);
}}
""")
    elif kind == "asphalt":
        blocks.append(f"""
{sel} body::before {{
  background-image:
    radial-gradient(circle at 15% 25%, rgba(255,255,255,0.03) 0 1px, transparent 2px),
    radial-gradient(circle at 80% 70%, rgba(255,255,255,0.025) 0 1px, transparent 2px);
  opacity: 1;
}}
""")
    elif kind == "waves":
        blocks.append(f"""
{sel} body::before {{
  background:
    repeating-linear-gradient(
      100deg,
      transparent,
      transparent 12px,
      {accent}0d 12px,
      {accent}0d 14px
    );
  opacity: 0.9;
}}
""")
    elif kind == "graphpaper":
        blocks.append(f"""
{sel} body::before {{
  background-image:
    linear-gradient({accent}18 1px, transparent 1px),
    linear-gradient(90deg, {accent}18 1px, transparent 1px);
  background-size: 24px 24px;
  opacity: 0.5;
}}
""")
    elif kind == "notice":
        blocks.append(f"""
{sel} body::before {{
  background: linear-gradient(180deg, {accent}12, transparent 30%);
  opacity: 1;
}}
""")
    elif kind == "ticker":
        blocks.append(f"""
{sel} body::before {{
  background:
    linear-gradient(90deg, {accent}15 0, transparent 20%, transparent 80%, {accent2}12 100%),
    repeating-linear-gradient(0deg, transparent, transparent 22px, {accent}08 22px, {accent}08 23px);
  opacity: 0.85;
}}
""")
    else:
        blocks.append(f"""
{sel} body::before {{ opacity: 0; }}
""")

    return "\n".join(blocks)


def theme_block(t: dict) -> str:
    tid = t["id"]
    sel = f'html[data-gd-theme="{tid}"]'
    btn_bg = t.get("btn_bg", t["accent"])
    radius = t["radius"]
    light = t.get("light", False)

    extra_rules = ""
    if t.get("extra") == "bevel":
        extra_rules += f"""
{sel} .btn, {sel} .btn-primary, {sel} button.btn {{
  border: 2px solid #ffffff !important;
  border-bottom-color: #000000 !important;
  border-right-color: #000000 !important;
  border-top-color: #ffffff !important;
  border-left-color: #ffffff !important;
  box-shadow: none !important;
}}
{sel} .nav-tab.active {{
  outline: 1px solid {t["accent"]};
}}
"""
    if t.get("extra") == "hud":
        extra_rules += f"""
{sel} .header::after {{
  content: "SYS // ONLINE";
  position: absolute; right: 12px; bottom: 2px;
  font-size: 9px; letter-spacing: 0.15em;
  color: {t["accent"]}; opacity: 0.55;
  font-family: {t["mono"]};
}}
{sel} .header {{ position: sticky; }}
"""
    if t.get("extra") == "ornate":
        extra_rules += f"""
{sel} .logo, {sel} .header .logo {{
  text-shadow: 0 0 12px {t["accent"]}88, 0 1px 0 {t["accent2"]};
}}
{sel} .panel, {sel} .endpoint, {sel} .flow-step, {sel} .founder-card {{
  box-shadow: inset 0 0 0 1px {t["accent"]}33, 0 8px 32px rgba(0,0,0,0.4) !important;
}}
"""
    if t.get("extra") == "leather":
        extra_rules += f"""
{sel} .panel, {sel} .endpoint, {sel} .msg {{
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), 0 4px 0 {t["bg2"]}, 0 8px 24px rgba(0,0,0,0.45) !important;
}}
"""
    if t.get("extra") == "crt":
        extra_rules += f"""
{sel} body {{
  animation: gd-crt-flicker 4s infinite;
}}
@keyframes gd-crt-flicker {{
  0%, 97%, 100% {{ opacity: 1; }}
  98% {{ opacity: 0.97; }}
  99% {{ opacity: 0.99; }}
}}
{sel} .btn-primary, {sel} .btn.btn-primary {{
  box-shadow: 0 0 12px {t["glow"]} !important;
}}
"""
    if t.get("extra") == "manuscript":
        extra_rules += f"""
{sel} h2::first-letter {{
  font-size: 1.6em;
  color: {t["accent"]};
  font-weight: 700;
  float: left;
  line-height: 1;
  padding-right: 4px;
}}
"""
    if t.get("extra") == "goldedge":
        extra_rules += f"""
{sel} .panel, {sel} .founder-card, {sel} .endpoint {{
  border: 1px solid {t["accent"]} !important;
  box-shadow: 0 0 0 3px {t["bg"]}, 0 0 0 4px {t["accent"]}55 !important;
}}
"""
    if t.get("extra") == "noir":
        extra_rules += f"""
{sel} .btn-primary, {sel} .btn.btn-primary {{
  background: #fafafa !important;
  color: #0a0a0a !important;
  border: 1px solid #fafafa !important;
}}
{sel} a {{ text-decoration: underline; text-underline-offset: 3px; }}
"""
    if t.get("extra") == "stamp":
        extra_rules += f"""
{sel} .badge, {sel} .method {{
  border: 2px solid {t["accent"]} !important;
  text-transform: uppercase;
  letter-spacing: 0.08em;
}}
"""
    if t.get("extra") == "swiss":
        extra_rules += f"""
{sel} .btn, {sel} .btn-primary {{
  border-radius: 0 !important;
  border: 2px solid #000 !important;
}}
{sel} .header {{
  border-bottom: 3px solid #000 !important;
}}
"""
    if t.get("extra") == "neon":
        extra_rules += f"""
{sel} .btn-primary, {sel} .cell.filled {{
  box-shadow: 0 0 10px {t["accent"]}, 0 0 20px {t["accent2"]}55 !important;
}}
"""
    if t.get("extra") == "chalkdust":
        extra_rules += f"""
{sel} h1, {sel} h2, {sel} .logo {{
  font-weight: 400;
  letter-spacing: 0.02em;
}}
"""

    # Light-theme scrollbars / inputs need care
    scrollbar = f"""
{sel} ::-webkit-scrollbar {{ width: 10px; height: 10px; }}
{sel} ::-webkit-scrollbar-track {{ background: {t["bg2"]}; }}
{sel} ::-webkit-scrollbar-thumb {{
  background: {t["accent"]}88;
  border-radius: {radius};
  border: 2px solid {t["bg2"]};
}}
"""

    return f"""
/* ═══════════════════════════════════════════════════════════════
   Theme: {tid}
   ═══════════════════════════════════════════════════════════════ */
{sel} {{
  color-scheme: {"light" if light else "dark"};
  --gd-bg: {t["bg"]};
  --gd-bg2: {t["bg2"]};
  --gd-elevated: {t["elevated"]};
  --gd-fg: {t["fg"]};
  --gd-muted: {t["muted"]};
  --gd-accent: {t["accent"]};
  --gd-accent2: {t["accent2"]};
  --gd-danger: {t["danger"]};
  --gd-border: {t["border"]};
  --gd-header: {t["header"]};
  --gd-radius: {radius};
  --gd-glow: {t["glow"]};
  --gd-font: {t["font"]};
  --gd-mono: {t["mono"]};
  --gd-btn-bg: {btn_bg};
  --gd-btn-fg: {t["btn_fg"]};
}}

{sel},
{sel} body {{
  background: {t["bg"]} !important;
  color: {t["fg"]} !important;
  font-family: {t["font"]} !important;
}}

{sel} ::selection {{
  background: {t["selection"]};
  color: {t["fg"]};
}}

{sel} a {{ color: {t["accent"]} !important; }}
{sel} a:hover {{ color: {t["accent2"]} !important; }}

/* Header / chrome */
{sel} .header,
{sel} header {{
  background: {t["header"]} !important;
  border-bottom-color: {t["border"]} !important;
  color: {t["fg"]} !important;
  backdrop-filter: blur(10px);
}}
{sel} .logo,
{sel} .brand,
{sel} .header .logo {{
  color: {t["accent"]} !important;
}}
{sel} .header-links a,
{sel} .header-title,
{sel} .user-count,
{sel} .badge {{
  color: {t["muted"]} !important;
}}
{sel} .header-links a:hover {{ color: {t["accent"]} !important; }}

/* Nav */
{sel} .nav-tab {{
  color: {t["muted"]} !important;
  border-radius: {radius} !important;
}}
{sel} .nav-tab:hover {{
  background: {t["elevated"]} !important;
  color: {t["fg"]} !important;
}}
{sel} .nav-tab.active {{
  background: color-mix(in srgb, {t["accent"]} 22%, transparent) !important;
  color: {t["accent"]} !important;
}}

/* Buttons */
{sel} .btn,
{sel} .btn-primary,
{sel} .btn.btn-primary,
{sel} .hero-btn.primary {{
  background: {btn_bg} !important;
  color: {t["btn_fg"]} !important;
  border-radius: {radius} !important;
  border: 1px solid transparent !important;
  box-shadow: 0 0 0 0 transparent, 0 2px 12px {t["glow"]};
  transition: transform 0.15s, box-shadow 0.15s, filter 0.15s;
}}
{sel} .btn-primary:hover,
{sel} .btn.btn-primary:hover,
{sel} .hero-btn.primary:hover {{
  filter: brightness(1.08);
  box-shadow: 0 0 20px {t["glow"]};
}}
{sel} .btn-secondary,
{sel} .hero-btn.secondary,
{sel} .lang-btn {{
  background: color-mix(in srgb, {t["elevated"]} 80%, transparent) !important;
  color: {t["fg"]} !important;
  border: 1px solid {t["border"]} !important;
  border-radius: {radius} !important;
}}
{sel} .btn-secondary:hover,
{sel} .hero-btn.secondary:hover,
{sel} .lang-btn:hover {{
  border-color: {t["accent"]} !important;
  color: {t["accent"]} !important;
}}
{sel} .lang-btn.active {{
  background: {t["accent"]} !important;
  border-color: {t["accent"]} !important;
  color: {t["btn_fg"]} !important;
}}
{sel} .btn-danger {{
  background: {t["danger"]} !important;
  color: #fff !important;
  border-radius: {radius} !important;
}}

/* Surfaces */
{sel} .panel,
{sel} .endpoint,
{sel} .flow-step,
{sel} .founder-card,
{sel} .notification-dropdown,
{sel} .modal-content,
{sel} .auth-popup,
{sel} .chat-login-card,
{sel} .msg,
{sel} .code-block,
{sel} pre,
{sel} .hc-log,
{sel} .transcript-view {{
  background: {t["elevated"]} !important;
  border-color: {t["border"]} !important;
  color: {t["fg"]} !important;
  border-radius: {radius} !important;
}}
{sel} .panel-header,
{sel} .endpoint-header,
{sel} .notification-header {{
  background: color-mix(in srgb, {t["bg2"]} 70%, {t["elevated"]}) !important;
  border-color: {t["border"]} !important;
  color: {t["fg"]} !important;
}}

/* Chat bubbles */
{sel} .msg.user {{
  background: color-mix(in srgb, {t["accent"]} 22%, {t["elevated"]}) !important;
  border: 1px solid {t["border"]} !important;
}}
{sel} .msg.assistant,
{sel} .msg.doc {{
  background: {t["elevated"]} !important;
  border: 1px solid {t["border"]} !important;
}}

/* Forms */
{sel} input,
{sel} textarea,
{sel} select,
{sel} .settings-select,
{sel} .custom-prompt-textarea {{
  background: {t["bg2"]} !important;
  color: {t["fg"]} !important;
  border: 1px solid {t["border"]} !important;
  border-radius: {radius} !important;
  font-family: inherit !important;
}}
{sel} input:focus,
{sel} textarea:focus,
{sel} select:focus {{
  outline: 2px solid {t["accent"]} !important;
  outline-offset: 1px;
  border-color: {t["accent"]} !important;
}}
{sel} input::placeholder,
{sel} textarea::placeholder {{
  color: {t["muted"]} !important;
  opacity: 0.8;
}}

/* Settings / toggles */
{sel} .settings-group-title {{
  color: {t["muted"]} !important;
  letter-spacing: 0.08em;
}}
{sel} .settings-label {{ color: {t["fg"]} !important; }}
{sel} .settings-desc {{ color: {t["muted"]} !important; }}
{sel} .settings-item {{ border-bottom-color: {t["border"]} !important; }}
{sel} .settings-toggle {{
  background: {t["bg2"]} !important;
  border: 1px solid {t["border"]};
}}
{sel} .settings-toggle.on {{
  background: {t["accent"]} !important;
}}

/* Typography helpers */
{sel} h1, {sel} h2, {sel} h3 {{
  color: {t["fg"] if light else t["accent"]} !important;
}}
{sel} h2 {{ color: {t["accent"]} !important; }}
{sel} p, {sel} .subtitle, {sel} .profile-empty {{
  color: {t["muted"]} !important;
}}
{sel} code, {sel} .method, {sel} pre {{
  font-family: {t["mono"]} !important;
}}

/* Docs-specific */
{sel} .method.get {{ background: color-mix(in srgb, {t["accent"]} 30%, transparent) !important; color: {t["accent"]} !important; }}
{sel} .method.post {{ background: color-mix(in srgb, {t["accent2"]} 30%, transparent) !important; color: {t["accent2"]} !important; }}
{sel} .spec-link {{
  background: {t["elevated"]} !important;
  border-color: {t["border"]} !important;
  color: {t["fg"]} !important;
  border-radius: {radius} !important;
}}
{sel} .spec-link:hover {{
  border-color: {t["accent"]} !important;
  color: {t["accent"]} !important;
}}

/* Stickers board */
{sel} .area-label,
{sel} thead th:first-child {{
  background: {t["bg"]} !important;
  color: {t["muted"]} !important;
}}
{sel} .cell.filled {{
  background: color-mix(in srgb, {t["accent"]} 14%, transparent) !important;
}}
{sel} .cell.today-col {{
  border-color: {t["accent"]} !important;
}}
{sel} thead th.today-col {{
  color: {t["accent"]} !important;
}}
{sel} .header h1 {{ color: {t["accent"]} !important; }}

/* Hero */
{sel} .hero {{
  background: linear-gradient(180deg, color-mix(in srgb, {t["accent"]} 12%, transparent) 0%, transparent 100%) !important;
  border-bottom-color: {t["border"]} !important;
}}
{sel} .hero p {{ color: {t["muted"]} !important; }}

/* User chrome */
{sel} .user-badge {{
  background: {t["elevated"]} !important;
  color: {t["fg"]} !important;
  border: 1px solid {t["border"]};
  border-radius: {radius} !important;
}}
{sel} .notification-bell {{ color: {t["muted"]} !important; }}
{sel} .notification-bell:hover {{ color: {t["fg"]} !important; }}
{sel} .notification-badge {{ background: {t["danger"]} !important; }}

/* Starter / misc chips */
{sel} .starter-btn {{
  background: {t["elevated"]} !important;
  border: 1px solid {t["border"]} !important;
  color: {t["fg"]} !important;
  border-radius: {radius} !important;
}}
{sel} .starter-btn:hover {{
  border-color: {t["accent"]} !important;
  color: {t["accent"]} !important;
}}

/* Style picker chrome (shared component) */
{sel} .gd-style-picker {{
  border-color: {t["border"]};
}}
{sel} .gd-style-option {{
  background: {t["bg2"]};
  border-color: {t["border"]};
  color: {t["fg"]};
}}
{sel} .gd-style-option:hover,
{sel} .gd-style-option.selected {{
  border-color: {t["accent"]};
  box-shadow: 0 0 0 1px {t["accent"]}, 0 4px 16px {t["glow"]};
}}
{sel} .gd-style-option.selected {{
  background: color-mix(in srgb, {t["accent"]} 12%, {t["elevated"]});
}}

{scrollbar}
{pattern_css(t)}
{extra_rules}
"""


def main():
    parts = [
        dedent(
            """\
            /* Auto-generated by scripts/generate_theme_css.py — do not hand-edit.
               GreenDial multi-skin UI themes. Applied via html[data-gd-theme="…"].
            */
            """
        ),
        dedent(
            """\
            /* ── Shared picker chrome (theme-independent base) ───────── */
            .gd-style-picker {
              display: grid;
              grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
              gap: 10px;
              margin-top: 10px;
            }
            .gd-style-option {
              display: flex;
              flex-direction: column;
              gap: 6px;
              padding: 10px 12px;
              border: 1px solid rgba(255,255,255,0.12);
              border-radius: 12px;
              background: rgba(0,0,0,0.2);
              cursor: pointer;
              text-align: left;
              transition: border-color 0.15s, box-shadow 0.15s, transform 0.12s;
              font: inherit;
              color: inherit;
            }
            .gd-style-option:hover { transform: translateY(-1px); }
            .gd-style-option.selected { outline: none; }
            .gd-style-swatches {
              display: flex; gap: 4px; height: 14px;
            }
            .gd-style-swatches span {
              flex: 1; border-radius: 3px;
              border: 1px solid rgba(0,0,0,0.25);
              min-width: 0;
            }
            .gd-style-name {
              font-size: 13px; font-weight: 650;
              letter-spacing: 0.01em;
            }
            .gd-style-meta {
              font-size: 10px; text-transform: uppercase;
              letter-spacing: 0.08em; opacity: 0.55;
            }
            .gd-style-blurb {
              font-size: 11px; line-height: 1.35; opacity: 0.7;
            }
            .gd-style-badge {
              display: inline-block;
              font-size: 9px; font-weight: 700;
              letter-spacing: 0.06em; text-transform: uppercase;
              padding: 2px 6px; border-radius: 4px;
              background: rgba(255,255,255,0.08);
              width: fit-content;
            }
            .gd-style-section-title {
              font-size: 11px; font-weight: 700;
              letter-spacing: 0.1em; text-transform: uppercase;
              opacity: 0.5; margin: 18px 0 8px;
            }
            .gd-style-compact {
              display: flex; align-items: center; gap: 8px;
            }
            .gd-style-compact select {
              font-size: 12px; padding: 4px 8px;
              max-width: 200px;
            }
            .gd-style-toolbar {
              display: flex; align-items: center; gap: 8px;
              font-size: 12px; opacity: 0.85;
            }
            """
        ),
    ]

    for t in THEMES:
        parts.append(theme_block(t))

    # page_default uses emerald until JS resolves — no special skin needed
    css = "\n".join(parts)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(css)
    print(f"Wrote {OUT} ({len(css):,} bytes, {len(THEMES)} themes)")


if __name__ == "__main__":
    main()
