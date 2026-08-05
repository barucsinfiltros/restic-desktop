"""App chrome + terminal color presets (independent)."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtGui import QColor


def icons_dir() -> Path:
    """Directory containing bundled SVG icons (dev + frozen)."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        meipass = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        candidate = meipass / "icons"
        if candidate.is_dir():
            return candidate
        candidate = meipass / "app" / "icons"
        if candidate.is_dir():
            return candidate
    return Path(__file__).resolve().parent / "icons"


def _icon_url(name: str) -> str:
    # Qt stylesheets want forward-slash absolute paths.
    return icons_dir().joinpath(name).as_posix()


def icon_path(name: str) -> str:
    """Filesystem path to a bundled icon (for QIcon)."""
    return str(icons_dir() / name)


def app_window_icon():
    """Best available app icon for window / taskbar / .exe branding."""
    from PyQt6.QtGui import QIcon

    icons = icons_dir()
    # Multi-size .ico is ideal on Windows; PNG works well on Linux.
    for name in ("app.ico", "app.png", "app.svg"):
        path = icons / name
        if path.is_file():
            return QIcon(str(path))
    return QIcon()


@dataclass(frozen=True)
class AppTheme:
    id: str
    name: str
    bg: str
    sidebar: str
    surface: str
    border: str
    text: str
    muted: str
    accent: str
    accent_hover: str
    accent_soft: str
    danger: str
    ok: str


@dataclass(frozen=True)
class TerminalTheme:
    id: str
    name: str
    bg: QColor
    fg: QColor
    cursor: QColor
    # Shell ANSI colors (pyte names) — per theme so light themes stay readable.
    ansi: dict[str, QColor]
    ansi_bright: dict[str, QColor]


def _c(r: int, g: int, b: int) -> QColor:
    return QColor(r, g, b)


# Dark-background ANSI (VS Code / Windows Terminal defaults-ish).
ANSI_PALETTE_DARK: dict[str, QColor] = {
    "black": _c(0, 0, 0),
    "red": _c(205, 49, 49),
    "green": _c(13, 188, 121),
    "brown": _c(229, 229, 16),
    "blue": _c(36, 114, 200),
    "magenta": _c(188, 63, 188),
    "cyan": _c(17, 168, 205),
    "white": _c(229, 229, 229),
    "default": _c(204, 204, 204),
}
ANSI_PALETTE_BRIGHT_DARK: dict[str, QColor] = {
    "black": _c(102, 102, 102),
    "red": _c(241, 76, 76),
    "green": _c(35, 209, 139),
    "brown": _c(245, 245, 67),
    "blue": _c(59, 142, 234),
    "magenta": _c(214, 112, 214),
    "cyan": _c(41, 184, 219),
    "white": _c(255, 255, 255),
    "default": _c(255, 255, 255),
}

# Light-background ANSI — darker hues (esp. green) so prompts stay readable.
ANSI_PALETTE_LIGHT: dict[str, QColor] = {
    "black": _c(24, 28, 36),
    "red": _c(180, 35, 40),
    "green": _c(15, 110, 55),
    "brown": _c(150, 110, 10),
    "blue": _c(25, 85, 175),
    "magenta": _c(140, 45, 150),
    "cyan": _c(15, 120, 140),
    "white": _c(90, 96, 108),
    "default": _c(30, 36, 48),
}
ANSI_PALETTE_BRIGHT_LIGHT: dict[str, QColor] = {
    "black": _c(110, 118, 130),
    "red": _c(200, 45, 50),
    "green": _c(20, 140, 70),
    "brown": _c(170, 125, 15),
    "blue": _c(35, 105, 200),
    "magenta": _c(160, 60, 170),
    "cyan": _c(20, 145, 165),
    "white": _c(40, 46, 58),
    "default": _c(20, 26, 36),
}


def _term(
    id_: str,
    name: str,
    bg: QColor,
    fg: QColor,
    cursor: QColor,
    *,
    light: bool = False,
    ansi: dict[str, QColor] | None = None,
    ansi_bright: dict[str, QColor] | None = None,
) -> TerminalTheme:
    if ansi is None:
        ansi = ANSI_PALETTE_LIGHT if light else ANSI_PALETTE_DARK
    if ansi_bright is None:
        ansi_bright = (
            ANSI_PALETTE_BRIGHT_LIGHT if light else ANSI_PALETTE_BRIGHT_DARK
        )
    return TerminalTheme(
        id=id_,
        name=name,
        bg=bg,
        fg=fg,
        cursor=cursor,
        ansi=dict(ansi),
        ansi_bright=dict(ansi_bright),
    )


APP_THEMES: dict[str, AppTheme] = {
    "slate": AppTheme(
        id="slate",
        name="Slate",
        bg="#0c1015",
        sidebar="#182028",
        surface="#1a222c",
        border="#24303c",
        text="#d7dde5",
        muted="#8b95a5",
        accent="#5a8cc8",
        accent_hover="#78a8d8",
        accent_soft="rgba(90, 140, 200, 0.18)",
        danger="#f07178",
        ok="#3dd68c",
    ),
    "midnight": AppTheme(
        id="midnight",
        name="Midnight",
        bg="#080a10",
        sidebar="#151928",
        surface="#181c28",
        border="#252b3c",
        text="#e2e6f0",
        muted="#8a93a8",
        accent="#7c6cf0",
        accent_hover="#968af5",
        accent_soft="rgba(124, 108, 240, 0.20)",
        danger="#f07178",
        ok="#3dd68c",
    ),
    "classic": AppTheme(
        id="classic",
        name="Classic",
        bg="#080808",
        sidebar="#161616",
        surface="#1a1a1a",
        border="#2a2a2a",
        text="#d0d0d0",
        muted="#888888",
        accent="#33aa55",
        accent_hover="#44cc66",
        accent_soft="rgba(51, 170, 85, 0.20)",
        danger="#cc5555",
        ok="#44cc66",
    ),
    "ember": AppTheme(
        id="ember",
        name="Ember",
        bg="#140e0c",
        sidebar="#1e1612",
        surface="#241c17",
        border="#3a2c24",
        text="#e8ddd4",
        muted="#a08a7a",
        accent="#d4784a",
        accent_hover="#e89266",
        accent_soft="rgba(212, 120, 74, 0.20)",
        danger="#e06060",
        ok="#5cbc7a",
    ),
    "ocean": AppTheme(
        id="ocean",
        name="Ocean",
        bg="#0a1214",
        sidebar="#122022",
        surface="#16262a",
        border="#243840",
        text="#d5e4e8",
        muted="#7f9aa3",
        accent="#2aa8a0",
        accent_hover="#3fc4bb",
        accent_soft="rgba(42, 168, 160, 0.20)",
        danger="#e07070",
        ok="#4ecf8a",
    ),
    "graphite": AppTheme(
        id="graphite",
        name="Graphite",
        bg="#121416",
        sidebar="#1c1f24",
        surface="#22262c",
        border="#32383f",
        text="#e4e6ea",
        muted="#9399a3",
        accent="#6b7f96",
        accent_hover="#8498ad",
        accent_soft="rgba(107, 127, 150, 0.22)",
        danger="#d96b6b",
        ok="#5bbf8a",
    ),
    "paper": AppTheme(
        id="paper",
        name="Paper",
        bg="#f3f4f6",
        sidebar="#e8eaee",
        surface="#ffffff",
        border="#cfd3da",
        text="#1c2430",
        muted="#5c6675",
        accent="#2f6fed",
        accent_hover="#4a84f5",
        accent_soft="rgba(47, 111, 237, 0.14)",
        danger="#c62828",
        ok="#1b8a4c",
    ),
    "mist": AppTheme(
        id="mist",
        name="Mist",
        bg="#eef2f0",
        sidebar="#e2e9e5",
        surface="#f7faf8",
        border="#c5d0ca",
        text="#1a2a24",
        muted="#5a6e66",
        accent="#2f7a62",
        accent_hover="#3d9478",
        accent_soft="rgba(47, 122, 98, 0.16)",
        danger="#b33a3a",
        ok="#2a8f55",
    ),
    "nord": AppTheme(
        id="nord",
        name="Nord",
        bg="#2e3440",
        sidebar="#3b4252",
        surface="#434c5e",
        border="#4c566a",
        text="#eceff4",
        muted="#a0a8b8",
        accent="#88c0d0",
        accent_hover="#8fbcbb",
        accent_soft="rgba(136, 192, 208, 0.22)",
        danger="#bf616a",
        ok="#a3be8c",
    ),
    "mocha": AppTheme(
        id="mocha",
        name="Mocha",
        bg="#1a1410",
        sidebar="#241c16",
        surface="#2c221b",
        border="#3d3026",
        text="#ebe0d4",
        muted="#a89888",
        accent="#c4a574",
        accent_hover="#d4b888",
        accent_soft="rgba(196, 165, 116, 0.20)",
        danger="#d07060",
        ok="#8fbc7a",
    ),
    "aurora": AppTheme(
        id="aurora",
        name="Aurora",
        bg="#0b1210",
        sidebar="#121c18",
        surface="#18241e",
        border="#26362e",
        text="#d8ebe2",
        muted="#7f9a8e",
        accent="#3db88a",
        accent_hover="#55c89a",
        accent_soft="rgba(61, 184, 138, 0.20)",
        danger="#e07070",
        ok="#4ecf8a",
    ),
    "snow": AppTheme(
        id="snow",
        name="Snow",
        bg="#f0f4f8",
        sidebar="#e4ebf2",
        surface="#ffffff",
        border="#c5d0dc",
        text="#1a2330",
        muted="#5a6a7c",
        accent="#3d7ea6",
        accent_hover="#4f90b8",
        accent_soft="rgba(61, 126, 166, 0.14)",
        danger="#c0392b",
        ok="#1e8a5a",
    ),
    "linen": AppTheme(
        id="linen",
        name="Linen",
        bg="#f5f2ec",
        sidebar="#ebe6dc",
        surface="#fcfaf6",
        border="#d4cdc0",
        text="#2a2620",
        muted="#6e665c",
        accent="#5a7a8a",
        accent_hover="#6b8b9c",
        accent_soft="rgba(90, 122, 138, 0.16)",
        danger="#b5453a",
        ok="#3d8a5c",
    ),
    "chalk": AppTheme(
        id="chalk",
        name="Chalk",
        bg="#f7f7f5",
        sidebar="#ecece8",
        surface="#ffffff",
        border="#d0d0ca",
        text="#222222",
        muted="#666660",
        accent="#0d9488",
        accent_hover="#14b8a6",
        accent_soft="rgba(13, 148, 136, 0.14)",
        danger="#dc2626",
        ok="#16a34a",
    ),
}

