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
    # themes.py lives in ui/ — icons/ is at the project root
    return Path(__file__).resolve().parent.parent / "icons"


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
        ok="#0f6e37",
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
        ok="#146b3c",
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
        ok="#0f6b3a",
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
        ok="#1f6b40",
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
        ok="#166534",
    ),
    # --- 2026 modern additions ---
    "obsidian": AppTheme(
        id="obsidian",
        name="Obsidian",
        bg="#050505",
        sidebar="#0e0e10",
        surface="#141416",
        border="#26262c",
        text="#ececf1",
        muted="#8b8b96",
        accent="#22d3ee",
        accent_hover="#67e8f9",
        accent_soft="rgba(34, 211, 238, 0.16)",
        danger="#fb7185",
        ok="#34d399",
    ),
    "nebula": AppTheme(
        id="nebula",
        name="Nebula",
        bg="#0a0612",
        sidebar="#140c1f",
        surface="#1a1228",
        border="#2e2142",
        text="#efe6ff",
        muted="#a894c4",
        accent="#d946ef",
        accent_hover="#e879f9",
        accent_soft="rgba(217, 70, 239, 0.18)",
        danger="#fb7185",
        ok="#4ade80",
    ),
    "porcelain": AppTheme(
        id="porcelain",
        name="Porcelain",
        bg="#f4f5f8",
        sidebar="#e9ebf1",
        surface="#ffffff",
        border="#d0d4de",
        text="#141820",
        muted="#5c6575",
        accent="#4f46e5",
        accent_hover="#6366f1",
        accent_soft="rgba(79, 70, 229, 0.12)",
        danger="#dc2626",
        ok="#0f6e37",
    ),
    "bloom": AppTheme(
        id="bloom",
        name="Bloom",
        bg="#faf6f4",
        sidebar="#f1e9e5",
        surface="#fffbfa",
        border="#e2d5cf",
        text="#2a1f1c",
        muted="#7a6862",
        accent="#e11d48",
        accent_hover="#fb7185",
        accent_soft="rgba(225, 29, 72, 0.12)",
        danger="#b91c1c",
        ok="#166534",
    ),
    # High-contrast OLED black
    "void": AppTheme(
        id="void",
        name="Void",
        bg="#000000",
        sidebar="#0a0a0a",
        surface="#111111",
        border="#2a2a2a",
        text="#f5f5f5",
        muted="#a0a0a0",
        accent="#e8e8e8",
        accent_hover="#ffffff",
        accent_soft="rgba(255, 255, 255, 0.12)",
        danger="#ff5c5c",
        ok="#3dd68c",
    ),
    # Deep purple / violet accent
    "iris": AppTheme(
        id="iris",
        name="Iris",
        bg="#0c0a14",
        sidebar="#161222",
        surface="#1c1830",
        border="#322a4a",
        text="#ece8ff",
        muted="#9b93b8",
        accent="#8b5cf6",
        accent_hover="#a78bfa",
        accent_soft="rgba(139, 92, 246, 0.20)",
        danger="#f472b6",
        ok="#4ade80",
    ),
    # Warmer cream / parchment
    "cream": AppTheme(
        id="cream",
        name="Cream",
        bg="#f6efe4",
        sidebar="#ebe2d4",
        surface="#fbf7f0",
        border="#d9cdb8",
        text="#2c2418",
        muted="#7a6c58",
        accent="#b45309",
        accent_hover="#d97706",
        accent_soft="rgba(180, 83, 9, 0.14)",
        danger="#b91c1c",
        ok="#166534",
    ),
    # Cool high-contrast office white
    "office": AppTheme(
        id="office",
        name="Office",
        bg="#ffffff",
        sidebar="#f0f2f5",
        surface="#ffffff",
        border="#c8cdd5",
        text="#0a0a0a",
        muted="#4b5563",
        accent="#0052cc",
        accent_hover="#1a66e0",
        accent_soft="rgba(0, 82, 204, 0.10)",
        danger="#c62828",
        ok="#0f6e37",
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
    "obsidian": _term(
        "obsidian", "Obsidian",
        QColor(8, 8, 10), QColor(236, 236, 241), QColor(34, 211, 238, 150),
    ),
    "nebula": _term(
        "nebula", "Nebula",
        QColor(12, 8, 22), QColor(239, 230, 255), QColor(217, 70, 239, 150),
    ),
    "porcelain": _term(
        "porcelain", "Porcelain",
        QColor(255, 255, 255), QColor(20, 24, 32), QColor(79, 70, 229, 140),
        light=True,
    ),
    "bloom": _term(
        "bloom", "Bloom",
        QColor(255, 251, 250), QColor(42, 31, 28), QColor(225, 29, 72, 140),
        light=True,
    ),
    "void": _term(
        "void", "Void",
        QColor(0, 0, 0), QColor(245, 245, 245), QColor(232, 232, 232, 160),
    ),
    "iris": _term(
        "iris", "Iris",
        QColor(12, 10, 20), QColor(236, 232, 255), QColor(139, 92, 246, 150),
    ),
    "cream": _term(
        "cream", "Cream",
        QColor(251, 247, 240), QColor(44, 36, 24), QColor(180, 83, 9, 140),
        light=True,
    ),
    "office": _term(
        "office", "Office",
        QColor(255, 255, 255), QColor(10, 10, 10), QColor(0, 82, 204, 140),
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


def combo_selection_colors(theme: AppTheme) -> tuple[str, str]:
    """
    Background + text for QComboBox popup selection.

    Dark themes: darkened accent + white text (readable on Classic / Nord /
    Aurora / Obsidian / Void and similar).
    Light themes: keep the normal accent highlight.
    """
    t = theme
    light_ui = _hex_luminance(t.bg) > 0.55
    accent_l = _hex_luminance(t.accent)
    if light_ui:
        return t.accent, ("#111827" if accent_l > 0.55 else "#ffffff")

    # Pull accent toward black so pale accents (Nord, Void, Obsidian cyan) stay dark.
    ratio = 0.55 if accent_l > 0.45 else 0.38
    bg = _mix_hex(t.accent, "#000000", ratio)
    # Keep a floor so selection still reads as accent-tinted, not pure black.
    if _hex_luminance(bg) < 0.12:
        bg = _mix_hex(t.accent, t.surface, 0.35)
    return bg, "#ffffff"


def _make_combo_popup_delegate(theme: AppTheme, parent=None):
    """Owner-draw combo rows so Windows cannot paint a light system highlight."""
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QColor
    from PyQt6.QtWidgets import QStyle, QStyledItemDelegate, QStyleOptionViewItem

    sel_bg, sel_fg = combo_selection_colors(theme)

    class _ComboPopupDelegate(QStyledItemDelegate):
        def paint(self, painter, option, index):  # noqa: N802
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)

            flags = index.flags()
            # Separators are not selectable
            if not (flags & Qt.ItemFlag.ItemIsSelectable):
                super().paint(painter, option, index)
                return

            selected = bool(opt.state & QStyle.StateFlag.State_Selected)
            hovered = bool(opt.state & QStyle.StateFlag.State_MouseOver)

            painter.save()
            if selected:
                painter.fillRect(opt.rect, QColor(sel_bg))
                pen = QColor(sel_fg)
            elif hovered:
                hover_bg = _mix_hex(theme.surface, theme.accent, 0.28)
                painter.fillRect(opt.rect, QColor(hover_bg))
                pen = QColor(theme.text)
            else:
                painter.fillRect(opt.rect, QColor(theme.surface))
                pen = QColor(theme.text)

            text = index.data(Qt.ItemDataRole.DisplayRole)
            if text is None:
                text = ""
            painter.setPen(pen)
            painter.drawText(
                opt.rect.adjusted(8, 0, -8, 0),
                int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
                str(text),
            )
            painter.restore()

        def sizeHint(self, option, index):  # noqa: N802
            hint = super().sizeHint(option, index)
            if hint.height() < 24:
                hint.setHeight(24)
            return hint

    return _ComboPopupDelegate(parent)


def apply_combo_popup_palette(combo, theme: AppTheme) -> None:
    """Force readable popup selection via owner-drawn delegate (+ palette backup)."""
    from PyQt6.QtGui import QColor, QPalette
    from PyQt6.QtWidgets import QComboBox, QListView

    if not isinstance(combo, QComboBox):
        return

    bg, fg = combo_selection_colors(theme)
    base = QColor(theme.surface)
    text = QColor(theme.text)
    highlight = QColor(bg)
    highlighted = QColor(fg)

    def _paint(pal: QPalette) -> QPalette:
        for group in (
            QPalette.ColorGroup.Active,
            QPalette.ColorGroup.Inactive,
            QPalette.ColorGroup.Disabled,
        ):
            pal.setColor(group, QPalette.ColorRole.Base, base)
            pal.setColor(group, QPalette.ColorRole.Window, base)
            pal.setColor(group, QPalette.ColorRole.Text, text)
            pal.setColor(group, QPalette.ColorRole.WindowText, text)
            pal.setColor(group, QPalette.ColorRole.Button, base)
            pal.setColor(group, QPalette.ColorRole.ButtonText, text)
            pal.setColor(group, QPalette.ColorRole.Highlight, highlight)
            pal.setColor(group, QPalette.ColorRole.HighlightedText, highlighted)
            pal.setColor(group, QPalette.ColorRole.AlternateBase, base)
            pal.setColor(group, QPalette.ColorRole.BrightText, highlighted)
        return pal

    combo.setPalette(_paint(combo.palette()))
    delegate = _make_combo_popup_delegate(theme, combo)
    combo.setItemDelegate(delegate)
    combo.setProperty("_resticComboThemeId", theme.id)

    view = combo.view()
    if view is not None:
        view.setAutoFillBackground(True)
        view.setPalette(_paint(view.palette()))
        view.setItemDelegate(delegate)
        # Background chrome only — selection is painted by the delegate.
        view.setStyleSheet(
            f"""
            QAbstractItemView, QListView {{
                background-color: {theme.surface};
                color: {theme.text};
                border: 1px solid {theme.border};
                outline: none;
                padding: 2px;
            }}
            """
        )
        if isinstance(view, QListView):
            view.setUniformItemSizes(True)


def polish_combo_popups(root, theme: AppTheme | None = None) -> None:
    """Apply readable combo popup colors under ``root`` (window or dialog)."""
    from PyQt6.QtWidgets import QApplication, QComboBox

    t = theme
    if t is None:
        app = QApplication.instance()
        tid = ""
        if app is not None:
            tid = str(app.property("resticThemeId") or "")
        t = get_app_theme(resolve_theme_id(tid or DEFAULT_APP_THEME_ID))

    combos: list = []
    if isinstance(root, QComboBox):
        combos.append(root)
    if root is not None and hasattr(root, "findChildren"):
        combos.extend(root.findChildren(QComboBox))
    seen = set()
    for combo in combos:
        cid = id(combo)
        if cid in seen:
            continue
        seen.add(cid)
        apply_combo_popup_palette(combo, t)


def build_stylesheet(theme: AppTheme) -> str:
    t = theme
    light = _hex_luminance(t.bg) > 0.55
    hover = "rgba(0, 0, 0, 0.06)" if light else "rgba(255, 255, 255, 0.07)"
    hover_strong = "rgba(0, 0, 0, 0.10)" if light else "rgba(255, 255, 255, 0.10)"
    combo_sel_bg, combo_sel_fg = combo_selection_colors(t)
    # Theme-tinted lifts (not flat grey) for translucent header / shell feel.
    header_wash = t.accent_soft
    shell_bg = _mix_hex(t.surface, t.bg, 0.35)
    # Soft jobs-row selection (accent_soft was far too loud).
    jobs_sel = soft_hex_rgba(t.accent, 0.10) if not light else soft_hex_rgba(t.accent, 0.08)
    jobs_header_wash = _mix_hex(shell_bg, t.surface, 0.55)
    jobs_header_wash = _mix_hex(jobs_header_wash, t.accent, 0.04)
    jobs_header_text = _mix_hex(t.muted, t.bg, 0.25)
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

        /* Logs find bar */
        #logsFindBar {{
            background: transparent;
            border: none;
        }}
        QLineEdit#logsFindEdit {{
            min-height: 28px;
            max-height: 32px;
        }}
        #logsFindCount {{
            color: {t.muted};
            font-size: 11px;
            background: transparent;
            border: none;
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
        QRadioButton {{
            color: {t.text};
            spacing: 8px;
            background: transparent;
        }}
        QRadioButton::indicator {{
            width: 14px;
            height: 14px;
            border-radius: 8px;
            border: 1px solid {t.border};
            background-color: {t.surface};
        }}
        QRadioButton::indicator:hover {{
            border-color: {t.accent};
        }}
        QRadioButton::indicator:checked {{
            background-color: {t.accent};
            border-color: {t.accent};
        }}
        QRadioButton:disabled {{
            color: {t.muted};
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
            selection-background-color: {combo_sel_bg};
            selection-color: {combo_sel_fg};
            padding: 4px;
        }}
        QComboBox QListView {{
            background-color: {t.surface};
            color: {t.text};
            outline: none;
            selection-background-color: {combo_sel_bg};
            selection-color: {combo_sel_fg};
        }}
        QComboBox QAbstractItemView::item {{
            color: {t.text};
            background-color: transparent;
            padding: 4px 8px;
            min-height: 22px;
        }}
        QComboBox QAbstractItemView::item:selected,
        QComboBox QListView::item:selected {{
            background-color: {combo_sel_bg};
            color: {combo_sel_fg};
        }}
        QComboBox QAbstractItemView::item:hover,
        QComboBox QListView::item:hover {{
            background-color: {t.accent_soft};
            color: {t.text};
        }}
        QComboBox QAbstractItemView::item:selected:hover,
        QComboBox QListView::item:selected:hover {{
            background-color: {combo_sel_bg};
            color: {combo_sel_fg};
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
        QDateEdit, QDateTimeEdit {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 6px;
            color: {t.text};
            padding: 4px 26px 4px 8px;
            min-height: 18px;
            selection-background-color: {t.accent};
        }}
        QDateEdit:focus, QDateTimeEdit:focus {{
            border-color: {t.accent};
        }}
        QDateEdit::drop-down, QDateTimeEdit::drop-down {{
            subcontrol-origin: border;
            subcontrol-position: center right;
            width: 22px;
            border: none;
            border-left: 1px solid {t.border};
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
            background-color: {t.surface};
        }}
        QDateEdit::drop-down:hover, QDateTimeEdit::drop-down:hover {{
            background-color: {t.accent_soft};
        }}
        QDateEdit::down-arrow, QDateTimeEdit::down-arrow {{
            image: url({_icon_url("combo_down.svg")});
            width: 10px;
            height: 6px;
        }}
        QDateEdit::down-arrow:hover, QDateTimeEdit::down-arrow:hover {{
            image: url({_icon_url("combo_down_hover.svg")});
        }}
        QCalendarWidget {{
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 8px;
        }}
        QCalendarWidget QWidget {{
            alternate-background-color: {shell_bg};
        }}
        QCalendarWidget QToolButton {{
            background-color: transparent;
            color: {t.text};
            border: none;
            border-radius: 6px;
            padding: 4px 8px;
            font-weight: 600;
        }}
        QCalendarWidget QToolButton:hover {{
            background-color: {hover};
        }}
        QCalendarWidget QMenu {{
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
        }}
        QCalendarWidget QSpinBox {{
            background-color: {t.surface};
            color: {t.text};
            border: 1px solid {t.border};
            border-radius: 4px;
        }}
        QCalendarWidget QAbstractItemView:enabled {{
            background-color: {t.surface};
            color: {t.text};
            selection-background-color: {t.accent};
            selection-color: #ffffff;
            outline: none;
        }}
        QCalendarWidget QAbstractItemView:enabled:hover {{
            background-color: {hover};
        }}
        QCalendarWidget QWidget#qt_calendar_navigationbar {{
            background-color: {jobs_header_wash};
            border-top-left-radius: 8px;
            border-top-right-radius: 8px;
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
        QLabel#mutedLabel {{
            color: {t.muted};
            font-size: 12px;
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
        #settingsDialog, #notesDialog, #hostDialog, #dualSftpDialog, #systemLogDialog, #workspacesDialog, #backupJobDialog {{
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
        #backupJobFooter {{
            background-color: {t.surface};
            border-top: 1px solid {t.border};
        }}
        QListWidget#backupJobList {{
            background-color: {t.bg};
            border: 1px solid {t.border};
            border-radius: 8px;
            padding: 4px;
            outline: none;
        }}
        QListWidget#backupJobList::item {{
            padding: 6px 8px;
            border-radius: 4px;
        }}
        QListWidget#backupJobList::item:selected {{
            background-color: {t.accent_soft};
            color: {t.text};
        }}
        #backupJobContent #pageSubtitle {{
            color: {t.muted};
            font-size: 12px;
            font-style: italic;
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
            selection-background-color: {combo_sel_bg};
            selection-color: {combo_sel_fg};
        }}
        #systemLogDialog QComboBox QAbstractItemView::item:selected {{
            background-color: {combo_sel_bg};
            color: {combo_sel_fg};
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

        /* Restic Desktop — modern nav + dashboard cards */
        #navSidebar {{
            background-color: {t.sidebar};
            border-right: 1px solid {t.border};
        }}
        #navHeaderRow {{
            background: transparent;
            border: none;
        }}
        #navLogo {{
            background: transparent;
            border: none;
        }}
        #navBrand {{
            color: {t.text};
            font-size: 15px;
            font-weight: 700;
            letter-spacing: 0.2px;
            padding: 2px 0 0 0;
        }}
        #navVersion {{
            color: {t.muted};
            font-size: 11px;
            padding: 2px 0 0 0;
        }}
        #navFooter {{
            color: {t.muted};
            font-size: 11px;
            padding: 0;
            line-height: 1.35;
        }}
        #navBrandIcon {{
            background-color: {t.accent_soft};
            border: 1px solid {t.border};
            border-radius: 10px;
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
            font-size: 15px;
            font-weight: 500;
            min-height: 38px;
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
        #contentArea, #dashboardPage, #repositoriesPage, #snapshotsPage {{
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
            padding: 2px 2px 4px 2px;
            font-size: 12px;
            font-weight: 600;
            min-height: 22px;
        }}
        QPushButton#linkBtn:hover {{
            color: {t.accent_hover};
            background-color: transparent;
            border: none;
        }}
        QPushButton#dangerLinkBtn {{
            background-color: transparent;
            color: {t.danger};
            border: none;
            padding: 2px 2px 4px 2px;
            font-size: 12px;
            font-weight: 600;
            min-height: 22px;
        }}
        QPushButton#dangerLinkBtn:hover {{
            color: {t.text};
            background-color: transparent;
            border: none;
        }}
        QPushButton#dangerBtn {{
            background-color: transparent;
            color: {t.danger};
            border: 1px solid {t.danger};
            padding: 3px 12px;
            border-radius: 5px;
            font-size: 12px;
            font-weight: 600;
            min-width: 72px;
            min-height: 22px;
        }}
        QPushButton#dangerBtn:hover {{
            background-color: {t.danger};
            color: #eef3f8;
            border-color: {t.danger};
        }}
        #repoActions, #snapshotActions, #jobActions {{
            background: transparent;
            border: none;
        }}
        #repoStatusCell {{
            background: transparent;
            border: none;
        }}
        #repoStatusLabel {{
            background: transparent;
            border: none;
            padding-bottom: 1px;
        }}
        #repoStatusDot {{
            border: none;
        }}
        #repoNameCell, #repoBadgesCell, #repoIconCell {{
            background: transparent;
            border: none;
        }}
        #repoNameLabel {{
            color: {t.text};
            background: transparent;
            border: none;
            font-size: 12px;
        }}
        #repoSwatch {{
            border: none;
            border-radius: 3px;
        }}
        #repoIconChip {{
            border: none;
            border-radius: 8px;
        }}
        #repoBadge {{
            background: transparent;
            border: none;
        }}
        #statCard {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 14px;
        }}
        #statCardIcon {{
            background-color: {t.accent_soft};
            border: none;
            border-radius: 14px;
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
        #jobsTableShell, #repoTableShell, #snapshotsTableShell, #backupJobsTableShell, #restoreSearchTableShell {{
            background-color: {shell_bg};
            border: 1px solid {t.border};
            border-radius: 10px;
        }}
        QTableWidget#jobsTable, QTableWidget#repoTable, QTableWidget#snapshotsTable, QTableWidget#backupJobsTable, QTableWidget#restoreSearchTable {{
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
        QTableWidget#jobsTable, QTableWidget#repoTable, QTableWidget#snapshotsTable, QTableWidget#backupJobsTable, QTableWidget#restoreSearchTable {{
            selection-background-color: {jobs_sel};
            selection-color: {t.muted};
        }}
        QTableWidget#jobsTable::item, QTableWidget#repoTable::item, QTableWidget#snapshotsTable::item, QTableWidget#backupJobsTable::item, QTableWidget#restoreSearchTable::item {{
            background-color: transparent;
            border: none;
            border-bottom: 1px solid {t.border};
            text-align: left;
            /* Fusion paints text in a tight rect; keep bottom padding >= top so descenders aren't clipped */
            padding: 4px 8px 10px 4px;
        }}
        QTableWidget#jobsTable::item:selected, QTableWidget#repoTable::item:selected, QTableWidget#snapshotsTable::item:selected, QTableWidget#backupJobsTable::item:selected, QTableWidget#restoreSearchTable::item:selected {{
            background-color: {jobs_sel};
            border-bottom: 1px solid {t.border};
        }}
        QTableWidget#jobsTable QHeaderView, QTableWidget#repoTable QHeaderView, QTableWidget#snapshotsTable QHeaderView, QTableWidget#backupJobsTable QHeaderView, QTableWidget#restoreSearchTable QHeaderView {{
            background-color: transparent;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
        }}
        QTableWidget#jobsTable QHeaderView::section,
        QTableWidget#repoTable QHeaderView::section,
        QTableWidget#snapshotsTable QHeaderView::section,
        QTableWidget#backupJobsTable QHeaderView::section,
        QTableWidget#restoreSearchTable QHeaderView::section {{
            background-color: {jobs_header_wash};
            color: {jobs_header_text};
            border: none;
            border-bottom: 1px solid {t.border};
            border-right: none;
            padding: 10px 8px 10px 8px;
            font-size: 12px;
            font-weight: 600;
            text-align: left;
        }}
        QTableWidget#jobsTable QHeaderView::section:hover,
        QTableWidget#repoTable QHeaderView::section:hover,
        QTableWidget#snapshotsTable QHeaderView::section:hover,
        QTableWidget#backupJobsTable QHeaderView::section:hover,
        QTableWidget#restoreSearchTable QHeaderView::section:hover {{
            color: {t.text};
            background-color: {hover};
        }}
        QTableWidget#jobsTable QHeaderView::section:first,
        QTableWidget#repoTable QHeaderView::section:first,
        QTableWidget#snapshotsTable QHeaderView::section:first,
        QTableWidget#backupJobsTable QHeaderView::section:first,
        QTableWidget#restoreSearchTable QHeaderView::section:first {{
            border-top-left-radius: 10px;
        }}
        QTableWidget#jobsTable QHeaderView::section:last,
        QTableWidget#repoTable QHeaderView::section:last,
        QTableWidget#snapshotsTable QHeaderView::section:last,
        QTableWidget#backupJobsTable QHeaderView::section:last,
        QTableWidget#restoreSearchTable QHeaderView::section:last {{
            border-top-right-radius: 10px;
        }}
        QTableWidget#jobsTable QTableCornerButton::section,
        QTableWidget#repoTable QTableCornerButton::section,
        QTableWidget#snapshotsTable QTableCornerButton::section,
        QTableWidget#backupJobsTable QTableCornerButton::section,
        QTableWidget#restoreSearchTable QTableCornerButton::section {{
            background-color: {jobs_header_wash};
            border: none;
            border-top-left-radius: 10px;
        }}
        QWidget#repoIconCell, QWidget#snapshotIdCell, QWidget#snapshotSizeCell {{
            background: transparent;
            margin: 0;
            padding: 0;
        }}
        QTableWidget#jobsTable QLabel#repoNameLabel,
        QTableWidget#repoTable QLabel#repoNameLabel,
        QTableWidget#snapshotsTable QLabel#repoNameLabel,
        QTableWidget#backupJobsTable QLabel#repoNameLabel {{
            background: transparent;
            padding: 0;
            margin: 0;
        }}
        QTableWidget#snapshotsTable QLabel#snapshotSizeLabel {{
            background: transparent;
            padding: 0;
            margin: 0;
            font-size: 12px;
        }}
        QPushButton#iconMenuBtn {{
            background: transparent;
            border: none;
            border-radius: 6px;
            padding: 4px;
            min-width: 28px;
            min-height: 28px;
        }}
        QPushButton#iconMenuBtn:hover {{
            background-color: {hover};
        }}
        QPushButton#iconMenuBtn:pressed {{
            background-color: {hover_strong};
        }}
        QTextEdit#snapshotDetails {{
            background-color: transparent;
            border: none;
            border-radius: 0;
            color: {t.text};
            padding: 0;
            font-size: 12px;
            min-height: 0px;
            max-height: 16777215px;
        }}
        QPlainTextEdit#restoreLog {{
            background-color: transparent;
            border: none;
            border-radius: 0;
            color: {t.text};
            padding: 0;
            font-size: 12px;
            font-family: Consolas, "Courier New", monospace;
        }}
        #restoreFormLabel {{
            color: {t.muted};
            font-size: 12px;
            font-weight: 600;
            background: transparent;
            border: none;
        }}
        #retentionFormLabel {{
            color: {t.muted};
            font-size: 12px;
            font-weight: 600;
            background: transparent;
            border: none;
        }}
        #restoreDestStrip {{
            background-color: {shell_bg};
            border: 1px solid {t.border};
            border-radius: 10px;
        }}
        #retentionKeepCell {{
            background-color: {shell_bg};
            border: 1px solid {t.border};
            border-radius: 10px;
        }}
        #retentionKeepField {{
            background: transparent;
            border: none;
        }}
        #retentionKeepLabel {{
            color: {t.muted};
            font-size: 12px;
            font-weight: 600;
            background: transparent;
            border: none;
        }}
        #retentionScroll, #retentionScrollContent {{
            background: transparent;
            border: none;
        }}
        #settingsScroll, #settingsScrollContent {{
            background: transparent;
            border: none;
        }}
        #settingsFormLabel {{
            color: {t.muted};
            font-size: 12px;
            font-weight: 600;
            background: transparent;
            border: none;
        }}
        #settingsFormRow {{
            background: transparent;
            border: none;
        }}
        #settingsHint {{
            color: {t.muted};
            font-size: 11px;
            background: transparent;
            border: none;
        }}
        #settingsNote {{
            color: {t.muted};
            font-size: 11px;
            padding: 10px 12px;
            background-color: {t.accent_soft};
            border: 1px solid {t.border};
            border-radius: 8px;
        }}
        #settingsStatusStrip {{
            background-color: {shell_bg};
            border: 1px solid {t.border};
            border-radius: 10px;
        }}
        #settingsStatusOk {{
            color: {t.ok};
            font-size: 12px;
            font-weight: 600;
            background: transparent;
            border: none;
        }}
        #settingsStatusWarn {{
            color: #e8b84a;
            font-size: 12px;
            font-weight: 600;
            background: transparent;
            border: none;
        }}
        #settingsStatusErr {{
            color: {t.danger};
            font-size: 12px;
            font-weight: 600;
            background: transparent;
            border: none;
        }}
        #settingsStatusMuted {{
            color: {t.muted};
            font-size: 12px;
            background: transparent;
            border: none;
        }}
        #settingsMachineId {{
            font-family: Consolas, "Courier New", monospace;
            font-size: 11px;
        }}
        #settingsAbout {{
            color: {t.muted};
            font-size: 12px;
            background: transparent;
            border: none;
            padding: 8px;
        }}
        QPlainTextEdit#retentionLog, QPlainTextEdit#backupProgressLog, QPlainTextEdit#appLog {{
            background-color: transparent;
            border: none;
            border-radius: 0;
            color: {t.text};
            padding: 0;
            font-size: 12px;
            font-family: Consolas, "Courier New", monospace;
        }}
        QTimeEdit#retentionTimeEdit {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 6px;
            color: {t.text};
            padding: 4px 26px 4px 8px;
            min-height: 18px;
            max-height: 26px;
            min-width: 120px;
            selection-background-color: {t.accent};
        }}
        QTimeEdit#retentionTimeEdit::up-button,
        QTimeEdit#retentionTimeEdit::down-button {{
            subcontrol-origin: border;
            width: 22px;
            height: 13px;
            border: none;
            border-left: 1px solid {t.border};
            background-color: {t.surface};
        }}
        QTimeEdit#retentionTimeEdit::up-button {{
            subcontrol-position: top right;
            border-top-right-radius: 6px;
        }}
        QTimeEdit#retentionTimeEdit::down-button {{
            subcontrol-position: bottom right;
            border-bottom-right-radius: 6px;
        }}
        QTimeEdit#retentionTimeEdit::up-arrow {{
            image: url({_icon_url("spin_up.svg")});
            width: 10px;
            height: 6px;
        }}
        QTimeEdit#retentionTimeEdit::down-arrow {{
            image: url({_icon_url("spin_down.svg")});
            width: 10px;
            height: 6px;
        }}
        QSpinBox#retentionKeepSpin {{
            max-height: 26px;
            min-height: 18px;
        }}
        #retentionInfoLabel {{
            color: {t.muted};
            font-size: 11px;
            background: transparent;
            border: none;
            padding-top: 4px;
        }}
        #browseMetaStrip {{
            background-color: {shell_bg};
            border: 1px solid {t.border};
            border-radius: 10px;
        }}
        #backupProgressLogShell {{
            background-color: {shell_bg};
            border: 1px solid {t.border};
            border-radius: 10px;
        }}
        #retentionStatusStrip {{
            background-color: {shell_bg};
            border: 1px solid {t.border};
            border-radius: 10px;
        }}
        #retentionStatusStrip QLabel#browseMetaValue[retentionScheduled="true"] {{
            color: {t.ok};
            font-weight: 600;
        }}
        #snapshotSummaryStrip {{
            background-color: {shell_bg};
            border: 1px solid {t.border};
            border-radius: 10px;
        }}
        #snapshotSummaryLabel {{
            color: {t.muted};
            font-size: 11px;
            font-weight: 600;
        }}
        #snapshotSummaryValue {{
            color: {t.text};
            font-size: 14px;
            font-weight: 600;
        }}
        #snapshotSummaryDivider {{
            background-color: {t.border};
            border: none;
            max-width: 1px;
        }}
        #browseMetaLabel {{
            color: {t.muted};
            font-size: 11px;
            font-weight: 600;
        }}
        #browseMetaValue {{
            color: {t.text};
            font-size: 13px;
        }}
        QTreeWidget#browseFileTree {{
            background-color: transparent;
            border: none;
            border-radius: 0;
            color: {t.text};
            outline: none;
            alternate-background-color: transparent;
            show-decoration-selected: 1;
            selection-background-color: {jobs_sel};
            selection-color: {t.muted};
        }}
        QTreeWidget#browseFileTree::item {{
            background-color: transparent;
            padding: 6px 8px 6px 4px;
            border: none;
            border-bottom: 1px solid {t.border};
            min-height: 28px;
        }}
        QTreeWidget#browseFileTree::item:selected {{
            background-color: {jobs_sel};
            color: {t.muted};
            border-bottom: 1px solid {t.border};
        }}
        QTreeWidget#browseFileTree::item:hover {{
            background-color: {hover};
        }}
        QTreeWidget#browseFileTree QHeaderView {{
            background-color: transparent;
            border-top-left-radius: 10px;
            border-top-right-radius: 10px;
        }}
        QTreeWidget#browseFileTree QHeaderView::section {{
            background-color: {jobs_header_wash};
            color: {jobs_header_text};
            border: none;
            border-bottom: 1px solid {t.border};
            border-right: none;
            padding: 10px 8px;
            font-size: 12px;
            font-weight: 600;
            text-align: left;
        }}
        QTreeWidget#browseFileTree QHeaderView::section:hover {{
            color: {t.text};
            background-color: {hover};
        }}
        QTreeWidget#browseFileTree QHeaderView::section:first {{
            border-top-left-radius: 10px;
        }}
        QTreeWidget#browseFileTree QHeaderView::section:last {{
            border-top-right-radius: 10px;
        }}
        QTreeWidget#browseFileTree QTableCornerButton::section {{
            background-color: {jobs_header_wash};
            border: none;
            border-top-left-radius: 10px;
        }}
        #browseFileTreeShell {{
            background-color: {shell_bg};
            border: 1px solid {t.border};
            border-radius: 10px;
        }}
        QLineEdit#browseSearch {{
            background-color: {shell_bg};
            border: 1px solid {t.border};
            border-radius: 8px;
            padding: 6px 10px;
            color: {t.text};
        }}
        QLineEdit#browseSearch:focus {{
            border-color: {t.accent};
        }}
        QPlainTextEdit#diffOutput {{
            background-color: {shell_bg};
            border: 1px solid {t.border};
            border-radius: 8px;
            color: {t.text};
            padding: 10px;
            font-size: 12px;
        }}
        #diffStatAdded {{
            color: #3dd68c;
            font-size: 12px;
            font-weight: 600;
        }}
        #diffStatModified {{
            color: #e8b84a;
            font-size: 12px;
            font-weight: 600;
        }}
        #diffStatRemoved {{
            color: {t.danger};
            font-size: 12px;
            font-weight: 600;
        }}
        #copyNote {{
            color: #e8b84a;
            font-size: 12px;
            padding-top: 4px;
        }}
        /* Title lives inside the frame — Fusion clips border-straddling titles. */
        QGroupBox {{
            background-color: {t.surface};
            border: 1px solid {t.border};
            border-radius: 10px;
            margin-top: 8px;
            padding-top: 18px;
            padding-left: 10px;
            padding-right: 10px;
            padding-bottom: 14px;
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
# Restic Desktop compatibility helpers
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
    """Ordered theme names for the Settings combo box (dark, then light)."""
    dark, light = theme_name_groups()
    return dark + light


def theme_name_groups() -> tuple[list[str], list[str]]:
    """Return (dark_names, light_names) for combo population."""
    dark = [t.name for t in APP_THEMES.values() if _hex_luminance(t.bg) <= 0.55]
    light = [t.name for t in APP_THEMES.values() if _hex_luminance(t.bg) > 0.55]
    return dark, light


def populate_theme_combo(combo) -> None:
    """Fill a QComboBox with dark themes, a separator, then light themes."""
    from PyQt6.QtWidgets import QComboBox

    if not isinstance(combo, QComboBox):
        return
    dark, light = theme_name_groups()
    combo.clear()
    combo.addItems(dark)
    if dark and light:
        combo.insertSeparator(combo.count())
    combo.addItems(light)


def apply_theme(app, settings_manager, theme: str, window=None) -> str:
    """
    Apply an AppTheme stylesheet to the QApplication (and optional main window).
    Returns the resolved theme id that was applied.
    """
    theme_id = resolve_theme_id(theme)
    settings_manager.set("theme", theme_id)
    app_theme = get_app_theme(theme_id)
    css = build_stylesheet(app_theme)
    app.setStyleSheet(css)
    try:
        app.setProperty("resticThemeId", theme_id)
    except Exception:
        pass
    if window is not None:
        window.setStyleSheet(css)
        polish_combo_popups(window, app_theme)
    # Dialogs / other top-levels created earlier
    try:
        for top in app.topLevelWidgets():
            polish_combo_popups(top, app_theme)
    except Exception:
        pass
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
    """Dashboard chart chrome colours derived from the active AppTheme."""
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


# Fixed palette for repository identity (Grafana-style; not user-configurable).
REPO_COLOR_PALETTE: tuple[str, ...] = (
    "#3b82f6",  # blue
    "#f97316",  # orange
    "#ef4444",  # red
    "#06b6d4",  # cyan
    "#22c55e",  # green
    "#a855f7",  # purple
    "#eab308",  # yellow
    "#ec4899",  # pink
    "#14b8a6",  # teal
    "#8b5cf6",  # violet
    "#f59e0b",  # amber
    "#64748b",  # slate
)


def soft_hex_rgba(hex_color: str, alpha: float = 0.18) -> str:
    """Return an rgba() stylesheet color from a hex accent."""
    c = _parse_hex_color(hex_color) or QColor("#3b82f6")
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha:.2f})"


