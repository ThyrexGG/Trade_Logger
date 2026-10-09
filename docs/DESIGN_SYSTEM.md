# TradeLogger design system: "Precision"

Last updated 2026-10-08. Covers the web app (`frontend/`). The desktop app is a
window around the same site, so it inherits all of this. The Android app
(`mobile/`) has the new icons but its screens still use the old gold theme.
Logo, voice and brand assets are in [BRAND.md](BRAND.md).

---

## 1. Why it looks like this

The brief was **"futuristic through precision: premium, intelligent,
technical, minimal, calm, not flashy or neon"**, for users who are mostly
**beginner traders**. Every decision below follows from one question: *what
helps someone make calm, clear decisions about real money?*

| Decision | Reason |
|---|---|
| Deep navy, not black | Softer than pure black on long sessions; reads as a serious instrument (cockpit, terminal) without harshness. |
| Gold removed | It read as "luxury / casino / get rich", the wrong mood for a discipline tool, and it was too close to the amber warning colour. |
| **One** accent (ice cyan) | If everything glows nothing stands out. Cyan means only "you can act here / this is now". |
| Green and red only on money | On a trading app colour must carry meaning. A red button next to a red loss is confusing. |
| No glass blur or glow | Blurred backgrounds make numbers harder to read and slowed weaker devices. Solid layered surfaces are clearer. |
| Geist + Geist Mono, max weight 600 | Built for interfaces; mono digits are equal width so prices and P&L line up. Lighter weights read as calm, not shouting. |
| Hairlines, not boxes | Rows of separate stat cards waste space and make everything equally loud. One divided panel shows more and scans faster. |
| Navigation by the trader's day | Pages were grouped by how the code was built; now they follow the order people use them. |
| Calm motion, no bounce | Trading is emotional enough; the UI should never add excitement, least of all when showing a loss. |

