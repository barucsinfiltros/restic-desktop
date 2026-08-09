"""Icon helpers for the modern UI shell."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

import ui.themes as themes


def icon_file(name: str) -> Path:
    path = Path(themes.icon_path(name))
    if path.is_file():
        return path
    return Path(themes.icons_dir()) / name


def tinted_icon(name: str, color: str, size: int = 18) -> QIcon:
    """Load an SVG and recolor non-transparent pixels to ``color``."""
    path = icon_file(name)
    if not path.is_file():
        return QIcon()

    renderer = QSvgRenderer(str(path))
    pm = QPixmap(size, size)
    pm.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pm)
    renderer.render(painter)
    painter.end()

    tint = QColor(color)
    img = pm.toImage()
    for y in range(img.height()):
        for x in range(img.width()):
            pixel = img.pixelColor(x, y)
            if pixel.alpha() == 0:
                continue
            tint.setAlpha(pixel.alpha())
            img.setPixelColor(x, y, tint)
    return QIcon(QPixmap.fromImage(img))


def icon(name: str, size: int = 18) -> QIcon:
    path = icon_file(name)
    if not path.is_file():
        return QIcon()
    ic = QIcon(str(path))
    # Ensure a usable size for toolbars / buttons.
    _ = ic.pixmap(QSize(size, size))
    return ic