TERMINAL_THEMES: dict[str, TerminalTheme] = {
    "slate": _term(
        "slate", "Slate",
        QColor(18, 22, 28), QColor(204, 204, 204), QColor(255, 255, 255, 120),
    ),
    "midnight": _term(
        "midnight", "Midnight",
        QColor(12, 14, 22), QColor(220, 224, 236), QColor(160, 150, 255, 140),
    ),
    "standard": _term(
        "standard", "Standard",
        QColor(0, 0, 0), QColor(204, 204, 204), QColor(255, 255, 255, 120),
    ),
    "matrix": _term(
        "matrix", "Matrix",
        QColor(0, 0, 0), QColor(51, 204, 51), QColor(51, 204, 51, 140),
        ansi={**ANSI_PALETTE_DARK, "green": _c(51, 204, 51), "default": _c(51, 204, 51)},
        ansi_bright={
            **ANSI_PALETTE_BRIGHT_DARK,
            "green": _c(80, 230, 80),
            "default": _c(80, 230, 80),
        },
    ),
    "ember": _term(
        "ember", "Ember",
        QColor(22, 14, 12), QColor(232, 210, 190), QColor(212, 120, 74, 150),
    ),
    "ocean": _term(
        "ocean", "Ocean",
        QColor(10, 20, 22), QColor(190, 220, 225), QColor(42, 168, 160, 150),
    ),
    "graphite": _term(
        "graphite", "Graphite",
        QColor(20, 22, 26), QColor(210, 214, 220), QColor(140, 160, 180, 140),
    ),
    "paper": _term(
        "paper", "Paper",
        QColor(250, 250, 252), QColor(30, 36, 48), QColor(47, 111, 237, 140),
        light=True,
    ),
    "mist": _term(
        "mist", "Mist",
        QColor(245, 250, 247), QColor(26, 42, 36), QColor(47, 122, 98, 140),
        light=True,
        ansi={
            **ANSI_PALETTE_LIGHT,
            "green": _c(18, 120, 72),
            "cyan": _c(20, 110, 100),
            "default": _c(26, 42, 36),
        },
    ),
    "nord": _term(
        "nord", "Nord",
        QColor(46, 52, 64), QColor(236, 239, 244), QColor(136, 192, 208, 150),
    ),
    "mocha": _term(
        "mocha", "Mocha",
        QColor(28, 22, 18), QColor(235, 224, 212), QColor(196, 165, 116, 150),
    ),
    "aurora": _term(
        "aurora", "Aurora",
        QColor(12, 20, 16), QColor(216, 235, 226), QColor(61, 184, 138, 150),
    ),
    "snow": _term(
        "snow", "Snow",
        QColor(248, 250, 252), QColor(26, 35, 48), QColor(61, 126, 166, 140),
        light=True,
    ),
    "linen": _term(
        "linen", "Linen",
        QColor(252, 250, 246), QColor(42, 38, 32), QColor(90, 122, 138, 140),
        light=True,
    ),
    "chalk": _term(
        "chalk", "Chalk",
        QColor(252, 252, 250), QColor(34, 34, 34), QColor(13, 148, 136, 140),
        light=True,
    ),
}

ANSI_PRESET_MATCH = "match"
ANSI_PRESET_DARK = "dark"
ANSI_PRESET_LIGHT = "light"
ANSI_PRESETS: tuple[tuple[str, str], ...] = (
    (ANSI_PRESET_MATCH, "Match theme"),
    (ANSI_PRESET_DARK, "Dark (bright)"),
    (ANSI_PRESET_LIGHT, "Light (readable)"),
)


def _parse_hex_color(value: str) -> QColor | None:
    text = (value or "").strip()
    if not text:
        return None
    if not text.startswith("#"):
        text = f"#{text}"
    color = QColor(text)
    return color if color.isValid() else None


def _brighten(color: QColor, factor: float = 1.18) -> QColor:
    h, s, v, a = color.getHsv()
    if h < 0:
        return QColor(color)
    return QColor.fromHsv(h, s, min(255, int(v * factor)), a)


def resolve_ansi_palette(
    theme: TerminalTheme,
    preset: str = ANSI_PRESET_MATCH,
    accent: str = "",
) -> tuple[dict[str, QColor], dict[str, QColor]]:
    """Return (ansi, ansi_bright) for a terminal theme + user preset.

    Optional accent hex overrides green (common username / prompt color).
    """
    key = (preset or ANSI_PRESET_MATCH).strip().lower()
    if key == ANSI_PRESET_DARK:
        ansi, bright = dict(ANSI_PALETTE_DARK), dict(ANSI_PALETTE_BRIGHT_DARK)
    elif key == ANSI_PRESET_LIGHT:
        ansi, bright = dict(ANSI_PALETTE_LIGHT), dict(ANSI_PALETTE_BRIGHT_LIGHT)
    else:
        ansi, bright = dict(theme.ansi), dict(theme.ansi_bright)

    accent_color = _parse_hex_color(accent)
    if accent_color is not None:
        ansi["green"] = QColor(accent_color)
        bright["green"] = _brighten(accent_color)
    return ansi, bright


DEFAULT_APP_THEME_ID = "slate"
DEFAULT_TERMINAL_THEME_ID = "slate"

MONO_FONTS = [
    "Cascadia Mono",
    "JetBrains Mono",
    "Ubuntu Mono",
    "Source Code Pro",
    "IBM Plex Mono",
    "DejaVu Sans Mono",
    "Consolas",
    "Courier New",
    "Lucida Console",
]


def mono_font_choices() -> list[str]:
    """Bundled families first, then system list (deduped)."""
    try:
        from .fonts import bundled_font_families
    except ImportError:
        bundled_font_families = lambda: []  # type: ignore[assignment]
    seen: set[str] = set()
    out: list[str] = []
    for family in list(bundled_font_families()) + MONO_FONTS:
        if family in seen:
            continue
        seen.add(family)
        out.append(family)
    return out


