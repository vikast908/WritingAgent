---
version: 1
name: Writing Agent
description: >
  Design system for Writing Agent — an autonomous writing system with a web
  dashboard (stdlib server + SPA), an interactive TUI (Rich + prompt_toolkit),
  and a one-shot CLI. Editorial and literary: ink on paper, one accent (the
  editor's manuscript red), a serif that's worth reading. Flat, borderless,
  type-led.
colors:
  ink: "#17171a"            # base text + brand mark
  ink-soft: "#3a3a3d"       # secondary ink
  accent: "#a3341f"         # manuscript red — the editor's pencil; primary interaction
  accent-strong: "#872a19"  # hover / pressed
  brass: "#b0812f"          # warm secondary counterpoint; used sparingly
  paper: "#faf8f4"          # light background — warm off-white, not blue-white
  paper-2: "#f2ede4"        # sidebar / recessed light surface
  surface-light: "#ffffff"  # cards, elevated light surfaces
  ink-900: "#121211"        # dark background — warm near-black
  surface-dark: "#1c1b19"   # cards, elevated dark surfaces
  foreground-light: "#17171a"
  foreground-dark: "#f3efe6" # warm paper-white text on dark
  red: "#c23b2b"            # destructive / error — deliberately hotter than brand oxblood
  green: "#2f7d5a"          # success (muted sage, not neon)
  orange: "#c07a2b"         # warning
  yellow: "#c9a227"         # categorical indicator (gold)
  cyan: "#3f6f78"           # categorical indicator (slate-teal)
  purple: "#7a6fa6"         # categorical indicator (muted)
typography:
  display:
    fontFamily: "Fraunces, 'Iowan Old Style', Charter, Georgia, 'Times New Roman', serif"
    fontWeight: 340
    opticalSize: 144
    lineHeight: 0.94
    letterSpacing: "-0.01em"
  h2:
    fontFamily: "Fraunces, 'Iowan Old Style', Charter, Georgia, serif"
    fontWeight: 380
    opticalSize: 72
    lineHeight: 1.05
  body-read:
    fontFamily: "Fraunces, 'Iowan Old Style', Charter, Georgia, serif"
    fontWeight: 400
    opticalSize: 18
    fontSize: 1.0625rem
    lineHeight: 1.62
    measure: 66ch
  drop-cap:
    fontFamily: "Fraunces, 'Iowan Old Style', Charter, Georgia, serif"
    fontWeight: 420
    opticalSize: 144
    lines: 3
  ui-sans:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, system-ui, sans-serif"
    fontSize: 0.8125rem
    lineHeight: 1.55
  ui-mono:
    fontFamily: "'JetBrains Mono', 'Cascadia Code', 'SF Mono', ui-monospace, Menlo, Consolas, monospace"
    fontSize: 0.8125rem
    lineHeight: 1.5
  label-caps:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif"
    fontSize: 0.6875rem
    fontWeight: 600
    letterSpacing: "0.14em"
    textTransform: uppercase
  kbd:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', system-ui, sans-serif"
rounded:
  none: 0px      # content surfaces, cards, reading column — square, page-like
  xs: 2px
  sm: 3px        # buttons, inputs
  md: 4px
  lg: 6px        # overlays, dialogs, popovers
  full: 9999px   # toggles, pills, avatar tiles
spacing:
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 48px
  measure: 66ch  # optimal reading line length on prose surfaces
components:
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.paper}"
    rounded: "{rounded.sm}"
    padding: "10px 20px"
  button-primary-hover:
    backgroundColor: "{colors.accent-strong}"
    textColor: "{colors.paper}"
  button-secondary:
    backgroundColor: "color-mix(in oklab, {colors.accent} 7%, transparent)"
    textColor: "{colors.accent}"
    rounded: "{rounded.sm}"
  button-ghost:
    backgroundColor: transparent
    rounded: "{rounded.sm}"
  surface-card:
    backgroundColor: "{colors.surface-light}"
    textColor: "{colors.foreground-light}"
    rounded: "{rounded.none}"
  surface-card-dark:
    backgroundColor: "{colors.surface-dark}"
    textColor: "{colors.foreground-dark}"
    rounded: "{rounded.none}"
  overlay:
    backgroundColor: "{colors.surface-light}"
    textColor: "{colors.foreground-light}"
    rounded: "{rounded.lg}"
  input:
    backgroundColor: "#fffdfa"
    rounded: "{rounded.sm}"
    padding: "8px 12px"
  segmented-control:
    backgroundColor: "color-mix(in oklab, {colors.accent} 6%, transparent)"
    rounded: "{rounded.sm}"
