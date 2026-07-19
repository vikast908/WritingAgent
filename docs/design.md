---
version: "3.0.0"
schemaVersion: "1.0.0"
name: Editorial Design System
status: stable
description: >
  A portable, cross-domain design system: editorial and literary, ink on warm
  paper, manuscript red for interaction, a real serif worth reading, and flat,
  type-led composition. This manifest is normative; prose below explains it.
tokenContract:
  root: tokens
  layers: [primitive, semantic, component]
  referenceSyntax: "{tokens.<layer>.<group>.<name>}"
  modeResolution: "Resolve semantic light/dark values before platform export."
  portability: "Adapters emit resolved values; platform syntax is not copied verbatim."
tokens:
  primitive:
    color:
      transparent: "transparent"
      ink-950: "#17171a"
      ink-800: "#3a3a3d"
      paper-50: "#faf8f4"
      paper-100: "#f2ede4"
      white: "#ffffff"
      field-light: "#fffdfa"
      night-950: "#121211"
      night-900: "#1c1b19"
      night-850: "#211f1c"
      paper-dark: "#f3efe6"
      red-700: "#a3341f"
      red-800: "#872a19"
      red-300: "#d9b9b0"
      red-dark-400: "#d8664c"
      red-dark-300: "#e0724f"
      brass-600: "#b0812f"
      brass-dark-400: "#cda24e"
      green-700: "#2f7d5a"
      green-dark-400: "#5aa07f"
      orange-700: "#a85f1e"
      orange-dark-400: "#d08a3a"
      error-600: "#c23b2b"
      error-800: "#9e2a1d"
      error-dark-400: "#e0604e"
      teal-700: "#3f6f78"
      teal-dark-400: "#5a97a2"
      purple-600: "#7a6fa6"
      purple-dark-300: "#a896d8"
      gold-700: "#8a6c00"
      gold-dark-300: "#e0bc45"
    space:
      "0": "0px"
      half: "2px"
      "1": "4px"
      "2": "8px"
      "3": "12px"
      "4": "16px"
      "5": "20px"
      "6": "24px"
      "8": "32px"
      "10": "40px"
      "12": "48px"
      "16": "64px"
    radius:
      none: "0px"
      xs: "2px"
      sm: "3px"
      md: "4px"
      lg: "6px"
      full: "9999px"
    size:
      border-width: "1px"
      focus-width: "2px"
      focus-offset: "1px"
      target-min: "24px"
      target-preferred: "44px"
      control-height: "44px"
      icon-compact: "12px"
      icon-default: "14px"
      icon-stroke: "1.5px"
      status-dot: "7px"
      sidebar: "216px"
      page-inset: "32px"
      content-max: "1100px"
      reading-measure: "66ch"
    number:
      drop-cap-lines: 3
    glyph:
      brand: "¶"
      loader: "▍"
    duration:
      fast: "120ms"
      base: "180ms"
      slow: "300ms"
      toast: "6000ms"
      toast-error: "10000ms"
      caret: "1.05s"
    breakpoint:
      sm: "640px"
      md: "880px"
      lg: "1128px"
      xl: "1440px"
    font:
      serif: "Fraunces, 'Iowan Old Style', Charter, Georgia, 'Times New Roman', serif"
      sans: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, system-ui, sans-serif"
      mono: "'JetBrains Mono', 'Cascadia Code', 'SF Mono', ui-monospace, Menlo, Consolas, monospace"
  semantic:
    color:
      ink: { light: "{tokens.primitive.color.ink-950}", dark: "{tokens.primitive.color.paper-dark}" }
      ink-soft: { light: "{tokens.primitive.color.ink-800}", dark: "#d0cbc2" }
      paper: { light: "{tokens.primitive.color.paper-50}", dark: "{tokens.primitive.color.night-950}" }
      paper-sunken: { light: "{tokens.primitive.color.paper-100}", dark: "{tokens.primitive.color.night-900}" }
      surface: { light: "{tokens.primitive.color.white}", dark: "{tokens.primitive.color.night-900}" }
      surface-raised: { light: "{tokens.primitive.color.white}", dark: "{tokens.primitive.color.night-850}" }
      field: { light: "{tokens.primitive.color.field-light}", dark: "{tokens.primitive.color.night-850}" }
      accent: { light: "{tokens.primitive.color.red-700}", dark: "{tokens.primitive.color.red-dark-400}" }
      accent-hover: { light: "{tokens.primitive.color.red-800}", dark: "{tokens.primitive.color.red-dark-300}" }
      accent-disabled: { light: "{tokens.primitive.color.red-300}", dark: "#6b4037" }
      on-accent: { light: "{tokens.primitive.color.paper-50}", dark: "{tokens.primitive.color.night-950}" }
      brass: { light: "{tokens.primitive.color.brass-600}", dark: "{tokens.primitive.color.brass-dark-400}" }
      text-primary: { light: "#252527", dark: "{tokens.primitive.color.paper-dark}" }
      text-secondary: { light: "#575657", dark: "#b7b2aa" }
      text-tertiary: { light: "#6b6a6a", dark: "#8a8780" }
      text-quaternary: { light: "#adabaa", dark: "#5f5b56" }
      hairline: { light: "#e8e6e3", dark: "#302e2b" }
      border: { light: "#958680", dark: "#796d68" }
      border-strong: { light: "#82736d", dark: "#8a7c75" }
      focus-ring: { light: "{tokens.primitive.color.red-700}", dark: "{tokens.primitive.color.red-dark-400}" }
      stroke-hair: { light: "#f3f1ed", dark: "#2a2825" }
      success: { light: "{tokens.primitive.color.green-700}", dark: "{tokens.primitive.color.green-dark-400}" }
      warning: { light: "{tokens.primitive.color.orange-700}", dark: "{tokens.primitive.color.orange-dark-400}" }
      error: { light: "{tokens.primitive.color.error-600}", dark: "{tokens.primitive.color.error-dark-400}" }
      error-strong: { light: "{tokens.primitive.color.error-800}", dark: "#f07562" }
      info: { light: "{tokens.primitive.color.teal-700}", dark: "{tokens.primitive.color.teal-dark-400}" }
      on-error: { light: "{tokens.primitive.color.paper-50}", dark: "{tokens.primitive.color.night-950}" }
      selection: { light: "#e7cdc5", dark: "#452c24" }
      scrim: { light: "rgba(0,0,0,0.32)", dark: "rgba(0,0,0,0.50)" }
      fill-primary: { light: "#eeddd6", dark: "#362620" }
      fill-secondary: { light: "#f1e4df", dark: "#2f221e" }
      fill-tertiary: { light: "#f4eae5", dark: "#29201d" }
      fill-quaternary: { light: "#f6eee9", dark: "#251f1c" }
      fill-quinary: { light: "#f7f2ee", dark: "#221d1b" }
      fill-info: { light: "#e4e8e5", dark: "#232a29" }
      fill-success: { light: "#e2e9e2", dark: "#232b25" }
      fill-warning: { light: "#f0e6da", dark: "#32281d" }
      fill-error: { light: "#f3e1dc", dark: "#34231f" }
      cat-1: { light: "{tokens.primitive.color.red-700}", dark: "{tokens.primitive.color.red-dark-400}" }
      cat-2: { light: "{tokens.primitive.color.teal-700}", dark: "{tokens.primitive.color.teal-dark-400}" }
      cat-3: { light: "{tokens.primitive.color.brass-600}", dark: "{tokens.primitive.color.brass-dark-400}" }
      cat-4: { light: "{tokens.primitive.color.green-700}", dark: "{tokens.primitive.color.green-dark-400}" }
      cat-5: { light: "{tokens.primitive.color.purple-600}", dark: "{tokens.primitive.color.purple-dark-300}" }
      cat-6: { light: "{tokens.primitive.color.gold-700}", dark: "{tokens.primitive.color.gold-dark-300}" }
    typography:
      display: { fontFamily: "{tokens.primitive.font.serif}", fontSize: "4rem", fontWeight: 340, opticalSize: 144, lineHeight: 0.94, letterSpacing: "-0.01em" }
      h1: { fontFamily: "{tokens.primitive.font.serif}", fontSize: "2.5rem", fontWeight: 380, opticalSize: 72, lineHeight: 1.05 }
      h2: { fontFamily: "{tokens.primitive.font.serif}", fontSize: "1.75rem", fontWeight: 420, opticalSize: 48, lineHeight: 1.12 }
      h3: { fontFamily: "{tokens.primitive.font.serif}", fontSize: "1.25rem", fontWeight: 540, opticalSize: 24, lineHeight: 1.25 }
      h4: { fontFamily: "{tokens.primitive.font.sans}", fontSize: "1rem", fontWeight: 650, lineHeight: 1.35 }
      body-read: { fontFamily: "{tokens.primitive.font.serif}", fontSize: "1.0625rem", fontWeight: 400, opticalSize: 18, lineHeight: 1.62, measure: "{tokens.primitive.size.reading-measure}" }
      drop-cap: { fontFamily: "{tokens.primitive.font.serif}", fontWeight: 420, opticalSize: 144, lineHeight: 0.82 }
      ui-sans: { fontFamily: "{tokens.primitive.font.sans}", fontSize: "0.875rem", lineHeight: 1.5 }
      ui-sans-compact: { fontFamily: "{tokens.primitive.font.sans}", fontSize: "0.8125rem", lineHeight: 1.5 }
      ui-mono: { fontFamily: "{tokens.primitive.font.mono}", fontSize: "0.8125rem", lineHeight: 1.5 }
      label-caps: { fontFamily: "{tokens.primitive.font.sans}", fontSize: "0.75rem", fontWeight: 600, letterSpacing: "0.12em", textTransform: uppercase }
      kbd: { fontFamily: "{tokens.primitive.font.sans}", fontSize: "0.75rem", fontWeight: 600, lineHeight: 1 }
      print-body: { fontFamily: "{tokens.primitive.font.serif}", fontSize: "11pt", lineHeight: 1.5, measure: "60–72 characters" }
      chapter-number: { fontFamily: "{tokens.primitive.font.serif}", fontWeight: 300, opticalSize: 144 }
      folio: { fontFamily: "{tokens.primitive.font.sans}", fontSize: "9pt", letterSpacing: "0.08em" }
      footnote: { fontFamily: "{tokens.primitive.font.serif}", fontSize: "8.5pt", lineHeight: 1.35 }
    radius:
      none: "{tokens.primitive.radius.none}"
      xs: "{tokens.primitive.radius.xs}"
      sm: "{tokens.primitive.radius.sm}"
      md: "{tokens.primitive.radius.md}"
      lg: "{tokens.primitive.radius.lg}"
      full: "{tokens.primitive.radius.full}"
    space:
      xxs: "{tokens.primitive.space.half}"
      xs: "{tokens.primitive.space.1}"
      sm: "{tokens.primitive.space.2}"
      md: "{tokens.primitive.space.4}"
      lg: "{tokens.primitive.space.6}"
      xl: "{tokens.primitive.space.12}"
      section: "{tokens.primitive.space.16}"
    elevation:
      flat: "none"
      shadow-card: "0 1px 2px rgba(0,0,0,0.05), 0 0 0 1px rgba(23,23,26,0.06)"
      shadow-page: "0 .125rem .25rem -.125rem rgba(0,0,0,.08), 0 .5rem .75rem -.375rem rgba(0,0,0,.07), 0 1.25rem 1.75rem -.875rem rgba(0,0,0,.06)"
    motion:
      fast: "{tokens.primitive.duration.fast}"
      base: "{tokens.primitive.duration.base}"
      slow: "{tokens.primitive.duration.slow}"
      ease-out: "cubic-bezier(0.16, 1, 0.3, 1)"
      ease-standard: "cubic-bezier(0.2, 0, 0, 1)"
      caret: "{tokens.primitive.duration.caret} step-end"
    layout:
      content-max: "{tokens.primitive.size.content-max}"
      reading-measure: "{tokens.primitive.size.reading-measure}"
      sidebar: "{tokens.primitive.size.sidebar}"
      page-inset: "{tokens.primitive.size.page-inset}"
      breakpoint-sm: "{tokens.primitive.breakpoint.sm}"
      breakpoint-md: "{tokens.primitive.breakpoint.md}"
      breakpoint-lg: "{tokens.primitive.breakpoint.lg}"
      breakpoint-xl: "{tokens.primitive.breakpoint.xl}"
    z-index: { base: 0, sticky: 100, dropdown: 200, overlay: 300, scrim: 400, modal: 401, tooltip: 500 }
  component:
    button-base:
      minHeight: "{tokens.primitive.size.control-height}"
      radius: "{tokens.semantic.radius.sm}"
      focusRing: "{tokens.primitive.size.focus-width} {tokens.semantic.color.focus-ring}"
      focusOffset: "{tokens.primitive.size.focus-offset}"
      loadingAccessibleName: preserve-action-and-append-progress
    button-primary:
      default: { background: "{tokens.semantic.color.accent}", text: "{tokens.semantic.color.on-accent}", radius: "{tokens.semantic.radius.sm}", minHeight: "{tokens.primitive.size.control-height}", paddingBlock: "{tokens.primitive.space.2}", paddingInline: "{tokens.primitive.space.5}" }
      hover: { background: "{tokens.semantic.color.accent-hover}" }
      active: { background: "{tokens.semantic.color.accent-hover}" }
      focus: { ring: "{tokens.primitive.size.focus-width} {tokens.semantic.color.focus-ring}", offset: "{tokens.primitive.size.focus-offset}" }
      disabled: { background: "{tokens.semantic.color.accent-disabled}", text: "{tokens.semantic.color.text-quaternary}" }
      loading: { visual: "{tokens.component.loader-caret.glyph}", accessibleName: preserve-action-and-append-progress }
    button-secondary: { default: "{tokens.semantic.color.fill-quaternary}", hover: "{tokens.semantic.color.fill-tertiary}", active: "{tokens.semantic.color.fill-primary}", text: "{tokens.semantic.color.accent}", base: "{tokens.component.button-base}" }
    button-ghost: { default: "{tokens.primitive.color.transparent}", hover: "{tokens.semantic.color.fill-tertiary}", active: "{tokens.semantic.color.fill-primary}", text: "{tokens.semantic.color.accent}", base: "{tokens.component.button-base}" }
    button-text: { default: "{tokens.primitive.color.transparent}", text: "{tokens.semantic.color.accent}", decoration: underline-on-hover, base: "{tokens.component.button-base}" }
    button-destructive: { default: "{tokens.semantic.color.error}", hover: "{tokens.semantic.color.error-strong}", active: "{tokens.semantic.color.error-strong}", text: "{tokens.semantic.color.on-error}", base: "{tokens.component.button-base}" }
    input:
      default: { background: "{tokens.semantic.color.field}", border: "{tokens.primitive.size.border-width} {tokens.semantic.color.border}", radius: "{tokens.semantic.radius.sm}", minHeight: "{tokens.primitive.size.control-height}", paddingInline: "{tokens.primitive.space.3}" }
      hover: { border: "{tokens.primitive.size.border-width} {tokens.semantic.color.border-strong}" }
      focus: { border: "{tokens.primitive.size.border-width} {tokens.semantic.color.focus-ring}", ring: "{tokens.primitive.size.focus-width} {tokens.semantic.color.focus-ring}", offset: "{tokens.primitive.size.focus-offset}" }
      error: { border: "{tokens.primitive.size.border-width} {tokens.semantic.color.error}", helper: "{tokens.semantic.color.error}" }
      disabled: { background: "{tokens.semantic.color.paper-sunken}", text: "{tokens.semantic.color.text-quaternary}" }
      read-only: { background: "{tokens.semantic.color.paper-sunken}", text: "{tokens.semantic.color.text-primary}", border: "{tokens.primitive.size.border-width} {tokens.semantic.color.hairline}" }
    select-native: { visual: "{tokens.component.input}", semantics: native-select }
    select-rich: { trigger: "{tokens.component.input}", menu: "{tokens.component.popover}", semantics: aria-combobox-listbox }
    segmented-control: { background: "{tokens.semantic.color.fill-quaternary}", hover: "{tokens.semantic.color.fill-tertiary}", selectedBackground: "{tokens.semantic.color.fill-primary}", selectedText: "{tokens.semantic.color.accent}", selectedMarker: "{tokens.semantic.color.accent}", focus: "{tokens.semantic.color.focus-ring}", disabledText: "{tokens.semantic.color.text-quaternary}", radius: "{tokens.semantic.radius.sm}" }
    switch: { on: "{tokens.semantic.color.accent}", off: "{tokens.semantic.color.border}", focus: "{tokens.semantic.color.focus-ring}", disabled: "{tokens.semantic.color.text-quaternary}", radius: "{tokens.semantic.radius.full}" }
    search-field: { background: "{tokens.primitive.color.transparent}", underline: "{tokens.semantic.color.hairline}", focusUnderline: "{tokens.semantic.color.focus-ring}", typography: "{tokens.semantic.typography.ui-sans}" }
    card: { background: "{tokens.semantic.color.surface}", edge: "{tokens.semantic.color.hairline}", radius: "{tokens.semantic.radius.none}" }
    overlay: { background: "{tokens.semantic.color.surface-raised}", shadow: "{tokens.semantic.elevation.shadow-page}", edge: "{tokens.semantic.color.stroke-hair}", radius: "{tokens.semantic.radius.lg}", scrim: "{tokens.semantic.color.scrim}" }
    popover: { background: "{tokens.semantic.color.surface-raised}", shadow: "{tokens.semantic.elevation.shadow-page}", edge: "{tokens.semantic.color.stroke-hair}", radius: "{tokens.semantic.radius.lg}" }
    tooltip: { background: "{tokens.semantic.color.ink}", text: "{tokens.semantic.color.paper}", shadow: "{tokens.semantic.elevation.shadow-page}", edge: "{tokens.semantic.color.stroke-hair}", radius: "{tokens.semantic.radius.sm}", typography: "{tokens.semantic.typography.ui-sans}" }
    toast: { background: "{tokens.semantic.color.surface-raised}", shadow: "{tokens.semantic.elevation.shadow-page}", edge: "{tokens.semantic.color.stroke-hair}", radius: "{tokens.semantic.radius.lg}", timeout: "{tokens.primitive.duration.toast}", errorTimeout: "{tokens.primitive.duration.toast-error}" }
    banner-info: { background: "{tokens.semantic.color.fill-info}", icon: "{tokens.semantic.color.info}", text: "{tokens.semantic.color.text-primary}" }
    banner-success: { background: "{tokens.semantic.color.fill-success}", icon: "{tokens.semantic.color.success}", text: "{tokens.semantic.color.text-primary}" }
    banner-warning: { background: "{tokens.semantic.color.fill-warning}", icon: "{tokens.semantic.color.warning}", text: "{tokens.semantic.color.text-primary}" }
    banner-error: { background: "{tokens.semantic.color.fill-error}", icon: "{tokens.semantic.color.error}", text: "{tokens.semantic.color.text-primary}" }
    badge: { background: "{tokens.semantic.color.fill-quaternary}", text: "{tokens.semantic.color.accent}", radius: "{tokens.semantic.radius.full}", typography: "{tokens.semantic.typography.label-caps}" }
    status-dot: { size: "{tokens.primitive.size.status-dot}", radius: "{tokens.semantic.radius.full}" }
    chip: { background: "{tokens.semantic.color.fill-quinary}", text: "{tokens.semantic.color.text-secondary}", radius: "{tokens.semantic.radius.xs}", typography: "{tokens.semantic.typography.ui-mono}" }
    progress: { track: "{tokens.semantic.color.fill-tertiary}", fill: "{tokens.semantic.color.accent}", indeterminateGlyph: "{tokens.primitive.glyph.loader}" }
    skeleton: { background: "{tokens.semantic.color.fill-tertiary}", edge: "{tokens.semantic.color.hairline}" }
    brand-mark: { glyph: "{tokens.primitive.glyph.brand}", tile: "{tokens.primitive.color.ink-950}", glyphColor: "{tokens.primitive.color.paper-50}", radius: "{tokens.semantic.radius.full}" }
    favicon: { glyph: "{tokens.primitive.glyph.brand}", tile: "{tokens.primitive.color.ink-950}", glyphColor: "{tokens.primitive.color.paper-50}", radius: "{tokens.semantic.radius.xs}" }
    loader-caret: { glyph: "{tokens.primitive.glyph.loader}", color: "{tokens.semantic.color.accent}", animation: "{tokens.semantic.motion.caret}" }
    reading-view: { typography: "{tokens.semantic.typography.body-read}", measure: "{tokens.semantic.layout.reading-measure}", dropCapTypography: "{tokens.semantic.typography.drop-cap}", dropCapLines: "{tokens.primitive.number.drop-cap-lines}" }
