---
version: 2
name: Editorial Design System
description: >
  A portable, cross-domain design system — editorial and literary: ink on warm
  paper, one accent (the editor's manuscript red), a real serif worth reading.
  Flat, borderless, type-led. Built to be reused across software (web/desktop),
  terminal (TUI/CLI), print & long-form (books, PDF/EPUB), and demos. Writing
  Agent is the reference implementation (see Appendix A). Every value is a token;
  colors are WCAG-AA verified (see Accessibility).
tokens:
  # Token architecture: primitive → semantic → component (see "Design tokens").
  # Names below are the SEMANTIC layer; port to CSS vars, Tailwind, JS/TS, or
  # Figma variables 1:1. Web CSS-var equivalents are given in parentheses.
colors:
  # ── anchors ──
  ink: "#17171a"              # base text + brand mark (--fg)
  ink-soft: "#3a3a3d"         # heavier-than-secondary ink
  paper: "#faf8f4"            # light background — warm off-white (--bg)
  paper-sunken: "#f2ede4"     # sidebar / recessed light surface (--sidebar)
  surface: "#ffffff"          # cards, elevated light surfaces (--surface)
  # ── accent (manuscript red) + states ──
  accent: "#a3341f"           # the one interaction color (--accent, --blue-2)
  accent-hover: "#872a19"     # hover / pressed (--blue)
  accent-muted: "color-mix(in oklab, #a3341f 10%, transparent)"  # tint fills
  accent-disabled: "#d9b9b0"  # pale accent on disabled CTAs
  on-accent: "#faf8f4"        # text/icon on an accent fill
  brass: "#b0812f"            # warm counterpoint — LARGE/rules/decorative only
  # ── text hierarchy (ink over bg at alpha) ──
  text-primary: "rgba(23,23,26,0.94)"    # body, headings
  text-secondary: "rgba(23,23,26,0.72)"  # supporting, metadata
  text-tertiary: "rgba(23,23,26,0.60)"   # muted labels, placeholders (AA-fixed)
  text-quaternary: "rgba(23,23,26,0.34)" # disabled/decorative ONLY, never info
  # ── edges & borders ──
  hairline: "color-mix(in srgb, #17171a 8%, transparent)"   # dividers (--hair)
  border: "color-mix(in srgb, #a3341f 12%, color-mix(in srgb,#17171a 8%,transparent))"  # inputs, cards
  border-strong: "color-mix(in srgb, #a3341f 20%, color-mix(in srgb,#17171a 12%,transparent))"  # hover/active edge
  focus-ring: "#a3341f"       # 2px focus ring (--accent)
  stroke-hair: "color-mix(in srgb, currentColor 3%, transparent)"  # overlay hairline
  # ── semantic / status ──
  success: "#2f7d5a"          # 4.71:1 on paper
  warning: "#a85f1e"          # 4.58:1 on paper (AA-fixed, was #c07a2b)
  error: "#c23b2b"            # 5.01:1 — destructive; hotter than brand accent
  error-strong: "#9e2a1d"     # error hover/pressed
  on-error: "#faf8f4"         # text on error fill
  info: "#3f6f78"             # informational banners (slate-teal)
  # ── selection & scrim ──
  selection: "color-mix(in srgb, #a3341f 22%, transparent)"  # ::selection
  scrim: "rgba(0,0,0,0.32)"   # overlay backdrop (light); 0.5 on dark
  # ── categorical / data-viz (indicators only, never interaction) ──
  cat-1: "#a3341f"   # accent red
  cat-2: "#3f6f78"   # cyan-slate
  cat-3: "#b0812f"   # brass
  cat-4: "#2f7d5a"   # green
  cat-5: "#7a6fa6"   # purple
  cat-6: "#c9a227"   # gold
  # ── dark-mode overrides (lift for legibility on ink) ──
  dark-bg: "#121211"
  dark-surface: "#1c1b19"
  dark-surface-raised: "#211f1c"
  dark-fg: "#f3efe6"          # warm paper-white, never pure #fff
  dark-accent: "#d8664c"      # 4.86:1 on dark card (AA-fixed, was #d05a41)
  dark-accent-hover: "#e0724f"
  dark-success: "#5aa07f"
  dark-warning: "#d08a3a"
  dark-error: "#e0604e"
  dark-brass: "#cda24e"
typography:
  # screen roles
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
  h3:
    fontFamily: "Fraunces, 'Iowan Old Style', Charter, Georgia, serif"
    fontWeight: 540
    fontSize: 1rem
    lineHeight: 1.25
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
  # print / long-form roles (see Typography → Print & long-form)
  print-body:
    fontFamily: "Fraunces, 'Iowan Old Style', Charter, Georgia, serif"
    fontSize: 11pt
    lineHeight: 1.5
    measure: "60–72 characters"
  chapter-number:
    fontFamily: "Fraunces, Georgia, serif"
    fontWeight: 300
    opticalSize: 144
  folio:
    fontFamily: "-apple-system, 'Segoe UI', system-ui, sans-serif"
    fontSize: 9pt
    letterSpacing: "0.08em"
  footnote:
    fontFamily: "Fraunces, Georgia, serif"
    fontSize: 8.5pt
    lineHeight: 1.35
rounded:
  none: 0px      # content surfaces, cards, reading column — square, page-like
  xs: 2px
  sm: 3px        # buttons, inputs, chips
  md: 4px
  lg: 6px        # overlays, dialogs, popovers, menus
  full: 9999px   # toggles, pills, avatar tiles, status dots
spacing:
  xxs: 2px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 48px
  section: 64px
  measure: 66ch  # optimal reading line length on prose surfaces
elevation:
  flat: "none"   # 95% of surfaces: hairline only, no shadow
  shadow-card: "0 1px 2px color-mix(in srgb,#000 5%,transparent), 0 0 0 1px color-mix(in srgb,#17171a 6%,transparent)"
  shadow-page: >   # the one overlay shadow (dialogs, menus, toasts)
    0 .125rem .25rem -.125rem color-mix(in srgb,#000 8%,transparent),
    0 .5rem .75rem -.375rem color-mix(in srgb,#000 7%,transparent),
    0 1.25rem 1.75rem -.875rem color-mix(in srgb,#000 6%,transparent)
motion:
  fast: 120ms       # controls: hover, small fades
  base: 180ms       # default transitions
  slow: 300ms       # overlays, view transitions
  ease-out: "cubic-bezier(0.16, 1, 0.3, 1)"
  ease-standard: "cubic-bezier(0.2, 0, 0, 1)"
  caret: "1.05s step-end"   # the Caret loader blink
breakpoints:
  sm: 640px
  md: 880px      # sidebar/grid collapse point (web dashboard)
  lg: 1128px
  xl: 1440px
zIndex:
  base: 0
  sticky: 100
  dropdown: 200
  overlay: 300     # toasts, run badge
  scrim: 400       # modal backdrop
  modal: 401
  tooltip: 500
components:
  button-primary:      { backgroundColor: "{colors.accent}", textColor: "{colors.on-accent}", rounded: "{rounded.sm}", padding: "10px 20px" }
  button-primary-hover:{ backgroundColor: "{colors.accent-hover}", textColor: "{colors.on-accent}" }
  button-primary-disabled: { backgroundColor: "{colors.accent-disabled}", textColor: "{colors.on-accent}", cursor: not-allowed }
  button-destructive:  { backgroundColor: "{colors.error}", textColor: "{colors.on-error}", rounded: "{rounded.sm}" }
  button-secondary:    { backgroundColor: "{colors.accent-muted}", textColor: "{colors.accent}", rounded: "{rounded.sm}" }
  button-ghost:        { backgroundColor: transparent, hoverFill: "{colors.accent-muted}", rounded: "{rounded.sm}" }
  button-text:         { backgroundColor: transparent, textColor: "{colors.accent}", decoration: "underline on hover" }
  input:               { backgroundColor: "#fffdfa", border: "1px {colors.border}", rounded: "{rounded.sm}", padding: "8px 12px" }
  input-hover:         { border: "1px {colors.border-strong}" }
  input-focus:         { border: "1px {colors.focus-ring}", ring: "2px {colors.focus-ring}" }
  input-error:         { border: "1px {colors.error}", helperColor: "{colors.error}" }
  input-disabled:      { backgroundColor: "{colors.paper-sunken}", textColor: "{colors.text-quaternary}", cursor: not-allowed }
  select:              { renders: "custom .csel (native option popups unthemeable)", menu: "{components.popover}" }
  segmented-control:   { backgroundColor: "{colors.accent-muted}", selectedFill: "{colors.surface}", selectedText: "{colors.accent}", rounded: "{rounded.sm}" }
  switch:              { onFill: "{colors.accent}", offFill: "{colors.border}", rounded: "{rounded.full}" }
  surface-card:        { backgroundColor: "{colors.surface}", rounded: "{rounded.none}", edge: "hairline OR shadow-card" }
  overlay:             { backgroundColor: "{colors.surface}", shadow: "{elevation.shadow-page}", edge: "{colors.stroke-hair}", rounded: "{rounded.lg}", scrim: "{colors.scrim}" }
  popover:             { backgroundColor: "{colors.surface}", shadow: "{elevation.shadow-page}", edge: "{colors.stroke-hair}", rounded: "{rounded.lg}" }
  tooltip:             { backgroundColor: "{colors.ink}", textColor: "{colors.paper}", rounded: "{rounded.sm}", typography: "{typography.ui-sans}" }
  toast:               { backgroundColor: "{colors.surface}", shadow: "{elevation.shadow-page}", edge: "{colors.stroke-hair}", rounded: "{rounded.lg}", errorText: "{colors.error}" }
  banner-info:         { backgroundColor: "color-mix(in srgb,{colors.info} 10%,transparent)", accentBar: "{colors.info}", textColor: "{colors.text-primary}" }
  banner-success:      { backgroundColor: "color-mix(in srgb,{colors.success} 10%,transparent)", accentBar: "{colors.success}" }
  banner-warning:      { backgroundColor: "color-mix(in srgb,{colors.warning} 10%,transparent)", accentBar: "{colors.warning}" }
  banner-error:        { backgroundColor: "color-mix(in srgb,{colors.error} 10%,transparent)", accentBar: "{colors.error}" }
  badge:               { backgroundColor: "{colors.accent-muted}", textColor: "{colors.accent}", rounded: "{rounded.full}", typography: "{typography.label-caps}" }
  status-dot:          { size: "7px", rounded: "{rounded.full}", colors: "success/warning/error/accent" }
  chip:                { backgroundColor: "color-mix(in srgb,{colors.accent} 5%,transparent)", textColor: "{colors.text-secondary}", rounded: "{rounded.sm}", typography: "{typography.ui-mono}" }
  brand-mark:          { glyph: "¶ (pilcrow)", tile: "{colors.ink}", glyphColor: "{colors.paper}", rounded: "{rounded.full}" }
  loader-caret:        { glyph: "▍", color: "{colors.accent}", animation: "{motion.caret}" }
  reading-view:        { fontFamily: "{typography.body-read}", measure: "{spacing.measure}", dropCap: "{typography.drop-cap}" }
---

## Overview

This is an **editorial, type-led design system** — ink on warm paper, one
accent (the editor's *manuscript red*), a real serif worth reading, flat and
borderless. It is written to be **reused across domains**: web/desktop software,
terminal apps (TUI/CLI), **print & long-form (books, PDF/EPUB)**, and demos.
Where the system needs a concrete example, **Writing Agent** is the reference
implementation (Appendix A) — but the core below is portable.

**Voice.** A tireless, exacting editor: precise without being cold, literary
without being precious. Interfaces should feel like a **well-set page** — the
kind of thing worth reading — not a dashboard bolted onto a screen.

**Principles.**

1. **Type is the interface.** A serif carries reading and display; UI sans and
   mono play support. Prose respects an optimal *measure* (~66ch). Nothing
   competes with the text.
2. **Ink and one accent.** Ink is the base for text and the brand mark. Exactly
   one chromatic accent — **manuscript red `#a3341f`** — drives interaction,
   links, and marks. Brass is a rare warm counterpoint; everything else is paper
   and hairlines.
3. **Flat, not boxed.** No card-in-card. Group with whitespace and a single
   hairline. Content surfaces are **square** (page-like); only controls and
   overlays carry a small radius.
4. **Borderless + shadow for elevation.** Overlays float on one shadow
   (`shadow-page`) plus a near-invisible hairline. No hard borders on dialogs,
   menus, toasts.
5. **Tokens over literals.** Everything is a token (below). Strokes and fills are
   *derived* from ink + accent, never hand-picked per component.
6. **One primitive per pattern.** Each interactive pattern — button, field,
   overlay, toast, loader — exists once. Forking a primitive is a regression.
7. **Accessible by construction.** Every color pair meets WCAG AA (verified);
   color is never the sole signal; focus is always visible. See Accessibility.

## Design tokens & architecture

Tokens are layered so the system ports to any stack without rewrites:

- **Primitive tokens** — raw values (`#a3341f`, `16px`, `Fraunces`). Never used
  directly in components.
- **Semantic tokens** — role-named (`accent`, `text-secondary`, `border`,
  `error`, `shadow-page`). Components reference *only* these. Theming swaps
  primitives behind semantics.
- **Component tokens** — per-component, per-state (`button-primary-hover`,
  `input-error`). Reference semantics.

**Naming:** `role[-variant][-state]` — e.g. `accent`, `accent-hover`,
`text-tertiary`, `banner-error`. Lowercase, hyphenated, stable across platforms.

**Portability targets (1:1 mapping):**

| Platform | Form |
|---|---|
| Web (CSS) | Custom properties: `--accent`, `--text-secondary`, `--shadow-page` |
| Tailwind | `theme.extend.colors.accent`, `boxShadow['page']`, etc. |
| JS / TS | Exported object: `tokens.color.accent`, `tokens.space.md` |
| Figma | Variables in matching collections (color / number / string) |
| Terminal | Palette dict / YAML skin (see Theming → TUI) |
| Print | CSS Paged Media / typesetting stylesheet (see Typography → Print) |

Derived tokens use `color-mix` so a single accent recolors strokes, fills, and
tints. A theme that only redefines `accent` + `ink` + `paper` recolors the
entire system (see Theming → contract).

## Colors

**Ink on paper with one accent.** Deliberately warm — a cream paper
(`#faf8f4`), not the cool blue-white of a typical app — so it reads as *print*,
not *chrome*.

**Anchors**
- **Ink `#17171a`** — primary text + brand mark. Never pure black. 16.9:1 on paper.
- **Accent / Manuscript red `#a3341f`** — the one interaction color: buttons,
  links, focus rings, active nav, selected states, editorial marks. Oxblood, not
  fire-engine — a red-pencil edit, not an alarm. `accent-hover #872a19` for
  press/hover.
- **Brass `#b0812f`** — warm counterpoint, used sparingly (a rule above a byline,
  a small highlight). **Large text / rules / decorative only** (3.28:1 — fails AA
  for body text). Never an interaction driver.

**Surfaces** — paper `#faf8f4`, paper-sunken `#f2ede4` (sidebar/recessed),
surface `#ffffff` (cards). Dark: bg `#121211`, surface `#1c1b19`, raised
`#211f1c`. Dark text is warm paper-white `#f3efe6`, never `#fff`.

**Semantic / status** — separated from the brand so the UI never looks like one
giant warning:

| Role | Light | Dark | On paper |
|---|---|---|---|
| success | `#2f7d5a` | `#5aa07f` | 4.71:1 ✓ |
| warning | `#a85f1e` | `#d08a3a` | 4.58:1 ✓ |
| error / destructive | `#c23b2b` | `#e0604e` | 5.01:1 ✓ |
| info | `#3f6f78` | `#5a97a2` | — |

Error is hotter and more saturated than the oxblood accent so "delete" never
reads as "link." Dark-mode accent lifts to `#d8664c` (4.86:1 on dark cards).

**Text hierarchy** (ink over background at alpha):

| Token | Alpha | On paper | Use |
|---|---|---|---|
| text-primary | 94% | 16:1 | body, headings |
| text-secondary | 72% | 6.9:1 | supporting, metadata |
| text-tertiary | 60% | 4.6:1 | muted labels, placeholders |
| text-quaternary | 34% | 2.2:1 | **disabled/decorative only — never information** |

**Fills** (accent mixed at descending strength): `fill-primary` 14% (selected),
`fill-secondary` 10% (active rows), `fill-tertiary` 7%, `fill-quaternary` 5%
(secondary buttons), `fill-quinary` 3%.

**Categorical / data-viz** — indicators only (charts, telemetry), never
interaction: red · cyan-slate · brass · green · purple · gold (ordered for
distinctness). See Data visualization for scales.

## Accessibility

The system targets **WCAG 2.2 AA** and is verified, not assumed.

**Contrast (verified).** Text ≥ 4.5:1 (normal) / 3:1 (large ≥ 24px, or ≥ 18.66px
bold); UI components & graphics ≥ 3:1. All body text, links, button labels, and
secondary text pass AA in both modes. Exceptions, by design:
- **Brass** and **text-tertiary** clear only the 3:1 bar → **large text / rules /
  placeholders only**.
- **text-quaternary** (2.2:1) is exempt (disabled/decorative) — **never carries
  information**.
- A new theme MUST preserve these ratios (Theming → contract).

**Focus.** Every interactive element shows a visible focus ring: 2px
`focus-ring` (accent), 1px offset. Never remove focus outlines; style them.

**Target size.** Interactive targets ≥ **44×44px** (pointer) / ≥ 24px with
spacing (WCAG 2.2 minimum). Icon buttons get padding to reach the floor.

**Keyboard.** Everything operable without a mouse. Overlays **trap focus**
(Tab cycles within; Esc closes; focus returns to the opener). Provide a skip
link to main content. Logical tab order follows visual order.

**Color is never the sole signal.** Status pairs color with an icon or label
(error field shows an icon + message, not just a red border). Charts add
pattern/label, not hue alone.

**Motion.** Honor `prefers-reduced-motion`: disable non-essential animation,
keep a plain fade. No parallax/auto-play under reduced motion.

**Content.** Images carry `alt`; decorative images use empty `alt`. Form fields
have programmatic labels; errors are linked via `aria-describedby`. Live regions
announce toasts/async results.

## Typography

Three families, strictly separated by role. **The serif is the identity.**

**Fraunces** (display + reading — vendored). A characterful old-style serif with
optical-size + weight axes, one variable WOFF2 (SIL OFL, offline). Carries both
**display** (wordmark, headings — high opsz, light weight, tight tracking) and
**reading** (body at low opsz, weight 400, line-height 1.62, measure 66ch).
Fallback: `'Iowan Old Style', Charter, Georgia, 'Times New Roman', serif`.

**System sans** (UI). Body chrome, labels, buttons, controls, sidebar. Native
stack, never vendored. Base 0.8125rem / 1.55. Small labels use `label-caps`
(uppercase, 0.14em, 600).

**JetBrains Mono** (code / figures / data). Stack falls back to Cascadia → SF
Mono → system mono.

**Kbd** — native UI face, small caps, never themed.

**Reading surfaces** constrain prose to the **measure** (66ch), center it, and
open with a **3-line drop cap** in accent — the signature reading flourish.

**Substitutes.** If Fraunces can't be vendored, `Newsreader` or `Source Serif 4`
transfer cleanly; the system-serif fallback keeps the editorial feel with zero
files. UI sans → any humanist sans (Inter is an acceptable substitute).

### Print & long-form (books, PDF/EPUB)

For book, report, and print output the screen scale gives way to a print scale:

- **Page geometry.** Symmetric or golden-ratio margins; generous inner margin
  for binding. Single measure of **60–72 characters**. Body at ~11pt / 1.5.
- **Baseline grid.** Vertical rhythm on a consistent leading; headings snap to
  the grid.
- **Running heads & folios.** Author/title verso, chapter recto; folio (page
  number) in `label-caps` at the foot or outer corner. Suppress on chapter
  openers and blank versos.
- **Chapter openers.** Recto start, sinkage from the top, oversized
  `chapter-number` (Fraunces light), optional drop cap or small-caps first line.
- **Detailing.** Real small-caps, old-style figures, ligatures; hang punctuation
  on justified measures; control widows/orphans (min 2 lines); enable
  hyphenation for justified text.
- **Footnotes / marginalia** in `footnote` (8.5pt), separated by a short rule.
- **Front/back matter.** Half-title, title, copyright, dedication, epigraph,
  TOC; then back matter (acknowledgments, about, colophon).
- **Images & plates.** Full-measure or full-bleed; captions in `ui-sans` /
  small; figure numbering.
- **Color management.** Screen tokens are sRGB; for offset print convert to
  CMYK and expect the manuscript-red to shift — proof it. Provide **bleed**
  (3mm) and trim marks for print PDFs. EPUB uses the screen tokens as-is.

## Layout & responsive

**Spacing** — 4px base: `xxs 2 · xs 4 · sm 8 · md 16 · lg 24 · xl 48 · section
64`. Group with space before rules.

**Grid & containers.** Content max ~1100px on dashboard views; **reading
surfaces cap at the 66ch measure** and center. Sidebar 216px (desktop). Page
inset 32px.

**Breakpoints.**

| Name | Width | Behavior |
|---|---|---|
| sm | < 640 | single column; sidebar → top bar / drawer; controls stack full-width |
| md | 640–880 | 2-column grids; sidebar collapses at ≤ 880 |
| lg | 880–1128 | full sidebar + main; grids 2–3 up |
| xl | ≥ 1440 | content caps; gutters absorb the rest |

Reduce columns at each step — never reflow rows unpredictably. Reading measure
never exceeds 66ch regardless of width.

**Layering (z-index).** `base 0 · sticky 100 · dropdown 200 · overlay 300
(toasts) · scrim 400 · modal 401 · tooltip 500`. Never hand-pick z-index — use
the scale.

**Density.** Default is comfortable. An optional **compact** mode tightens
row padding and control heights for data-dense demos; it never changes type
sizes below legibility or targets below the a11y floor.

## Shape & radius

Editorial means **crisp**. Content surfaces are square; radius appears only on
things you click or that float.

| Scale | Value | Use |
|---|---|---|
| none | 0px | cards, content surfaces, reading column, panels |
| xs | 2px | chips, small tags |
| sm | 3px | buttons, inputs, icon buttons |
| md | 4px | nested control groups |
| lg | 6px | overlays, dialogs, popovers, menus |
| full | 9999px | toggles, pills, status dots, the brand tile |

Square content + hairline rules reads like a set page. Do not soften cards "to
look friendly" — that erases the identity.

## Elevation & depth

One shadow system, three levels:

- **Flat** — 95% of surfaces: a single hairline, no shadow.
- **`shadow-card`** — cards/composer that must read against any background: soft
  1px + hairline. Usually cards stay flat; elevation is for things that *float*.
- **`shadow-page`** — the one overlay shadow (layered, downward-weighted, no hard
  border), paired with `stroke-hair` (3% currentColor). Every dialog, menu,
  popover, tooltip, toast uses it.
- **Scrim** — `rgba(0,0,0,0.32)` light / `0.5` dark behind modal overlays.

## Motion

Quick and functional. Tokens: `fast 120ms` (controls), `base 180ms`, `slow
300ms` (overlays/views); easings `ease-out` / `ease-standard`.

- **Hover:** color transition `fast`. **Focus:** ring appears immediately (no
  animate-in).
- **Overlay enter/exit:** fade + subtle scale (0.98→1, `slow`; reverse faster).
- **View transitions:** fade, staggered per element.
- **Loader — the Caret:** a blinking `▍` at `motion.caret` (see Notifications).
- **Reduced motion:** collapse everything beyond a fade.

## Edges & borders

Edges belong to the ink family (a whisper of accent warmth), never a separate
gray. Four weights + the overlay hairline:

| Token | Use |
|---|---|
| `hairline` | dividers, row separators, section rules (the default line) |
| `border` | resting input/card borders |
| `border-strong` | hover/active edges, focus-adjacent |
| `focus-ring` | 2px accent ring on `:focus-visible`, 1px offset |
| `stroke-hair` | the near-invisible 3% hairline on floating overlays |

Rules: prefer **whitespace over lines**; one hairline where a divider is truly
needed; never nest bordered boxes; tables use hairline row separators, no
column borders; the last row drops its border.

## Components

Each pattern exists once, with an explicit **state set**:
*default · hover · active · focus · disabled · loading · selected · error*.

### Buttons
- **Primary** — accent fill, `on-accent` text; hover → `accent-hover`; flat.
- **Destructive** — `error` fill, `on-error` text (distinct from primary red).
- **Secondary** — `accent-muted` wash, accent text.
- **Ghost** — transparent, hover `fill-tertiary`.
- **Text / link** — no chrome, accent, underline on hover.
- **Disabled** — `accent-disabled` (primary) / reduced opacity; `not-allowed`.
- **Loading** — label swaps to the Caret; button stays sized, disabled.
Icons inherit one size; never re-set per instance.

### Inputs, selects & forms
Shared control shape. Resting `border`; hover `border-strong`; focus full
`focus-ring` + 2px ring (immediate). Background `#fffdfa` (light) / translucent
(dark). Native number spinners removed. Native `<select>` popups can't be themed
→ custom `.csel` (button + `popover` menu, accent selected state, themed
scrollbar, full keyboard + ARIA). **Error state** below (Error states).

### SegmentedControl / Switch / SearchField
- **Segmented** — small mutually-exclusive sets; accent fill on the selected
  segment. Replaces radio piles.
- **Switch** — bare toggle, `full` radius, accent when on, `aria-label`.
- **SearchField** — borderless, underline-on-focus, auto-width; never a boxed
  tile.

### Surfaces
- **Card** — `surface`, square, hairline (or `shadow-card` when floating). No
  card-in-card.
- **ListRow** — flat, flush-left: label / description / action. Prefer spacing to
  dividers.
- **Code / CodeBlock** — JetBrains Mono; inline code 5% ink fill; blocks ride the
  editor surface.
- **ReadingView** — the hero prose surface: measure + reading spec + drop cap.

### Brand mark & Loader
- **BrandMark** — the **pilcrow `¶`** in Fraunces on an ink tile (`full` radius),
  identical light/dark. Sidebar header, favicon, TUI banner. No mascots.
- **Loader — the Caret** — a blinking `▍` (accent), optionally with a live
  word/token counter for long ops. Never the literal word "Loading…".

## Overlays

All floating surfaces share `shadow-page` + `stroke-hair` + `lg` radius and the
layer scale. Taxonomy:

| Overlay | Trigger / behavior | Dismiss |
|---|---|---|
| **Modal / Dialog** | blocking; scrim behind; **focus-trapped** | Esc · scrim click · × icon |
| **Sheet** | edge-anchored panel (mobile nav, filters) | Esc · scrim · swipe |
| **Popover / Menu** | anchored to a control (`.csel`, actions) | outside click · Esc · select |
| **Tooltip** | hover/focus hint; ink fill, paper text | blur / mouseout |
| **Toast** | transient feedback (see Notifications) | auto-timeout · × |

Rules: never the word "Close" (use an × icon); overlays close on Esc and
outside-click *except* install/onboarding; menus should flip when near a
viewport edge (collision) — a documented gap in the reference impl.

## Notifications & feedback

- **Toast** — transient, bottom-right, `surface` + `shadow-page`; success/plain
  vs error (error text in `error`). Auto-dismiss (~3s; ~6s for errors); × to
  close; announced via a live region. One at a time; queue extras.
- **Banner** — persistent, in-flow, full-width: `info` / `success` / `warning` /
  `error`, each a 10% tinted background + a 3px left accent bar + icon + message
  + optional action. For state that must stay visible (quota, degraded mode).
- **Alert (inline)** — a compact banner scoped to a section or form.
- **Badge** — small count/label pill (`accent-muted` + accent, `label-caps`).
- **Status dot** — 7px `full` dot: success/warning/error/accent (e.g. a live-run
  pulse). Always paired with a text label (color-not-sole-signal).
- **Progress** — thin accent bar on a faint track; indeterminate uses the Caret.
- **Empty / loading / skeleton** — `EmptyState` (centered, one guiding line);
  loading uses the Caret; skeletons are hairline-outlined blocks at `fill-tertiary`
  (no shimmer under reduced motion).

## Highlights & selection

- **Text selection** — `selection` (accent @22%) via `::selection`.
- **Selected item** — `fill-primary` wash + accent text/left-marker (nav item,
  list row, segmented segment, `.csel` option with a ✓).
- **Active row** — `fill-secondary`.
- **Hover** — `fill-tertiary` (never a heavy block).
- **Search / match highlight** — accent-tinted background on the matched span;
  keep text contrast ≥ 4.5:1.
- **"New" / emphasis marker** — a small accent badge or dot, plus a label; never
  color alone.
- **Focus highlight** — the `focus-ring`, distinct from selection.

## Error states

Errors are explicit, calm, and never rely on color alone.

- **Field validation** — border → `error`, an **icon + helper message** in
  `error` beneath, linked with `aria-describedby`; on submit, focus the first
  invalid field and summarize errors at the top of the form.
- **Inline / section error** — an `alert` (error banner) scoped to the region
  with a retry action where relevant.
- **Toast error** — for async/action failures; error text, longer timeout,
  live-region announced.
- **Full-page / boundary error** — a canonical `ErrorState`: mark/icon, a plain
  title, one-sentence cause, and a primary recovery action. Same look for React
  error boundaries, boot failures, and empty-with-error.
- **Destructive confirm** — a modal with **type-to-confirm** for irreversible
  actions; the confirm button is `destructive`.
- **Copy** — say what happened and what to do next ("Couldn't reach the model —
  check your key and retry"), never a raw stack trace.

## Iconography

Inline SVGs, one set, no mixing libraries. 14px (0.875rem) standard / 12px
compact; 1.5px stroke; inherit `currentColor`. Editorial glyphs (pilcrow ¶,
caret ▍, em-dash —, section §) are typographic, set in the font — not drawn.
Icons that carry meaning get an accessible label; icons beside text are
`aria-hidden`. Terminal: Rich box-drawing + the caret motif (no emoji spinners).

## Data visualization

- **Categorical** — the ordered set (red · cyan-slate · brass · green · purple ·
  gold); stop at 6, then group "other." Each series also gets a label/shape, not
  hue alone.
- **Sequential** — a single-hue ramp from `paper` → `accent` (or ink) for
  intensity.
- **Diverging** — `error` ↔ neutral ↔ `success` for signed values.
- **Contrast** — chart strokes/fills ≥ 3:1 against the surface; axis/labels use
  `text-tertiary` or stronger.
- **Colorblind-safe** — for critical distinctions use the Okabe-Ito set (shipped
  as the `highcontrast` theme in the reference impl) and rely on shape + label.

## Imagery & brand

- **Brand mark** — the pilcrow `¶`. **Clear space** ≥ the pilcrow's cap height on
  all sides; **min size** 16px (favicon) / 20px (UI). Ink tile + paper glyph,
  constant across themes. Misuse: don't recolor per theme, don't add effects,
  don't substitute a mascot.
- **Favicon** — ink tile, paper pilcrow, `xs` radius.
- **Photography/illustration** (marketing/book) — full-measure or full-bleed;
  let imagery carry visual weight so type can stay quiet (the editorial default).

## Voice & microcopy

- **Case** — sentence case for UI text, buttons, and headings ("Propose angles",
  not "Propose Angles"). `label-caps` is the only uppercase, for tiny labels.
- **Buttons** — a verb ("Save", "Propose angles", "Export"), not "OK/Submit".
- **Errors** — plain, specific, actionable; no blame, no jargon, no stack traces.
- **Empty states** — one line of guidance + the primary action.
- **Numbers/dates** — tabular figures for aligned numerals; ISO or localized
  dates consistently; currency/units explicit.
- **Tone** — the editor's voice: exact, warm, unfussy.

## Localization & RTL

- Use **logical properties** (`margin-inline`, `padding-block`, `start/end`), not
  left/right, so layouts mirror for RTL automatically.
- Mirror directional icons (chevrons, arrows) in RTL; never mirror the brand mark.
- Allow text to grow ~30% (German/Finnish) — don't fix widths to English.
- Provide non-Latin font fallbacks; the 66ch measure is Latin — adjust for
  scripts with different density (CJK ~ 40–45 characters).
- Keep number/date/currency formatting locale-aware.

## Theming

One identity, **recolored — never restructured**.

**Modes.** System (auto) · Light · Dark — one ink + manuscript-red identity;
System follows the OS. Preference stored per-client, independent of engine
settings.

**Named themes.** A shared palette catalog recolors the flat editorial layout —
same structure, shapes, type, and shadows; only the hue changes. The accent slot
takes the theme's brand color; ink/paper/edges derive from it via `color-mix`.

**Theming contract.** A valid theme MUST define `ink`, `paper`, `accent` (+ dark
equivalents) and MUST preserve the Accessibility ratios (body ≥ 4.5:1, UI ≥
3:1). Validate a new theme against the contrast table before shipping.

**Terminal (TUI).** A palette catalog (default **"ink & brass"**: gold primary,
brass secondary, manuscript-red status + wordmark gradient). Switch with
`/theme` (alias `/skin`). Skins define banner colors, accent, ok/warn/error,
status-bar meters, and the wordmark; missing values inherit the default. User
skins live in `~/.<app>/skins/` as YAML.

**CLI.** Inherits the active skin for styled output; plain when piped.

## Do's and Don'ts

- **Do** anchor on ink + one accent. Add a color only by extending the palette,
  and only for a semantic/categorical role.
- **Do** let type lead: serif display + reading, sans UI, mono data; respect the
  measure.
- **Do** keep content surfaces **square**; reserve radius for controls/overlays.
- **Do** use `shadow-page` + `stroke-hair` on every floating overlay; reference
  the z-index scale.
- **Do** reuse primitives; forking one is a regression.
- **Do** verify a new color/theme against the AA contrast table.
- **Don't** reintroduce blue as the brand. Blue is not this system's color.
- **Don't** nest cards; group with whitespace + a hairline.
- **Don't** ship the word "Loading…" or a generic spinner — use the Caret.
- **Don't** signal state with color alone; pair an icon/label.
- **Don't** remove focus outlines; style them.
- **Don't** use brass or text-tertiary for body text (large/rules/placeholder
  only); never text-quaternary for information.
- **Don't** let a named theme change layout, shape, type, or shadows — colors
  only.

## Governance & versioning

- **SemVer** the system. Breaking = renamed/removed token or changed semantic
  meaning (minor bump also updates this doc's `version`).
- **Changelog** every token addition/rename/deprecation; deprecate before
  removing (keep an alias one minor cycle).
- **Definition of done** for a component: all states specified, AA verified,
  keyboard + focus handled, tokens (not literals), documented here.
- **Single source of truth** — this file. Implementations sync to it (see the
  reference impl); drift is a bug.

## Adopting this system in a new project

1. Copy the **semantic tokens** (colors, type, spacing, radius, elevation,
   motion, z-index) into your platform's token form (table above).
2. Vendor **Fraunces** (or accept the system-serif fallback); wire the sans/mono
   stacks.
3. Build the primitives once: Button, Input/Field, Select (`.csel`), Overlay,
   Toast/Banner, Loader (Caret), BrandMark, ReadingView.
4. Set modes (System/Light/Dark); if adding a named theme, run the **theming
   contract** check.
5. Verify against **Accessibility** (contrast table, focus, targets, keyboard).
6. For print/book output, add the **Print & long-form** stylesheet.

---

## Appendix A — Reference implementation: Writing Agent

Writing Agent (an autonomous writing system) implements this system across three
surfaces that share one identity: a **web dashboard** (pure-stdlib server + SPA),
an **interactive TUI** (Rich + prompt_toolkit), and a **one-shot CLI**.

- **Type:** Fraunces vendored as one variable WOFF2 (SIL OFL), served over
  `/static/fonts/`; system sans for UI; JetBrains Mono for code/figures. Fully
  offline; fallback serif if the font doesn't load.
- **Identity:** ink on warm paper, manuscript-red accent, brass sparingly; square
  content surfaces, `shadow-page` overlays, the pilcrow wordmark, the Caret
  loader, drop-cap ReadingView on the manuscript.
- **Web views:** Studio · Live run (SSE) · Projects · Project (Overview /
  Activity / Evals / Artifacts / **Rejected** / **Export** / Cost) · Telemetry ·
  Skills · Settings. Export offers all six formats + a **Rewrite** (restyle in a
  style/persona/emotion). Custom `.csel` dropdowns, `ConfirmModal`
  (type-to-confirm), themed scrollbars.
- **Theming:** System / Light / Dark + the shared named-theme catalog
  (`ui.THEMES`) — colors-only recolor of the editorial layout, matched between
  web and TUI.
- **TUI default skin "ink & brass":** gold primary (`#c9a227`, legible on dark +
  distinct in the theme catalog), brass secondary, manuscript-red status, an
  oxblood→terracotta→gold wordmark gradient.

## Appendix B — Reference impl UI/UX audit & known gaps (2026-07-15)

**Fixed in the redesign:** native `<select>` popups → custom `.csel`; native
scrollbars → themed; native `prompt()/confirm()` → `ConfirmModal`
(type-to-confirm); number-input spinners removed; literal "Loading…" → Caret;
custom-select keyboard/ARIA; copy affordance on artifacts; wide tables scroll in
`overflow-x` containers; icon-only run badge got a role/label. All AA color
issues from the first pass are now fixed in the palette (warning orange
darkened, text-tertiary raised to 60%, dark accent lifted to `#d8664c`, brass
restricted to large/rules).

**Known gaps (accepted / documented):**
- **Responsive** — the dashboard is desktop-tuned (fixed 216px sidebar); the
  breakpoint spec above is the target, not yet fully implemented.
- **Markdown tables** in the artifact renderer show raw pipes (rare in reports).
- **`title=` tooltips** are native (not the themed `tooltip`).
- **Popover collision** — the `.csel` menu doesn't yet flip near a viewport edge.
- **Contrast** — now verified by computation (this pass); re-verify any new token.
- **SSE reconnect** is best-effort (no exponential backoff).