---

## Overview

Writing Agent is an autonomous writing system — it drafts, critiques, revises,
and ships articles and books. It runs across three surfaces that share one
identity: a **web dashboard** (pure-stdlib server + single-page app), an
**interactive TUI** (Rich + prompt_toolkit), and a **one-shot CLI**.

**Voice:** A tireless, exacting editor. Precise without being cold; literary
without being precious. The interface should feel like a well-set page — the
kind of thing worth reading — not like a dashboard bolted onto a model. Every
screen is about *words earning their place*.

**Principles across all surfaces:**

1. **Type is the interface.** This is a writing tool. A real serif carries the
   reading and display roles; UI sans and mono play support. Prose surfaces
   respect an optimal *measure* (~66ch). Nothing else competes with the text.
2. **Ink and one accent.** Ink-black is the base for text and the brand mark.
   Exactly one chromatic accent — **manuscript red** (`#a3341f`), the editor's
   pencil — drives interaction, links, and marks. Brass is a rare warm
   counterpoint. Everything else is paper and hairlines.
3. **Flat, not boxed.** No card-in-card. Group with whitespace and a single
   hairline rule, never nested rounded boxes. Content surfaces are **square**
   (page-like); only controls and overlays carry a small radius.
4. **Borderless + shadow for elevation.** Overlays float on `--shadow-page`
   plus a near-transparent hairline (`--stroke-hair`). No hard borders on
   dialogs, toasts, or popovers.
5. **Tokens over literals.** CSS custom properties on web; a Python theme
   catalog on the TUI; YAML skins on the CLI. Strokes and fills are *derived*
   from ink + accent via `color-mix`, never hand-picked per component.
6. **One surface, not three.** Every interactive pattern — navigation, buttons,
   overlays, loaders, dropdowns — appears once per codebase. Forking a
   primitive is a regression.

## Colors

The palette is **ink on paper with one accent**. It is deliberately warm — a
cream paper (`#faf8f4`), not the cool blue-white of a typical app — so the
product reads as *print*, not *chrome*.

**Anchors**

- **Ink (`#17171a`):** Primary text and the brand mark (the pilcrow). The
  darkest, most-used value. Contrast ~15:1 on paper.
- **Accent / Manuscript Red (`#a3341f`):** The one interaction color — buttons,
  links, focus rings, the active nav item, selected states, editorial marks.
  Oxblood, not fire-engine: it reads as a red-pencil edit, not an alarm.
  `accent-strong` (`#872a19`) is hover/pressed.
- **Brass (`#b0812f`):** A warm secondary counterpoint, used *sparingly* — a
  rule above a byline, a small highlight. Never an interaction driver. This is
  the through-line to the TUI's "ink & brass" default skin.

**Paper & surfaces**

- **Paper (`#faf8f4`):** Light-mode background seed — warm off-white.
- **Paper-2 (`#f2ede4`):** Sidebar / recessed light surface.
- **Surface Light (`#ffffff`):** Cards and elevated light surfaces.
- **Ink-900 (`#121211`):** Dark-mode background — warm near-black.
- **Surface Dark (`#1c1b19`):** Cards and elevated dark surfaces.
- **Foreground Light (`#17171a`) / Dark (`#f3efe6`):** Body text per scheme;
  dark-mode text is a warm paper-white, never pure `#fff`.

