"""Uniden BC780/BC785/UBC785XLT remote-control protocol.

Every command is ASCII text terminated by CR. The radio answers with a line
('OK', 'NG', 'ERR' or data) terminated by CR. Some commands (LCD, SS, IL) answer
with several lines.
"""
import re
import threading
import time

from .i18n import _
from .model import Channel, from_wire, to_wire, radio_text, MODULATIONS

SIM_PORT = "SIMULATOR"

MODES = {
    0: "SCAN", 1: "MANUAL", 2: "SEARCH", 3: "SEARCH HOLD", 4: "WX / SVC", 5: "WX / SVC HOLD",
    6: "TRUNK PROG", 8: "VFO", 9: "ID SEARCH", 10: "ID SEARCH HOLD", 11: "ID SCAN",
    12: "ID MANUAL", 13: "ID L/O REVIEW",
}

KEYS = {
    "SCAN": "00", "MANUAL": "01", "ATT": "03", "E": "04", "PRI": "05", "L/O": "06",
    "HOLD": "07", "LIMIT": "08", "SRCH": "09", "WX": "10", "MENU": "11", "SELECT": "12",
    "TRUNK": "13", "VFO": "14",
}


class ScannerError(Exception):
    pass


def _open_serial(port: str, baud: int, attempts: int = 4):
    """Open the port at 9600 first, then switch to the target speed.

    Clone CH340 chips on WCH driver 3.9 intermittently fail SetCommState when a
    port is opened directly at 19200 ("A device attached to the system is not
    functioning"); opening at 9600 and changing the rate afterwards is reliable.
    """
    import serial
    last = None
    for i in range(attempts):
        try:
            ser = serial.Serial(port, 9600, bytesize=8, parity="N", stopbits=1, timeout=0.05)
            if baud != 9600:
                ser.baudrate = baud
            ser.write(b"\r")  # flush any half-received command in the radio
            time.sleep(0.1)
            ser.reset_input_buffer()
            return ser
        except serial.SerialException as e:
            last = e
            time.sleep(0.6 * (i + 1))
    raise last


