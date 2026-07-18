"""WCAG 2.2 AA contrast enforcement for the Editorial Design System (docs/design.md).

The design manifest promises specific contrast ratios for its core foreground/background
pairs; this test computes them so a color change that drops a required pair below its
floor fails in CI instead of shipping. Body text ≥ 4.5:1, large/UI graphics ≥ 3:1.
"""
from writingagent import ui

PAPER = "#faf8f4"          # semantic.color.paper (light)
DARK_SURFACE = "#1c1b19"   # semantic.color.surface (dark)
PARCH = "#e6ddc9"          # TUI body parchment


def _lum(hex_: str) -> float:
    h = hex_.lstrip("#")
    chan = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [(c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4) for c in chan]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _ratio(a: str, b: str) -> float:
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def test_contrast_helper_matches_known_values():
    assert round(_ratio("#000000", "#ffffff"), 1) == 21.0
    assert round(_ratio("#ffffff", "#ffffff"), 1) == 1.0


def test_text_hierarchy_on_paper_is_body_safe():
    # every text tier that carries information is ≥ 4.5:1 on paper
    assert _ratio("#252527", PAPER) >= 4.5      # text-primary (~14.4)
    assert _ratio("#575657", PAPER) >= 4.5      # text-secondary (~6.3)
    assert _ratio("#6b6a6a", PAPER) >= 4.5      # text-tertiary (~4.62)


def test_accent_and_status_on_paper():
    assert _ratio("#a3341f", PAPER) >= 4.5      # manuscript-red accent (~6.45)
    assert _ratio("#2f7d5a", PAPER) >= 4.5      # success (~4.71)
    assert _ratio("#a85f1e", PAPER) >= 4.5      # warning (~4.58)
    assert _ratio("#c23b2b", PAPER) >= 4.5      # error (~5.01)
    assert _ratio("#3f6f78", PAPER) >= 4.5      # info (~5.27)


def test_dark_mode_accent_on_dark_surface():
    assert _ratio("#d8664c", DARK_SURFACE) >= 4.5   # dark accent (~4.86)


def test_interactive_borders_meet_the_3to1_ui_floor():
    assert _ratio("#958680", PAPER) >= 3.0      # light control border (~3.30)


def test_brass_is_large_text_only_not_body():
    # brass fails AA for body text on paper (design.md: rules/large/decorative only)
    assert _ratio("#b0812f", PAPER) < 4.5


def test_tui_editorial_accent_is_readable_on_parchment():
    # the migrated TUI default accent (manuscript red) clears the UI/large-text floor
    assert _ratio(ui.THEMES["editorial"]["GOLD"], PARCH) >= 3.0
    assert ui.THEMES["editorial"]["GOLD"].lower() == "#a3341f"   # migration landed