**Semantic** — separated from the brand so the UI never looks like one giant
warning:

- **Red / destructive (`#c23b2b`):** Errors and destructive actions. Kept
  deliberately *hotter and more saturated* than the oxblood brand accent so
  "delete" never reads as "link."
- **Green (`#2f7d5a`):** Success — a muted sage, not neon.
- **Orange (`#c07a2b`):** Warnings.
- **Yellow (`#c9a227`), Cyan (`#3f6f78`), Purple (`#7a6fa6`):** Categorical
  indicators only (telemetry-by-node, context-usage meters). Never interaction.

Dark-mode overrides (lift for legibility on ink):
accent → `#d05a41`, red → `#e0604e`, green → `#5aa07f`, brass → `#cda24e`.

### Text hierarchy

Text is `--ink` mixed toward transparent (light) / `--paper-fg` toward
transparent (dark):

| Token | Alpha | Use |
|-------|-------|-----|
| `--text-primary` | 94% | Body text, headings |
| `--text-secondary` | 72% | Supporting text, metadata |
| `--text-tertiary` | 52% | Muted labels, placeholders |
| `--text-quaternary` | 34% | Disabled, decorative |

### Stroke hierarchy

Strokes mix the accent (a whisper of red warmth) with ink at controlled ratios,
so borders feel like they belong to the ink family, not a separate gray:

| Token | Accent Mix | Ink Mix | Use |
|-------|-----------|---------|-----|
| `--stroke-primary` | 20% | 12% | Input borders, focus rings |
| `--stroke-secondary` | 12% | 8% | Default borders, section rules |
| `--stroke-tertiary` | 7% | 5% | In-panel dividers, hairline rows |
| `--stroke-quaternary` | 4% | 3% | Faint dividers |
| `--stroke-hair` | — | 3% currentColor | The near-invisible hairline paired with `--shadow-page` on overlays |

### Fill hierarchy

Fills mix the accent at descending strength (selected states carry a faint
red wash):

| Token | Accent Mix | Use |
|-------|-----------|-----|
| `--fill-primary` | 14% | Selected states, strong fills |
| `--fill-secondary` | 10% | Active rows |
| `--fill-tertiary` | 7% | Muted backgrounds |
| `--fill-quaternary` | 5% | Secondary buttons |
| `--fill-quinary` | 3% | Barely-there fills |

### Surfaces (web)

| Surface | Light | Dark |
|---------|-------|------|
| Chrome (main BG) | `#faf8f4` | `#121211` |
| Sidebar | `#f2ede4` | `#0e0e0d` (ink-900 −tint) |
| Card / Editor | `#ffffff` | `#1c1b19` |
| Elevated (overlay) | `#ffffff` + `--shadow-page` | `#211f1c` + `--shadow-page` |

### TUI skin colors (default — "ink & brass")

The TUI keeps a terminal-native palette that mirrors this identity. Ink-on-warm
with a brass/red editorial accent — *not* a general-purpose amber terminal.

| Token | Color | Use |
|-------|-------|-----|
| Banner border | `#b0812f` | Panel borders (brass hairline) |
| Banner title | `#a3341f` | Wordmark / panel titles (manuscript red) |
| Banner accent | `#c9a227` | Section headers |
| Banner dim | `#8a7a5c` | Muted labels, separators |
| Banner text | `#f3efe6` | Body text (paper-white) |
| UI accent | `#a3341f` | General UI accent |
| UI ok | `#3f7d5a` | Success |
| UI error | `#c23b2b` | Error |
| UI warn | `#c07a2b` | Warning |
| Prompt | `#f3efe6` | Input prompt |
| Status bar BG | `#1c1b19` | Status bar background |
| Status bar text | `#c9c2b4` | Status bar default text |
| Status bar good | `#7fae8f` | Healthy context usage |
| Status bar warn | `#c9a227` | Warning context usage |
| Status bar critical | `#e0604e` | Critical context usage |

