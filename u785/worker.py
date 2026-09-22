"""Background thread that owns the serial port.

The UI talks to it only through queued signals; long jobs check a cancel flag.
Polling runs on a timer inside the worker thread and pauses during jobs.
"""
import threading
import time

from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal, pyqtSlot

from .i18n import _
from .model import Channel
from .protocol import Scanner, ScannerError, MODES, signal_bars

FLAGS = ("PR", "DL", "AT", "MU", "LT", "BP")


class ScannerWorker(QObject):
    connected = pyqtSignal(dict)
    disconnected = pyqtSignal(str)
    status = pyqtSignal(dict)
    flags = pyqtSignal(dict)
    channel_read = pyqtSignal(object)            # Channel
    banks_read = pyqtSignal(list)                # [{bank, tag, search_tag, lo, hi}], selected
    progress = pyqtSignal(int, int, str)
    job_finished = pyqtSignal(str, bool, str)    # job, ok, message
    log = pyqtSignal(str, str)
    raw_reply = pyqtSignal(str, list)

    def __init__(self):
        super().__init__()
        self.scanner: Scanner | None = None
        self.cancel = threading.Event()
        self.poll_enabled = True
        self.timer = None
        self._errors = 0

    # --- lifecycle -------------------------------------------------------
    @pyqtSlot()
    def setup(self):
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._poll)

    @pyqtSlot(str, int)
    def open(self, port: str, baud: int):
        self.close_port(silent=True)
        try:
            self.scanner = Scanner(port, baud, log=lambda d, t: self.log.emit(d, t))
            info = self.scanner.identify()
            if info["model"] == "?":
                raise ScannerError(_("The scanner did not answer SI — check the port speed"))
            self.scanner.housekeeping()
            info.update(port=port, baud=baud)
            self.connected.emit(info)
            self._read_flags()
            self._errors = 0
            self.timer.start()
        except Exception as e:  # serial.SerialException or ScannerError
            self.close_port(silent=True)
            self.disconnected.emit(_explain(e))

    @pyqtSlot()
    def close(self):
        self.close_port(silent=False)

    def close_port(self, silent: bool):
        if self.timer:
            self.timer.stop()
        if self.scanner:
            self.scanner.close()
            self.scanner = None
            if not silent:
                self.disconnected.emit("")

    def _guard(self) -> bool:
        if not self.scanner:
            self.job_finished.emit("", False, _("Scanner not connected"))
            return False
        return True

    # --- polling ---------------------------------------------------------
    @pyqtSlot(bool)
    def set_polling(self, on: bool):
        self.poll_enabled = on

    def _poll(self):
        if not self.scanner or not self.poll_enabled:
            return
        try:
            s = {}
            sg = self.scanner.signal()
            if sg:
                s["level"], s["freq_hz"] = sg
                s["bars"] = signal_bars(sg[0])
            s["squelch"] = self.scanner.squelch_open()
            md = self.scanner.mode()
            s["mode_code"] = md
            s["mode"] = MODES.get(md, f"MD{md:02d}" if md is not None else "?")
            s["mod"] = self.scanner.modulation()
            s["lcd"] = self.scanner.lcd()
            self._errors = 0
            self.status.emit(s)
        except ScannerError:
            self._errors += 1
            if self._errors >= 4:
                self.close_port(silent=True)
                self.disconnected.emit(_("The scanner stopped responding"))
        except Exception as e:
            self.close_port(silent=True)
            self.disconnected.emit(_explain(e))

    def _read_flags(self):
        out = {}
        for code in FLAGS:
            try:
                out[code] = self.scanner.flag(code)
            except ScannerError:
                out[code] = None
        self.flags.emit(out)

    # --- commands --------------------------------------------------------
    @pyqtSlot(str)
    def send_raw(self, cmd: str):
        if not self._guard():
            return
        try:
            lines = self.scanner.command_lines(cmd, quiet=0.12, timeout=3.0)
            self.raw_reply.emit(cmd, lines)
        except ScannerError as e:
            self.raw_reply.emit(cmd, [f"! {e}"])

    @pyqtSlot(str, bool)
    def key(self, name: str, hold: bool):
        if not self._guard():
            return
        try:
            self.scanner.key(name, hold)
        except ScannerError as e:
            self.job_finished.emit("key", False, str(e))

    @pyqtSlot(str, str)
    def set_flag(self, code: str, value: str):
        if not self._guard():
            return
        try:
            self.scanner.ok(f"{code}{value}")
        except ScannerError as e:
            self.job_finished.emit("flag", False, str(e))
        self._read_flags()

    @pyqtSlot(int, str)
    def tune(self, hz: int, mod: str):
        if not self._guard():
            return
        try:
            self.scanner.tune(hz, mod if mod != "AUTO" else None)
            self.job_finished.emit("tune", True, "")
        except ScannerError as e:
            self.job_finished.emit("tune", False, str(e))

    @pyqtSlot(int)
    def goto_channel(self, number: int):
        if not self._guard():
            return
        try:
            self.scanner.ok(f"MA{number:03d}")
        except ScannerError as e:
            self.job_finished.emit("goto", False, str(e))

    # --- bulk jobs -------------------------------------------------------
    @pyqtSlot(list, bool)
    def read_channels(self, numbers: list, with_mod: bool):
        if not self._guard():
            return
        self.cancel.clear()
        total, done, failed = len(numbers), 0, []
        t0 = time.monotonic()
        for n in numbers:
            if self.cancel.is_set():
                break
            try:
                ch = self.scanner.read_channel(n, with_tag=True, with_mod=with_mod)
                self.channel_read.emit(ch)
            except ScannerError:
                failed.append(n)
            done += 1
            self.progress.emit(done, total, _("Reading channel {n:03d}", n=n))
        if with_mod:
            self._safe(lambda: self.scanner.key("SCAN"))
        msg = _("Read {ok} of {total} in {secs:.0f} s", ok=done - len(failed), total=total,
                secs=time.monotonic() - t0)
        if failed:
            msg += _("; errors: {list}", list=_short(failed))
        if self.cancel.is_set():
            msg = _("Cancelled. ") + msg
        self.job_finished.emit("read", not failed and not self.cancel.is_set(), msg)

    @pyqtSlot(list)
    def write_channels(self, channels: list):
        if not self._guard():
            return
        self.cancel.clear()
        total, done, failed = len(channels), 0, []
        for ch in channels:
            if self.cancel.is_set():
                break
            try:
                back = self.scanner.write_channel(ch)
                mismatch = back.freq_hz != ch.freq_hz
                if mismatch:
                    failed.append(ch.number)
                else:
                    back.tag = ch.tag  # keep the user's (untransliterated) text in the table
                    self.channel_read.emit(back)
            except ScannerError:
                failed.append(ch.number)
            done += 1
            self.progress.emit(done, total, _("Writing channel {n:03d}", n=ch.number))
        self._safe(lambda: self.scanner.key("SCAN"))
        msg = _("Wrote {ok} of {total}", ok=done - len(failed), total=total)
        if failed:
            msg += _("; not written: {list}", list=_short(failed))
        if self.cancel.is_set():
            msg = _("Cancelled. ") + msg
        self.job_finished.emit("write", not failed and not self.cancel.is_set(), msg)

    @pyqtSlot()
    def read_banks(self):
        if not self._guard():
            return
        rows = []
        try:
            selected = self.scanner.selected_banks()
            for b in "ABCDEFGHIJ":
                lo, hi = self.scanner.search_limits(b)
                rows.append(dict(bank=b, tag=self.scanner.bank_tag(b),
                                 search_tag=self.scanner.search_tag(b), lo=lo, hi=hi,
                                 selected=b in selected))
                self.progress.emit(len(rows), 10, _("Bank {b}", b=b))
            self.banks_read.emit(rows)
            self.job_finished.emit("banks", True, _("Banks read"))
        except ScannerError as e:
            self.job_finished.emit("banks", False, str(e))

    @pyqtSlot(list)
    def write_banks(self, rows: list):
        if not self._guard():
            return
        try:
            for i, r in enumerate(rows, 1):
                self.scanner.set_bank_tag(r["bank"], r["tag"])
                self.progress.emit(i, len(rows), _("Bank {b}", b=r["bank"]))
            sel = "".join(r["bank"] for r in rows if r["selected"])
            if sel:
                self.scanner.select_banks(sel)
            self.job_finished.emit("banks_write", True, _("Banks written"))
        except ScannerError as e:
            self.job_finished.emit("banks_write", False, str(e))

    def _safe(self, fn):
        try:
            fn()
        except ScannerError:
            pass


def _short(nums: list[int]) -> str:
    s = ", ".join(str(n) for n in nums[:12])
    return s + (f" … (+{len(nums) - 12})" if len(nums) > 12 else "")


def _explain(e: Exception) -> str:
    text = str(e)
    if "not functioning" in text or "Cannot configure port" in text:
        return _("The USB-serial driver could not configure the port (typical of CH340 clones). "
                 "Replug the cable and try again.")
    if "PermissionError" in text or "Access is denied" in text:
        return _("The port is in use by another program.")
    if "FileNotFoundError" in text or "could not open port" in text:
        return _("Port not found. Check the cable.")
    return text


def start_worker() -> tuple[QThread, ScannerWorker]:
    thread = QThread()
    worker = ScannerWorker()
    worker.moveToThread(thread)
    thread.started.connect(worker.setup)
    thread.start()
    return thread, worker