def get_app_theme(theme_id: str) -> AppTheme:
    return APP_THEMES.get(theme_id, APP_THEMES[DEFAULT_APP_THEME_ID])


def get_terminal_theme(theme_id: str) -> TerminalTheme:
    return TERMINAL_THEMES.get(theme_id, TERMINAL_THEMES[DEFAULT_TERMINAL_THEME_ID])


# Back-compat alias used by older settings rows.
def get_theme(theme_id: str) -> AppTheme:
    return get_app_theme(theme_id)


def _hex_luminance(color: str) -> float:
    """Relative luminance 0..1 for a #RRGGBB color."""
    h = color.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) < 6:
        return 0.0
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


def _mix_hex(color_a: str, color_b: str, ratio: float) -> str:
    """Blend two #RRGGBB colors; ratio 0 → a, 1 → b."""
    def _rgb(value: str) -> tuple[int, int, int]:
        h = value.strip().lstrip("#")
        if len(h) == 3:
            h = "".join(ch * 2 for ch in h)
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    try:
        ar, ag, ab = _rgb(color_a)
        br, bg, bb = _rgb(color_b)
    except Exception:
        return color_a
    ratio = max(0.0, min(1.0, ratio))
    r = int(ar + (br - ar) * ratio)
    g = int(ag + (bg - ag) * ratio)
    b = int(ab + (bb - ab) * ratio)
    return f"#{r:02x}{g:02x}{b:02x}"


