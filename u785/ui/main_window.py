"""Main window: connection bar, radio panel, channel memory, banks, console."""
import os
import sys
import time

from PyQt5.QtCore import QMetaObject, QProcess, QSettings, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QTextCharFormat, QKeySequence
from PyQt5.QtWidgets import (QAction, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout,
                             QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMenu, QMessageBox,
                             QPlainTextEdit, QProgressBar, QPushButton, QShortcut, QSplitter,
                             QStatusBar, QTableWidget, QTableWidgetItem, QTabWidget, QToolButton,
                             QVBoxLayout, QWidget, QButtonGroup, QHeaderView, QScrollArea)

from .. import __version__, csvio, i18n
from ..i18n import LANGUAGES, _, language
from ..model import BANKS, CHANNELS, MODULATIONS, bank_range, format_mhz
from ..protocol import SIM_PORT
from ..worker import start_worker
from . import theme
from .channels import ChannelFilter, ChannelModel, ChannelView
from .import_dialog import ImportDialog
from .widgets import FreqEntry, LcdDisplay, SignalMeter

APP_NAME = "UBC785 Studio"
BAUDS = [19200, 9600, 4800, 2400]
POLL_CMDS = {"SG", "SQ", "MD", "RM", "LCD"}
STEPS = [("5", 5_000), ("6.25", 6_250), ("8.33", 8_333), ("10", 10_000),
         ("12.5", 12_500), ("25", 25_000), ("50", 50_000), ("100", 100_000)]


