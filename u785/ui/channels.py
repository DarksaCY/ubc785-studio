"""Channel memory table: model, filter proxy, editors and the view."""
import copy

from PyQt5.QtCore import (QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt,
                          pyqtSignal)
from PyQt5.QtGui import QColor, QKeySequence, QBrush
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QComboBox, QHeaderView,
                             QLineEdit, QStyledItemDelegate, QTableView)

from .. import tones
from ..i18n import _
from ..model import (Channel, MODULATIONS, blank_memory, format_mhz, parse_freq, validate_freq,
                     radio_text)
from ..csvio import parse_csv_text
from . import theme

COLS = ["#", _("BANK"), _("FREQ, MHz"), _("MOD"), _("TAG"), _("TONE"), "DLY", "L/O", "ATT", "REC"]
C_NUM, C_BANK, C_FREQ, C_MOD, C_TAG, C_TONE, C_DLY, C_LO, C_ATT, C_REC = range(10)
BOOL_COLS = {C_DLY: "delay", C_LO: "lockout", C_ATT: "atten", C_REC: "record"}


class ChannelModel(QAbstractTableModel):
    error = pyqtSignal(str)
    dirty_changed = pyqtSignal(int)

    def __init__(self):
        super().__init__()
        self.channels = blank_memory()
        self.device = blank_memory()     # last state known to be in the radio

    # --- Qt model API ----------------------------------------------------
    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.channels)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(COLS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return COLS[section]
        if orientation == Qt.Horizontal and role == Qt.TextAlignmentRole:
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        return None

    def flags(self, index):
        f = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        c = index.column()
        if c in BOOL_COLS:
            return f | Qt.ItemIsUserCheckable
        if c in (C_FREQ, C_MOD, C_TAG, C_TONE):
            return f | Qt.ItemIsEditable
        return f

    def data(self, index, role=Qt.DisplayRole):
        ch = self.channels[index.row()]
        c = index.column()
        if role == Qt.DisplayRole:
            if c == C_NUM:
                return f"{ch.number:03d}"
            if c == C_BANK:
                return ch.bank
            if ch.empty and c not in (C_FREQ,):
                return ""
            if c == C_FREQ:
                return format_mhz(ch.freq_hz, "—")
            if c == C_MOD:
                return ch.mod
            if c == C_TAG:
                return ch.tag
            if c == C_TONE:
                return "" if ch.tone == 0 else tones.label(ch.tone)
        if role == Qt.EditRole:
            return {C_FREQ: format_mhz(ch.freq_hz), C_MOD: ch.mod, C_TAG: ch.tag,
                    C_TONE: tones.label(ch.tone)}.get(c)
        if role == Qt.CheckStateRole and c in BOOL_COLS and not ch.empty:
            return Qt.Checked if getattr(ch, BOOL_COLS[c]) else Qt.Unchecked
        if role == Qt.ForegroundRole:
            if ch.dirty and c in (C_NUM, C_FREQ):
                return QBrush(QColor(theme.AMBER))
            if c in (C_NUM, C_BANK) or ch.empty:
                return QBrush(QColor(theme.FAINT))
            if c == C_FREQ:
                return QBrush(QColor(theme.TEXT))
            if c == C_MOD:
                return QBrush(QColor(theme.CYAN))
            if c == C_TONE:
                return QBrush(QColor(theme.GREEN))
            if ch.lockout:
                return QBrush(QColor(theme.DIM))
        if role == Qt.BackgroundRole and ch.dirty:
            return QBrush(QColor(255, 179, 71, 22))
        if role == Qt.FontRole and c == C_FREQ and not ch.empty:
            return theme.mono(10.5, bold=True)
        if role == Qt.ToolTipRole:
            if c == C_TAG and ch.tag and radio_text(ch.tag).rstrip() != ch.tag[:16]:
                return _("On the scanner display: “{text}”", text=radio_text(ch.tag).rstrip())
            if ch.dirty:
                return _("Modified — not yet written to the scanner")
        if role == Qt.TextAlignmentRole:
            # PyQt5 needs a plain int here; returning Qt.Alignment crashes the view.
            if c == C_FREQ:
                return int(Qt.AlignRight | Qt.AlignVCenter)
            return int(Qt.AlignLeft | Qt.AlignVCenter)
        return None

    def setData(self, index, value, role=Qt.EditRole):
        ch = self.channels[index.row()]
        c = index.column()
        try:
            if role == Qt.CheckStateRole and c in BOOL_COLS:
                if ch.empty:
                    return False
                setattr(ch, BOOL_COLS[c], value == Qt.Checked)
            elif role == Qt.EditRole and c == C_FREQ:
                hz = parse_freq(value)
                err = validate_freq(hz)
                if err:
                    raise ValueError(err)
                was_empty = ch.empty
                ch.freq_hz = hz
                if hz == 0:
                    ch.clear()
                elif was_empty:
                    ch.lockout = False
                    ch.delay = True
            elif role == Qt.EditRole and c == C_MOD:
                if value not in MODULATIONS:
                    raise ValueError(_("Unknown modulation {value}", value=repr(value)))
                ch.mod = value
            elif role == Qt.EditRole and c == C_TAG:
                ch.tag = str(value).strip()
            elif role == Qt.EditRole and c == C_TONE:
                ch.tone = tones.parse(value)
            else:
                return False
        except ValueError as e:
            self.error.emit(str(e))
            return False
        self._touch(index.row())
        return True

    # --- bulk operations -------------------------------------------------
    def _touch(self, row: int):
        ch = self.channels[row]
        ch.dirty = ch.content() != self.device[row].content()
        self.dataChanged.emit(self.index(row, 0), self.index(row, len(COLS) - 1))
        self.dirty_changed.emit(self.dirty_count())

    def dirty_count(self) -> int:
        return sum(1 for ch in self.channels if ch.dirty)

    def dirty_channels(self) -> list[Channel]:
        return [copy.copy(ch) for ch in self.channels if ch.dirty]

    def from_device(self, ch: Channel):
        """A channel was read from / confirmed by the radio."""
        row = ch.number - 1
        self.device[row] = copy.copy(ch)
        self.device[row].dirty = False
        self.channels[row] = copy.copy(self.device[row])
        self.dataChanged.emit(self.index(row, 0), self.index(row, len(COLS) - 1))
        self.dirty_changed.emit(self.dirty_count())

    def put(self, number: int, src: Channel):
        row = number - 1
        self.channels[row].copy_from(src)
        self._touch(row)

    def clear_rows(self, rows: list[int]):
        for r in rows:
            self.channels[r].clear()
            self._touch(r)

    def revert(self):
        for r, ch in enumerate(self.channels):
            if ch.dirty:
                self.channels[r] = copy.copy(self.device[r])
        self.dataChanged.emit(self.index(0, 0), self.index(len(self.channels) - 1, len(COLS) - 1))
        self.dirty_changed.emit(self.dirty_count())

    def free_numbers(self, numbers) -> list[int]:
        return [n for n in numbers if self.channels[n - 1].empty]


class ChannelFilter(QSortFilterProxyModel):
    def __init__(self):
        super().__init__()
        self.bank = ""
        self.text = ""
        self.hide_empty = False

    def set(self, bank=None, text=None, hide_empty=None):
        if bank is not None:
            self.bank = bank
        if text is not None:
            self.text = text.strip().lower()
        if hide_empty is not None:
            self.hide_empty = hide_empty
        self.invalidateFilter()

    def filterAcceptsRow(self, row, parent):
        ch = self.sourceModel().channels[row]
        if self.bank and ch.bank != self.bank:
            return False
        if self.hide_empty and ch.empty and not ch.dirty:
            return False
        if self.text:
            hay = f"{ch.number:03d} {format_mhz(ch.freq_hz)} {ch.tag} {ch.mod}".lower()
            return all(part in hay for part in self.text.split())
        return True


class ComboDelegate(QStyledItemDelegate):
    def __init__(self, items, parent=None):
        super().__init__(parent)
        self.items = items

    def createEditor(self, parent, option, index):
        cb = QComboBox(parent)
        cb.addItems(self.items)
        cb.setMaxVisibleItems(20)
        return cb

    def setEditorData(self, editor, index):
        i = editor.findText(index.data(Qt.EditRole) or "")
        editor.setCurrentIndex(max(i, 0))
        editor.showPopup()

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText())