def build_stylesheet(theme: AppTheme) -> str:
    t = theme
    light = _hex_luminance(t.bg) > 0.55
    hover = "rgba(0, 0, 0, 0.06)" if light else "rgba(255, 255, 255, 0.07)"
    hover_strong = "rgba(0, 0, 0, 0.10)" if light else "rgba(255, 255, 255, 0.10)"
    # Theme-tinted lifts (not flat grey) for translucent header / shell feel.
    header_wash = t.accent_soft
    shell_bg = _mix_hex(t.surface, t.bg, 0.35)
    # Thin overlay-style scrollbars (no system chrome / arrow buttons).
    sb_track = "transparent"
    sb_handle = "rgba(0, 0, 0, 0.22)" if light else "rgba(255, 255, 255, 0.18)"
    sb_handle_hover = "rgba(0, 0, 0, 0.34)" if light else "rgba(255, 255, 255, 0.28)"
    sb_handle_pressed = t.accent
    return f"""
        QMainWindow {{
            background-color: transparent;
            color: {t.text};
        }}
        #windowRoot {{
            background-color: {t.bg};
            border: 1px solid {t.border};
            border-radius: 10px;
        }}
        #windowRoot[maximized="1"] {{
            border-radius: 0px;
            border: none;
        }}
        #titleBar {{
            background-color: {t.bg};
            border-bottom: 1px solid {t.border};
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
        }}
        #windowRoot[maximized="1"] #titleBar {{
            border-top-left-radius: 0px;
            border-top-right-radius: 0px;
        }}
        #titleBarTitle {{
            color: {t.text};
            font-size: 12px;
            font-weight: 600;
            letter-spacing: 0.3px;
        }}
        #titleBarStatus {{
            color: {t.accent};
            font-size: 11px;
            font-weight: 500;
            padding-left: 8px;
        }}
        #titleBarIcon {{
            background: transparent;
        }}
        #titleBarActionBtn {{
            background-color: transparent;
            color: {t.muted};
            border: none;
            border-radius: 6px;
            padding: 0 10px;
            font-size: 12px;
            font-weight: 500;
            min-height: 26px;
            max-height: 28px;
        }}
        #titleBarActionBtn:hover {{
            background-color: {hover};
            color: {t.text};
            border: none;
        }}
        #titleBarActionBtn:disabled {{
            color: {t.accent};
            background-color: transparent;
            border: none;
        }}
        #titleBarBtn {{
            background-color: transparent;
            color: {t.muted};
            border: none;
            border-radius: 6px;
            padding: 0;
            font-size: 13px;
            min-width: 36px;
            max-width: 36px;
        }}
        #titleBarBtn:hover {{
            background-color: {hover};
            color: {t.text};
        }}
        #titleBarCloseBtn {{
            background-color: transparent;
            color: {t.muted};
            border: none;
            border-radius: 6px;
            padding: 0;
            font-size: 12px;
            min-width: 36px;
            max-width: 36px;
        }}
        #titleBarCloseBtn:hover {{
            background-color: {t.danger};
            color: #ffffff;
        }}

        QSplitter::handle {{
            background-color: rgba(255, 255, 255, 0.08);
        }}
        QSplitter::handle:hover {{
            background-color: rgba(255, 255, 255, 0.16);
        }}
        QSplitter::handle:horizontal {{
            width: 5px;
        }}
        QSplitter::handle:vertical {{
            height: 5px;
        }}

        QScrollBar:vertical {{
            background: {sb_track};
            width: 8px;
            margin: 2px 1px 2px 0;
            border: none;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical {{
            background: {sb_handle};
            min-height: 28px;
            border-radius: 4px;
            margin: 0;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {sb_handle_hover};
        }}
        QScrollBar::handle:vertical:pressed {{
            background: {sb_handle_pressed};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical {{
            height: 0;
            width: 0;
            border: none;
            background: transparent;
        }}
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: transparent;
        }}

        QScrollBar:horizontal {{
            background: {sb_track};
            height: 8px;
            margin: 0 2px 1px 2px;
            border: none;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal {{
            background: {sb_handle};
            min-width: 28px;
            border-radius: 4px;
            margin: 0;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {sb_handle_hover};
        }}
        QScrollBar::handle:horizontal:pressed {{
            background: {sb_handle_pressed};
        }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal {{
            height: 0;
            width: 0;
            border: none;
            background: transparent;
        }}
        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {{
            background: transparent;
        }}

        #sidebar, #sidebarCollapsed {{
            background-color: {t.sidebar};
            border: none;
            border-right: 1px solid rgba(255, 255, 255, 0.06);
        }}
        #sidebarHeaderRow {{
            background: transparent;
        }}
        #sidebarHeader {{
            color: {t.muted};
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 1.2px;
            text-transform: uppercase;
            padding: 0 4px;
        }}
        #sidebarToggleBtn {{
            background-color: transparent;
            color: {t.muted};
            border: 1px solid {t.border};
            border-radius: 6px;
            padding: 0px;
            font-size: 14px;
            font-weight: 700;
            min-width: 28px;
            max-width: 48px;
            min-height: 28px;
        }}
        #sidebarToggleBtn:hover {{
            color: {t.text};
            background-color: {hover};
            border-color: {t.border};
        }}

        #hostList {{
            background-color: transparent;
            border: none;
            outline: none;
            font-size: 13px;
            color: {t.text};
            padding: 0;
        }}
        #hostList::item {{
            height: 32px;
            padding: 0 16px;
            margin: 0;
            border: none;
            border-left: 3px solid transparent;
            border-radius: 0;
        }}
        #hostList::item:hover {{
            background-color: {hover};
        }}
        #hostList::item:selected,
        #hostList::item:selected:active,
        #hostList::item:selected:!active {{
            background-color: {t.accent_soft};
            color: {t.text};
            border-left: 3px solid {t.accent};
        }}
        #hostList::item:selected:hover {{
            background-color: {t.accent_soft};
        }}

        #sidebarActions {{
            background: transparent;
        }}
        #addHostBtn, #quickConnectBtn, #sysLogBtn, #notesBtn, #workspacesBtn, #settingsBtn, #sidebarMenuBtn {{
            background-color: transparent;
            color: {t.muted};
            border: 1px dashed {t.border};
            padding: 8px 12px;
            margin: 0 12px;
            border-radius: 8px;
            text-align: center;
            font-size: 13px;
            min-width: 0;
            max-width: 16777215px;
        }}
        #addHostBtn:hover, #quickConnectBtn:hover, #sysLogBtn:hover,
        #notesBtn:hover, #workspacesBtn:hover, #settingsBtn:hover, #sidebarMenuBtn:hover {{
            background-color: {hover};
            color: {t.text};
            border-color: {t.border};
        }}
        #sidebarMenuBtn:checked {{
            background-color: {hover};
            color: {t.text};
        }}

        /* Collapsed rail — separate objectName (attribute selectors are flaky). */
        #sidebarCollapsed #hostList::item {{
            padding: 0px;
            border-left: none;
            border-radius: 8px;
            margin: 2px 8px;
            height: 36px;
            font-size: 13px;
            font-weight: 600;
        }}
        #sidebarCollapsed #hostList::item:selected,
        #sidebarCollapsed #hostList::item:selected:active,
        #sidebarCollapsed #hostList::item:selected:!active {{
            border-left: none;
            background-color: {t.accent_soft};
        }}
        #sidebarCollapsed QPushButton#addHostBtn,
        #sidebarCollapsed QPushButton#quickConnectBtn,
        #sidebarCollapsed QPushButton#sysLogBtn,
        #sidebarCollapsed QPushButton#notesBtn,
        #sidebarCollapsed QPushButton#workspacesBtn,
        #sidebarCollapsed QPushButton#settingsBtn,
        #sidebarCollapsed QPushButton#sidebarMenuBtn {{
            margin: 2px 8px;
            padding: 0px;
            min-width: 48px;
            max-width: 48px;
            min-height: 36px;
            max-height: 36px;
            font-size: 13px;
            font-weight: 600;
            text-align: center;
        }}
        #sidebarCollapsed QPushButton#sidebarToggleBtn {{
            margin: 2px 8px;
            padding: 0px;
            min-width: 48px;
            max-width: 48px;
            min-height: 28px;
            max-height: 28px;
            font-size: 16px;
            font-weight: 700;
            text-align: center;
        }}

        #sessionTabs {{
            background-color: {t.bg};
            color: {t.text};
        }}
        #sessionTabs::pane {{
            border: 0;
            margin: 0;
            padding: 0;
            top: 0px;
            background-color: {t.bg};
        }}
        #sessionTabs QTabBar {{
            background-color: {t.bg};
            border: 0;
            outline: 0;
        }}
        #sessionTabs QTabBar::tab {{
            background-color: {t.bg};
            color: {t.muted};
            padding: 4px 12px;
            margin: 3px 3px 3px 0;
            border: 1px solid transparent;
            border-radius: 6px;
            min-height: 0;
        }}
        #sessionTabs QTabBar::tab:hover {{
            color: {t.text};
            background-color: {hover};
            border-color: {t.border};
        }}
        #sessionTabs QTabBar::tab:selected {{
            color: {t.text};
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-bottom: 2px solid {t.accent};
            border-radius: 6px;
            font-weight: 600;
        }}
        #sessionTabs QTabBar::close-button {{
            margin-left: 4px;
        }}

        #sessionStatus {{
            background-color: {t.bg};
            color: {t.muted};
            padding: 0 12px;
            font-size: 11px;
            border: none;
        }}
        #sessionStatus[state="ok"] {{ color: {t.ok}; }}
        #sessionStatus[state="err"] {{ color: {t.danger}; }}

        #paneStatusRow {{
            background-color: {t.bg};
            border-top: 1px solid {t.surface};
        }}
        #paneCloseBtn {{
            background-color: transparent;
            border: none;
            color: {t.muted};
            padding: 0;
            min-width: 0;
            max-width: none;
            border-radius: 0;
            font-size: 11px;
        }}
        #paneCloseBtn:hover {{
            color: {t.text};
            background-color: rgba(255, 255, 255, 0.08);
        }}
        #sessionLogBtn {{
            background-color: transparent;
            border: none;
            border-left: 1px solid {t.surface};
            color: {t.muted};
            padding: 0 10px;
            min-width: 44px;
            max-width: none;
            border-radius: 0;
            font-size: 11px;
        }}
        #sessionLogBtn:hover {{
            color: {t.text};
            background-color: rgba(255, 255, 255, 0.08);
        }}
        #sessionLogBtn[logging="1"] {{
            color: {t.ok};
        }}
        #sessionLogBtn:checked {{
            color: {t.ok};
        }}

        #sessionSplitter::handle {{
            background-color: {t.border};
        }}
        #sessionSplitter::handle:hover {{
            background-color: {t.accent};
        }}

        #sftpPaneTitle {{
            color: {t.muted};
            font-size: 11px;
            font-weight: 600;
            padding: 0 4px;
        }}
        #sftpToolBtn {{
            background-color: transparent;
            color: {t.muted};
            border: 1px solid {t.border};
            border-radius: 4px;
            padding: 0;
            min-width: 28px;
            max-width: 28px;
            font-size: 13px;
        }}
        #sftpToolBtn:hover {{
            color: {t.text};
            background-color: rgba(255, 255, 255, 0.08);
            border-color: {t.accent};
        }}
        #sftpToolBtn:disabled {{
            color: {t.border};
            border-color: {t.surface};
        }}
        #sftpPathEdit {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 4px;
            color: {t.text};
            padding: 3px 8px;
            min-height: 20px;
        }}
        #sftpTree {{
            background-color: {t.bg};
            border: 1px solid {t.surface};
            color: {t.text};
            alternate-background-color: {t.surface};
            outline: none;
            show-decoration-selected: 1;
        }}
        #sftpTree::item {{
            padding: 2px 4px;
            border-radius: 3px;
            min-height: 20px;
        }}
        #sftpTree::item:hover {{
            background-color: {hover};
        }}
        #sftpTree::item:selected {{
            background-color: {t.accent_soft};
            color: {t.text};
        }}
        #sftpTree::item:selected:hover {{
            background-color: {t.accent_soft};
            color: {t.text};
        }}
        #sftpTree QHeaderView::section {{
            background-color: {t.surface};
            color: {t.muted};
            border: none;
            border-bottom: 1px solid {t.border};
            border-right: 1px solid {t.border};
            padding: 4px 8px;
            font-size: 11px;
        }}
        #sftpTree QHeaderView::section:hover {{
            background-color: {hover};
            color: {t.text};
        }}
        #sftpTree QHeaderView::section:pressed {{
            background-color: {t.accent_soft};
            color: {t.text};
        }}

        #FindBar {{
            background-color: {t.surface};
            border-bottom: 1px solid {t.border};
        }}
        #FindBar QLineEdit {{
            min-height: 18px;
            max-height: 24px;
        }}
        #FindBar QToolButton#FindPrev,
        #FindBar QToolButton#FindNext,
        #FindBar QPushButton#FindClose {{
            background-color: transparent;
            border: 1px solid {t.border};
            border-radius: 4px;
            color: {t.muted};
            padding: 2px 8px;
            min-width: 28px;
            max-width: 36px;
        }}
        #FindCount {{
            color: {t.muted};
            font-size: 11px;
        }}

        #HostFilterBar {{
            background-color: transparent;
        }}
        #HostFilterBar QLineEdit#HostFilterEdit {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 6px;
            padding: 2px 8px;
            color: {t.text};
            selection-background-color: {t.accent};
            min-height: 18px;
            max-height: 24px;
        }}
        #HostFilterBar QLineEdit#HostFilterEdit:focus {{
            border-color: {t.border};
        }}
        #HostFilterBar QPushButton#HostFilterClose,
        #HostFilterBar QPushButton#HostFilterAction {{
            background-color: transparent;
            border: 1px solid {t.border};
            border-radius: 4px;
            color: {t.muted};
            padding: 0px;
            min-width: 28px;
            max-width: 28px;
        }}
        #HostFilterBar QPushButton#HostFilterClose:hover,
        #HostFilterBar QPushButton#HostFilterAction:hover {{
            background-color: {hover};
            color: {t.text};
            border-color: {t.border};
        }}

        /* Quiet default buttons — accent only on explicit primary actions. */
        QPushButton {{
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
            padding: 3px 10px;
            border-radius: 5px;
            font-size: 12px;
            min-height: 22px;
        }}
        QPushButton:hover {{
            background-color: {hover};
            border-color: {t.accent};
            color: {t.text};
        }}
        QPushButton:pressed {{
            background-color: {t.accent_soft};
        }}
        QPushButton:disabled {{
            color: {t.muted};
            background-color: {t.surface};
            border-color: {t.border};
        }}
        QPushButton:checked {{
            background-color: {t.accent_soft};
            border-color: {t.accent};
            color: {t.text};
        }}
        /* Title-bar chrome must not inherit the bordered surface button look. */
        #titleBarBtn, #titleBarCloseBtn {{
            background-color: transparent;
            border: none;
            padding: 0;
            min-height: 0;
            max-height: none;
        }}
        #titleBarActionBtn {{
            min-height: 26px;
            max-height: 28px;
            border: none;
        }}

        /* After generic QPushButton:hover so find-bar chrome wins. */
        #FindBar QToolButton#FindPrev:hover,
        #FindBar QToolButton#FindNext:hover,
        #FindBar QPushButton#FindClose:hover {{
            background-color: {hover_strong};
            border-color: {t.border};
            color: {t.text};
        }}
        #FindBar QToolButton#FindPrev:pressed,
        #FindBar QToolButton#FindNext:pressed,
        #FindBar QPushButton#FindClose:pressed {{
            background-color: {hover_strong};
            border-color: {t.border};
        }}

        QPushButton#dialogSecondary {{
            background-color: transparent;
            color: {t.muted};
            border: 1px solid {t.border};
            padding: 3px 10px;
            border-radius: 5px;
            font-size: 12px;
            min-width: 64px;
            min-height: 22px;
        }}
        QPushButton#dialogSecondary:hover {{
            background-color: {hover};
            color: {t.text};
            border-color: {t.accent};
        }}
        QPushButton#dialogPrimary {{
            background-color: {t.accent_soft};
            color: {t.text};
            border: 1px solid {t.accent};
            padding: 3px 10px;
            border-radius: 5px;
            font-size: 12px;
            min-width: 64px;
            min-height: 22px;
        }}
        QPushButton#dialogPrimary:hover {{
            background-color: {t.accent};
            color: #eef3f8;
            border-color: {t.accent_hover};
        }}

        QDialogButtonBox QPushButton {{
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
            padding: 3px 10px;
            border-radius: 5px;
            font-size: 12px;
            min-width: 64px;
            min-height: 22px;
        }}
        QDialogButtonBox QPushButton:hover {{
            background-color: {hover};
            border-color: {t.accent};
        }}
        QDialogButtonBox QPushButton[text="Cancel"],
        QDialogButtonBox QPushButton[text="No"],
        QDialogButtonBox QPushButton[text="&No"] {{
            background-color: transparent;
            color: {t.muted};
            border: 1px solid {t.border};
        }}
        QDialogButtonBox QPushButton[text="Cancel"]:hover,
        QDialogButtonBox QPushButton[text="No"]:hover,
        QDialogButtonBox QPushButton[text="&No"]:hover {{
            background-color: {hover};
            color: {t.text};
            border-color: {t.accent};
        }}

        QMessageBox#confirmDialog {{
            background-color: {t.sidebar};
            color: {t.text};
        }}
        QMessageBox#confirmDialog QLabel {{
            color: {t.text};
            font-size: 13px;
        }}
        QMessageBox#confirmDialog QPushButton {{
            padding: 4px 12px;
            font-size: 12px;
            min-width: 64px;
        }}

        QLineEdit, QComboBox, QTextEdit, QPlainTextEdit {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            padding: 4px 8px;
            border-radius: 6px;
            color: {t.text};
            selection-background-color: {t.accent};
        }}
        QCheckBox {{
            color: {t.text};
            spacing: 8px;
        }}
        QCheckBox::indicator {{
            width: 14px;
            height: 14px;
            border-radius: 3px;
            border: 1px solid {t.border};
            background-color: {t.surface};
        }}
        QCheckBox::indicator:checked {{
            background-color: {t.accent};
            border-color: {t.accent};
        }}
        QComboBox {{
            padding: 4px 26px 4px 8px;
            min-height: 18px;
            max-height: 26px;
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
        }}
        QComboBox:on {{
            background-color: {t.surface};
            color: {t.text};
        }}
        QComboBox QAbstractItemView {{
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
            outline: none;
            selection-background-color: {t.accent_soft};
            selection-color: {t.text};
            padding: 4px;
        }}
        QComboBox QAbstractItemView::item {{
            color: {t.text};
            background-color: {t.surface};
            padding: 4px 8px;
            min-height: 22px;
        }}
        QComboBox QAbstractItemView::item:selected {{
            background-color: {t.accent_soft};
            color: {t.text};
        }}
        QComboBox QAbstractItemView::item:hover {{
            background-color: {hover};
            color: {t.text};
        }}
        QComboBox::drop-down {{
            subcontrol-origin: border;
            subcontrol-position: center right;
            width: 22px;
            border: none;
            border-left: 1px solid {t.border};
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
            background-color: {t.surface};
        }}
        QComboBox::drop-down:hover {{
            background-color: {t.accent_soft};
        }}
        QComboBox::down-arrow {{
            image: url({_icon_url("combo_down.svg")});
            width: 10px;
            height: 6px;
        }}
        QComboBox::down-arrow:hover {{
            image: url({_icon_url("combo_down_hover.svg")});
        }}
        QSpinBox {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 6px;
            color: {t.text};
            selection-background-color: {t.accent};
            min-height: 18px;
            max-height: 26px;
            padding: 4px 26px 4px 8px;
        }}
        QSpinBox::up-button, QSpinBox::down-button {{
            subcontrol-origin: border;
            width: 22px;
            height: 13px;
            border: none;
            border-left: 1px solid {t.border};
            background-color: {t.surface};
        }}
        QSpinBox::up-button {{
            subcontrol-position: top right;
            border-top-right-radius: 6px;
        }}
        QSpinBox::down-button {{
            subcontrol-position: bottom right;
            border-bottom-right-radius: 6px;
        }}
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
            background-color: {t.accent_soft};
        }}
        QSpinBox::up-button:pressed, QSpinBox::down-button:pressed {{
            background-color: {t.accent};
        }}
        QSpinBox::up-arrow {{
            image: url({_icon_url("spin_up.svg")});
            width: 10px;
            height: 6px;
        }}
        QSpinBox::down-arrow {{
            image: url({_icon_url("spin_down.svg")});
            width: 10px;
            height: 6px;
        }}
        QTextEdit {{
            padding: 8px;
            min-height: 80px;
            max-height: none;
        }}
        QTextEdit#repoStatsOutput {{
            min-height: 0px;
            max-height: 16777215px;
            background-color: {t.bg};
        }}
        QLabel {{
            color: {t.text};
        }}
        QMessageBox, QDialog {{
            background-color: {t.sidebar};
            color: {t.text};
        }}
        #dualSftpHostTree {{
            background-color: {t.bg};
            border: 1px solid {t.border};
            border-radius: 6px;
            color: {t.text};
            outline: none;
            padding: 6px;
            show-decoration-selected: 1;
        }}
        #dualSftpHostTree::item {{
            padding: 5px 8px;
            border-radius: 4px;
            min-height: 22px;
        }}
        #dualSftpHostTree::item:hover {{
            background-color: {hover};
        }}
        #dualSftpHostTree::item:selected,
        #dualSftpHostTree::item:selected:active,
        #dualSftpHostTree::item:selected:!active {{
            background-color: {t.accent_soft};
            color: {t.text};
        }}
        #dualSftpHostTree::branch {{
            background: transparent;
        }}
        #dualSftpHostTree::branch:has-children:!has-siblings:closed,
        #dualSftpHostTree::branch:closed:has-children:has-siblings {{
            border-image: none;
            image: url({_icon_url("tree_closed.svg")});
        }}
        #dualSftpHostTree::branch:open:has-children:!has-siblings,
        #dualSftpHostTree::branch:open:has-children:has-siblings {{
            border-image: none;
            image: url({_icon_url("tree_open.svg")});
        }}

        /* Framed dialogs (Settings / Notes / Host / host picker / System log) — transparent shell; #windowRoot paints chrome */
        #settingsDialog, #notesDialog, #hostDialog, #dualSftpDialog, #systemLogDialog, #workspacesDialog {{
            background-color: transparent;
        }}
        #framedDialogBody {{
            background-color: {t.bg};
            border-bottom-left-radius: 10px;
            border-bottom-right-radius: 10px;
        }}
        #windowRoot[maximized="1"] #framedDialogBody {{
            border-bottom-left-radius: 0px;
            border-bottom-right-radius: 0px;
        }}

        /* Settings dialog — left rail + content (mirrors main sidebar) */
        #settingsNavRail {{
            background-color: {t.sidebar};
            border-right: 1px solid {t.border};
        }}
        #settingsNavHeader {{
            color: {t.muted};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            padding: 0 6px 4px 6px;
        }}
        #settingsNav {{
            background-color: transparent;
            border: none;
            outline: none;
            color: {t.text};
        }}
        #settingsNav::item {{
            padding: 6px 10px;
            border-radius: 6px;
            color: {t.muted};
        }}
        #settingsNav::item:hover {{
            background-color: {hover};
            color: {t.text};
        }}
        #settingsNav::item:selected,
        #settingsNav::item:selected:active,
        #settingsNav::item:selected:!active {{
            background-color: {t.accent_soft};
            color: {t.text};
        }}
        #settingsContent {{
            background-color: {t.bg};
        }}
        #settingsPageTitle {{
            color: {t.text};
            font-size: 15px;
            font-weight: 600;
        }}
        #settingsHint {{
            color: {t.muted};
            font-size: 12px;
        }}
        #shortcutsList {{
            background-color: {t.bg};
            border: 1px solid {t.border};
            border-radius: 6px;
            color: {t.text};
            outline: none;
            alternate-background-color: {t.surface};
            padding: 4px;
        }}
        #shortcutsList::item {{
            padding: 3px 6px;
            min-height: 22px;
        }}
        #shortcutsList QHeaderView::section {{
            background-color: {t.surface};
            color: {t.muted};
            border: none;
            border-bottom: 1px solid {t.border};
            padding: 4px 8px;
            font-size: 11px;
        }}
        #settingsStack {{
            background-color: transparent;
        }}

        #sshPolicyTabs {{
            background-color: transparent;
            color: {t.text};
        }}
        #sshPolicyTabs::pane {{
            border: 1px solid {t.border};
            border-top: none;
            margin: 0;
            padding: 0;
            top: -1px;
            background-color: {t.bg};
            border-bottom-left-radius: 6px;
            border-bottom-right-radius: 6px;
        }}
        #sshPolicyTabs QTabBar {{
            background-color: transparent;
            border: none;
        }}
        #sshPolicyTabs QTabBar::tab {{
            background-color: {t.surface};
            color: {t.muted};
            padding: 8px 14px;
            margin-right: 2px;
            border: 1px solid {t.border};
            border-bottom: none;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
        }}
        #sshPolicyTabs QTabBar::tab:hover {{
            color: {t.text};
            background-color: {hover};
        }}
        #sshPolicyTabs QTabBar::tab:selected {{
            background-color: {t.bg};
            color: {t.text};
            border-bottom: 2px solid {t.accent};
            font-weight: 600;
        }}
        #sshAlgList {{
            background-color: {t.bg};
            border: none;
            color: {t.text};
            outline: none;
            padding: 4px;
        }}
        #sshAlgList::item {{
            padding: 4px 8px;
            border-radius: 4px;
        }}
        #sshAlgList::item:hover {{
            background-color: {hover};
        }}
        #sshAlgList::item:selected {{
            background-color: {t.accent_soft};
            color: {t.text};
        }}

        /* Dual SFTP / Jump host picker tree (body of #dualSftpDialog FramedDialog) */
        #dualSftpHostTree {{
            background-color: {t.bg};
            border: 1px solid {t.border};
            border-radius: 6px;
            color: {t.text};
            outline: none;
            padding: 4px;
            show-decoration-selected: 1;
        }}
        #dualSftpHostTree::item {{
            padding: 4px 8px;
            border-radius: 4px;
            min-height: 22px;
        }}
        #dualSftpHostTree::item:hover {{
            background-color: {hover};
        }}
        #dualSftpHostTree::item:selected,
        #dualSftpHostTree::item:selected:active,
        #dualSftpHostTree::item:selected:!active {{
            background-color: {t.accent_soft};
            color: {t.text};
        }}
        #dualSftpHostTree::branch {{
            background: transparent;
        }}
        #dualSftpHostTree::branch:has-children:!has-siblings:closed,
        #dualSftpHostTree::branch:closed:has-children:has-siblings {{
            border-image: none;
            image: url({_icon_url("tree_closed.svg")});
        }}
        #dualSftpHostTree::branch:open:has-children:!has-siblings,
        #dualSftpHostTree::branch:open:has-children:has-siblings {{
            border-image: none;
            image: url({_icon_url("tree_open.svg")});
        }}
        #dualSftpHostTree::branch:hover {{
            background: transparent;
        }}
        #sshAlgList::indicator {{
            width: 14px;
            height: 14px;
            border-radius: 3px;
            border: 1px solid {t.border};
            background-color: {t.surface};
        }}
        #sshAlgList::indicator:checked {{
            background-color: {t.accent};
            border-color: {t.accent};
        }}
        #knownHostsList {{
            background-color: {t.bg};
            border: 1px solid {t.border};
            border-radius: 6px;
            color: {t.text};
            outline: none;
            padding: 4px;
        }}
        #knownHostsList::item {{
            padding: 6px 8px;
            border-radius: 4px;
        }}
        #knownHostsList::item:hover {{
            background-color: {hover};
        }}
        #knownHostsList::item:selected {{
            background-color: {t.accent_soft};
            color: {t.text};
        }}

        #pasteConfirmDialog {{
            background-color: {t.sidebar};
        }}
        #pasteConfirmTitle {{
            color: {t.text};
            font-size: 13px;
            font-weight: 600;
        }}
        #pasteConfirmHint {{
            color: {t.muted};
            font-size: 11px;
        }}
        #pasteConfirmBadge {{
            color: {t.muted};
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 8px;
            padding: 2px 8px;
            font-size: 11px;
        }}
        #pasteConfirmEditor {{
            background-color: {t.bg};
            border: 1px solid {t.border};
            border-radius: 6px;
            padding: 6px 8px;
            color: {t.text};
            selection-background-color: {t.accent};
            min-height: 0px;
            max-height: 16777215px;
        }}
        #pasteConfirmEditor:focus {{
            border-color: {t.accent};
        }}
        #pasteConfirmHandle {{
            background-color: {t.border};
            border: none;
            border-radius: 2px;
            margin: 0 80px;
            min-height: 4px;
            max-height: 4px;
        }}
        #pasteConfirmHandle:hover {{
            background-color: {t.accent};
        }}
        QMenu, QMenu#roundedMenu {{
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 8px;
            padding: 6px;
        }}
        QMenu::item, QMenu#roundedMenu::item {{
            padding: 6px 24px 6px 12px;
            border-radius: 5px;
        }}
        QMenu::item:selected, QMenu#roundedMenu::item:selected {{
            background-color: {t.accent_soft};
        }}
        QMenu::separator, QMenu#roundedMenu::separator {{
            height: 1px;
            background: {t.border};
            margin: 4px 8px;
        }}
        QInputDialog {{
            background-color: {t.sidebar};
            color: {t.text};
        }}

        /* Notes dialog (sidebar scratchpad) — Settings-like surface + accent */
        #notesBody {{
            background-color: {t.bg};
        }}
        #notesHeader {{
            background-color: {t.sidebar};
            border: none;
        }}
        #notesPageTitle {{
            color: {t.accent};
            font-size: 15px;
            font-weight: 600;
            letter-spacing: 0.01em;
        }}
        #notesHeaderAccent {{
            background-color: {t.accent};
            border: none;
            max-height: 2px;
            min-height: 2px;
        }}
        #notesContent {{
            background-color: {t.bg};
        }}
        #notesHint {{
            color: {t.muted};
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.03em;
            text-transform: uppercase;
        }}
        #notesFindBar {{
            background-color: {t.sidebar};
            border-bottom: 1px solid {t.border};
        }}
        #notesFindEdit {{
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 6px;
            padding: 5px 10px;
            min-height: 22px;
            selection-background-color: {t.accent};
        }}
        #notesFindEdit:focus {{
            border-color: {t.accent};
            background-color: {t.surface};
        }}
        #notesFindBtn {{
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 6px;
            padding: 2px 8px;
            min-width: 28px;
            min-height: 24px;
        }}
        #notesFindBtn:hover {{
            background-color: {t.accent_soft};
            border-color: {t.accent};
            color: {t.text};
        }}
        #notesFindCount {{
            color: {t.muted};
            font-size: 11px;
        }}
        #notesFindClose {{
            background-color: {t.surface};
            color: {t.muted};
            border: 1px solid {t.border};
            border-radius: 6px;
            padding: 2px 0;
            min-height: 24px;
        }}
        #notesFindClose:hover {{
            background-color: {hover};
            color: {t.text};
            border-color: {t.accent};
        }}
        #notesTabBar {{
            background-color: transparent;
            border: 0;
            outline: 0;
        }}
        #notesTabBar::tab {{
            background-color: transparent;
            color: {t.muted};
            padding: 4px 12px;
            margin: 3px 3px 3px 0;
            border: 1px solid transparent;
            border-radius: 6px;
            min-height: 0;
        }}
        #notesTabBar::tab:hover {{
            color: {t.text};
            background-color: {hover};
            border-color: {t.border};
        }}
        #notesTabBar::tab:selected {{
            color: {t.text};
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-bottom: 2px solid {t.accent};
            border-radius: 6px;
            font-weight: 600;
        }}
        #notesTabBar::close-button {{
            margin-left: 4px;
        }}
        #notesEditorHost {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 8px;
        }}
        #notesEditorHost:focus-within {{
            border-color: {t.accent};
        }}
        #notesEditor, #notesEditorHost QPlainTextEdit {{
            background-color: {t.surface};
            color: {t.text};
            border: none;
            border-radius: 8px;
            padding: 10px 12px;
            selection-background-color: {t.accent};
        }}
        #notesRightCombo {{
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 6px;
            padding: 4px 8px;
            min-height: 22px;
        }}
        #notesRightCombo:hover, #notesRightCombo:focus {{
            border-color: {t.accent};
        }}
        #notesSplitter::handle {{
            background-color: {t.border};
            width: 2px;
            margin: 4px 2px;
            border-radius: 1px;
        }}
        #notesSplitter::handle:hover {{
            background-color: {t.accent};
        }}

        /* Workspaces dialog — same surface language as Notes */
        #workspacesBody {{
            background-color: {t.bg};
        }}
        #workspacesHeader {{
            background-color: {t.sidebar};
            border: none;
        }}
        #workspacesPageTitle {{
            color: {t.accent};
            font-size: 15px;
            font-weight: 600;
            letter-spacing: 0.01em;
        }}
        #workspacesHeaderAccent {{
            background-color: {t.accent};
            border: none;
            max-height: 2px;
            min-height: 2px;
        }}
        #workspacesContent {{
            background-color: {t.bg};
        }}
        #workspacesHint {{
            color: {t.muted};
            font-size: 12px;
        }}
        #workspacesAlongside {{
            color: {t.text};
            spacing: 8px;
        }}
        #workspacesList {{
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 8px;
            outline: none;
            padding: 4px;
        }}
        #workspacesList::item {{
            background-color: transparent;
            color: {t.text};
            border-radius: 6px;
            padding: 8px 10px;
            margin: 2px 0;
            min-height: 40px;
        }}
        #workspacesList::item:hover {{
            background-color: {hover};
        }}
        #workspacesList::item:selected {{
            background-color: {t.accent_soft};
            color: {t.text};
            border-left: 3px solid {t.accent};
        }}
        #workspacesList::item:selected:hover {{
            background-color: {t.accent_soft};
        }}

        /* System log dialog */
        #systemLogBody {{
            background-color: {t.bg};
        }}
        #systemLogDialog QLabel {{
            color: {t.muted};
            font-size: 12px;
        }}
        #systemLogDialog QComboBox {{
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 4px;
            padding: 3px 8px;
            min-height: 20px;
        }}
        #systemLogDialog QComboBox::drop-down {{
            border: none;
        }}
        #systemLogDialog QComboBox QAbstractItemView {{
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
            selection-background-color: {t.accent_soft};
        }}
        #systemLogDialog QLineEdit {{
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 4px;
            padding: 3px 8px;
            min-height: 20px;
            selection-background-color: {t.accent};
        }}
        #systemLogDialog QDateTimeEdit {{
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 4px;
            padding: 3px 8px;
            min-height: 20px;
        }}
        #systemLogDialog QDateTimeEdit::drop-down {{
            border: none;
        }}
        #systemLogDialog QPushButton#dialogSecondary:checked {{
            background-color: {t.accent_soft};
            color: {t.text};
            border-color: {t.accent};
        }}
        #logTable {{
            background-color: {t.bg};
            border: 1px solid {t.surface};
            color: {t.text};
            alternate-background-color: {t.surface};
            gridline-color: transparent;
            font-size: 12px;
        }}
        #logTable::item {{
            padding: 2px 6px;
        }}
        #logTable::item:selected {{
            background-color: {t.accent_soft};
            color: {t.text};
        }}
        #logTable QHeaderView::section {{
            background-color: {t.surface};
            color: {t.muted};
            border: none;
            border-bottom: 1px solid {t.border};
            padding: 4px 8px;
            font-size: 11px;
            font-weight: 600;
        }}
        #logDivider {{
            color: {t.border};
        }}
        #logStatus {{
            color: {t.muted};
            font-size: 11px;
        }}

        /* Restic Manager — modern nav + dashboard cards */
        #navSidebar {{
            background-color: {t.sidebar};
            border-right: 1px solid {t.border};
        }}
        #navBrand {{
            color: {t.text};
            font-size: 15px;
            font-weight: 700;
            letter-spacing: 0.2px;
            padding: 0 4px;
        }}
        #navVersion {{
            color: {t.muted};
            font-size: 11px;
            padding: 0 4px 4px 4px;
        }}
        #navFooter {{
            color: {t.muted};
            font-size: 11px;
            padding: 0;
            line-height: 1.35;
        }}
        #navBrandIcon {{
            background: transparent;
            border: none;
        }}
        #navFooterRow {{
            background: transparent;
            border: none;
        }}
        #navDivider {{
            background-color: {t.border};
            border: none;
            max-height: 1px;
        }}
        QPushButton#navBtn {{
            background-color: transparent;
            color: {t.muted};
            border: 1px solid transparent;
            border-radius: 8px;
            padding: 8px 10px;
            text-align: left;
            font-size: 13px;
            font-weight: 500;
            min-height: 36px;
        }}
        QPushButton#navBtn:hover {{
            background-color: {hover};
            color: {t.text};
        }}
        QPushButton#navBtn:checked {{
            background-color: {t.accent_soft};
            color: {t.text};
            border: 1px solid transparent;
            border-left: 3px solid {t.accent};
            font-weight: 600;
        }}
        QPushButton#navBtn:pressed {{
            background-color: {t.accent_soft};
        }}
        #contentArea, #dashboardPage {{
            background-color: {t.bg};
        }}
        #pageTitle {{
            color: {t.text};
            font-size: 26px;
            font-weight: 700;
            letter-spacing: -0.3px;
        }}
        #pageSubtitle {{
            color: {t.muted};
            font-size: 13px;
            font-weight: 400;
        }}
        QPushButton#toolbarBtn {{
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 8px;
            padding: 8px 14px;
            font-size: 12px;
            min-height: 32px;
        }}
        QPushButton#toolbarBtn:hover {{
            border-color: {t.accent};
            background-color: {hover};
        }}
        QPushButton#linkBtn {{
            background-color: transparent;
            color: {t.accent};
            border: none;
            padding: 4px 2px;
            font-size: 12px;
            font-weight: 600;
            min-height: 0;
        }}
        QPushButton#linkBtn:hover {{
            color: {t.accent_hover};
            background-color: transparent;
            border: none;
        }}
        #statCard {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 12px;
        }}
        #statCardIcon {{
            background-color: {t.accent_soft};
            border-radius: 10px;
        }}
        #statCardValue {{
            color: {t.text};
            font-size: 28px;
            font-weight: 700;
            letter-spacing: -0.5px;
        }}
        #statCardTitle {{
            color: {t.text};
            font-size: 13px;
            font-weight: 600;
        }}
        #statCardSubtitle {{
            color: {t.muted};
            font-size: 11px;
        }}
        #sectionCard, #chartCard {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 12px;
        }}
        #sectionCardTitle {{
            color: {t.text};
            font-size: 15px;
            font-weight: 600;
        }}
        #jobsTableShell {{
            background-color: {shell_bg};
            border: 1px solid {t.border};
            border-radius: 10px;
        }}
        QTableWidget#jobsTable {{
            background-color: transparent;
            border: none;
            border-radius: 0;
            color: {t.text};
            gridline-color: transparent;
            outline: none;
            alternate-background-color: transparent;
            selection-background-color: {t.accent_soft};
            selection-color: {t.text};
        }}
        QTableWidget#jobsTable::item {{
            background-color: transparent;
            padding: 10px 8px;
            border: none;
            border-bottom: 1px solid {t.border};
        }}
        QTableWidget#jobsTable::item:selected {{
            background-color: {t.accent_soft};
            color: {t.text};
            border-bottom: 1px solid {t.border};
        }}
        QTableWidget#jobsTable QHeaderView {{
            background-color: transparent;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
        }}
        QTableWidget#jobsTable QHeaderView::section {{
            background-color: {header_wash};
            color: {t.muted};
            border: none;
            border-bottom: 1px solid {t.border};
            border-right: none;
            padding: 10px 8px;
            font-size: 11px;
            font-weight: 600;
        }}
        QTableWidget#jobsTable QHeaderView::section:hover {{
            color: {t.text};
            background-color: {hover};
        }}
        QTableWidget#jobsTable QHeaderView::section:first {{
            border-top-left-radius: 10px;
        }}
        QTableWidget#jobsTable QHeaderView::section:last {{
            border-top-right-radius: 10px;
        }}
        QTableWidget#jobsTable QTableCornerButton::section {{
            background-color: {header_wash};
            border: none;
            border-top-left-radius: 10px;
        }}
        /* Title lives inside the frame — Fusion clips border-straddling titles. */
        QGroupBox {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 10px;
            margin-top: 8px;
            padding-top: 16px;
            padding-left: 10px;
            padding-right: 10px;
            padding-bottom: 8px;
            font-weight: 600;
            color: {t.text};
        }}
        QGroupBox::title {{
            subcontrol-origin: padding;
            subcontrol-position: top left;
            left: 8px;
            top: 2px;
            padding: 0 2px;
            color: {t.muted};
            background-color: transparent;
        }}
        QTableWidget, QTreeWidget, QListWidget {{
            background-color: {t.bg};
            border: 1px solid {t.border};
            border-radius: 8px;
            color: {t.text};
            alternate-background-color: {t.surface};
            gridline-color: {t.border};
            outline: none;
        }}
        QTableWidget::item:selected, QTreeWidget::item:selected, QListWidget::item:selected {{
            background-color: {t.accent_soft};
            color: {t.text};
        }}
        QHeaderView::section {{
            background-color: {t.surface};
            color: {t.muted};
            border: none;
            border-bottom: 1px solid {t.border};
            border-right: 1px solid {t.border};
            padding: 6px 8px;
            font-size: 11px;
            font-weight: 600;
        }}
        QTabWidget::pane {{
            border: 1px solid {t.border};
            border-radius: 8px;
            background-color: {t.bg};
        }}
        QTabBar::tab {{
            background-color: {t.surface};
            color: {t.muted};
            border: 1px solid {t.border};
            border-bottom: none;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            padding: 6px 14px;
            margin-right: 2px;
        }}
        QTabBar::tab:selected {{
            background-color: {t.bg};
            color: {t.text};
            border-bottom: 1px solid {t.bg};
        }}
        QTabBar::tab:hover:!selected {{
            color: {t.text};
            background-color: {hover};
        }}
        QProgressBar {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 6px;
            text-align: center;
            color: {t.text};
            min-height: 16px;
        }}
        QProgressBar::chunk {{
            background-color: {t.accent};
            border-radius: 5px;
        }}
        QStatusBar {{
            background-color: {t.bg};
            color: {t.muted};
            border-top: 1px solid {t.border};
        }}
    """