## Typography

Three families, strictly separated by role. The serif is the identity.

**Fraunces** (display + reading — vendored): A characterful old-style serif
with optical-size and weight axes, bundled once as a variable WOFF2 (SIL OFL,
fully offline). It carries **both** the display role (the wordmark, hero
headlines, section heads — high optical size, light weight, tight tracking)
**and** the reading role (manuscript body at low optical size, weight 400,
line-height 1.62). One file, two jobs — that's why it's the single vendored
face. Fallback stack when the font hasn't loaded:
`'Iowan Old Style', Charter, Georgia, 'Times New Roman', serif`.

- **Display:** opsz 144, wght 340, `letter-spacing: -0.01em`, line-height 0.94.
- **Reading (prose surfaces):** opsz 18, wght 400, `font-size: 1.0625rem`,
  line-height 1.62, `max-width: 66ch` (the measure).
- **Drop cap:** the first letter of a shipped manuscript / reading view is set
  as a 3-line drop cap (Fraunces, wght 420) — the signature reading flourish.

**System Sans** (UI): The workhorse for body chrome, labels, buttons, form
controls, sidebar, dialogs. Native stack, never vendored:
`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, system-ui, sans-serif`.
Base 0.8125rem / line-height 1.55. Small labels use `label-caps` (uppercase,
0.14em tracking, weight 600).

**JetBrains Mono** (code / figures / telemetry): Stack
`'JetBrains Mono', 'Cascadia Code', 'SF Mono', ui-monospace, Menlo, Consolas, monospace`.
Used for code blocks, diffs, cost tables, trace lines, inline code.

**Kbd / Keycaps:** Always the native UI face, never themed. Small caps.

**TUI:** Terminal-native. Rich panels and tables; monospace throughout. The
wordmark renders as a figlet banner in the active skin's colors; the loader is
the caret motif (below), not an emoji spinner.

## Layout

### Web dashboard (SPA)

Fixed sidebar + variable main pane.

| Token | Value | Use |
|-------|-------|-----|
| `--sidebar-width` | 216px | Persistent left sidebar |
| `--main-max` | 1100px | Max width for dashboard views |
| `--measure` | 66ch | Reading column on prose surfaces (manuscript, reports) |
| `--page-inset-x` | 32px | Page side padding |
| `--gap` | 24px | Default section gap |

- **Reading surfaces** (manuscript, artifact viewer, restyled drafts) constrain
  prose to `--measure` and center it on the surface — a column of type, not a
  full-bleed wall of text.
- **Rows** (`ListRow`): flat, flush-left, label / description / action. No
  dividers between rows unless the list needs them; prefer spacing. When needed:
  one `--stroke-tertiary` hairline.
- **Overlays** ride one shared shell (scrim + centered card).

### TUI (Python, Rich + prompt_toolkit)

Terminal-native. No grid. Wordmark banner (figlet) on entry; response panels use
Rich `Panel` with border colors from the active skin; status bar at the bottom
carries context-usage meters. Spinner at the input line during API calls is the
caret motif.

### Shape / radius

Editorial means **crisp**. Content surfaces are square; radius appears only on
things you click.

| Scale | Value | Use |
|-------|-------|-----|
| `none` | 0px | **Cards, content surfaces, reading column, panels** |
| `xs` | 2px | Chips, small tags |
| `sm` | 3px | Buttons, inputs, icon buttons |
| `md` | 4px | Nested control groups |
| `lg` | 6px | Overlays, dialogs, popovers, dropdown menus |
| `full` | 9999px | Toggles, pills, the brand tile |

Square content + hairline rules is the whole point: it reads like a set page.
Do not soften cards "to look friendlier" — that erases the identity.

## Elevation & Depth

One shadow system.