class Scanner:
    """Thread-safe command/response channel to the radio."""

    def __init__(self, port: str, baud: int = 19200, log=None):
        if port == SIM_PORT:
            from .simulator import SimulatedSerial
            self.ser = SimulatedSerial()
        else:
            self.ser = _open_serial(port, baud)
        self.port = port
        self.lock = threading.RLock()
        self.log = log or (lambda direction, text: None)

    def close(self):
        try:
            self.ser.close()
        except Exception:
            pass

    # --- low level -------------------------------------------------------
    def _read_line(self, deadline: float) -> str | None:
        buf = bytearray()
        while time.monotonic() < deadline:
            chunk = self.ser.read(1)
            if not chunk:
                continue
            if chunk in (b"\r", b"\n"):
                if buf:
                    return buf.decode("ascii", "replace")
                continue
            buf += chunk
        return buf.decode("ascii", "replace") if buf else None

    def command(self, cmd: str, timeout: float = 1.5) -> str:
        """Send one command and return the first response line."""
        with self.lock:
            self.ser.reset_input_buffer()
            self.log("tx", cmd)
            self.ser.write(cmd.encode("ascii", "replace") + b"\r")
            line = self._read_line(time.monotonic() + timeout)
            if line is None:
                self.log("err", _("{cmd}: no response", cmd=cmd))
                raise ScannerError(_("No response to {cmd}", cmd=repr(cmd)))
            self.log("rx", line)
            return line

    def command_lines(self, cmd: str, quiet: float = 0.25, timeout: float = 5.0) -> list[str]:
        """Send a command whose answer spans several lines; stop on 'END' or silence."""
        with self.lock:
            self.ser.reset_input_buffer()
            self.log("tx", cmd)
            self.ser.write(cmd.encode("ascii", "replace") + b"\r")
            lines = []
            hard = time.monotonic() + timeout
            first = self._read_line(time.monotonic() + 1.5)
            if first is None:
                self.log("err", _("{cmd}: no response", cmd=cmd))
                raise ScannerError(_("No response to {cmd}", cmd=repr(cmd)))
            lines.append(first)
            while time.monotonic() < hard and lines[-1] != "END":
                line = self._read_line(min(hard, time.monotonic() + quiet))
                if line is None:
                    break
                lines.append(line)
            self.log("rx", "\n".join(lines))
            return lines

    def ok(self, cmd: str) -> str:
        r = self.command(cmd)
        if r in ("NG", "ERR"):
            raise ScannerError(f"{cmd!r} → {r}")
        return r

    # --- identification --------------------------------------------------
    def identify(self) -> dict:
        info = {"model": "?", "version": "?"}
        si = self.command("SI")
        if si.startswith("SI"):
            parts = si[2:].strip().split(",")
            # 'Model:UB343ZH(UBC785XLT)' -> 'UBC785XLT (UB343ZH)'
            raw = parts[0].strip().removeprefix("Model:")
            m = re.fullmatch(r"(\w+)\((\w+)\)", raw)
            info["model"] = f"{m.group(2)} ({m.group(1)})" if m else (raw or "?")
            if len(parts) > 2:
                info["firmware"] = parts[2].strip()
        try:
            vr = self.command("VR")
            info["version"] = vr[2:].strip() if vr.startswith("VR") else vr
        except ScannerError:
            pass
        return info

    def housekeeping(self):
        """Switch off auto-reporting features so they don't pollute replies."""
        for c in ("QUF", "IDF", "RIF"):
            try:
                self.command(c, timeout=0.8)
            except ScannerError:
                pass

    # --- status ----------------------------------------------------------
    def mode(self) -> int | None:
        r = self.command("MD")
        m = re.match(r"MD\s*(\d+)", r)
        return int(m.group(1)) if m else None

    def signal(self) -> tuple[int, int] | None:
        r = self.command("SG")
        m = re.match(r"S\s*(\d+)\s+F\s*(\d{8})", r)
        if not m:
            return None
        return int(m.group(1)), from_wire(m.group(2))

    def squelch_open(self) -> bool:
        return self.command("SQ").startswith("+")

    def lcd(self) -> list[str]:
        return parse_lcd(self.command_lines("LCD", quiet=0.08, timeout=1.5))

    def step(self) -> str | None:
        r = self.command("ST")
        return r[2:].strip() if r.startswith("ST") else None

    def flag(self, code: str) -> str | None:
        """Query a two-letter on/off style setting; returns the letter after the code."""
        r = self.command(code)
        if r.startswith(code) and len(r) > len(code):
            return r[len(code):].strip()
        return None

    # --- memory ----------------------------------------------------------
    def read_channel(self, number: int, with_tag: bool = True, with_mod: bool = False) -> Channel:
        r = self.command(f"PM{number:03d}")
        ch = parse_pm(r, number)
        if with_tag:
            ch.tag = self.read_tag(number)
        if with_mod and not ch.empty:
            self.ok(f"MA{number:03d}")
            ch.mod = self.modulation() or ch.mod
        return ch

    def read_tag(self, number: int) -> str:
        req = f"TA C {number:03d}"
        return parse_tag(self.command(req), req)

    def modulation(self) -> str | None:
        r = self.command("RM")
        m = re.match(r"RM\s*(\w+)", r)
        return m.group(1) if m and m.group(1) in MODULATIONS else None

    def write_channel(self, ch: Channel) -> Channel:
        """Program one memory channel and read it back."""
        n = f"{ch.number:03d}"
        if ch.empty:
            self.command(f"PM{n} 00000000")
            self.ok(f"TA C {n} {' ' * 16}")
            return self.read_channel(ch.number)
        r = self.command(f"PM{n} {to_wire(ch.freq_hz)}")
        if r in ("NG", "ERR"):
            raise ScannerError(_("Channel {n}: the scanner rejected the frequency ({r})", n=ch.number, r=r))
        # PM write leaves the radio in manual mode on this channel,
        # so the per-channel settings below apply to it.
        self.ok(f"RM {ch.mod}")
        self.ok("DLN" if ch.delay else "DLF")
        self.ok("LON" if ch.lockout else "LOF")
        self.ok("ATN" if ch.atten else "ATF")
        self.command("ARN" if ch.record else "ARF")
        self.command(f"CS{ch.tone:03d}")
        self.ok(f"TA C {n} {radio_text(ch.tag)}")
        back = self.read_channel(ch.number)
        back.mod = ch.mod
        return back

    # --- banks -----------------------------------------------------------
    def bank_tag(self, bank: str) -> str:
        req = f"TA B {bank}"
        return parse_tag(self.command(req), req)

    def search_tag(self, bank: str) -> str:
        req = f"TA S {bank}"
        return parse_tag(self.command(req), req)

    def set_bank_tag(self, bank: str, tag: str):
        self.ok(f"TA B {bank} {radio_text(tag)}")

    def search_limits(self, bank: str) -> tuple[int, int]:
        lo = re.search(r"(\d{8})", self.command(f"LL {bank}"))
        hi = re.search(r"(\d{8})", self.command(f"LU {bank}"))
        return (from_wire(lo.group(1)) if lo else 0, from_wire(hi.group(1)) if hi else 0)

    def selected_banks(self) -> str:
        r = self.command("SB")
        return re.sub(r"[^A-J]", "", r[2:]) if r.startswith("SB") else ""

    def select_banks(self, banks: str):
        self.command(f"SB {banks}")

    # --- control ---------------------------------------------------------
    def key(self, name: str, hold: bool = False):
        self.command(f"KEY{KEYS.get(name, name)}{'H' if hold else ''}")

    def tune(self, hz: int, mod: str | None = None):
        r = self.command(f"RF{to_wire(hz)}?")
        if r in ("NG", "ERR"):
            raise ScannerError(_("The scanner rejected the frequency ({r})", r=r))
        if mod:
            self.command(f"RM {mod}")