def prefer_ui_font():
    """Return a modern UI font family available on this system."""
    from PyQt6.QtGui import QFontDatabase

    families = set(QFontDatabase.families())
    for name in (
        "Segoe UI Variable",
        "Segoe UI",
        "Inter",
        "SF Pro Text",
        "Helvetica Neue",
    ):
        if name in families:
            return name
    return "Segoe UI"

# ---------------------------------------------------------------------------
# Restic Manager compatibility helpers
# ---------------------------------------------------------------------------

# Map legacy QDarkStyle theme ids → new AppTheme ids.
LEGACY_THEME_MAP: dict[str, str] = {
    "light": "paper",
    "light-green": "mist",
    "light-blue": "snow",
    "dark": "slate",
    "dark-cyan": "ocean",
    "dark-navy": "midnight",
    "dark-green": "aurora",
    "dark-purple": "midnight",
    "dark-indigo": "midnight",
    "dark-magenta": "mocha",
    "solarized-dark": "ocean",
    "monokai-dark": "classic",
    "dracula": "midnight",
    "nord-dark": "nord",
    "tokyo-night": "midnight",
    "catppuccin-mocha": "mocha",
    "gruvbox-dark": "ember",
    "one-dark": "graphite",
    "rose-pine": "mocha",
    "everforest": "aurora",
    "kanagawa": "graphite",
    "night-owl": "midnight",
    "palenight": "midnight",
    "arctic": "nord",
    "horizon": "ember",
    "moonlight": "midnight",
    "github-dark": "graphite",
    "vscode-dark": "slate",
    "material-dark": "graphite",
    "cyberpunk-neon": "ember",
    "matrix-green": "classic",
    "sunset-orange": "linen",
    "forest-moss": "aurora",
    "cool-grey": "graphite",
    "pure-black": "classic",
    "midnight-blue": "midnight",
    "amoled-black": "classic",
}