**`--shadow-page`** (overlays): a layered, downward-weighted shadow with
negative spread on each layer — contact → mid → ambient → falloff. No hard
border; pairs with `--stroke-hair` (a 3% `currentColor` hairline). Every
overlay, dialog, toast, popover, and dropdown menu uses this pair.

```css
--shadow-page:
  0 0.125rem 0.25rem -0.125rem color-mix(in srgb, #000 8%, transparent),
  0 0.5rem 0.75rem -0.375rem  color-mix(in srgb, #000 7%, transparent),
  0 1.25rem 1.75rem -0.875rem color-mix(in srgb, #000 6%, transparent),
  0 2.25rem 3rem -1.75rem     color-mix(in srgb, #000 0%, transparent);
--stroke-hair: color-mix(in srgb, currentColor 3%, transparent);
```

**Standard shadows** (`xs`–`lg`): for non-overlay surfaces that must read
against any background (composer, floating badge). Single light source from
above; include a 1px hairline in the stack. Cards themselves are usually flat
(hairline only) — elevation is reserved for things that *float*.

## Components

### Button

One component. Variants: `default` (primary), `destructive`, `secondary`,
`outline`, `ghost`, `link`, `text`. Sizes: `default`, `xs`, `sm`, `lg`,
`inline`, and icon sizes.

- **Primary:** filled `--accent` (manuscript red), paper text; hover →
  `--accent-strong`. Flat (no shadow).
- **Destructive:** filled `--red` (the hotter semantic red), paper text.
- **Secondary:** soft red wash (`--fill-quaternary`), accent text, no shadow.
- **Ghost:** transparent, hover fill on `--fill-tertiary`.
- **Text / link:** no chrome, accent color, underline on hover. Inline actions.

Icons inside buttons inherit a single size; never re-set per instance.

### Input / Textarea / Select

Shared control shape. Resting border `--stroke-secondary`; hover lifts to
`--stroke-primary`; focus goes full `--accent` ring (immediate, no animation).
Background `#fffdfa` (light) / translucent over chrome (dark). OS number
spinners removed (`appearance: textfield`).

Native `<select>` popups **cannot** be themed, so selects are a custom `.csel`
dropdown: a styled button + a floating menu on `--shadow-page` + `--stroke-hair`,
accent selected state, themed scrollbar inside, full keyboard support
(Arrow/Enter/Esc, ARIA `listbox`/`option`).

### SearchField

Borderless, underline-on-focus, auto-width. Never wrapped in a bordered tile.

### SegmentedControl

For small mutually-exclusive sets (color mode, view tabs). Accent fill on the
selected segment. Replaces radio piles and pill rows.

### Switch

Bare toggle, `full` radius, with `aria-label`. Accent when on.

### Overlay / Dialog / Toast / ConfirmModal

Every overlay uses `--shadow-page` + `--stroke-hair`, `lg` radius, a scrim, and
close via `Esc` / click-out / an ×-icon (never the word "Close"). Destructive
actions use `ConfirmModal` with **type-to-confirm**. Native `prompt()`/
`confirm()` are never used.

### Loader — the Caret

The signature motion. Never the literal word "Loading…", never a generic
spinner. The loader is a **blinking text caret** `▍` — the cursor of a writer at
work — optionally paired with a live word-count / token-count ticking up for
long operations (drafting, revising). On the TUI it's the same caret at the
input line.

### BrandMark — the Pilcrow

The wordmark glyph is a **pilcrow `¶`** set in Fraunces, ink on a soft paper
tile (`full` radius), identical in light and dark. It's the app's mark in the
sidebar header, the favicon, and the TUI banner. No sparkles, no robots, no
mascot — a typographic mark for a typographic product. The **caret `▍`** is its
motion companion (loader, cursor).

### LogView

Raw log surface: no background, hairline border, tight padding, small mono.
Every place raw logs surface (Live run, Activity, Cost trace) uses this.

### EmptyState

Centered, quiet, one line of guidance. Don't hand-roll centered empties.

### Code / CodeBlock