# --- parsers ---------------------------------------------------------------
def parse_pm(resp: str, number: int) -> Channel:
    m = re.search(r"C\s*(\d{3})\s+F\s*(\d{8})", resp)
    if not m:
        raise ScannerError(_("Unexpected PM{n:03d} reply: {resp}", n=number, resp=repr(resp)))
    ch = Channel(int(m.group(1)) or number, freq_hz=from_wire(m.group(2)))
    rest = resp[m.end():]
    flags = dict(re.findall(r"\b([TDLAR])([NF])\b", rest))
    ch.delay = flags.get("D", "N") == "N"
    ch.lockout = flags.get("L", "F") == "N"
    ch.atten = flags.get("A", "F") == "N"
    ch.record = flags.get("R", "F") == "N"
    tone = re.search(r"\bN(\d{2,3})\b", rest)
    ch.tone = int(tone.group(1)) if tone else 0
    mod = re.search(r"\b(AUTO|AM|NFM|WFM|FM)\b", rest)
    if mod:
        ch.mod = mod.group(1)
    return ch


def parse_tag(resp: str, request: str) -> str:
    """The radio echoes the request: 'TA C 001' -> 'TA C 001 PFO Tower Main'."""
    if resp in ("NG", "ERR"):
        return ""
    text = resp[len(request):] if resp.startswith(request) else resp
    text = text.strip()
    return "" if text == "_" else text  # the radio shows an unset tag as '_'


def parse_lcd(lines: list[str]) -> list[str]:
    """UBC785XLT answers 'LCD' with four text rows: 'LCD1 [16 chars][16 chars]'.

    Returns the four 16-character rows of the main text area.
    """
    rows = ["", "", "", ""]
    for line in lines:
        m = re.match(r"LCD(\d)\s*\[([^\]]*)\]", line)
        if m and 1 <= int(m.group(1)) <= 4:
            rows[int(m.group(1)) - 1] = m.group(2)
    return rows


def signal_bars(level: int) -> int:
    """Map SG 0..255 to the 0..6 bar scale documented for the BC780."""
    for bars, top in ((0, 55), (1, 60), (2, 80), (3, 95), (4, 125), (5, 140)):
        if level <= top:
            return bars
    return 6
