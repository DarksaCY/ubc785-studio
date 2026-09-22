"""Custom-painted radio widgets: LCD mirror, signal meter, frequency entry."""
from PyQt5.QtCore import QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen, QFontMetricsF
from PyQt5.QtWidgets import QLabel, QLineEdit, QVBoxLayout, QWidget

from ..i18n import _
from ..model import parse_freq, validate_freq, format_mhz
from . import theme


class LcdDisplay(QWidget):
    """Mirror of the scanner's 4x16 character display."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows = ["", "", "", ""]
        self.online = False
        self.setMinimumHeight(150)

    def set_rows(self, rows: list[str]):
        self.rows = [(r or "")[:16].ljust(16) for r in rows[:4]] + [""] * (4 - len(rows[:4]))
        self.update()

    def set_online(self, online: bool):
        self.online = online
        if not online:
            self.rows = ["", "", "", ""]
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        p.setPen(QPen(QColor("#3a2a10" if self.online else theme.BORDER), 1))
        p.setBrush(QColor(theme.LCD_BG if self.online else theme.PANEL2))
        p.drawRoundedRect(r, 8, 8)

        inner = r.adjusted(14, 10, -14, -10)
        line_h = inner.height() / 4
        font = theme.mono(10)
        # Fit 16 characters to the width, but never exceed the row height.
        font.setPointSizeF(10)
        fm = QFontMetricsF(font)
        scale = min(inner.width() / fm.horizontalAdvance("W" * 16), line_h * 0.72 / fm.height())
        font.setPointSizeF(max(6.0, 10 * scale))
        p.setFont(font)
        fm = QFontMetricsF(font)
        cell = fm.horizontalAdvance("W")
        x0 = inner.left() + (inner.width() - cell * 16) / 2

        ghost = QColor(theme.AMBER)
        ghost.setAlpha(12)
        lit = QColor(theme.AMBER)
        for i in range(4):
            top = inner.top() + line_h * i
            # faint character cells, like an unlit dot-matrix LCD
            p.setPen(Qt.NoPen)
            p.setBrush(ghost)
            for k in range(16):
                p.drawRoundedRect(QRectF(x0 + k * cell + 1, top + line_h * 0.12,
                                         cell - 2, line_h * 0.76), 1.5, 1.5)
            if self.online:
                p.setPen(lit)
                for k, chr_ in enumerate(self.rows[i]):
                    p.drawText(QRectF(x0 + k * cell, top, cell, line_h), Qt.AlignCenter, chr_)
        if not self.online:
            p.setPen(QColor(theme.FAINT))
            p.setFont(theme.mono(9))
            p.drawText(r, Qt.AlignCenter, _("NO LINK TO SCANNER"))


class SignalMeter(QWidget):
    """Six-bar S-meter (matching the radio) with the raw 0-255 level underneath."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.level = 0
        self.bars = 0
        self.squelch = False
        self.setMinimumHeight(38)

    def set_signal(self, level: int, bars: int, squelch: bool):
        self.level, self.bars, self.squelch = level, bars, squelch
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        n, gap = 6, 5
        label_w = 70
        bar_w = (w - label_w - gap * (n - 1)) / n
        for i in range(n):
            x = i * (bar_w + gap)
            bh = h * (0.35 + 0.65 * (i + 1) / n)
            on = i < self.bars
            color = QColor(theme.AMBER if on else theme.RAISED)
            if on and i >= 4:
                color = QColor("#ff8a3d")
            p.setPen(Qt.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QRectF(x, h - bh, bar_w, bh), 2, 2)
        p.setFont(theme.mono(9))
        p.setPen(QColor(theme.GREEN if self.squelch else theme.FAINT))
        tx = w - label_w + 10
        p.drawText(QRectF(tx, 0, label_w - 10, h / 2), Qt.AlignLeft | Qt.AlignVCenter,
                   _("● OPEN") if self.squelch else _("○ CLOSED"))
        p.setPen(QColor(theme.DIM))
        p.drawText(QRectF(tx, h / 2, label_w - 10, h / 2), Qt.AlignLeft | Qt.AlignVCenter,
                   f"S {self.level:3d}")


class FreqEntry(QWidget):
    """Big frequency field that understands many notations and previews the result."""

    submitted = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        self.edit = QLineEdit()
        self.edit.setObjectName("freqEntry")
        self.edit.setPlaceholderText("145.500")
        self.edit.setToolTip(_("Formats: 145.5  145,500  145.500.000  145500k  145.5 MHz  1.2975G"))
        self.hint = QLabel(" ")
        self.hint.setObjectName("dim")
        lay.addWidget(self.edit)
        lay.addWidget(self.hint)
        self.edit.textChanged.connect(self._preview)
        self.edit.returnPressed.connect(self._submit)

    def value(self) -> int | None:
        try:
            hz = parse_freq(self.edit.text())
        except ValueError:
            return None
        return hz if hz and not validate_freq(hz) else None

    def set_value(self, hz: int):
        self.edit.setText(format_mhz(hz))

    def _preview(self, text):
        if not text.strip():
            self.hint.setText(" ")
            return
        try:
            hz = parse_freq(text)
            err = validate_freq(hz)
            if err:
                self._hint(err, theme.RED)
            else:
                self._hint(_("= {f} MHz   ⏎ tune", f=format_mhz(hz)), theme.DIM)
        except ValueError as e:
            self._hint(str(e), theme.RED)

    def _hint(self, text, color):
        self.hint.setText(text)
        self.hint.setStyleSheet(f"color: {color};")

    def _submit(self):
        hz = self.value()
        if hz:
            self.submitted.emit(hz)