JetBrains Mono, 0.8125rem. Inline code: 5% ink fill (light) / 7% paper fill
(dark). Blocks ride the editor surface.

### ReadingView (writing-specific)

The surface that renders a shipped manuscript / promo draft / report. Prose
constrained to `--measure`, Fraunces reading spec, a 3-line **drop cap** on the
opening paragraph, generous leading. This is where the editorial identity is
most visible — treat it as the hero.

## Motion

Quick, functional (~100–200ms on controls). Respect `prefers-reduced-motion`
for anything beyond a fade.

- **Hover:** `transition-colors 180ms ease-out`.
- **Focus:** immediate ring (no animate-in).
- **View transitions:** fade, staggered per element.
- **Loader:** the caret blink (~1s cycle); word/token counter increments live.
- **Overlay enter/exit:** fade + subtle scale (0.98 → 1 in ~150ms; reverse in
  ~100ms).

## Iconography

Inline SVGs, sized 14px (0.875rem) standard / 12px compact. One set, no mixing
libraries. Stroke icons inherit `currentColor`. Editorial glyphs (pilcrow ¶,
caret ▍, em-dash —, section §) are typographic, not iconographic — set in the
font, not drawn as SVG.

**TUI:** Rich box-drawing panels; the caret motif for progress; no emoji
spinners.

## Theming

One identity, recolored — never restructured.

### Web dashboard

- **System (auto), Light, Dark** — the canonical modes. One ink + manuscript-red
  identity; System follows the OS. Preference stored browser-side in
  `localStorage`, independent of the engine `theme` setting.
