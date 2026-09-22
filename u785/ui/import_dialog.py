"""CSV import dialog: preview, choose placement, show warnings."""
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout,
                             QLabel, QPlainTextEdit, QRadioButton, QSpinBox, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QCheckBox, QHeaderView)

from .. import tones
from ..i18n import _
from ..model import BANKS, CHANNELS, Channel, bank_range, format_mhz


class ImportDialog(QDialog):
    def __init__(self, path: str, items: list[Channel], warnings: list[str], model, parent=None):
        super().__init__(parent)
        self.items = items
        self.model = model
        self.setWindowTitle(_("Import CSV"))
        self.resize(820, 620)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)

        has_numbers = any(ch.number for ch in items)
        found = _("Frequencies found: {n}", n=len(items))
        if has_numbers:
            found += _(" · file has channel numbers")
        title = QLabel(f"<b>{path}</b><br><span style='color:#7a8494'>{found}</span>")
        lay.addWidget(title)

        preview = QTableWidget(min(len(items), 200), 5)
        preview.setHorizontalHeaderLabels(["#", _("FREQUENCY"), _("MOD"), _("TAG"), _("TONE")])
        preview.verticalHeader().hide()
        preview.setEditTriggers(QTableWidget.NoEditTriggers)
        preview.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        for r, ch in enumerate(items[:200]):
            for c, v in enumerate([f"{ch.number:03d}" if ch.number else "—", format_mhz(ch.freq_hz),
                                   ch.mod, ch.tag, "" if not ch.tone else tones.label(ch.tone)]):
                preview.setItem(r, c, QTableWidgetItem(v))
        lay.addWidget(preview, 1)

        lay.addWidget(QLabel(_("Place into:")))
        self.group = QButtonGroup(self)
        self.r_numbers = QRadioButton(_("By channel numbers from the file"))
        self.r_start = QRadioButton(_("Sequentially, starting at channel"))
        self.r_bank = QRadioButton(_("Into free channels of bank"))
        for i, rb in enumerate((self.r_numbers, self.r_start, self.r_bank)):
            self.group.addButton(rb, i)
        self.r_numbers.setEnabled(has_numbers)
        (self.r_numbers if has_numbers else self.r_start).setChecked(True)

        self.start = QSpinBox()
        self.start.setRange(1, CHANNELS)
        self.bank = QComboBox()
        self.bank.addItems([f"{b}  ({bank_range(b).start:03d}–{bank_range(b).stop - 1:03d})"
                            for b in BANKS])
        lay.addWidget(self.r_numbers)
        row = QHBoxLayout()
        row.addWidget(self.r_start)
        row.addWidget(self.start)
        row.addStretch()
        lay.addLayout(row)
        row = QHBoxLayout()
        row.addWidget(self.r_bank)
        row.addWidget(self.bank)
        row.addStretch()
        lay.addLayout(row)
        self.skip_dupes = QCheckBox(_("Skip frequencies already in memory"))
        self.skip_dupes.setChecked(True)
        lay.addWidget(self.skip_dupes)

        if warnings:
            lay.addWidget(QLabel("<span style='color:#ff6b6b'>" + _("Warnings ({n}):", n=len(warnings)) + "</span>"))
            w = QPlainTextEdit("\n".join(warnings))
            w.setReadOnly(True)
            w.setMaximumHeight(110)
            lay.addWidget(w)

        self.summary = QLabel()
        self.summary.setObjectName("dim")
        lay.addWidget(self.summary)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(_("Import"))
        buttons.button(QDialogButtonBox.Ok).setObjectName("primary")
        buttons.button(QDialogButtonBox.Cancel).setText(_("Cancel"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)

        for sig in (self.group.buttonClicked, self.start.valueChanged,
                    self.bank.currentIndexChanged, self.skip_dupes.toggled):
            sig.connect(self._update)
        self._update()

    def plan(self) -> tuple[list[tuple[int, Channel]], int]:
        """Return ([(target_number, channel)], skipped_count)."""
        existing = {ch.freq_hz for ch in self.model.channels if not ch.empty}
        items = self.items
        skipped = 0
        if self.skip_dupes.isChecked():
            kept = [ch for ch in items if ch.freq_hz not in existing]
            skipped = len(items) - len(kept)
            items = kept
        mode = self.group.checkedId()
        if mode == 0:
            pairs = [(ch.number, ch) for ch in items if ch.number]
            skipped += len(items) - len(pairs)
        elif mode == 1:
            first = self.start.value()
            pairs = [(first + i, ch) for i, ch in enumerate(items) if first + i <= CHANNELS]
            skipped += len(items) - len(pairs)
        else:
            free = self.model.free_numbers(bank_range(BANKS[self.bank.currentIndex()]))
            pairs = list(zip(free, items))
            skipped += len(items) - len(pairs)
        return pairs, skipped

    def _update(self, *args):
        pairs, skipped = self.plan()
        overwrite = sum(1 for n, _ch in pairs if not self.model.channels[n - 1].empty)
        text = _("Channels to fill: {n}", n=len(pairs))
        if pairs:
            text += f" ({pairs[0][0]:03d}–{pairs[-1][0]:03d})"
        if overwrite:
            text += _(" · overwrites occupied: {n}", n=overwrite)
        if skipped:
            text += _(" · skipped: {n}", n=skipped)
        self.summary.setText(text)
