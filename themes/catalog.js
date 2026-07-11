/**
 * GreenDial UI style catalog.
 *
 * - SHARED themes appear on every page.
 * - Each page also has UNIQUE themes (available on that page + always
 *   choosable from Settings "full menu").
 * - page_default: semi-random daily pick from the current page's pool.
 */
(function (global) {
  'use strict';

  const SHARED = [
    {
      id: 'emerald_protocol',
      name: 'Emerald Protocol',
      category: 'GreenDial',
      blurb: 'The classic GreenDial night clinic — deep navy, living emerald, soft glass.',
      swatches: ['#1a1a2e', '#10b981', '#2a2a4e', '#eee'],
      themeColor: '#1a1a2e',
    },
    {
      id: 'borland',
      name: 'Borland',
      category: 'Borland',
      blurb: 'Turbo Pascal IDE energy — cobalt panels, amber text, chunky system chrome.',
      swatches: ['#000084', '#ffff55', '#00aaaa', '#c0c0c0'],
      themeColor: '#000084',
    },
    {
      id: 'deep_plasma',
      name: 'Deep Plasma',
      category: 'DeepPlasma',
      blurb: 'Tokamak night — violet cores, cyan field lines, magnetic glow.',
      swatches: ['#0b0618', '#c084fc', '#22d3ee', '#f0abfc'],
      themeColor: '#0b0618',
    },
    {
      id: 'faster_than_lightspeed',
      name: 'Faster Than Lightspeed',
      category: 'FasterThanLightspeed',
      blurb: 'Hyperspace streak — abyssal black, ice-blue starlines, hot white cores.',
      swatches: ['#020617', '#38bdf8', '#e0f2fe', '#a78bfa'],
      themeColor: '#020617',
    },
    {
      id: 'ghost_recon',
      name: 'Ghost Recon',
      category: 'GhostRecon',
      blurb: 'Tactical HUD — olive drab, night-vision green, mission-brief grit.',
      swatches: ['#0f1410', '#84cc16', '#3f6212', '#d9f99d'],
      themeColor: '#0f1410',
    },
  ];

  const BY_PAGE = {
    app: [
      {
        id: 'magic_the_gathering',
        name: 'Magic: The Gathering',
        category: 'MagicTheGathering',
        blurb: 'Mana-glow parchment — gold filigree, jewel inks, summoning circle chrome.',
        swatches: ['#1c1410', '#d4a017', '#7c3aed', '#f5e6c8'],
        themeColor: '#1c1410',
      },
      {
        id: 'dungeon_crawler_rpg',
        name: 'Dungeon Crawler RPG',
        category: 'DungeonCrawlerRPG',
        blurb: 'Torchlit stone UI — leather panels, brass corners, hit-point red.',
        swatches: ['#1a120b', '#c4a574', '#b45309', '#fef3c7'],
        themeColor: '#1a120b',
      },
      {
        id: 'graph_trotterization',
        name: 'Graph Trotterization',
        category: 'GraphTrotterization',
        blurb: 'Spectral graph theory — nodes, edges, Laplacian blues on slate.',
        swatches: ['#0f172a', '#60a5fa', '#34d399', '#e2e8f0'],
        themeColor: '#0f172a',
      },
      {
        id: 'crt_phosphor',
        name: 'CRT Phosphor',
        category: 'CRTTerminal',
        blurb: 'Green phosphor terminal — scanlines, bloom, teletype intimacy.',
        swatches: ['#001100', '#33ff66', '#0a2a0a', '#9affb0'],
        themeColor: '#001100',
      },
      {
        id: 'velvet_clinic',
        name: 'Velvet Clinic',
        category: 'VelvetClinic',
        blurb: 'Quiet luxury wellness — plum velvet, rose gold, soft serif calm.',
        swatches: ['#1a1020', '#e8b4bc', '#9f7aea', '#faf5ff'],
        themeColor: '#1a1020',
      },
    ],
    about: [
      {
        id: 'illuminated_manuscript',
        name: 'Illuminated Manuscript',
        category: 'IlluminatedManuscript',
        blurb: 'Medieval folio — vellum cream, ruby initials, gold leaf edges.',
        swatches: ['#f4ecd8', '#7f1d1d', '#b45309', '#1c1917'],
        themeColor: '#f4ecd8',
      },
      {
        id: 'ethos_marble',
        name: 'Ethos Marble',
        category: 'EthosMarble',
        blurb: 'Civic stone — Carrara white, sage green, engraved headings.',
        swatches: ['#f8faf9', '#047857', '#334155', '#cbd5e1'],
        themeColor: '#f8faf9',
      },
      {
        id: 'founder_atelier',
        name: 'Founder Atelier',
        category: 'FounderAtelier',
        blurb: 'Studio loft — warm charcoal, copper wire, sketchbook cream.',
        swatches: ['#1c1917', '#d97706', '#fafaf9', '#a8a29e'],
        themeColor: '#1c1917',
      },
      {
        id: 'bounty_treasury',
        name: 'Bounty Treasury',
        category: 'BountyTreasury',
        blurb: 'Vault of UB gold — deep green lacquer, coin-edge brass, ledger ink.',
        swatches: ['#052e16', '#fbbf24', '#14532d', '#fef3c7'],
        themeColor: '#052e16',
      },
      {
        id: 'quiet_library',
        name: 'Quiet Library',
        category: 'QuietLibrary',
        blurb: 'Reading room — oak shelves, lamp amber, soft paper quiet.',
        swatches: ['#292524', '#fbbf24', '#f5f5f4', '#78716c'],
        themeColor: '#292524',
      },
    ],
    docs: [
      {
        id: 'openapi_blueprint',
        name: 'OpenAPI Blueprint',
        category: 'OpenAPIBlueprint',
        blurb: 'Engineer’s blueprint — cyan grid, inked routes, drafting precision.',
        swatches: ['#0c1a24', '#38bdf8', '#0ea5e9', '#e0f2fe'],
        themeColor: '#0c1a24',
      },
      {
        id: 'schema_noir',
        name: 'Schema Noir',
        category: 'SchemaNoir',
        blurb: 'Hard-boiled API noir — near-black, mono type, stark white edges.',
        swatches: ['#0a0a0a', '#fafafa', '#525252', '#a3a3a3'],
        themeColor: '#0a0a0a',
      },
      {
        id: 'spec_terminal',
        name: 'Spec Terminal',
        category: 'SpecTerminal',
        blurb: 'ANSI man-page — charcoal shell, amber prompts, code-first clarity.',
        swatches: ['#111827', '#fbbf24', '#6b7280', '#f3f4f6'],
        themeColor: '#111827',
      },
      {
        id: 'courier_manual',
        name: 'Courier Manual',
        category: 'CourierManual',
        blurb: 'Printed field manual — cream paper, red stamps, typewriter rules.',
        swatches: ['#f5f0e6', '#991b1b', '#1f2937', '#78716c'],
        themeColor: '#f5f0e6',
      },
      {
        id: 'grid_reference',
        name: 'Grid Reference',
        category: 'GridReference',
        blurb: 'Swiss grid system — stark white, pure black, one electric accent.',
        swatches: ['#ffffff', '#000000', '#2563eb', '#e5e5e5'],
        themeColor: '#ffffff',
      },
    ],
    stickers: [
      {
        id: 'scrapbook_pastel',
        name: 'Scrapbook Pastel',
        category: 'ScrapbookPastel',
        blurb: 'Washi-tape board — soft pastels, torn paper, sticker joy.',
        swatches: ['#fff7ed', '#fb7185', '#a78bfa', '#67e8f9'],
        themeColor: '#fff7ed',
      },
      {
        id: 'emoji_arcade',
        name: 'Emoji Arcade',
        category: 'EmojiArcade',
        blurb: 'Cabinet glow — magenta cabinets, neon cyan, high-score gold.',
        swatches: ['#1e0338', '#f0abfc', '#22d3ee', '#fde047'],
        themeColor: '#1e0338',
      },
      {
        id: 'polaroid_wall',
        name: 'Polaroid Wall',
        category: 'PolaroidWall',
        blurb: 'Pinboard of snaps — cork brown, white frames, flash warmth.',
        swatches: ['#44403c', '#fafaf9', '#f59e0b', '#78716c'],
        themeColor: '#44403c',
      },
      {
        id: 'bubble_pop',
        name: 'Bubble Pop',
        category: 'BubblePop',
        blurb: 'Soda-pop UI — glossy bubbles, sky gradients, playful bounce.',
        swatches: ['#ecfeff', '#06b6d4', '#f472b6', '#ffffff'],
        themeColor: '#ecfeff',
      },
      {
        id: 'chalk_board',
        name: 'Chalk Board',
        category: 'ChalkBoard',
        blurb: 'Classroom slate — dusted green, chalk white, eraser smudge.',
        swatches: ['#1a2e1a', '#f5f5f4', '#86efac', '#a3a3a3'],
        themeColor: '#1a2e1a',
      },
    ],
    unprompted: [
      {
        id: 'street_interview',
        name: 'Street Interview',
        category: 'StreetInterview',
        blurb: 'Mic-check urban — asphalt, highlighter yellow, clip-on chrome.',
        swatches: ['#18181b', '#facc15', '#e4e4e7', '#71717a'],
        themeColor: '#18181b',
      },
      {
        id: 'radio_wave',
        name: 'Radio Wave',
        category: 'RadioWave',
        blurb: 'Broadcast night — VU meters, warm amber dials, FM static haze.',
        swatches: ['#1c1210', '#f59e0b', '#fb923c', '#fef3c7'],
        themeColor: '#1c1210',
      },
      {
        id: 'field_notes',
        name: 'Field Notes',
        category: 'FieldNotes',
        blurb: 'Reporter’s notebook — graph paper, blue ballpoint, coffee rings.',
        swatches: ['#f8fafc', '#1d4ed8', '#0f172a', '#94a3b8'],
        themeColor: '#f8fafc',
      },
      {
        id: 'civic_bulletin',
        name: 'Civic Bulletin',
        category: 'CivicBulletin',
        blurb: 'Town-hall board — municipal blue, notice-paper cream, stamp red.',
        swatches: ['#1e3a5f', '#fefce8', '#dc2626', '#93c5fd'],
        themeColor: '#1e3a5f',
      },
      {
        id: 'night_dispatch',
        name: 'Night Dispatch',
        category: 'NightDispatch',
        blurb: 'Late desk radio — indigo, signal green, ticker-tape urgency.',
        swatches: ['#0b1220', '#4ade80', '#818cf8', '#e0e7ff'],
        themeColor: '#0b1220',
      },
    ],
  };

  const PAGE_LABELS = {
    app: 'App (Chat)',
    about: 'About',
    docs: 'Docs',
    stickers: 'Sticker Board',
    unprompted: 'Unprompted',
  };

  function allThemes() {
    const list = SHARED.slice();
    Object.keys(BY_PAGE).forEach((p) => {
      BY_PAGE[p].forEach((t) => list.push(Object.assign({ pageExclusive: p }, t)));
    });
    return list;
  }

  function byId(id) {
    if (id === 'page_default') {
      return {
        id: 'page_default',
        name: 'Page default',
        category: 'System',
        blurb: 'Semi-random style chosen for each page (stable for the day).',
        swatches: ['#1a1a2e', '#10b981', '#7c3aed', '#38bdf8'],
        themeColor: '#1a1a2e',
      };
    }
    return allThemes().find((t) => t.id === id) || null;
  }

  function poolForPage(page) {
    return SHARED.concat(BY_PAGE[page] || []);
  }

  function hashStr(s) {
    let h = 2166136261;
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  /** Semi-random but stable for (page, UTC day). */
  function pageDefaultId(page) {
    const pool = poolForPage(page);
    if (!pool.length) return 'emerald_protocol';
    const day = new Date().toISOString().slice(0, 10);
    const h = hashStr(page + '|' + day);
    return pool[h % pool.length].id;
  }

  global.GD_THEME_CATALOG = {
    SHARED: SHARED,
    BY_PAGE: BY_PAGE,
    PAGE_LABELS: PAGE_LABELS,
    allThemes: allThemes,
    byId: byId,
    poolForPage: poolForPage,
    pageDefaultId: pageDefaultId,
  };
})(typeof window !== 'undefined' ? window : globalThis);
