"""Modern QPainter chart widgets for the dashboard."""
from __future__ import annotations

import math
from typing import Sequence

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontMetrics,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QStackedLayout,
    QVBoxLayout,
    QWidget,
)


def _qcolor(value: str, fallback: str = "#3b82f6") -> QColor:
    c = QColor(value or "")
    return c if c.isValid() else QColor(fallback)


def _lighten(color: QColor, amount: float = 0.28) -> QColor:
    amount = max(0.0, min(1.0, amount))
    return QColor(
        int(color.red() + (255 - color.red()) * amount),
        int(color.green() + (255 - color.green()) * amount),
        int(color.blue() + (255 - color.blue()) * amount),
        color.alpha(),
    )


def _darken(color: QColor, amount: float = 0.22) -> QColor:
    amount = max(0.0, min(1.0, amount))
    return QColor(
        int(color.red() * (1.0 - amount)),
        int(color.green() * (1.0 - amount)),
        int(color.blue() * (1.0 - amount)),
        color.alpha(),
    )


class _DonutRing(QWidget):
    """Painted doughnut ring with centre total label."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setMinimumSize(160, 160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._sizes: list[float] = []
        self._colors: list[QColor] = []
        self._total_label = "—"
        self._total_caption = "Total"
        self._bg = QColor("#1a222c")
        self._text = QColor("#e8eef5")
        self._muted = QColor("#8b95a5")
        self._empty_message = "No data available"

    def set_theme(self, *, bg: str, text: str, muted: str, grid: str = "") -> None:
        self._bg = _qcolor(bg, "#1a222c")
        self._text = _qcolor(text, "#e8eef5")
        self._muted = _qcolor(muted, "#8b95a5")
        self.update()

    def set_data(
        self,
        sizes: Sequence[float],
        colors: Sequence[str],
        *,
        total_label: str,
        total_caption: str = "Total",
        empty_message: str = "No data available",
    ) -> None:
        self._sizes = [max(0.0, float(s)) for s in sizes]
        self._colors = [_qcolor(c) for c in colors]
        while len(self._colors) < len(self._sizes):
            self._colors.append(QColor("#3b82f6"))
        self._total_label = total_label or "—"
        self._total_caption = total_caption
        self._empty_message = empty_message
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillRect(self.rect(), self._bg)

        total = sum(self._sizes)
        side = min(self.width(), self.height()) - 8
        cx = self.width() / 2.0
        cy = self.height() / 2.0
        outer = QRectF(cx - side / 2, cy - side / 2, side, side)
        ring_width = side * 0.22
        inner = QRectF(outer).adjusted(ring_width, ring_width, -ring_width, -ring_width)

        if total <= 0:
            painter.setPen(self._muted)
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._empty_message)
            painter.end()
            return

        start_deg = 90.0  # top
        # Tiny overlap kills anti-alias hairline seams; no visible borders/gaps.
        overlap = 0.45
        for size, color in zip(self._sizes, self._colors):
            if size <= 0:
                continue
            span = (size / total) * 360.0
            draw_span = span + overlap
            path = QPainterPath()
            path.arcMoveTo(outer, start_deg)
            path.arcTo(outer, start_deg, -draw_span)
            end_deg = start_deg - draw_span
            path.arcTo(inner, end_deg, draw_span)
            path.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.fillPath(path, color)

            pct = size / total * 100.0
            if pct >= 5.5 and span > 14.0:
                mid = start_deg - span / 2.0
                rad = math.radians(mid)
                r = (side / 2.0) - ring_width / 2.0
                lx = cx + math.cos(rad) * r
                ly = cy - math.sin(rad) * r
                painter.setPen(QColor(255, 255, 255, 230))
                font = painter.font()
                font.setPointSize(8)
                font.setBold(True)
                painter.setFont(font)
                label = f"{pct:.1f}%"
                br = painter.fontMetrics().boundingRect(label)
                painter.drawText(
                    int(lx - br.width() / 2),
                    int(ly + br.height() / 3),
                    label,
                )
                painter.setPen(Qt.PenStyle.NoPen)

            start_deg -= span

        # Centre labels
        painter.setPen(self._text)
        title_font = QFont(painter.font())
        title_font.setPointSize(14)
        title_font.setBold(True)
        painter.setFont(title_font)
        title_br = painter.fontMetrics().boundingRect(self._total_label)
        painter.drawText(
            int(cx - title_br.width() / 2),
            int(cy - 2),
            self._total_label,
        )
        painter.setPen(self._muted)
        cap_font = QFont(painter.font())
        cap_font.setPointSize(9)
        cap_font.setBold(False)
        painter.setFont(cap_font)
        cap_br = painter.fontMetrics().boundingRect(self._total_caption)
        painter.drawText(
            int(cx - cap_br.width() / 2),
            int(cy + title_br.height() - 2),
            self._total_caption,
        )
        painter.end()


class _DonutLegend(QWidget):
    """Colour-dot legend: full name (wrap) + size, tooltip for full text."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("donutLegend")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(2, 4, 2, 4)
        self._root.setSpacing(6)
        self._root.addStretch(1)
        self._text = "#e8eef5"
        self._muted = "#8b95a5"

    def set_theme(self, *, text: str, muted: str) -> None:
        self._text = text
        self._muted = muted
        for i in range(self._root.count()):
            item = self._root.itemAt(i)
            w = item.widget() if item else None
            if w is None:
                continue
            name = w.findChild(QLabel, "donutLegendName")
            size = w.findChild(QLabel, "donutLegendSize")
            if name is not None:
                name.setStyleSheet(
                    f"color: {self._text}; background: transparent; border: none; font-size: 11px;"
                )
            if size is not None:
                size.setStyleSheet(
                    f"color: {self._muted}; background: transparent; border: none; font-size: 11px;"
                )

    def set_items(self, names: Sequence[str], sizes: Sequence[str], colors: Sequence[str]) -> None:
        while self._root.count():
            item = self._root.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        for name, size_text, color in zip(names, sizes, colors):
            row = QWidget(self)
            row.setObjectName("donutLegendRow")
            row.setToolTip(f"{name} — {size_text}")
            hl = QHBoxLayout(row)
            hl.setContentsMargins(0, 0, 0, 0)
            hl.setSpacing(8)
            hl.setAlignment(Qt.AlignmentFlag.AlignTop)

            dot = QLabel(row)
            dot.setFixedSize(10, 10)
            dot.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
            dot.setStyleSheet(
                f"background-color: {color}; border: none; border-radius: 5px;"
            )
            hl.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)

            text_col = QVBoxLayout()
            text_col.setContentsMargins(0, 0, 0, 0)
            text_col.setSpacing(1)

            name_lbl = QLabel(name, row)
            name_lbl.setObjectName("donutLegendName")
            name_lbl.setWordWrap(True)
            name_lbl.setToolTip(name)
            name_lbl.setStyleSheet(
                f"color: {self._text}; background: transparent; border: none; font-size: 11px;"
            )
            text_col.addWidget(name_lbl)

            size_lbl = QLabel(size_text, row)
            size_lbl.setObjectName("donutLegendSize")
            size_lbl.setStyleSheet(
                f"color: {self._muted}; background: transparent; border: none; font-size: 11px;"
            )
            text_col.addWidget(size_lbl)

            hl.addLayout(text_col, stretch=1)
            self._root.addWidget(row)

        self._root.addStretch(1)