def _normalize_repo_hex(value: str | None) -> str | None:
    c = _parse_hex_color(value or "")
    if c is None:
        return None
    return f"#{c.red():02x}{c.green():02x}{c.blue():02x}"


def _palette_index_for_name(name: str) -> int:
    import hashlib

    digest = hashlib.md5((name or "").encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % len(REPO_COLOR_PALETTE)


def ensure_repo_colors(repositories: list | None) -> bool:
    """Assign missing ``color`` values on repository dicts. Returns True if changed."""
    if not repositories:
        return False

    used: set[str] = set()
    for repo in repositories:
        if not isinstance(repo, dict):
            continue
        existing = _normalize_repo_hex(repo.get("color"))
        if existing:
            used.add(existing.lower())

    changed = False
    for repo in repositories:
        if not isinstance(repo, dict):
            continue
        existing = _normalize_repo_hex(repo.get("color"))
        if existing:
            if repo.get("color") != existing:
                repo["color"] = existing
                changed = True
            continue

        name = str(repo.get("name") or "")
        start = _palette_index_for_name(name)
        chosen = None
        for offset in range(len(REPO_COLOR_PALETTE)):
            candidate = REPO_COLOR_PALETTE[(start + offset) % len(REPO_COLOR_PALETTE)]
            if candidate.lower() not in used:
                chosen = candidate
                break
        if chosen is None:
            chosen = REPO_COLOR_PALETTE[start]
        repo["color"] = chosen
        used.add(chosen.lower())
        changed = True
    return changed


def repo_color_for_name(name: str, repositories: list | None = None) -> str:
    """Return the stored colour for a repository name, or a stable palette fallback."""
    key = (name or "").strip()
    if repositories:
        for repo in repositories:
            if not isinstance(repo, dict):
                continue
            if (repo.get("name") or "").strip() == key:
                stored = _normalize_repo_hex(repo.get("color"))
                if stored:
                    return stored
                break
    return REPO_COLOR_PALETTE[_palette_index_for_name(key)]


STYLESHEET_SCROLL = ""  # Scrollbars are included in build_stylesheet().