class TextDelegate(QStyledItemDelegate):
    def __init__(self, placeholder="", max_len=None, parent=None):
        super().__init__(parent)
        self.placeholder = placeholder
        self.max_len = max_len

    def createEditor(self, parent, option, index):
        e = QLineEdit(parent)
        e.setPlaceholderText(self.placeholder)
        if self.max_len:
            e.setMaxLength(self.max_len)
        return e


class ChannelView(QTableView):
    goto = pyqtSignal(int)
    status = pyqtSignal(str)

    def __init__(self, model: ChannelModel, proxy: ChannelFilter):
        super().__init__()
        self.src = model
        self.proxy = proxy
        self.setModel(proxy)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
                             | QAbstractItemView.AnyKeyPressed)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(28)
        h = self.horizontalHeader()
        h.setHighlightSections(False)
        widths = [52, 58, 140, 78, 0, 120, 48, 48, 48, 48]
        for i, w in enumerate(widths):
            if w:
                self.setColumnWidth(i, w)
        h.setSectionResizeMode(C_TAG, QHeaderView.Stretch)
        # Delegates need a Qt parent, otherwise Python garbage-collects them under the view.
        self.setItemDelegateForColumn(C_FREQ, TextDelegate("145.500 / 145500k", parent=self))
        self.setItemDelegateForColumn(C_TAG, TextDelegate(_("tag (16 chars)"), 32, parent=self))
        self.setItemDelegateForColumn(C_MOD, ComboDelegate(MODULATIONS, parent=self))
        self.setItemDelegateForColumn(C_TONE, ComboDelegate(tones.ALL_LABELS, parent=self))
        self.doubleClicked.connect(self._double)

    def selected_rows(self) -> list[int]:
        rows = {self.proxy.mapToSource(i).row() for i in self.selectionModel().selectedRows()}
        return sorted(rows)

    def _double(self, index):
        if index.column() in (C_NUM, C_BANK):
            self.goto.emit(self.proxy.mapToSource(index).row() + 1)

    def keyPressEvent(self, e):
        if e.matches(QKeySequence.Copy):
            self.copy_rows()
        elif e.matches(QKeySequence.Paste):
            self.paste_rows()
        elif e.key() in (Qt.Key_Delete, Qt.Key_Backspace) and self.state() != QAbstractItemView.EditingState:
            rows = self.selected_rows()
            self.src.clear_rows(rows)
            self.status.emit(_("Cleared {n} channel(s) (remember to write)", n=len(rows)))
        else:
            super().keyPressEvent(e)

    def copy_rows(self):
        lines = ["channel\tfrequency_mhz\tmodulation\ttag\ttone\tdelay\tlockout\tattenuator\trecord"]
        for r in self.selected_rows():
            ch = self.src.channels[r]
            lines.append("\t".join([str(ch.number), format_mhz(ch.freq_hz), ch.mod, ch.tag,
                                    tones.label(ch.tone), str(int(ch.delay)), str(int(ch.lockout)),
                                    str(int(ch.atten)), str(int(ch.record))]))
        QApplication.clipboard().setText("\n".join(lines))
        self.status.emit(_("Copied {n} channel(s)", n=len(lines) - 1))

    def paste_rows(self):
        text = QApplication.clipboard().text()
        if not text.strip():
            return
        items, warnings = parse_csv_text(text)
        rows = self.selected_rows()
        start = rows[0] + 1 if rows else 1
        n = start
        for ch in items:
            if n > len(self.src.channels):
                break
            self.src.put(n, ch)
            n += 1
        msg = _("Pasted {n} channel(s) starting at {start:03d}", n=n - start, start=start)
        if warnings:
            msg += _(" — {n} warning(s)", n=len(warnings))
        self.status.emit(msg)