- **Named themes** — the dashboard also exposes the shared theme catalog
  (derived from the TUI's `ui.THEMES`), so a theme's *colors* match on both
  surfaces (e.g. the same "supabase" emerald web-side and TUI-side). A named
  theme **recolors** the flat editorial layout — it never changes the structure,
  shapes, type roles, or shadow system. The accent slot takes the theme's brand
  color; ink/paper/hairlines derive from it via `color-mix`.

### TUI skins

Python theme catalog (`ui.THEMES`), default **"ink & brass."** Switch with
`/theme <name>` (alias `/skin <name>`). A skin defines banner colors, UI accent,
ok/warn/error, status-bar meter colors, and the figlet wordmark — every value
optional, missing values inherit from the default. User skins live in
`~/.writingagent/skins/` as YAML.

### CLI

Inherits the active TUI skin's colors for any styled output; plain when piped.

## Do's and Don'ts

- **Do** anchor on ink + one accent (manuscript red). Introduce a new color only
  by extending the palette first, and only for a categorical/semantic role.
- **Do** let type lead. Serif for display + reading, sans for UI, mono for code.
  Respect the 66ch measure on prose.
- **Do** keep content surfaces **square**; reserve radius for controls and
  overlays.
- **Do** use `--shadow-page` + `--stroke-hair` on every floating overlay. Never
  hardcode borders on dialogs.
- **Do** reuse primitives (`Button`, `SearchField`, `SegmentedControl`,
  `ListRow`, `Loader`, `ConfirmModal`, `LogView`, `ReadingView`). Forking one is
  a regression.
- **Do** derive strokes/fills from ink + accent via `color-mix`, not hand-picked
  grays.
- **Don't** reintroduce blue as the brand. Blue is not this product's color.
- **Don't** nest cards inside cards. Flat; group with whitespace + a hairline.
- **Don't** soften content surfaces to look "friendlier" — square is the
  identity.
- **Don't** ship the literal word "Loading…" or a generic spinner. Use the Caret
  loader.
- **Don't** use native `<select>` popups, `prompt()`, or `confirm()` — they
  ignore the tokens. Use `.csel` and `ConfirmModal`.
- **Don't** let a named theme change layout, shape, type, or shadows — colors
  only.
- **Don't** use Nous/Hermes vocabulary (`shadow-nous`, `nous-girl`, `.hermes`).
  This system's names are `--shadow-page`, the pilcrow mark, `~/.writingagent`.

---

## Web dashboard application (`writing-agent web`)

The local web dashboard (`src/writingagent/webui/`) implements this system.

- **Type:** Fraunces (one vendored variable WOFF2, SIL OFL) for display + reading
  + drop-cap; system sans for UI; JetBrains Mono stack for code/figures. If the
  serif fails to load, the fallback serif stack keeps the editorial feel. No
  other fonts vendored — fully offline.
- **Identity:** ink on warm paper, manuscript-red accent, brass sparingly; square
  content surfaces, `--shadow-page` overlays, the pilcrow wordmark, the caret
  loader.
- **Views:** Studio, Live run (SSE), Projects, Project (Overview / Activity /
  Evals / Artifacts / **Rejected** / **Export** / Cost), Telemetry, Skills,
  Settings. The Rejected tab renders dropped diagrams inline + reject records +
  draft snapshots. Export offers all six formats plus a **Rewrite** (restyle in a
  style / persona / emotion, flash tier). Manuscript + report rendering uses
  `ReadingView` (measure + drop cap).
- **Theming:** System / Light / Dark + the shared named-theme catalog
  (`ui.THEMES`), colors-only recolor of the editorial layout.

---

## Web dashboard — UI/UX audit (2026-07-15)

Interaction gaps the redesign addressed (native/OS-rendered pieces that ignore
the tokens), plus accepted limitations.

### Fixed

- **Native `<select>` popups** → custom `.csel` dropdown (styled button +
  floating menu on `--shadow-page` + hairline, accent selected state, themed
  scrollbar, full keyboard + ARIA).
- **Native scrollbars** → themed globally (WebKit `::-webkit-scrollbar*` +
  Firefox `scrollbar-width/color`): thin, in-palette, hover state.
- **Native `prompt()`/`confirm()`** (destructive delete) → `ConfirmModal`
  overlay (scrim + card, Esc/click-out, type-to-confirm). Canonical overlay.
- **`<input type=number>` OS spinners** → removed (`appearance: textfield`).
- **Literal "Loading…"** → the Caret loader (`loadingHTML()`).
- **Custom-select keyboard access** → Arrow/Enter/Esc, focus return, ARIA
  `haspopup`/`expanded`/`listbox`/`option`/`selected`.
- **No copy affordance** → Copy button in the artifact viewer.
- **Wide tables** (telemetry recent-calls) → `overflow-x:auto` container so they
  scroll in place.
- **Icon-only run badge** → `role="button"`, `tabindex`, `aria-label`.

### Known limitations (accepted / documented)

- **Not responsive for mobile.** Fixed 216px sidebar, no collapse; desktop-tuned.
  Acceptable for a local tool; narrow windows aren't optimized.
- **Artifact markdown renderer is minimal.** Headings, lists, code, quotes,
  links, images — but **not markdown tables** (raw pipes show). Reports rarely
  use tables.
- **`title=` tooltips are native** (theme control, error chip, chart labels) —
  not themed; low priority.
- **Custom-select menu doesn't flip** near the bottom of a scroll container; no
  collision detection yet.
- **Modal has no focus trap** (Tab can reach the page behind); Esc/click-out/
  initial-focus work.
- **Contrast not formally audited.** Ink-on-paper and the accents look right by
  eye and follow the palette, but haven't been run through a WCAG checker. (Note:
  manuscript red on paper for small text should be verified — oxblood at small
  sizes is the one at-risk pairing; use `--accent-strong` or ink for small red
  text if it fails.)
- **Textarea resize handle** is the native corner (OS-styled).
- **SSE reconnect** is best-effort (a "reconnecting…" line); no exponential
  backoff.

### Pending — implementation of this rebrand

`design.md` now specifies the editorial identity; the **implementation** (SPA
tokens/fonts in `static/index.html`, TUI default skin in `ui.py`/`branding.py`,
vendoring Fraunces) is a follow-up change, not yet applied.
