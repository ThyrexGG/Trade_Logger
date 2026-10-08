# TradeLogger brand guide

Last updated 2026-10-08. This replaces the gold/black candlestick identity from
W11 (2026-09-14). For the rest of the visual system (colours, type, components,
layout), see [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md).

## 1. What TradeLogger is (and how it should feel)

TradeLogger is a private trading journal for retail traders, most of them
beginners. It syncs their trades, shows their performance, and explains market
context in plain English.

The brand should feel **calm, precise and trustworthy**: a well-made
instrument, not a casino. Trading is already emotional; the product's job is to
lower the temperature. That rules out gold, glow, hype words and celebration
noise as defaults.

- **Name:** TradeLogger, one word with a capital T and capital L. Never "Trade
  Logger", "TRADELOGGER" or "Tradelogger".
- **Domain:** tradelogger.site
- **Promise (one line):** "Your trading journal, made clear."
- **Supporting line:** "Every trade synced, every number in plain English."
- **Descriptor:** "Trading journal · analytics · market context"

## 2. The mark

![mark](../brand/logo-tile.svg)

The mark is **a trade drawn the way TradeLogger draws trades**: the same
picture as the Position Track on the Overview page.

| Part | Meaning | Colour |
|---|---|---|
| Short horizontal bar, bottom left | the **stop loss** below the entry | red (`--tl-negative`) |
| Rising, stepped line | the **trade's path**: up, a pull-back, then on to target | cyan (`--tl-accent-fill`) |
| Faint horizontal line, top | the **target** level | cyan at 45% opacity |
| Dot on the target line | the **trade landing on its target** | cyan |

It deliberately avoids candlesticks, bull/bear animals, arrows and dollar
signs: every trading app uses those. The stop is what makes the mark ours:
TradeLogger cares about *where you'd be wrong*, not only where you hope to go.

### Construction

- Drawn on a **64 × 64 grid**. The single source of truth is `GLYPH` in
  [`brand/build_brand_assets.py`](../brand/build_brand_assets.py); the in-app
  [`BrandMark.tsx`](../frontend/src/components/shell/BrandMark.tsx) uses the
  same coordinates.
- Tile: rounded square, corner radius **14/64**, fill `#111826`, 1-unit edge in
  `rgba(160,182,220,0.18)`.
- Path: points (14,42) → (25,31) → (33,37.5) → (48,17.5), stroke 4.6, round
  caps and joins.
- Stop: (11.5,49.5) → (23,49.5), stroke 4, round caps.
- Target line: y = 17.5 from x 13 to 52, stroke 2.2, 45% opacity. A ring of
  radius 7.4 is cut out around the dot so it reads as "landed on the line".
- Dot: centre (48,17.5), radius 5.
- **Small-size variant (16–24 px):** no target line or ring; heavier strokes
  (path 7, stop 6.5, dot 7). Used automatically in the Windows `.ico` and the
  Android notification icon.

### Versions

| File | Use |
|---|---|
| `brand/logo-tile.svg` | the default: mark on its navy tile |
| `brand/logo-glyph-dark.svg` | mark without a tile, on dark grounds |
| `brand/logo-glyph-light.svg` | mark without a tile, on light grounds (darker cyan `#12a8d8`, red `#dc2626`) |
| `brand/logo-mono.svg` | single colour (`currentColor`), for stamps, embossing, monochrome icons |

### Rules

- **Clear space:** keep at least ¼ of the tile's width empty around it.
- **Minimum size:** 16 px (use the small variant below 32 px).
- **Don't:** recolour the stop green or the path red (the colours carry
  meaning), add glow or gradients, rotate it, put it in a circle, or outline
  the glyph.
- **Lockup:** mark + "TradeLogger" in Geist SemiBold, letter-spacing −0.015em,
  gap = 40% of the mark's height. Stacked (mark above) for square spaces;
  horizontal everywhere else (`BrandLockup` in the app).

## 3. Colour