---

## Overview

This is an **editorial, type-led design system** - ink on warm paper, one
interaction accent (the editor's *manuscript red*), a real serif worth reading, flat and
borderless. It is written to be **reused across domains**: web/desktop software,
terminal apps (TUI/CLI), **print & long-form (books, PDF/EPUB)**, and demos.
Where the system needs a concrete example, **Writing Agent** is the reference
implementation (Appendix A) - but the core below is portable.

**Voice.** A tireless, exacting editor: precise without being cold, literary
without being precious. Interfaces should feel like a **well-set page** - the
kind of thing worth reading - not a dashboard bolted onto a screen.

**Normative boundary.** The YAML manifest is the normative token source. Sections
from Overview through Adopting this system define normative design and behavior.
Appendices are non-normative implementation notes. If prose and a token disagree,
the token wins and the prose must be corrected in the same change.

**Principles.**

1. **Type is the interface.** A serif carries reading and display; UI sans and
   mono play support. Prose respects an optimal *measure* (~66ch). Nothing
   competes with the text.
2. **Ink and one accent.** Ink is the base for text and the brand mark. Exactly
   one chromatic accent - **manuscript red `#a3341f`** - drives interaction,
   links, and marks. Brass is a rare warm counterpoint; everything else is paper
   and hairlines.
3. **Flat, not boxed.** No card-in-card. Group with whitespace and a single
   hairline. Content surfaces are **square** (page-like); only controls and
   overlays carry a small radius.
4. **Borderless + shadow for elevation.** Overlays float on one shadow
   (`shadow-page`) plus a near-invisible hairline. No hard borders on dialogs,
   menus, toasts.
5. **Tokens over literals.** Every reusable visual, spatial, timing, and layout
   value is a token. Platform adapters consume resolved values; components never
   introduce literals.
6. **One primitive per pattern.** Each interactive pattern - button, field,
   overlay, toast, loader - exists once. Forking a primitive is a regression.
7. **Accessible by construction.** Every permitted foreground/background and
   essential component-boundary pair meets its WCAG target; color is never the
   sole signal and focus is always visible. See Accessibility.

## Design tokens & architecture

Tokens are layered so the system ports to any stack without rewrites:

- **Primitive tokens** - raw colors, dimensions, durations, and font stacks.
  Components never reference primitive colors directly; fixed brand assets are
  the sole exception.
- **Semantic tokens** - role-named values (`accent`, `text-secondary`, `border`,
  `error`, `shadow-page`) with explicit light and dark modes where applicable.
- **Component tokens** - anatomy and state values (`button-primary.hover`,
  `input.error`). They reference semantic tokens, plus primitive dimensions when
  the dimension has no semantic meaning.

**Naming:** `role[-variant][-state]` - e.g. `accent`, `accent-hover`,
`text-tertiary`, `banner-error`. Lowercase, hyphenated, stable across platforms.

**Portability targets (adapter mapping):**

| Platform | Form |
|---|---|
| Web (CSS) | Custom properties: `--accent`, `--text-secondary`, `--shadow-page` |
| Tailwind | `theme.extend.colors.accent`, `boxShadow['page']`, etc. |
| JS / TS | Resolved object: `tokens.semantic.color.accent`, etc. |
| Figma | Variables with Light/Dark modes and matching semantic names |
| Terminal | Palette dict / YAML skin (see Theming → TUI) |
| Print | CSS Paged Media / typesetting stylesheet (see Typography → Print) |

The source manifest stores resolved cross-platform values. A theme generator may
use OKLCH or `color-mix()` during authoring, but exported tokens must be concrete
values so CSS, Figma, native apps, terminals, and print produce the same result.
Adapters must not copy CSS-only syntax into platforms that cannot interpret it.

## Colors

**Ink on paper with one accent.** Deliberately warm - a cream paper
(`#faf8f4`), not the cool blue-white of a typical app - so it reads as *print*,
not *chrome*.

**Anchors**
- **Ink `#17171a`** - primary text + brand mark. Never pure black. 16.9:1 on paper.
- **Accent / Manuscript red `#a3341f`** - the one interaction color: buttons,
  links, focus rings, active nav, selected states, editorial marks. Oxblood, not
  fire-engine - a red-pencil edit, not an alarm. `accent-hover #872a19` for
  press/hover.
- **Brass `#b0812f`** - warm counterpoint, used sparingly (a rule above a byline,
  a small highlight). **Large text / rules / decorative only** (3.28:1 - fails AA
  for body text). Never an interaction driver.

**Surfaces** - paper `#faf8f4`, paper-sunken `#f2ede4` (sidebar/recessed),
surface `#ffffff` (cards), and field `#fffdfa`. Dark: bg `#121211`, surface
`#1c1b19`, raised/field `#211f1c`. Dark text is warm paper-white `#f3efe6`,
never `#fff`.

**Semantic / status** - separated from the brand so the UI never looks like one
giant warning:

| Role | Light | Dark | On paper |
|---|---|---|---|
| success | `#2f7d5a` | `#5aa07f` | 4.71:1 ✓ |
| warning | `#a85f1e` | `#d08a3a` | 4.58:1 ✓ |
| error / destructive | `#c23b2b` | `#e0604e` | 5.01:1 ✓ |
| info | `#3f6f78` | `#5a97a2` | 5.27:1 ✓ |

Error is hotter and more saturated than the oxblood accent so "delete" never
reads as "link." Dark-mode accent lifts to `#d8664c` (4.86:1 on dark cards).

**Text hierarchy** uses resolved solid colors so contrast does not change with
the implementation's compositing behavior:

| Token | Light | Minimum light contrast | Use |
|---|---|---|---|
| text-primary | `#252527` | 14.4:1 | body, headings |
| text-secondary | `#575657` | 6.3:1 | supporting, metadata |
| text-tertiary | `#6b6a6a` | 4.62:1 | muted labels, placeholders |
| text-quaternary | `#adabaa` | exempt | **disabled/decorative only - never information** |

**Fills** are explicit semantic tokens: `fill-primary` (selected),
`fill-secondary` (active rows), `fill-tertiary` (hover), `fill-quaternary`
(secondary controls), and `fill-quinary` (subtle decoration). Their resolved
light/dark values are in the manifest; they are not interaction signals alone.

**Categorical / data-viz** - indicators only (charts, telemetry), never
interaction: red · cyan-slate · brass · green · purple · gold (ordered for
distinctness). See Data visualization for scales.

## Accessibility

The system targets **WCAG 2.2 AA**. Verification is automated for every shipped
theme and repeated whenever a color, mode, or component-boundary token changes.

**Contrast.** Text is ≥ 4.5:1 (normal) / 3:1 (large ≥ 24px, or ≥ 18.66px bold);
essential UI boundaries and graphics are ≥ 3:1. Test every foreground against
every surface on which it is allowed—not only against the canvas.

- `text-tertiary` is normal-text safe on every light and dark surface.
- **Brass** is large text, rules, charts, or decoration only in light mode.
- `hairline` and `stroke-hair` are decorative. They must never be the only
  visible boundary or state signal. Interactive boundaries use `border` or
  `border-strong`, both ≥ 3:1 on their supported adjacent surfaces.
- `text-quaternary` is restricted to disabled or decorative content. Required
  instructions, values, status, and placeholder text use `text-tertiary` or
  stronger.
- A new theme must pass the complete contrast matrix before shipping.

**Baseline verified pairs.** Accent/paper 6.45:1; warning/paper 4.58:1;
success/paper 4.71:1; error/paper 5.01:1; dark accent/dark surface 4.86:1.
The light control border is 3.30:1 on paper; the dark control border is at
least 3.28:1 on supported dark surfaces.

**Focus.** Every interactive element shows a visible focus ring: 2px
`focus-ring` (accent), 1px offset. Never remove focus outlines; style them.

**Target size.** Prefer **44×44 CSS px** for primary and touch controls. The
WCAG 2.2 AA floor is 24×24 CSS px, subject to its spacing and inline exceptions.
Icon buttons receive padding to reach 44×44 wherever layout permits.

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
announce toasts and asynchronous results. Loading controls retain their original
accessible name and append a progress state such as “Saving, in progress.”

## Typography

Three families, strictly separated by role. **The serif is the identity.**

**Fraunces** (display + reading - vendored). A characterful old-style serif with
optical-size + weight axes, using a variable WOFF2 for each required style
(roman, plus italic when the product uses italic text; SIL OFL, offline). Carries both
**display** (wordmark, headings - high opsz, light weight, tight tracking) and
**reading** (body at low opsz, weight 400, line-height 1.62, measure 66ch).
Fallback: `'Iowan Old Style', Charter, Georgia, 'Times New Roman', serif`.

**System sans** (UI). Body chrome, labels, buttons, controls, sidebar. Native
stack, never vendored. Base 0.875rem / 1.5; compact UI may use 0.8125rem.
Small labels use `label-caps` (0.75rem, uppercase, 0.12em, 600).

**JetBrains Mono** (code / figures / data). Stack falls back to Cascadia → SF
Mono → system mono.

**Kbd** - native UI face, small caps, never themed.

`opticalSize` is an abstract token. Web adapters emit the Fraunces `opsz` axis
through `font-variation-settings` or `font-optical-sizing`; adapters that do not
support variable axes ignore it without changing the role's size or line height.

**Reading surfaces** constrain prose to the **measure** (66ch), center it, and
open with a **3-line drop cap** in accent - the signature reading flourish.

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
  CMYK and expect the manuscript-red to shift - proof it. Provide **bleed**
  (3mm) and trim marks for print PDFs. EPUB uses the screen tokens as-is.

## Layout & responsive

**Spacing** - 4px base: `xxs 2 · xs 4 · sm 8 · md 16 · lg 24 · xl 48 · section
64`. Group with space before rules.

**Grid & containers.** Content max is `content-max` (1100px) on dashboard views;
**reading surfaces cap at `reading-measure` (66ch)** and center. Desktop sidebar
and page inset use the `sidebar` and `page-inset` layout tokens.

**Breakpoints.**

| Viewport class | Width | Behavior |
|---|---|---|
| xs | < 640 | single column; sidebar → top bar/drawer; controls stack |
| sm | 640–879 | one or two columns; sidebar remains collapsed |
| md | 880–1127 | full sidebar + main; grids up to two columns |
| lg | 1128–1439 | full sidebar; grids up to three columns |
| xl | ≥ 1440 | content caps; gutters absorb the rest |

The manifest values are min-width thresholds: `sm 640`, `md 880`, `lg 1128`,
and `xl 1440`. Use those names consistently in CSS and application code.

Reduce columns at each step - never reflow rows unpredictably. Reading measure
never exceeds 66ch regardless of width.

**Layering (z-index).** `base 0 · sticky 100 · dropdown 200 · overlay 300
(toasts) · scrim 400 · modal 401 · tooltip 500`. Never hand-pick z-index - use
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
look friendly" - that erases the identity.

## Elevation & depth

One shadow system, three levels:

- **Flat** - 95% of surfaces: a single hairline, no shadow.
- **`shadow-card`** - cards/composer that must read against any background: soft
  1px + hairline. Usually cards stay flat; elevation is for things that *float*.
- **`shadow-page`** - the one overlay shadow (layered, downward-weighted, no hard
  border), paired with `stroke-hair` (3% currentColor). Every dialog, menu,
  popover, tooltip, toast uses it.
- **Scrim** - `rgba(0,0,0,0.32)` light / `0.5` dark behind modal overlays.

## Motion

Quick and functional. Tokens: `fast 120ms` (controls), `base 180ms`, `slow
300ms` (overlays/views); easings `ease-out` / `ease-standard`.

- **Hover:** color transition `fast`. **Focus:** ring appears immediately (no
  animate-in).
- **Overlay enter/exit:** fade + subtle scale (0.98→1, `slow`; reverse faster).
- **View transitions:** fade, staggered per element.
- **Loader - the Caret:** a blinking `▍` at `motion.caret` (see Notifications).
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

Each pattern exists once. Specify only states that apply; do not manufacture
meaningless states to complete a checklist.

| Primitive | Required states |
|---|---|
| Button | default · hover · active · focus · disabled · loading |
| Field | default · hover · focus · disabled · error · read-only |
| Select/menu | closed · open · focus · disabled · option-selected · error |
| Toggle/segmented | off/unselected · on/selected · hover · focus · disabled |
| Overlay | closed · entering · open · exiting |
| Async feedback | idle · loading · success · empty · error |

**Anatomy and behavior.** Every component specification records its parts,
keyboard interaction, accessible name/description, focus behavior, content
rules, and applicable states alongside its visual tokens. Native semantics are
preferred. Custom widgets follow the relevant ARIA Authoring Practices pattern
and receive automated keyboard tests.

### Buttons
- **Primary** - accent fill, `on-accent` text; hover → `accent-hover`; flat.
- **Destructive** - `error` fill, `on-error` text (distinct from primary red).
- **Secondary** - `accent-muted` wash, accent text.
- **Ghost** - transparent, hover `fill-tertiary`.
- **Text / link** - no chrome, accent, underline on hover.
- **Disabled** - `accent-disabled` (primary) / reduced opacity; `not-allowed`.
- **Loading** - the visible label may swap to the Caret, but the button retains
  its action name and exposes progress (for example, “Export, in progress”). The
  button stays sized and cannot be activated twice.
Icons inherit one size; never re-set per instance.

### Inputs, selects & forms
Shared control shape. Resting `border`; hover `border-strong`; focus full
`focus-ring` + 2px ring (immediate). Background uses the `field` token. Keep
native number spinners unless the product supplies equally discoverable and
keyboard-operable increment/decrement controls. Prefer native `<select>` for
simple forms. Use custom `.csel` only when search, rich options, or controlled
cross-platform rendering is a product requirement; it must implement the
combobox/listbox keyboard and ARIA contract. **Error state** below.

### SegmentedControl / Switch / SearchField
- **Segmented** - small mutually-exclusive sets; `fill-primary` on the selected
  segment with accent text/marker. It may visually replace radio controls, but
  preserves an accessible radiogroup and arrow-key behavior.
- **Switch** - bare toggle, `full` radius, accent when on. It has a visible label
  or an equivalent accessible name and exposes `aria-checked`.
- **SearchField** - borderless, underline-on-focus, auto-width; never a boxed
  tile.

### Surfaces
- **Card** - `surface`, square, hairline (or `shadow-card` when floating). No
  card-in-card.
- **ListRow** - flat, flush-left: label / description / action. Prefer spacing to
  dividers.
- **Code / CodeBlock** - JetBrains Mono; inline code 5% ink fill; blocks ride the
  editor surface. A code frame may carry three **window-control dots** - editorial
  traffic lights (manuscript-red · brass · sage), **visible in both light and dark**
  (never a low-contrast gray). **Wide code** (e.g. ASCII diagrams) **scrolls
  horizontally within its own frame - never clipped**, with a themed scrollbar.
- **ReadingView** - the hero prose surface: measure + reading spec + drop cap.

### Brand mark, Masthead & Loaders
- **BrandMark** - the **pilcrow `¶`** in Fraunces on an ink tile (`full` radius),
  identical light/dark. The favicon is the documented `xs`-radius exception.
  Sidebar header and TUI banner use the standard mark. No substitute logo.
- **TUI masthead** - a big gradient figlet wordmark (default face `colossal`), the
  editorial gradient sweeping manuscript-red → ember → hot-gold (`ui.STOPS`) and
  framed top and bottom by a mirrored flame rule. It sits on the **left**; on a wide
  terminal a GET STARTED command column sits beside it (stacking beneath on a narrow
  one, collapsing to a one-line wordmark when the mark would wrap), and it prints
  **every launch**. The gradient stops and figlet face are per-theme (each theme owns a *distinct*
  face, but all at the same big block scale - the small personality faces were retired in 0.4.1); a
  fallback face chain preserves the mark if a theme's font is unavailable. `/theme <name>` reprints
  the masthead live (on a cleared screen) so a face/palette previews without relaunching.
- **Loader - the Caret** - a blinking `▍` (accent) for view/content loading,
  optionally with a live word/token counter. “Loading…” is never shown visually,
  but an equivalent localized status is always available to assistive technology.
- **Loader - the live-run grid spinner** - the dashboard's "now running" activity
  indicator is a **3×3 grid of rounded cells**: a comet lights the 8-cell outer ring
  clockwise (staggered `animation-delay`s) with a white-hot **HDR bloom** head
  (accent + white + a layered box-shadow glow) trailing into the accent; the centre
  cell stays a dim core. Done = a solid green grid; idle = a static dim grid;
  reduced-motion = a static legible grid. Pure CSS, brand-colored via
  `--accent`/`--green`; the warm comet deliberately echoes the TUI masthead's flame
  gradient (one identity across surfaces).

## Overlays

All floating surfaces share `shadow-page` + `stroke-hair` + `lg` radius and the
layer scale. Taxonomy:

| Overlay | Trigger / behavior | Dismiss |
|---|---|---|
| **Modal / Dialog** | blocking; scrim behind; **focus-trapped** | Esc · optional scrim click · × icon |
| **Sheet** | edge-anchored panel (mobile nav, filters) | Esc · scrim · swipe |
| **Popover / Menu** | anchored to a control (`.csel`, actions) | outside click · Esc · select |
| **Tooltip** | hover/focus hint; ink fill, paper text | blur / mouseout |
| **Toast** | transient feedback (see Notifications) | auto-timeout · × |

Rules: use an × icon when a compact visual close control is appropriate, but give
it a localized accessible name such as “Close dialog.” Outside-click dismissal
is disabled for destructive confirmation, unsaved work, onboarding, and other
flows where accidental dismissal loses effort. Menus flip or shift near viewport
edges and remain reachable at 400% zoom.

## Notifications & feedback

- **Toast** - transient, bottom-right, `surface-raised` + `shadow-page`;
  success/plain vs error. Default timeout is 6s and error timeout 10s. Pause the
  timer on hover/focus; do not auto-dismiss a toast containing an action or
  information the user must retain. Provide an accessible close control and live
  announcement. Show one at a time and queue extras.
- **Banner** - persistent, in-flow, full-width: `info` / `success` / `warning` /
  `error`, using the corresponding `fill-*` token + icon + message + optional
  action. The manifest's resolved fills are equivalent to a 12% authoring tint;
  do not recompute them at runtime. No accent side-bar—stripes read as decoration.
  For state that must stay visible (quota, degraded mode).
- **Alert (inline)** - a compact banner scoped to a section or form.
- **Badge** - small count/label pill (`accent-muted` + accent, `label-caps`).
- **Status dot** - 7px `full` dot: success/warning/error/accent (e.g. a live-run
  pulse). Always paired with a text label (color-not-sole-signal).
- **Progress** - thin accent bar on a faint track; indeterminate uses the Caret.
- **Empty / loading / skeleton** - `EmptyState` (centered, one guiding line);
  loading uses the Caret; skeletons are hairline-outlined blocks at `fill-tertiary`
  (no shimmer under reduced motion).

## Highlights & selection

- **Text selection** - `selection` (accent @22%) via `::selection`.
- **Selected item** - `fill-primary` wash + accent text/left-marker (nav item,
  list row, segmented segment, `.csel` option with a ✓).
- **Active row** - `fill-secondary`.
- **Hover** - `fill-tertiary` (never a heavy block).
- **Search / match highlight** - accent-tinted background on the matched span;
  keep text contrast ≥ 4.5:1.
- **"New" / emphasis marker** - a small accent badge or dot, plus a label; never
  color alone.
- **Focus highlight** - the `focus-ring`, distinct from selection.

## Error states

Errors are explicit, calm, and never rely on color alone.

- **Field validation** - border → `error`, an **icon + helper message** in
  `error` beneath, linked with `aria-describedby`; on submit, focus the first
  invalid field and summarize errors at the top of the form.
- **Inline / section error** - an `alert` (error banner) scoped to the region
  with a retry action where relevant.
- **Toast error** - for async/action failures; error text, longer timeout,
  live-region announced.
- **Full-page / boundary error** - a canonical `ErrorState`: mark/icon, a plain
  title, one-sentence cause, and a primary recovery action. Same look for React
  error boundaries, boot failures, and empty-with-error.
- **Destructive confirm** - a modal with **type-to-confirm** for irreversible
  actions; the confirm button is `destructive`.
- **Copy** - say what happened and what to do next ("Couldn't reach the model -
  check your key and retry"), never a raw stack trace.

## Iconography

Inline SVGs, one set, no mixing libraries. 14px (0.875rem) standard / 12px
compact; 1.5px stroke; inherit `currentColor`. Editorial glyphs (pilcrow ¶,
caret ▍, em-dash -, section §) are typographic, set in the font - not drawn.
Icons that carry meaning get an accessible label; icons beside text are
`aria-hidden`. Terminal: Rich box-drawing + the caret motif (no emoji spinners).
**Heading anchor links** (the copy-link affordance) use a **muted** icon that
reveals on heading hover and turns **accent on hover** - never a loud, always-on
colored mark.

## Data visualization

- **Categorical** - use the mode-specific `cat-1`…`cat-6` values in the manifest;
  stop at 6, then group “other.” Every light and dark mark is ≥ 3:1 against its
  supported surface. Each series also gets a label/shape, not hue alone.
- **Sequential** - use a tested single-hue ramp. Any cell or mark required to
  understand the data must meet 3:1 against adjacent colors or receive a
  contrasting outline/direct label. Near-paper tints are decorative only.
- **Diverging** - `error` ↔ neutral ↔ `success` for signed values.
- **Contrast** - essential chart strokes/fills are ≥ 3:1 against their supported
  surface; axis and legend text use `text-tertiary` or stronger and meet normal
  text contrast.
- **Colorblind-safe** - for critical distinctions use the Okabe-Ito set (shipped
  as the `highcontrast` theme in the reference impl) and rely on shape + label.

## Imagery & brand

- **Brand mark** - the pilcrow `¶`. **Clear space** ≥ the pilcrow's cap height on
  all sides; **min size** 16px (favicon) / 20px (UI). Ink tile + paper glyph,
  constant across themes. Misuse: don't recolor per theme, don't add effects,
  don't substitute a mascot.
- **Favicon** - ink tile, paper pilcrow, `xs` radius.
- **Photography/illustration** (marketing/book) - full-measure or full-bleed;
  let imagery carry visual weight so type can stay quiet (the editorial default).

## Voice & microcopy

- **Case** - sentence case for UI text, buttons, and headings ("Propose angles",
  not "Propose Angles"). `label-caps` is the only uppercase, for tiny labels.
- **Buttons** - a verb ("Save", "Propose angles", "Export"), not "OK/Submit".
- **Errors** - plain, specific, actionable; no blame, no jargon, no stack traces.
- **Empty states** - one line of guidance + the primary action.
- **Numbers/dates** - tabular figures for aligned numerals; ISO or localized
  dates consistently; currency/units explicit.
- **Tone** - the editor's voice: exact, warm, unfussy.

## Localization & RTL

- Use **logical properties** (`margin-inline`, `padding-block`, `start/end`), not
  left/right, so layouts mirror for RTL automatically.
- Mirror directional icons (chevrons, arrows) in RTL; never mirror the brand mark.
- Allow text to grow ~30% (German/Finnish) - don't fix widths to English.
- Provide non-Latin font fallbacks; the 66ch measure is Latin - adjust for
  scripts with different density (CJK ~ 40–45 characters).
- Keep number/date/currency formatting locale-aware.

## Theming

One identity, **recolored - never restructured**.

**Modes.** System (auto) · Light · Dark - one ink + manuscript-red identity;
System follows the OS. Preference stored per-client, independent of engine
settings.

**Named themes.** A shared palette catalog recolors the flat editorial layout—
same structure, shapes, type, and shadows; only color values change. Theme
authoring may derive colors programmatically, but committed manifests contain
resolved light/dark values for every semantic color.

**Theming contract.** A valid theme defines every mode-dependent semantic color,
including surfaces, text hierarchy, action states, control borders, focus,
status, fills, scrim, and categorical data colors. Body text is ≥ 4.5:1 and
essential UI/graphics are ≥ 3:1 on every allowed surface. CI validates the full
matrix before shipping; defining only ink, paper, and accent is insufficient.

**Terminal (TUI).** The default “ink & brass” skin preserves manuscript red as
the interaction accent. Brass is decorative/secondary; success, warning, error,
and data colors retain their semantic roles. Switch with `/theme`. Terminal
adapters use resolved ANSI colors with tested fallback pairs; missing skin values
inherit the complete default semantic map. User skins live in
`~/.<app>/skins/` as YAML.

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
- **Don't** display a generic spinner or visual “Loading…” label—use the Caret;
  do expose a localized loading status to assistive technology.
- **Don't** signal state with color alone; pair an icon/label.
- **Don't** remove focus outlines; style them.
- **Don't** use brass for body text. Reserve `text-tertiary` for short muted
  labels/placeholders rather than primary reading text; never use
  `text-quaternary` for information.
- **Don't** let a named theme change layout, shape, type, or shadows - colors
  only.
- **Don't** style chrome with a bare class selector (`.header`, `.card`) that can
  also match a component's own sub-parts (e.g. a code-frame's `.header`) - scope to
  the element (`header.header`), or you get doubled borders and stray fills.
- **Don't** size an icon in `em` next to large display type - it inherits the
  heading's font size and balloons. Use a fixed `rem` for anchor/inline icons.

## Governance & versioning

- **SemVer** the system using `major.minor.patch`. Breaking = renamed/removed
  token or changed semantic meaning. `schemaVersion` changes only when the
  manifest structure changes; `version` changes for design-system releases.
- **Changelog** every token addition, rename, and deprecation. During minor
  releases keep a deprecated alias for at least one minor cycle; a major release
  may remove aliases when it includes an explicit migration map.
- **Definition of done** for a component: applicable states specified, anatomy
  documented, AA verified, keyboard/focus/accessibility semantics tested, tokens
  only, RTL/zoom/reduced-motion covered, and visual regression fixtures added.
- **Single source of truth** - the YAML manifest is normative. Generated platform
  files are build artifacts and are never edited by hand. Prose and reference
  notes are reviewed for drift in the same pull request.

## Adopting this system in a new project

1. Run a platform adapter against the manifest; do not manually copy values.
   Resolve light/dark modes and references before emitting platform files.
2. Vendor **Fraunces** (or accept the system-serif fallback); wire the sans/mono
   stacks.
3. Build the primitives once: Button, Input/Field, native Select plus `.csel`
   where justified, Overlay, Toast/Banner, Loader (Caret), BrandMark, ReadingView.
4. Set modes (System/Light/Dark); if adding a named theme, run the **theming
   contract** check.
5. Verify the complete contrast matrix, keyboard contracts, focus return, target
   sizes, zoom/reflow, RTL, reduced motion, and accessible loading states.
6. For print/book output, add the **Print & long-form** stylesheet.
7. Add token-reference validation, contrast tests, component accessibility tests,
   and light/dark visual regression pages to CI.

---

# Non-normative reference material

The appendices record product implementation status. They do not redefine core
tokens or grant exceptions silently; any divergence is listed as a known gap.

## Appendix A - Reference implementation: Writing Agent

Writing Agent (an autonomous writing system) implements this system across three
surfaces that share one identity: a **web dashboard** (pure-stdlib server + SPA),
an **interactive TUI** (Rich + prompt_toolkit), and a **one-shot CLI**.

- **Type:** Fraunces variable WOFF2 assets for the required roman/italic styles
  (SIL OFL), served over `/static/fonts/`; system sans for UI; JetBrains Mono for code/figures. Fully
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
  (`ui.THEMES`) - colors-only recolor of the editorial layout, matched between
  web and TUI.
- **TUI target skin “ink & brass”:** manuscript red is the interaction accent;
  brass is secondary/decorative; semantic status colors remain distinct. The
  former gold-primary palette and multicolor wordmark are deprecated because
  they conflict with the cross-surface interaction and brand contracts.
- **Documentation site (Astro + Starlight, repo `writingagentdocs`):** the public
  docs implement the same identity via Starlight CSS-variable overrides - ink on
  warm paper, manuscript-red accent + links + hero CTA, **Fraunces** serif for
  headings and reading body (loaded from Google Fonts alongside **JetBrains Mono**),
  system sans for UI chrome, square hairline surfaces, accent-tinted selection.
  Code frames carry the three editorial **window-dots** and horizontally **scroll**
  wide content; **heading anchor links** are muted (accent on hover, fixed 1rem
  icon); the landing faux-terminal previews the TUI **“ink & brass”** skin. The
  target brand asset is the ink-tile pilcrow. Any retained pen-nib logo, favicon,
  or alternate wordmark is a migration gap—not a permitted brand variant.
  Header chrome is scoped to `header.header` - a bare `.header` collides with the
  inner nav wrapper and Expressive-Code frame headers (doubled hairlines).

## Appendix B - Reference implementation audit & known gaps (2026-07-18)

**Fixed in the redesign:** justified rich selects use `.csel`; native scrollbars
are themed where supported; native `prompt()/confirm()` became `ConfirmModal`;
visual “Loading…” became the Caret while retaining an accessible status;
custom-select keyboard/ARIA, artifact copy affordances, horizontally scrollable
wide tables, and an accessible run badge were added. The normative palette now
uses solid text colors, ≥3:1 interactive borders, complete dark semantics, and
mode-specific categorical colors.

**Known gaps (accepted / documented):**
- **Responsive** - the dashboard is desktop-tuned; the tokenized sidebar and
  breakpoint behavior above are the target, not yet fully implemented.
- **Markdown tables** in the artifact renderer show raw pipes (rare in reports).
- **`title=` tooltips** are native (not the themed `tooltip`).
- **Popover collision** - the `.csel` menu does not yet flip near a viewport edge.
- **Number inputs** - removed native spinners still need an equally discoverable,
  keyboard-operable replacement or restoration of the native controls.
- **Brand migration** - TUI gold-primary/multicolor wordmark and documentation
  pen-nib assets must migrate to the normative interaction and pilcrow contracts.
- **Contrast automation** - baseline tokens are verified; the complete
  theme/surface/state matrix must still be enforced in CI.
- **SSE reconnect** is best-effort (no exponential backoff).

## Appendix C - Changelog and migration

### 3.0.0 - 2026-07-18

- Replaced the ambiguous top-level token block with the normative
  `tokens.primitive`, `tokens.semantic`, and `tokens.component` schema.
- Added complete light/dark semantic colors, concrete cross-platform values,
  missing fill tokens, mode-specific data colors, layout dimensions, timeouts,
  typography roles, and component state tokens.
- Raised interactive borders and tertiary text to their required contrast floors.
- Clarified native/custom select policy, loading announcements, close-control
  naming, toast timing, target sizing, responsive ranges, and chart contrast.
- Made the pilcrow and manuscript-red interaction contracts consistent across
  web, TUI, CLI, documentation, and brand guidance.
- Marked reference implementation notes as non-normative and recorded remaining
  product migrations explicitly.

**Migration from version 2:** read former root paths through the new layers:
`colors.*` → `tokens.semantic.color.*`, `typography.*` →
`tokens.semantic.typography.*`, `rounded.*` → `tokens.semantic.radius.*`, and
`components.*` → `tokens.component.*`. Platform adapters resolve the requested
light/dark mode before emitting values. Removed CSS-only derived values must be
replaced with the resolved semantic values in this manifest.