Inspiration (studied, not copied): [Linear's UI redesign](https://linear.app/now/how-we-redesigned-the-linear-ui)
and [design refresh](https://linear.app/now/behind-the-latest-design-refresh),
[Vercel Geist](https://vercel.com/design/components),
[Bloomberg Terminal UX](https://www.bloomberg.com/company/?p=34667),
[Matt Ström on UI density](https://mattstromawn.com/writing/ui-density/).

---

## 2. Principles

1. **Scan → understand → decide → act.** Every page leads with the answer, then
   the explanation, then the controls.
2. **Information hierarchy:** NOW (what needs attention) → TODAY → ANALYZE →
   REFERENCE. Higher levels sit higher and are louder.
3. **Plain English first.** A beginner-readable summary, with the expert detail
   behind a "More details" toggle. Page guides on every page. No developer
   wording ("endpoint", "authoritative", CLI commands) in the UI.
4. **One primary button per screen.** Everything else is secondary or ghost.
5. **Real data only.** No placeholder numbers; empty and error states say what
   happened and what to do.
6. **Futuristic through precision**, not effects: alignment, tabular figures,
   fine rules, exact time-zone maths.

---

## 3. Colour

Defined in [`frontend/src/styles/tokens.css`](../frontend/src/styles/tokens.css).
Dark is the default; light applies from the OS preference, and the account
menu's choice (`[data-theme]`) overrides both.

### Luminance scale (depth comes from lightness steps + hairlines, not shadows)

| Token | Dark | Light | Use |
|---|---|---|---|
| `--tl-background` | `#0b0f17` | `#f4f6fa` | page ground |
| `--tl-surface` | `#111722` | `#ffffff` | cards, panels |
| `--tl-surface-elevated` | `#171e2b` | `#eef1f6` | active nav item, inputs, raised rows |
| `--tl-surface-hover` | `#1f2836` | — | hover |
| `--tl-border` / `--tl-border-subtle` | rgba(160,182,220,.14 / .08) | rgba(15,30,60,.14 / .08) | hairlines |
| `--tl-grid-line` | very faint | very faint | chart grids |

### Text

`--tl-text-primary` `#e8edf5`, `--tl-text-secondary` `#a4afc2`,
`--tl-text-muted` `#77849a` (light: `#0e1726` / `#3c4a5f` / `#5b6779`, all
AA ≥ 4.5:1 on light surfaces).

### Accent: one colour, one job

| Token | Dark | Light | Use |
|---|---|---|---|
| `--tl-accent-fill` | `#5ad1f5` | `#12a8d8` | primary button, selection marks, "now" |
| `--tl-accent` | `#5ad1f5` | `#0a6f94` | accent **text** and icons |
| `--tl-accent-fill-hover` | `#7ddcf8` | | primary hover |
| `--tl-accent-soft` / `--tl-accent-line` | cyan 10% / 42% | | focus rings, feature-card edge |

### Semantic: on figures only, never large fills

`--tl-positive` `#3ddc97` (gain) · `--tl-negative` `#f87171` (loss, stops) ·
`--tl-warning` `#f5b23d` · `--tl-info` `#8b9cff` (information / system).
P&L always carries a **+/− sign** too, so colour is never the only signal.

Legacy names (`--tl-glass-*`, `--tl-gradient-*`, `--tl-glow-*`) still exist
because many components read them, but they now resolve to solid Precision
values. **Don't use them in new code.**

---

## 4. Type

- `--tl-font-sans`: **Geist**; `--tl-font-mono`: **Geist Mono** (Google Fonts,
  weights 400–600, loaded in `index.html`).
- Tailwind's `font-bold`/`extrabold`/`black` are remapped to **600**
  (`index.css` theme), so nothing can render heavier.
- `.font-mono`, `code`, `kbd` use **tabular numbers**. All prices, P&L, times
  and counts are mono.
- Scale in use: page title 1.45rem/600 (`.tl-page-title`); card titles
  0.9rem/600; body 0.875rem; labels 0.68rem mono uppercase, tracking 0.08em
  (`.tl-label`, `.tl-eyebrow`).

---

## 5. Shape, spacing, motion tokens

- Radius: `--tl-radius-sm` 5px · `--tl-radius` 8px · `--tl-radius-lg` 10px.
- Shadow: only `--tl-shadow-pop`, for things floating over the page (menus,
  popovers).
- Easing: `--tl-ease` `cubic-bezier(0.2, 0.7, 0.2, 1)` (no overshoot);
  durations `--tl-dur-fast` 120ms, `--tl-dur` 200ms.
- Layout: sidebar 228px, top bar 52px, content max width 1320px.

---

## 6. Component kit

[`frontend/src/styles/kit.css`](../frontend/src/styles/kit.css), all in
`@layer components`, so Tailwind utilities can still override a kit class
inline. Build new UI from these instead of ad-hoc class strings.

| Class | What it is |
|---|---|
| `.tl-card` | the standard panel (surface, hairline, radius-lg) |
| `.tl-card--feature` | the *one* card per page that matters most: a 1px inset accent edge |
| `.tl-card-head` + `.tl-card-title` + `.tl-rule` | a card heading: title, optional label, fine rule filling the row (wraps on phones) |
| `.tl-card-body` | standard card padding |
| `.tl-figures` | **a row of stats as one divided panel**, replacing rows of stat cards; any `.tl-stat`/`OpsMetric` inside loses its own box |
| `.tl-stat`, `-label`, `-value`, `-sub` | a single statistic |
| `.tl-figure` | a large mono figure |
| `.tl-btn` + `--primary` / `--secondary` / `--ghost`, sizes `--sm` / `--lg` | buttons; **one primary per screen** |
| `.tl-seg` | segmented control; the selected item is whichever child has `aria-selected`, `aria-pressed`, `aria-checked` or `aria-current="page"` |
| `.tl-chip` | filter chip |
| `.tl-select`, `.tl-input` | form fields with a cyan focus ring |
| `.tl-toolbar` | the filter row under a page header |
| `.tl-page-title`, `.tl-eyebrow`, `.tl-label` | page title, mono over-title, small mono label |
| `.tl-state` (`--quiet`, `-icon`, `-icon--error`) | empty / error / unavailable states |
| `.tl-skeleton` | loading shimmer |

Shared React pieces: `PageContainer` (zone eyebrow, title, page guide, actions),
`PageGuide` + `lib/pageGuides.ts` (the one-line guide with "How it works"),
`MoreDetails` (native `<details>` for expert panels), `InfoTip`/`<Term>`
(glossary tooltips), `SectionCard` (`feature` prop), `SectionError`,
`OpsMetric`, `OpsUnavailable`.

---

## 7. Navigation (information architecture)

Defined in [`frontend/src/lib/navigation.ts`](../frontend/src/lib/navigation.ts).
**URLs did not change**; only grouping and labels did. A page's zone is found
by membership first, then by URL prefix.

| Zone | Pages (label → route) |
|---|---|
| **Today** | Overview `/workspace/home` · Positions · Price Alerts |
| **Plan** | Trade Planner `/workspace/trade-planner` · Position Size `/workspace/risk` · Charts `/workspace/market` |
| **Review** | Journal · Analytics · Ask AI `/workspace/assistant` |
| **Learn** | Market Intelligence · Economic News `/research/macro` · Crypto Carry |
| **Settings** (bottom of sidebar) | Connections · System Health · Partners |

- Sign-in lands on **Overview**.
- Old routes redirect: Command Center → Overview; Loss Limits → Overview;
  Killzone Scanner → Trade Planner; Chart Analyzer → Trade Planner `?tab=chart`.
- **Phone:** bottom bar with Today / Plan / Review / Learn plus **More**
  (opens the full menu).
- **Top bar:** breadcrumbs; status chips only when something is true (local
  mode, syncing, reconnecting); search; the avatar **account menu** (theme,
  click sounds, connection health, version, sign out).

---

## 8. Overview: the command centre

[`pages/HomePage.tsx`](../frontend/src/pages/HomePage.tsx) +
[`components/home/`](../frontend/src/components/home/). Ordered by the
hierarchy in §2. **One account at a time** (switcher at the top, remembered
per device in `tl.home.account`); accounts are never mixed.

1. **Market strip** (`MarketStrip.tsx`): market mood, the US dollar, how many
   markets lean up or down, then up to six markets with an arrow and a 3-step
   strength meter. **Markets you trade come first.** Refreshes every 5 minutes;
   links into Market Intelligence.
2. **Session Rail** (`SessionRail.tsx`, `sessions.ts`): today on *your* clock:
   Sydney, Tokyo, London and New York sessions in each city's own time, plus
   the killzones in New York time (London 02–05, NY AM 08:30–11, NY PM
   13:30–16, Asian 20–24, matching the backend's `detect_active_killzone`), a
   live "now" marker, and your trades from today. Weekends show as closed. All
   time-zone maths via `Intl`, so daylight-saving shifts are exact.
3. **Now panel:** Today / Open now / This month / Win rate (6 months) as one
   figure row, then open trades as **Position Tracks**.
4. **Position Track** (`PositionTracks.tsx`): each open trade drawn from
   stop → entry → now → target, with its **R multiple** (how many times the
   risk you're up or down) and a **warning if there's no stop loss**.
5. **Closed today** and **Price alerts**.
6. **Performance** (`PnlHeatmap.tsx`): a compact P&L calendar beside a
   running-total chart, starting at your first trade (13–26 weeks; 13 on
   phones), plus one quiet line of highlights: Best day, Toughest day, Best
   market, Day streak. Clicking a day opens its trades (`DayTradesPanel.tsx`).

---

## 9. Motion and sound

**Motion is short, smooth and only says "this changed".** No bounce or
overshoot anywhere. Everything decorative switches off under
`prefers-reduced-motion: reduce`.

| Where | What |
|---|---|
| Every page | 200ms fade-and-rise on arrival (`.tl-page-in`) |
| Overview figures | count up from zero on first load (`useCountUp`, 900ms) |
| P&L calendar | squares appear in a quick stagger (`tl-heat-pop`) |
| Running-total chart | the line draws itself, the area fades in, and the latest point breathes slowly (`tl-draw`, `tl-pulse`) |
| Highlights | rise into view as you scroll (CSS scroll-driven animation; browsers without it just show them) |
| Loading | skeleton shimmer, then a soft fade to real content |
| Menus, toasts | 180ms pop or slide in |

**Sound** ([`lib/sound.ts`](../frontend/src/lib/sound.ts)): a soft, quiet
"plop" (Web Audio, synthesized, no audio files) on buttons, links and tabs,
via one delegated listener. "Bubble" plays when you turn sounds on; a "chime"
is available for success moments. **On by default, toggle in the account
menu**, remembered per device (`tl.sound`). Text fields never click; any
element with `data-silent` (or inside one) is silent.

---

## 10. Page patterns

- **Header:** zone eyebrow → title → one-line page guide → actions on the right
  (one primary, e.g. "Sync now").
- **Toolbar:** account select, date range or segmented filters, view toggle.
  Advanced filters collapse behind a "Filters" button with a count.
- **Results before settings:** e.g. Analytics shows your numbers first and
  the prop-challenge setup below them.
- **Figure rows** (`.tl-figures`) instead of rows of stat cards.
- **Expert detail** behind `MoreDetails`.
- **Empty states** say what to do next ("Connect a broker", "No trades
  today yet").

---

## 11. Checking UI changes

`npm run build` passing is not enough. A layout bug once shipped with a clean
build. Before pushing UI work:

1. Run an **isolated** backend (local SQLite, multiuser auth, no broker
   credentials; **never** the production `DATABASE_URL` in `.env`) and Vite
   with `VITE_DEV_API_PROXY_TARGET` pointing at it.
2. Seed test data under an `audit-…@example.com` user.
3. Screenshot every changed page in **dark, light and phone (390px)** with
   Playwright, and check for page errors and sideways overflow
   (`documentElement.scrollWidth > innerWidth`, ignoring `body`, which hides
   overflow-x).
4. Clean up the test rows and user.

Don't run the full `pytest` suite at the same time: its fixtures delete
`%@example.com` users from the same SQLite file.

---

## 12. Not yet converted

- **Android app** screens (`mobile/`): new icons and splash only; screens are
  still gold.
- **Find setups**, **Economic News** and Analytics' detail charts use the new
  styling but still carry expert-level content; they're next for plain-English
  simplification.
- The **claude.ai/design canvas** from early in the redesign shows the
  abandoned playful-gold direction; it is not a reference.

## 13. Change log

| Date | Commit | Change |
|---|---|---|
| 2026-10-07 | `aee1056`…`abac6fe` | Animated Home (later Overview); one account at a time; Command Center folded in |
| 2026-10-08 | `3d18e5e` | Plain-English Market Intelligence + page guides everywhere |
| 2026-10-08 | `15feaa3` | Loss Limits removed; Killzone Scanner + Chart Analyzer merged into Trade Planner |
| 2026-10-08 | `1fede99` | Precision system, trader's-day navigation, Overview command centre |
| 2026-10-08 | `230c301` | New logo and all brand assets, login and legal screens, branded reset email; see [BRAND.md](BRAND.md) |
| 2026-10-08 | (this change) | Link chips + link editor on notes and trade cards; see [JOURNAL_LINKS.md](JOURNAL_LINKS.md) |

## Phone app

`mobile/src/theme.ts` mirrors the dark tokens above (navy ground, ice-cyan accent `#5ad1f5`, green `#3ddc97` / red `#f87171` / amber `#f5b23d`, radii 5/8/10), so the phone matches the desktop app. Selected chips and outlined buttons use `colors.accentSoft` / `colors.accentLine`; text on the accent fill uses `colors.accentInk`. The phone is dark-only and still uses the system font (Geist is not bundled). Change the tokens in `theme.ts`, never hard-code gold or old reds in a screen.