def panel(title: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("panel")
    lay = QVBoxLayout(f)
    lay.setContentsMargins(14, 12, 14, 14)
    lay.setSpacing(8)
    if title:
        t = QLabel(title.upper())
        t.setObjectName("section")
        lay.addWidget(t)
    return f, lay


def list_ports() -> list[str]:
    try:
        from serial.tools import list_ports as lp
        ports = sorted(p.device for p in lp.comports())
    except Exception:
        ports = []
    return ports + [SIM_PORT]


class MainWindow(QMainWindow):
    # queued calls into the worker thread
    sig_open = pyqtSignal(str, int)
    sig_close = pyqtSignal()
    sig_read = pyqtSignal(list, bool)
    sig_write = pyqtSignal(list)
    sig_raw = pyqtSignal(str)
    sig_key = pyqtSignal(str, bool)
    sig_flag = pyqtSignal(str, str)
    sig_tune = pyqtSignal(int, str)
    sig_goto = pyqtSignal(int)
    sig_banks_read = pyqtSignal()
    sig_banks_write = pyqtSignal(list)
    sig_poll = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.settings = QSettings("u785", "studio")
        self.setWindowTitle(f"{APP_NAME} {__version__}")
        self.resize(1480, 920)
        self.connected = False
        self.busy = False
        self.last_freq = 0
        self.hide_next_rx = False

        self.model = ChannelModel()
        self.proxy = ChannelFilter()
        self.proxy.setSourceModel(self.model)

        self.worker_thread, self.worker = start_worker()
        self._wire_worker()

        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(14, 12, 14, 8)
        outer.setSpacing(12)
        outer.addWidget(self._build_topbar())
        split = QSplitter(Qt.Horizontal)
        split.addWidget(self._build_radio_panel())
        split.addWidget(self._build_tabs())
        split.setStretchFactor(1, 1)
        split.setSizes([430, 1050])
        split.setHandleWidth(12)
        outer.addWidget(split, 1)
        self.setCentralWidget(root)
        self._build_statusbar()

        self.model.error.connect(lambda m: self.flash(m, error=True))
        self.model.dirty_changed.connect(self._dirty_changed)
        self._set_connected(False)
        geo = self.settings.value("geometry")
        if geo:
            self.restoreGeometry(geo)
        self._was_maximized = self.settings.value("maximized", False, bool)
        for keys in ("F11", "Alt+Return", "Alt+Enter"):
            QShortcut(QKeySequence(keys), self, self.toggle_fullscreen)
        if self.settings.value("fullscreen", False, bool):
            self.showFullScreen()
            self.fs_btn.setChecked(True)

    # ------------------------------------------------------------------ build
    def _build_topbar(self) -> QWidget:
        bar, lay = panel()
        lay.setDirection(QHBoxLayout.LeftToRight)
        lay.setContentsMargins(14, 8, 14, 8)
        logo = QLabel(f"<span style='color:{theme.AMBER};font-weight:bold'>UBC785</span>"
                      f"<span style='color:{theme.DIM}'> STUDIO</span>")
        logo.setStyleSheet("font-size: 13pt;")
        lay.addWidget(logo)
        lay.addSpacing(24)

        self.port_box = QComboBox()
        self.port_box.setMinimumWidth(140)
        self.refresh_ports()
        refresh = QToolButton()
        refresh.setText("⟳")
        refresh.setToolTip(_("Refresh port list"))
        refresh.clicked.connect(self.refresh_ports)
        self.baud_box = QComboBox()
        self.baud_box.addItems([str(b) for b in BAUDS])
        self.baud_box.setCurrentText(str(self.settings.value("baud", 19200)))
        self.connect_btn = QPushButton(_("Connect"))
        self.connect_btn.setObjectName("primary")
        self.connect_btn.setMinimumWidth(130)
        self.connect_btn.clicked.connect(self.toggle_connection)
        for w in (QLabel(_("PORT")), self.port_box, refresh, QLabel(_("BAUD")), self.baud_box,
                  self.connect_btn):
            if isinstance(w, QLabel):
                w.setObjectName("section")
            lay.addWidget(w)
        lay.addSpacing(18)
        self.link_dot = QLabel("●")
        self.link_label = QLabel(_("not connected"))
        self.link_label.setObjectName("dim")
        lay.addWidget(self.link_dot)
        lay.addWidget(self.link_label)
        lay.addStretch()
        lay.addWidget(QLabel(_("LANG"), objectName="section"))
        self.lang_box = QComboBox()
        for code, name in LANGUAGES.items():
            self.lang_box.addItem(name, code)
        self.lang_box.setCurrentIndex(list(LANGUAGES).index(language()))
        self.lang_box.currentIndexChanged.connect(self._change_language)
        lay.addWidget(self.lang_box)
        lay.addSpacing(18)
        self.fs_btn = QToolButton()
        self.fs_btn.setText("⛶")
        self.fs_btn.setCheckable(True)
        self.fs_btn.setToolTip(_("Full screen (F11 / Alt+Enter)"))
        self.fs_btn.clicked.connect(self.toggle_fullscreen)
        lay.addWidget(self.fs_btn)
        lay.addSpacing(12)
        self.mode_badge = QLabel("—")
        self.mode_badge.setObjectName("badgeCyan")
        lay.addWidget(QLabel(_("MODE"), objectName="section"))
        lay.addWidget(self.mode_badge)
        return bar

    def _build_radio_panel(self) -> QWidget:
        col = QWidget()
        lay = QVBoxLayout(col)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(12)

        # Display
        disp, dl = panel(_("Scanner display"))
        self.lcd = LcdDisplay()
        dl.addWidget(self.lcd)
        freq_row = QHBoxLayout()
        self.freq_label = QLabel("—")
        self.freq_label.setObjectName("bigFreq")
        mhz = QLabel(_("MHz"))
        mhz.setObjectName("dim")
        self.mod_badge = QLabel("—")
        self.mod_badge.setObjectName("badge")
        freq_row.addWidget(self.freq_label)
        freq_row.addWidget(mhz, 0, Qt.AlignBottom)
        freq_row.addStretch()
        freq_row.addWidget(self.mod_badge, 0, Qt.AlignVCenter)
        dl.addLayout(freq_row)
        self.meter = SignalMeter()
        dl.addWidget(self.meter)
        lay.addWidget(disp)

        # Keys
        keys, kl = panel(_("Controls"))
        grid = QGridLayout()
        grid.setSpacing(6)
        key_defs = [("SCAN", "SCAN", False), ("MANUAL", "MANUAL", False), ("▲ HOLD", "HOLD", False),
                    ("▼ LIMIT", "LIMIT", False), ("SRCH", "SRCH", False), ("PRI", "PRI", False),
                    ("L/O", "L/O", False), ("WX", "WX", False), ("TRUNK", "TRUNK", False)]
        self.key_buttons = []
        for i, (label, key, hold) in enumerate(key_defs):
            b = QPushButton(label)
            b.setObjectName("key")
            b.clicked.connect(lambda _, k=key, h=hold: self.sig_key.emit(k, h))
            grid.addWidget(b, i // 3, i % 3)
            self.key_buttons.append(b)
        kl.addLayout(grid)
        lay.addWidget(keys)

        # Direct tuning
        tune, tl = panel(_("Direct tuning (VFO)"))
        self.freq_entry = FreqEntry()
        self.freq_entry.submitted.connect(self.tune)
        tl.addWidget(self.freq_entry)
        row = QHBoxLayout()
        self.tune_mod = QComboBox()
        self.tune_mod.addItems(MODULATIONS)
        self.tune_mod.setCurrentText("NFM")
        self.step_box = QComboBox()
        for name, hz in STEPS:
            self.step_box.addItem(_("{v} kHz", v=name), hz)
        self.step_box.setCurrentIndex(3)
        down = QPushButton("−")
        up = QPushButton("+")
        down.setToolTip(_("Step down (Ctrl+↓)"))
        up.setToolTip(_("Step up (Ctrl+↑)"))
        down.clicked.connect(lambda: self.step_tune(-1))
        up.clicked.connect(lambda: self.step_tune(+1))
        self.tune_btn = QPushButton(_("Tune"))
        self.tune_btn.setObjectName("primary")
        self.tune_btn.clicked.connect(lambda: self.tune(self.freq_entry.value() or 0))
        for w in (self.tune_mod, self.step_box, down, up):
            row.addWidget(w)
        row.addStretch()
        row.addWidget(self.tune_btn)
        tl.addLayout(row)
        self.tune_widgets = [self.freq_entry, self.tune_mod, down, up, self.tune_btn]
        QShortcut(QKeySequence("Ctrl+Up"), self, lambda: self.step_tune(+1))
        QShortcut(QKeySequence("Ctrl+Down"), self, lambda: self.step_tune(-1))
        lay.addWidget(tune)

        # Functions
        funcs, fl = panel(_("Functions"))
        grid = QGridLayout()
        grid.setSpacing(6)
        self.flag_buttons = {}
        for i, (code, label, tip) in enumerate([
            ("PR", "PRIORITY", _("Priority channel")), ("DL", "DELAY", _("Delay (current channel)")),
            ("AT", "ATT", _("Attenuator (current channel)")), ("BP", "BEEP", _("Key beep")),
        ]):
            b = QPushButton(label)
            b.setCheckable(True)
            b.setToolTip(tip)
            b.clicked.connect(lambda on, c=code: self.sig_flag.emit(c, "N" if on else "F"))
            grid.addWidget(b, 0 if i < 2 else 1, i % 2)
            self.flag_buttons[code] = b
        fl.addLayout(grid)
        row = QHBoxLayout()
        self.light_box = self._choice(row, _("BACKLIGHT"), [(_("On"), "N"), (_("Dim"), "D"), (_("Off"), "F")], "LT")
        fl.addLayout(row)
        row = QHBoxLayout()
        # MU is a *mute* switch: MUN = mute on (silent), MUF = mute off (audio open).
        # The protocol doc describes the replies the other way round; the radio confirms this mapping.
        self.mute_box = self._choice(row, _("AUDIO"), [(_("Auto"), "A"), (_("Open"), "F"), (_("Mute"), "N")], "MU")
        fl.addLayout(row)
        lay.addWidget(funcs)
        lay.addStretch()

        scroll = QScrollArea()
        scroll.setWidget(col)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setMinimumWidth(400)
        return scroll

    def _choice(self, row: QHBoxLayout, title: str, options, code: str) -> QButtonGroup:
        lab = QLabel(title)
        lab.setObjectName("section")
        lab.setMinimumWidth(96)
        row.addWidget(lab)
        group = QButtonGroup(self)
        for text, val in options:
            b = QPushButton(text)
            b.setCheckable(True)
            b.setProperty("val", val)
            group.addButton(b)
            row.addWidget(b)
        group.setExclusive(True)
        group.buttonClicked.connect(lambda b, c=code: self.sig_flag.emit(c, b.property("val")))
        return group

    def _build_tabs(self) -> QWidget:
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_channels_tab(), _("Channels"))
        self.tabs.addTab(self._build_banks_tab(), _("Banks"))
        self.tabs.addTab(self._build_console_tab(), _("Console"))
        return self.tabs

    def _build_channels_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 8)
        lay.setSpacing(10)

        row = QHBoxLayout()
        self.read_btn = QToolButton()
        self.read_btn.setText(_("↓ Read from scanner"))
        self.read_btn.setPopupMode(QToolButton.MenuButtonPopup)
        self.read_btn.clicked.connect(lambda: self.read_channels(list(range(1, CHANNELS + 1))))
        m = QMenu(self)
        m.addAction(_("Entire memory (1–500)"), lambda: self.read_channels(list(range(1, CHANNELS + 1))))
        m.addAction(_("Current bank"), self.read_current_bank)
        m.addAction(_("Selected channels"), lambda: self.read_channels([r + 1 for r in self.view.selected_rows()]))
        self.read_btn.setMenu(m)
        self.write_btn = QPushButton(_("↑ Write changes"))
        self.write_btn.setObjectName("primary")
        self.write_btn.clicked.connect(self.write_changes)
        self.revert_btn = QPushButton(_("Revert edits"))
        self.revert_btn.clicked.connect(self.model.revert)
        self.mod_check = QCheckBox(_("Read modulation"))
        self.mod_check.setToolTip(_("Modulation is not part of the PM reply: to read it the scanner\n"
                                    "switches to each channel (MA + RM). Reading takes longer."))
        self.mod_check.setChecked(self.settings.value("read_mod", False, bool))
        row.addWidget(self.read_btn)
        row.addWidget(self.write_btn)
        row.addWidget(self.revert_btn)
        row.addWidget(self.mod_check)
        row.addStretch()
        imp = QPushButton(_("Import CSV"))
        imp.clicked.connect(self.import_csv)
        exp = QToolButton()
        exp.setText(_("Export CSV"))
        exp.setPopupMode(QToolButton.InstantPopup)
        em = QMenu(self)
        em.addAction(_("All programmed channels"), lambda: self.export_csv("all"))
        em.addAction(_("Visible only (filter)"), lambda: self.export_csv("visible"))
        em.addAction(_("Selected only"), lambda: self.export_csv("selected"))
        em.addSeparator()
        em.addAction(_("Full memory image (incl. empty)"), lambda: self.export_csv("full"))
        exp.setMenu(em)
        row.addWidget(imp)
        row.addWidget(exp)
        lay.addLayout(row)

        row = QHBoxLayout()
        row.setSpacing(4)
        self.bank_group = QButtonGroup(self)
        for i, b in enumerate([_("ALL")] + list(BANKS)):
            btn = QPushButton(b)
            btn.setCheckable(True)
            btn.setMinimumWidth(34 if b in BANKS else 52)
            btn.setProperty("bank", b if b in BANKS else "")
            if i == 0:
                btn.setChecked(True)
            self.bank_group.addButton(btn)
            row.addWidget(btn)
        self.bank_group.buttonClicked.connect(lambda b: self.proxy.set(bank=b.property("bank")))
        row.addSpacing(12)
        self.search = QLineEdit()
        self.search.setPlaceholderText(_("Search: frequency, tag, number…   (Ctrl+F)"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda t: self.proxy.set(text=t))
        QShortcut(QKeySequence.Find, self, self.search.setFocus)
        row.addWidget(self.search, 1)
        self.hide_empty = QCheckBox(_("Hide empty"))
        self.hide_empty.toggled.connect(lambda on: self.proxy.set(hide_empty=on))
        row.addWidget(self.hide_empty)
        lay.addLayout(row)

        self.view = ChannelView(self.model, self.proxy)
        self.view.goto.connect(self.sig_goto.emit)
        self.view.status.connect(self.flash)
        self.view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._channel_menu)
        lay.addWidget(self.view, 1)

        hint = QLabel(_("Double-click a number to jump to that channel on the scanner · Del — clear · "
                        "Ctrl+C / Ctrl+V — copy and paste rows (works with Excel too)"))
        hint.setObjectName("dim")
        hint.setStyleSheet("font-size: 8pt;")
        lay.addWidget(hint)
        return w

    def _build_banks_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        row = QHBoxLayout()
        rb = QPushButton(_("↓ Read banks"))
        rb.clicked.connect(self.sig_banks_read.emit)
        wb = QPushButton(_("↑ Write banks"))
        wb.setObjectName("primary")
        wb.clicked.connect(self.write_banks)
        self.bank_buttons = [rb, wb]
        row.addWidget(rb)
        row.addWidget(wb)
        row.addStretch()
        lay.addLayout(row)
        self.banks_table = QTableWidget(10, 6)
        self.banks_table.setHorizontalHeaderLabels(
            [_("BANK"), _("CHANNELS"), _("BANK TAG"), _("IN SCAN"), _("SEARCH: LOW"), _("SEARCH: HIGH")])
        self.banks_table.verticalHeader().hide()
        self.banks_table.verticalHeader().setDefaultSectionSize(30)
        self.banks_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.banks_table.setShowGrid(False)
        for i, b in enumerate(BANKS):
            r = bank_range(b)
            for c, text in enumerate([b, f"{r.start:03d}–{r.stop - 1:03d}", "", "", "", ""]):
                item = QTableWidgetItem(text)
                if c != 2:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                if c == 3:
                    item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
                    item.setCheckState(Qt.Checked)
                self.banks_table.setItem(i, c, item)
        lay.addWidget(self.banks_table, 1)
        note = QLabel(_("Bank tags appear on the scanner display (up to 16 characters, Cyrillic is "
                        "transliterated). “Scan” selects which banks take part in scanning."))
        note.setObjectName("dim")
        note.setWordWrap(True)
        lay.addWidget(note)
        return w

    def _build_console_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        self.console.setMaximumBlockCount(5000)
        self.console.setFont(theme.mono(9.5))
        lay.addWidget(self.console, 1)
        row = QHBoxLayout()
        self.cmd_edit = QLineEdit()
        self.cmd_edit.setPlaceholderText(_("Protocol command, e.g. PM001, TA C 001, SG, KEY00 …"))
        self.cmd_edit.returnPressed.connect(self.send_console)
        self.cmd_history, self.cmd_pos = [], 0
        self.cmd_edit.installEventFilter(self)
        send = QPushButton(_("Send"))
        send.clicked.connect(self.send_console)
        self.show_poll = QCheckBox(_("Show polling"))
        clear = QPushButton(_("Clear"))
        clear.clicked.connect(self.console.clear)
        row.addWidget(self.cmd_edit, 1)
        row.addWidget(send)
        row.addWidget(self.show_poll)
        row.addWidget(clear)
        lay.addLayout(row)
        return w

    def _build_statusbar(self):
        sb = QStatusBar()
        self.setStatusBar(sb)
        self.status_msg = QLabel("")
        sb.addWidget(self.status_msg, 1)
        self.dirty_label = QLabel("")
        self.dirty_label.setStyleSheet(f"color: {theme.AMBER};")
        sb.addPermanentWidget(self.dirty_label)
        self.progress = QProgressBar()
        self.progress.setFixedWidth(220)
        self.progress.hide()
        sb.addPermanentWidget(self.progress)
        self.cancel_btn = QPushButton(_("Stop"))
        self.cancel_btn.setObjectName("danger")
        self.cancel_btn.hide()
        self.cancel_btn.clicked.connect(self.worker.cancel.set)
        sb.addPermanentWidget(self.cancel_btn)

    # ------------------------------------------------------------ worker I/O
    def _wire_worker(self):
        w = self.worker
        self.sig_open.connect(w.open)
        self.sig_close.connect(w.close)
        self.sig_read.connect(w.read_channels)
        self.sig_write.connect(w.write_channels)
        self.sig_raw.connect(w.send_raw)
        self.sig_key.connect(w.key)
        self.sig_flag.connect(w.set_flag)
        self.sig_tune.connect(w.tune)
        self.sig_goto.connect(w.goto_channel)
        self.sig_banks_read.connect(w.read_banks)
        self.sig_banks_write.connect(w.write_banks)
        self.sig_poll.connect(w.set_polling)
        w.connected.connect(self._on_connected)
        w.disconnected.connect(self._on_disconnected)
        w.status.connect(self._on_status)
        w.flags.connect(self._on_flags)
        w.channel_read.connect(self.model.from_device)
        w.banks_read.connect(self._on_banks)
        w.progress.connect(self._on_progress)
        w.job_finished.connect(self._on_job_finished)
        w.log.connect(self._on_log)
        w.raw_reply.connect(self._on_raw_reply)

    def refresh_ports(self):
        current = self.port_box.currentText() or self.settings.value("port", "COM5")
        self.port_box.clear()
        self.port_box.addItems(list_ports())
        i = self.port_box.findText(current)
        self.port_box.setCurrentIndex(i if i >= 0 else 0)

    def toggle_connection(self):
        if self.connected:
            self.sig_close.emit()
            return
        port, baud = self.port_box.currentText(), int(self.baud_box.currentText())
        self.settings.setValue("port", port)
        self.settings.setValue("baud", baud)
        self.connect_btn.setEnabled(False)
        self.connect_btn.setText(_("Connecting…"))
        self.sig_open.emit(port, baud)

    def _on_connected(self, info: dict):
        self._set_connected(True)
        fw = _(" · firmware {fw}", fw=info["firmware"]) if info.get("firmware") else ""
        self.link_label.setText(f"{info['model']}{fw} · {info['port']} @ {info['baud']}")
        self.flash(_("Scanner connected"))

    def _on_disconnected(self, reason: str):
        self._set_connected(False)
        if reason:
            self.flash(reason, error=True)
            QMessageBox.warning(self, APP_NAME, reason)

    def _set_connected(self, on: bool):
        self.connected = on
        self.connect_btn.setEnabled(True)
        self.connect_btn.setText(_("Disconnect") if on else _("Connect"))
        self.connect_btn.setObjectName("" if on else "primary")
        self.connect_btn.style().unpolish(self.connect_btn)
        self.connect_btn.style().polish(self.connect_btn)
        self.link_dot.setStyleSheet(f"color: {theme.GREEN if on else theme.FAINT};")
        if not on:
            self.link_label.setText(_("not connected"))
            self.mode_badge.setText("—")
            self.freq_label.setText("—")
            self.mod_badge.setText("—")
            self.meter.set_signal(0, 0, False)
        self.lcd.set_online(on)
        self.port_box.setEnabled(not on)
        self.baud_box.setEnabled(not on)
        self._update_enabled()

    def _update_enabled(self):
        live = self.connected and not self.busy
        for wdg in self.key_buttons + self.tune_widgets + list(self.flag_buttons.values()) \
                + self.bank_buttons + [self.read_btn]:
            wdg.setEnabled(live)
        for g in (self.light_box, self.mute_box):
            for b in g.buttons():
                b.setEnabled(live)
        self.write_btn.setEnabled(live and self.model.dirty_count() > 0)

    def _on_status(self, s: dict):
        if "freq_hz" in s:
            self.last_freq = s["freq_hz"]
            self.freq_label.setText(format_mhz(s["freq_hz"], "—"))
            self.meter.set_signal(s["level"], s["bars"], s["squelch"])
        self.mode_badge.setText(s.get("mode", "?"))
        self.mod_badge.setText(s.get("mod") or "—")
        self.lcd.set_rows(s.get("lcd", []))

    def _on_flags(self, flags: dict):
        for code, b in self.flag_buttons.items():
            b.setChecked(flags.get(code) == "N")
        for group, code in ((self.light_box, "LT"), (self.mute_box, "MU")):
            for b in group.buttons():
                if b.property("val") == flags.get(code):
                    b.setChecked(True)

    def _on_progress(self, done: int, total: int, text: str):
        self.progress.setMaximum(total)
        self.progress.setValue(done)
        self.status_msg.setText(f"{text}  ({done}/{total})")

    def _on_job_finished(self, job: str, ok: bool, msg: str):
        if job in ("read", "write", "banks", "banks_write"):
            self._set_busy(False)
            if job == "write" and ok:
                self.settings.setValue("last_write", time.strftime("%Y-%m-%d %H:%M"))
        if msg:
            self.flash(msg, error=not ok)

    def _set_busy(self, on: bool):
        self.busy = on
        self.progress.setVisible(on)
        self.cancel_btn.setVisible(on)
        self.progress.setValue(0)
        self._update_enabled()

    # ---------------------------------------------------------------- actions
    def tune(self, hz: int):
        if not hz:
            self.flash(_("Enter a frequency between 25 and 1300 MHz"), error=True)
            return
        self.freq_entry.set_value(hz)
        self.sig_tune.emit(hz, self.tune_mod.currentText())
        self.flash(_("Tuning to {f} MHz {mod}", f=format_mhz(hz), mod=self.tune_mod.currentText()))

    def step_tune(self, direction: int):
        base = self.freq_entry.value() or self.last_freq
        if not base or not self.connected:
            return
        self.tune(base + direction * self.step_box.currentData())

    def read_channels(self, numbers: list[int]):
        if not numbers or not self.connected:
            return
        if self.model.dirty_count():
            r = QMessageBox.question(
                self, APP_NAME, _("There are unwritten changes. Reading will replace them with data from the scanner. Continue?"))
            if r != QMessageBox.Yes:
                return
        with_mod = self.mod_check.isChecked()
        self.settings.setValue("read_mod", with_mod)
        self._set_busy(True)
        self.sig_read.emit(numbers, with_mod)

    def read_current_bank(self):
        b = self.proxy.bank
        if not b:
            self.flash(_("Choose a bank with the A–J buttons above the table"), error=True)
            return
        self.read_channels(list(bank_range(b)))

    def write_changes(self):
        dirty = self.model.dirty_channels()
        if not dirty:
            return
        cleared = sum(1 for ch in dirty if ch.empty)
        text = _("Write {n} changed channel(s) to the scanner?", n=len(dirty))
        if cleared:
            text += "\n\n" + _("{n} of them will be erased.", n=cleared)
        text += "\n\n" + _("While writing, the scanner switches to manual mode and then returns to SCAN.")
        if QMessageBox.question(self, APP_NAME, text) != QMessageBox.Yes:
            return
        self._set_busy(True)
        self.sig_write.emit(dirty)

    def write_banks(self):
        rows = []
        for i, b in enumerate(BANKS):
            rows.append(dict(bank=b, tag=self.banks_table.item(i, 2).text(),
                             selected=self.banks_table.item(i, 3).checkState() == Qt.Checked))
        if not any(r["selected"] for r in rows):
            self.flash(_("At least one bank must be included in scanning"), error=True)
            return
        self._set_busy(True)
        self.sig_banks_write.emit(rows)

    def _on_banks(self, rows: list):
        for i, r in enumerate(rows):
            self.banks_table.item(i, 2).setText(r["tag"])
            self.banks_table.item(i, 3).setCheckState(Qt.Checked if r["selected"] else Qt.Unchecked)
            self.banks_table.item(i, 4).setText(format_mhz(r["lo"], "—"))
            self.banks_table.item(i, 5).setText(format_mhz(r["hi"], "—"))

    def _channel_menu(self, pos):
        rows = self.view.selected_rows()
        if not rows:
            return
        m = QMenu(self)
        m.addAction(_("Go to channel {n:03d} on the scanner", n=rows[0] + 1),
                    lambda: self.sig_goto.emit(rows[0] + 1)).setEnabled(self.connected)
        m.addAction(_("Read from scanner ({n})", n=len(rows)),
                    lambda: self.read_channels([r + 1 for r in rows])).setEnabled(self.connected)
        m.addSeparator()
        m.addAction(_("Copy  Ctrl+C"), self.view.copy_rows)
        m.addAction(_("Paste  Ctrl+V"), self.view.paste_rows)
        m.addAction(_("Clear ({n})  Del", n=len(rows)), lambda: self.model.clear_rows(rows))
        m.exec_(self.view.viewport().mapToGlobal(pos))

    def import_csv(self):
        path, _filter = QFileDialog.getOpenFileName(self, _("Import CSV"), self.settings.value("csv_dir", ""),
                                                    _("CSV (*.csv *.txt);;All files (*)"))
        if not path:
            return
        self.settings.setValue("csv_dir", os.path.dirname(path))
        try:
            items, warnings = csvio.read_csv(path)
        except Exception as e:
            QMessageBox.critical(self, APP_NAME, _("Could not read the file:\n{e}", e=e))
            return
        if not items:
            QMessageBox.warning(self, APP_NAME, _("No frequencies found in the file.") + "\n\n" + "\n".join(warnings[:10]))
            return
        dlg = ImportDialog(os.path.basename(path), items, warnings, self.model, self)
        if dlg.exec_():
            pairs, _skipped = dlg.plan()
            for n, ch in pairs:
                self.model.put(n, ch)
            self.flash(_("Imported {n} channel(s) — review them and press “Write changes”", n=len(pairs)))

    def export_csv(self, scope: str):
        if scope == "selected":
            chans = [self.model.channels[r] for r in self.view.selected_rows()]
        elif scope == "visible":
            chans = [self.model.channels[self.proxy.mapToSource(self.proxy.index(i, 0)).row()]
                     for i in range(self.proxy.rowCount())]
        else:
            chans = self.model.channels
        default = os.path.join(self.settings.value("csv_dir", os.path.expanduser("~")),
                               f"ubc785_{time.strftime('%Y%m%d')}.csv")
        path, _filter = QFileDialog.getSaveFileName(self, _("Export CSV"), default, "CSV (*.csv)")
        if not path:
            return
        self.settings.setValue("csv_dir", os.path.dirname(path))
        n = csvio.export_csv(chans, path, include_empty=scope == "full")
        self.flash(_("Saved {n} channel(s) → {path}", n=n, path=path))

    # ---------------------------------------------------------------- console
    def send_console(self):
        cmd = self.cmd_edit.text().strip()
        if not cmd:
            return
        if not self.connected:
            self.flash(_("Scanner not connected"), error=True)
            return
        self.cmd_history.append(cmd)
        self.cmd_pos = len(self.cmd_history)
        self.cmd_edit.clear()
        self.sig_raw.emit(cmd)

    def eventFilter(self, obj, e):
        if obj is self.cmd_edit and e.type() == e.KeyPress and self.cmd_history:
            if e.key() == Qt.Key_Up:
                self.cmd_pos = max(0, self.cmd_pos - 1)
            elif e.key() == Qt.Key_Down:
                self.cmd_pos = min(len(self.cmd_history), self.cmd_pos + 1)
            else:
                return False
            self.cmd_edit.setText(self.cmd_history[self.cmd_pos] if self.cmd_pos < len(self.cmd_history) else "")
            return True
        return False

    def _on_log(self, direction: str, text: str):
        if direction == "tx":
            self.hide_next_rx = text in POLL_CMDS and not self.show_poll.isChecked()
            if self.hide_next_rx:
                return
        elif direction == "rx" and self.hide_next_rx:
            return
        colors = {"tx": theme.CYAN, "rx": theme.TEXT, "err": theme.RED}
        arrow = {"tx": "→", "rx": "←", "err": "!"}[direction]
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(colors[direction]))
        cur = self.console.textCursor()
        cur.movePosition(cur.End)
        for line in text.split("\n"):
            cur.insertText(f"{time.strftime('%H:%M:%S')} {arrow} {line}\n", fmt)
        self.console.setTextCursor(cur)
        self.console.ensureCursorVisible()

    def _on_raw_reply(self, cmd: str, lines: list):
        pass  # already shown via the log stream

    # ------------------------------------------------------------------ misc
    def _dirty_changed(self, n: int):
        self.dirty_label.setText(_("● modified: {n}", n=n) if n else "")
        self._update_enabled()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showMaximized() if self._was_maximized else self.showNormal()
        else:
            self._was_maximized = self.isMaximized()
            self.showFullScreen()
        self.fs_btn.setChecked(self.isFullScreen())

    def _change_language(self):
        code = self.lang_box.currentData()
        if code == language():
            return
        self.settings.setValue("language", code)
        # Ask in the language being switched to.
        current = language()
        i18n.set_language(code)
        question = _("Restart the app now to switch the language?")
        i18n.set_language(current)
        if QMessageBox.question(self, APP_NAME, question) == QMessageBox.Yes:
            self._restart = True
            self.close()

    def flash(self, text: str, error: bool = False):
        self.status_msg.setStyleSheet(f"color: {theme.RED if error else theme.DIM};")
        self.status_msg.setText(text)

    def closeEvent(self, e):
        if self.model.dirty_count():
            r = QMessageBox.question(self, APP_NAME, _("There are unwritten changes. Quit without writing?"))
            if r != QMessageBox.Yes:
                self._restart = False
                e.ignore()
                return
        self.settings.setValue("fullscreen", self.isFullScreen())
        self.settings.setValue("maximized", self._was_maximized if self.isFullScreen() else self.isMaximized())
        if not self.isFullScreen():
            self.settings.setValue("geometry", self.saveGeometry())
        # Close the port synchronously in the worker thread before stopping it.
        QMetaObject.invokeMethod(self.worker, "close", Qt.BlockingQueuedConnection)
        self.worker_thread.quit()
        self.worker_thread.wait(2000)
        if getattr(self, "_restart", False):
            _relaunch()
        super().closeEvent(e)


def _relaunch():
    """Start a fresh copy of the app (used after switching the language)."""
    exe = sys.executable
    windowed = os.path.join(os.path.dirname(exe), "pythonw.exe")
    if os.path.exists(windowed):
        exe = windowed
    project = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    QProcess.startDetached(exe, ["-m", "u785"], project)