The brand uses the product's own palette. Full token list:
[DESIGN_SYSTEM.md §3](DESIGN_SYSTEM.md#3-colour).

| Role | Dark | Light |
|---|---|---|
| Ground (deep navy) | `#0b0f17` | `#f4f6fa` |
| Icon tile | `#111826` | — |
| Accent (ice cyan) | `#5ad1f5` | fill `#12a8d8`, text `#0a6f94` |
| Stop / loss | `#f87171` | `#b91c1c` |
| Profit | `#3ddc97` | `#047857` |
| Text | `#e8edf5` / `#a4afc2` / `#77849a` | `#0e1726` / `#3c4a5f` / `#5b6779` |

**One accent only.** Cyan marks the thing you can act on, or the "now". Red
and green appear only on money and stops, never as decoration.

## 4. Type

- **Geist** (UI and headings) and **Geist Mono** (figures, labels, codes). Both
  by Vercel, SIL Open Font License; files in `brand/fonts/` for asset
  generation, served from Google Fonts in the app.
- Weights: 400 for body, 500 for emphasis, **600 maximum**. Nothing bolder.
- Numbers always in mono with tabular figures so columns line up.
- Small uppercase labels: Geist Mono, 0.68rem, letter-spacing 0.08em.

## 5. Voice

Write for a beginner trader who is a little stressed.

- Plain words first ("how sure the market looks", not "conviction score"); put
  the term of art in a tooltip if needed.
- Short, active sentences. Say what a button does ("Sync now", "Send reset
  link").
- Calm about losses: "Toughest day", not "Worst day!". No exclamation marks in
  product copy.
- Honest about limits: it's a journal, **not financial advice**, and we never
  show invented numbers.

## 6. Asset inventory

Everything below is **generated**; edit the script, never the PNGs by hand.

```
python brand/build_brand_assets.py
```

| File | Size | Where it appears |
|---|---|---|
| `frontend/public/favicon.svg` | vector | browser tab (modern browsers) |
| `frontend/public/favicon.png` | 192 | browser tab fallback |
| `frontend/public/icon-192.png`, `icon-512.png` | 192, 512 | installed web app (PWA) icon |
| `frontend/public/icon-maskable-512.png` | 512 | Android PWA icon (OS crops it; mark in the central 70%) |
| `frontend/public/apple-touch-icon.png` | 180 | iPhone/iPad home screen (opaque, iOS rounds it) |
| `frontend/public/og-image.png` | 1200×630 | link previews (WhatsApp, X, Discord, iMessage…) |
| `frontend/public/wordmark.png` / `wordmark-transparent.png` | 1024 | stacked lockup for socials and press |
| `frontend/public/avatar-tiktok.png` | 1024 | social profile picture (circle-safe) |
| `desktop/build/icon.ico` | 16–256 | Windows desktop app, taskbar, installer |
| `desktop/build/overlay-badge.png` | 64 | taskbar badge when a price alert fires |
| `mobile/assets/icon.png` | 1024 | Expo/iOS app icon |
| `mobile/assets/android-icon-foreground.png` / `-background.png` / `-monochrome.png` | 1024 | Android adaptive + themed icon |
| `mobile/assets/splash-icon.png` | 1024 | Android app splash (on `#0b0f17`) |
| `mobile/assets/notification-icon.png` | 96 | Android status bar (white silhouette) |
| `mobile/assets/favicon.png` | 48 | Expo web |
| `favicon.png`, `app_icon.png`, `trade_logger_logo.png` (repo root) | 192 / 1024 | legacy copies kept in sync |

Related config: `frontend/index.html` (icons, theme-color),
`frontend/public/manifest.webmanifest` (colours, description),
`frontend/public/sw.js` (cache name bumped to `tl-shell-v2` so installed apps
pick up the new icons), `desktop/main.js` (window background `#0b0f17`),
`mobile/app.json` (splash, adaptive-icon and notification colours).

**Emails:** the password-reset email (`api/email_sender.py::_branded`) uses a
light layout with the icon, the name, and a `#0a6f94` button. It's light on
purpose: dark-mode mail clients invert light emails cleanly but mangle dark
ones.

## 7. When the new icons show up

| Surface | When |
|---|---|
| Website, browser tab, link previews | next deploy, after a reload (link-preview caches on X/Discord etc. can take days) |
| Installed web app (PWA) | after the next launch; some phones only refresh the home-screen icon on reinstall |
| Windows desktop app | the window loads the website, so the in-app logo updates immediately; the **taskbar/installer icon** needs a new desktop build (`desktop/`, electron-builder) |
| Android app | next `eas build` |
| Flutter prototype (`trade_logger_app/`) | not updated; it's a retired prototype |

## 8. History

- **2026-10-08 · Precision rebrand** (this document): navy + ice cyan, the
  stop/path/target mark, Geist.
- **2026-09-14 · W11:** gold/gray-on-black candlestick mark (retired).
- **Before that:** teal/blue candlestick mark (retired).