class DonutChart(QFrame):
    """Doughnut + side legend panel."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("donutChart")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._stack = QStackedLayout(self)
        self._stack.setContentsMargins(0, 0, 0, 0)

        # Empty state — full-width centred message (avoids clipping beside the legend)
        self._empty = QLabel('Click "Refresh Dashboard" to load data', self)
        self._empty.setObjectName("donutChartEmpty")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty.setWordWrap(True)
        self._empty.setMinimumHeight(240)
        self._stack.addWidget(self._empty)

        data = QWidget(self)
        data.setObjectName("donutChartData")
        row = QHBoxLayout(data)
        row.setContentsMargins(4, 4, 8, 4)
        row.setSpacing(10)

        self._ring = _DonutRing(data)
        row.addWidget(self._ring, stretch=5)

        self._legend = _DonutLegend(data)
        self._legend.setMinimumWidth(160)
        row.addWidget(self._legend, stretch=4)
        self._stack.addWidget(data)

        self._stack.setCurrentIndex(0)
        self._bg = "#1a222c"
        self._muted = "#8b95a5"
        self._apply_empty_style()

    def _apply_empty_style(self) -> None:
        self._empty.setStyleSheet(
            f"QLabel#donutChartEmpty {{"
            f"  color: {self._muted};"
            f"  background: {self._bg};"
            f"  border: none;"
            f"  font-size: 10pt;"
            f"  padding: 24px;"
            f"}}"
        )

    def set_theme(self, *, bg: str, text: str, muted: str, grid: str = "") -> None:
        self._bg = bg
        self._muted = muted
        self.setStyleSheet(f"QFrame#donutChart {{ background: {bg}; border: none; }}")
        self._apply_empty_style()
        self._ring.set_theme(bg=bg, text=text, muted=muted, grid=grid)
        self._legend.set_theme(text=text, muted=muted)

    def set_data(
        self,
        names: Sequence[str],
        sizes: Sequence[float],
        colors: Sequence[str],
        *,
        total_label: str,
        size_labels: Sequence[str] | None = None,
        empty_message: str = "No data available",
    ) -> None:
        has_data = sum(float(s) for s in sizes) > 0
        if not has_data:
            self._empty.setText(empty_message)
            self._stack.setCurrentIndex(0)
            self._ring.set_data([], [], total_label="—", empty_message=empty_message)
            self._legend.set_items([], [], [])
            return

        self._stack.setCurrentIndex(1)
        self._ring.set_data(
            sizes,
            colors,
            total_label=total_label,
            empty_message=empty_message,
        )
        labels = list(size_labels) if size_labels is not None else [""] * len(names)
        self._legend.set_items(names, labels, colors)
        self.update()

    def clear(self, message: str = 'Click "Refresh Dashboard" to load data') -> None:
        self.set_data([], [], [], total_label="—", empty_message=message)


class RoundedBarChart(QWidget):
    """Vertical bars with rounded tops; names via bottom legend + hover tooltip."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("roundedBarChart")
        self.setMinimumHeight(240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMouseTracking(True)
        self._names: list[str] = []
        self._values: list[float] = []
        self._colors: list[QColor] = []
        self._bar_rects: list[QRectF] = []
        self._bg = QColor("#1a222c")
        self._text = QColor("#e8eef5")
        self._muted = QColor("#8b95a5")
        self._grid = QColor("#2a3544")
        self._empty_message = "No snapshots found"
        self._y_label = "Snapshot Count"
        self._hover_index = -1

    def set_theme(self, *, bg: str, text: str, muted: str, grid: str = "") -> None:
        self._bg = _qcolor(bg, "#1a222c")
        self._text = _qcolor(text, "#e8eef5")
        self._muted = _qcolor(muted, "#8b95a5")
        self._grid = _qcolor(grid or muted, "#2a3544")
        self.update()

    def set_data(
        self,
        names: Sequence[str],
        values: Sequence[float],
        colors: Sequence[str],
        *,
        empty_message: str = "No snapshots found",
        y_label: str = "Snapshot Count",
    ) -> None:
        self._names = list(names)
        self._values = [max(0.0, float(v)) for v in values]
        self._colors = [_qcolor(c) for c in colors]
        while len(self._colors) < len(self._values):
            self._colors.append(QColor("#22c55e"))
        self._empty_message = empty_message
        self._y_label = y_label
        self._hover_index = -1
        self.setToolTip("")
        self.update()

    def clear(self, message: str = "Click Refresh Dashboard to load data") -> None:
        self.set_data([], [], [], empty_message=message)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        pos = event.position()
        hit = -1
        for i, rect in enumerate(self._bar_rects):
            # Generous hit area above/below bar for easier hover
            hit_rect = QRectF(rect.left() - 2, 0, rect.width() + 4, self.height())
            if hit_rect.contains(pos):
                hit = i
                break
        if hit != self._hover_index:
            self._hover_index = hit
            if 0 <= hit < len(self._names):
                self.setToolTip(f"{self._names[hit]}: {int(self._values[hit])} snapshots")
            else:
                self.setToolTip("")
            self.update()
        super().mouseMoveEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        if self._hover_index >= 0:
            self._hover_index = -1
            self.setToolTip("")
            self.update()
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.fillRect(self.rect(), self._bg)

        left = 44
        right = 12
        top = 18
        # Reserve room for wrapping colour legend (not truncated axis text)
        legend_h = 56 if self._names else 8
        bottom = legend_h + 8
        plot = QRectF(
            left,
            top,
            max(1.0, self.width() - left - right),
            max(1.0, self.height() - top - bottom),
        )

        self._bar_rects = []

        if not self._values or sum(self._values) <= 0:
            painter.setPen(self._muted)
            font = painter.font()
            font.setPointSize(10)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._empty_message)
            painter.end()
            return

        max_v = max(self._values) or 1.0
        if max_v <= 5:
            y_max = max(1.0, math.ceil(max_v))
        else:
            y_max = math.ceil(max_v * 1.15)

        tick_font = painter.font()
        tick_font.setPointSize(8)
        painter.setFont(tick_font)
        ticks = 4
        for i in range(ticks + 1):
            t = i / ticks
            y = plot.bottom() - t * plot.height()
            painter.setPen(QPen(self._grid, 1, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            val = int(round(y_max * t))
            painter.setPen(self._muted)
            label = str(val)
            br = painter.fontMetrics().boundingRect(label)
            painter.drawText(
                int(plot.left() - br.width() - 8),
                int(y + br.height() / 3),
                label,
            )

        painter.save()
        painter.setPen(self._muted)
        yf = painter.font()
        yf.setPointSize(9)
        painter.setFont(yf)
        painter.translate(14, plot.center().y())
        painter.rotate(-90)
        br = painter.fontMetrics().boundingRect(self._y_label)
        painter.drawText(int(-br.width() / 2), 0, self._y_label)
        painter.restore()

        n = len(self._values)
        gap = plot.width() * 0.04
        bar_w = (plot.width() - gap * (n + 1)) / max(1, n)
        bar_w = max(10.0, min(bar_w, 48.0))
        total_bars = n * bar_w + (n + 1) * gap
        x0 = plot.left() + max(0.0, (plot.width() - total_bars) / 2) + gap
        radius = min(10.0, bar_w * 0.35)

        for i, (name, value, color) in enumerate(
            zip(self._names, self._values, self._colors)
        ):
            h = (value / y_max) * plot.height() if y_max else 0.0
            x = x0 + i * (bar_w + gap)
            y = plot.bottom() - h
            rect = QRectF(x, y, bar_w, max(h, 0.0))
            self._bar_rects.append(rect)

            path = QPainterPath()
            path.moveTo(rect.left(), rect.bottom())
            path.lineTo(rect.left(), rect.top() + radius)
            path.quadTo(rect.left(), rect.top(), rect.left() + radius, rect.top())
            path.lineTo(rect.right() - radius, rect.top())
            path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + radius)
            path.lineTo(rect.right(), rect.bottom())
            path.closeSubpath()

            fill = color
            if i == self._hover_index:
                fill = _lighten(color, 0.12)
            grad = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            grad.setColorAt(0.0, _lighten(fill, 0.35))
            grad.setColorAt(1.0, _darken(fill, 0.18))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.fillPath(path, grad)

            if value > 0:
                painter.setPen(self._text)
                vf = painter.font()
                vf.setPointSize(8)
                vf.setBold(True)
                painter.setFont(vf)
                label = str(int(value))
                br = painter.fontMetrics().boundingRect(label)
                painter.drawText(
                    int(rect.center().x() - br.width() / 2),
                    int(rect.top() - 4),
                    label,
                )

        # Bottom colour legend — full names, wrap across rows; no ellipsis axis text
        self._paint_legend(painter, QRectF(left, plot.bottom() + 10, plot.width(), legend_h - 4))
        painter.end()

    def _paint_legend(self, painter: QPainter, area: QRectF) -> None:
        if not self._names:
            return
        painter.setPen(self._muted)
        font = painter.font()
        font.setPointSize(9)
        font.setBold(False)
        painter.setFont(font)
        fm = QFontMetrics(font)
        x = area.left()
        y = area.top()
        row_h = fm.height() + 6
        for name, color in zip(self._names, self._colors):
            text_w = fm.horizontalAdvance(name)
            need = 12 + 6 + text_w + 14
            if x + need > area.right() and x > area.left():
                x = area.left()
                y += row_h
            if y + row_h > area.bottom() + 4:
                # Overflow: remaining names still available via bar hover tooltip
                break
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawEllipse(QPointF(x + 5, y + row_h / 2 - 1), 4, 4)
            painter.setPen(self._muted)
            painter.drawText(int(x + 14), int(y + fm.ascent() + 2), name)
            x += need