def resolve_theme_id(theme: str | None) -> str:
    """Resolve a stored theme name/id to a known AppTheme id."""
    if not theme:
        return DEFAULT_APP_THEME_ID
    key = str(theme).strip()
    # Combo may store display names ("Slate") — match by name.
    for tid, t in APP_THEMES.items():
        if tid == key or t.name == key:
            return tid
    return LEGACY_THEME_MAP.get(key, DEFAULT_APP_THEME_ID)


def theme_display_names() -> list[str]:
    """Ordered theme names for the Settings combo box."""
    # Dark first, then light — mirrors SSH client grouping.
    dark = [t.name for t in APP_THEMES.values() if _hex_luminance(t.bg) <= 0.55]
    light = [t.name for t in APP_THEMES.values() if _hex_luminance(t.bg) > 0.55]
    return dark + light


def apply_theme(app, settings_manager, theme: str, window=None) -> str:
    """
    Apply an AppTheme stylesheet to the QApplication (and optional main window).
    Returns the resolved theme id that was applied.
    """
    theme_id = resolve_theme_id(theme)
    settings_manager.set("theme", theme_id)
    css = build_stylesheet(get_app_theme(theme_id))
    app.setStyleSheet(css)
    if window is not None:
        window.setStyleSheet(css)
    return theme_id


def theme_splash_colors_for(theme: str) -> tuple[str, str]:
    """Return (bg, text) splash colors for a theme id/name."""
    t = get_app_theme(resolve_theme_id(theme))
    return t.bg, t.text


# Back-compat aliases used by restic_manager splash / chart code.
theme_splash_colors = {tid: t.bg for tid, t in APP_THEMES.items()}
theme_text_colors = {
    tid: t.text
    for tid, t in APP_THEMES.items()
    if _hex_luminance(t.bg) > 0.55
}


def get_chart_colors(theme: str):
    """Matplotlib chart colors derived from the active AppTheme."""
    t = get_app_theme(resolve_theme_id(theme))
    is_light = _hex_luminance(t.bg) > 0.55
    return {
        "bg_color": t.bg,
        "text_color": t.text,
        "grid_color": t.border,
        "is_light": is_light,
        "accent": t.accent,
        "ok": t.ok,
        "danger": t.danger,
        "surface": t.surface,
        "muted": t.muted,
    }


STYLESHEET_SCROLL = ""  # Scrollbars are included in build_stylesheet().
