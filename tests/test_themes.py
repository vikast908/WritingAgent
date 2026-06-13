"""Theme registry + switcher tests: completeness, apply/fallback, gradient
sampling, the shell's live palette sync, and the settings field."""
import pytest

from book_agent import shell, ui
from book_agent.config import Settings


@pytest.fixture(autouse=True)
def restore_default_theme():
    yield
    ui.apply_theme(ui.DEFAULT_THEME)
    shell._sync_palette()


def test_every_theme_defines_the_full_palette():
    for name, theme in ui.THEMES.items():
        for key in ui._PALETTE_KEYS:
            assert key in theme, f"theme '{name}' missing {key}"
        assert len(theme["STOPS"]) >= 2
        assert theme["DESC"]


def test_apply_theme_rebinds_and_falls_back():
    assert ui.apply_theme("kazama") == "kazama"
    assert ui.GOLD == ui.THEMES["kazama"]["GOLD"]
    assert ui.current_theme == "kazama"
    # Unknown name -> default, not an exception.
    assert ui.apply_theme("does-not-exist") == ui.DEFAULT_THEME
    assert ui.GOLD == ui.THEMES[ui.DEFAULT_THEME]["GOLD"]


def test_flame_color_samples_active_theme():
    ui.apply_theme("supabase")
    stops = ui.THEMES["supabase"]["STOPS"]
    assert ui.flame_color(0.0) == stops[0]
    assert ui.flame_color(1.0) == stops[-1]
    # Explicit stops still override.
    assert ui.flame_color(0.0, ("#000000", "#ffffff")) == "#000000"


def test_shell_sync_palette_follows_theme():
    ui.apply_theme("violet-bloom")
    shell._sync_palette()
    assert shell.GOLD == ui.THEMES["violet-bloom"]["GOLD"]
    # The prompt/marker glyph is the fixed brand nib (matches the logo), not the per-theme fleuron.
    assert shell._FLEURON == shell._NIB == "✒"


def test_themes_are_visually_distinct():
    """Every theme's accent must be a different hue - no two near-identical."""
    def rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    accents = {name: rgb(t["GOLD"]) for name, t in ui.THEMES.items()}
    names = list(accents)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            dist = sum((x - y) ** 2 for x, y in zip(accents[a], accents[b], strict=True)) ** 0.5
            assert dist > 60, f"themes '{a}' and '{b}' have near-identical accents"


def test_settings_theme_default():
    assert Settings().theme == "editorial"


def test_theme_changes_wordmark_face():
    """A theme switch must change the typography, not just the colors."""
    ui.apply_theme("editorial")
    editorial_mark = shell._wordmark()
    ui.apply_theme("fallout")
    fallout_mark = shell._wordmark()
    assert editorial_mark != fallout_mark


def test_every_theme_face_is_available():
    """Each theme's FONT must exist in the installed pyfiglet (no silent fallback)."""
    import pyfiglet
    fonts = set(pyfiglet.FigletFont.getFonts())
    for name, theme in ui.THEMES.items():
        assert theme["FONT"] in fonts, f"theme '{name}' wants missing font {theme['FONT']}"


def test_banner_renders_in_every_theme():
    import io

    from rich.console import Console
    for name in ui.THEMES:
        ui.apply_theme(name)
        shell._sync_palette()
        c = Console(force_terminal=True, color_system="truecolor",
                    width=100, file=io.StringIO())
        shell._banner(c)
        assert c.file.getvalue()
