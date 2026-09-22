"""In-memory stand-in for a UBC785XLT, speaking the same text protocol.

Response formats mirror what a real UB343ZH (fw 107) returns on the wire.
"""
import random
import re
import time

from .model import BANKS, CHANNELS, bank_of, from_wire, to_wire, format_mhz

_DEMO = {
    1: (130_625_000, "PFO Tower Main", "AM"), 2: (119_900_000, "PFO Tower Sec", "AM"),
    3: (121_500_000, "Guard", "AM"), 51: (145_500_000, "2m Calling", "NFM"),
    52: (433_500_000, "70cm Calling", "NFM"), 101: (156_800_000, "VHF Channel 16", "NFM"),
    102: (156_100_000, "VHF Channel 2", "NFM"), 151: (446_006_250, "PMR 1", "NFM"),
    152: (446_018_750, "PMR 2", "NFM"),
}
_BANK_TAGS = {"A": "AVIATION", "B": "HAM", "C": "MARINE", "D": "PMR446"}


class SimulatedSerial:
    def __init__(self):
        self.mem = {n: dict(f=0, d=False, l=True, a=False, r=False, n=0, tag="", mod="AUTO")
                    for n in range(1, CHANNELS + 1)}
        for n, (f, tag, mod) in _DEMO.items():
            self.mem[n].update(f=f, d=True, l=False, tag=tag, mod=mod)
        self.bank_tags = {b: _BANK_TAGS.get(b, "") for b in BANKS}
        self.search_tags = {b: "" for b in BANKS}
        self.state = dict(md=1, ch=102, vfo=0, mod="NFM", DL="F", AT="F", PR="F", MU="A",
                          LT="N", BP="N", QU="F", ID="F", RI="F", CT="F", AR="F", LO="F", EL="F")
        self.banks = BANKS
        self.out = bytearray()
        self.inbuf = bytearray()
        self.is_open = True

    # --- pyserial-like surface -------------------------------------------
    def write(self, data: bytes):
        self.inbuf += data
        while b"\r" in self.inbuf:
            line, _, rest = self.inbuf.partition(b"\r")
            self.inbuf = bytearray(rest)
            reply = self.handle(line.decode("ascii", "replace").strip())
            for r in reply if isinstance(reply, list) else [reply]:
                self.out += r.encode("ascii", "replace") + b"\r"
        time.sleep(0.004)

    def read(self, n: int = 1) -> bytes:
        if not self.out:
            time.sleep(0.01)
            return b""
        chunk, self.out = bytes(self.out[:n]), self.out[n:]
        return chunk

    def reset_input_buffer(self):
        self.out.clear()

    def close(self):
        self.is_open = False

    # --- helpers ---------------------------------------------------------
    def _cur(self):
        return self.mem[self.state["ch"]]

    def _freq(self):
        return self.state["vfo"] if self.state["md"] == 8 else self._cur()["f"]

    def _pm(self, n):
        c = self.mem[n]
        yn = lambda b: "N" if b else "F"
        return (f"C{n:03d} F{to_wire(c['f'])} TF D{yn(c['d'])} L{yn(c['l'])} "
                f"A{yn(c['a'])} R{yn(c['r'])} N{c['n']:03d}")

    def _step_channel(self, delta):
        n = self.state["ch"]
        for _ in range(CHANNELS):
            n = (n - 1 + delta) % CHANNELS + 1
            if self.mem[n]["f"]:
                self.state["ch"] = n
                return

    # --- protocol --------------------------------------------------------
    def handle(self, cmd: str):
        st = self.state
        if self.state["md"] == 0:           # scanning: hop to another channel now and then
            if random.random() < 0.3:
                self._step_channel(1)
        if cmd == "SI":
            return "SI Model:UB343ZH(UBC785XLT),0000000000,107"
        if cmd == "VR":
            return "VR1.00"
        if cmd == "MD":
            return f"MD{st['md']:02d}"
        if cmd == "SQ":
            return "+" if random.random() < 0.25 else "-"
        if cmd in ("SG", "WI"):
            lvl = random.randint(40, 180) if random.random() < 0.4 else random.randint(0, 50)
            return f"{cmd[0]}{lvl:03d} F{to_wire(self._freq())}"
        if cmd == "LCD":
            c = self._cur()
            b = bank_of(st["ch"])
            if st["md"] == 8:
                rows = ["      VFO      ", f" {format_mhz(st['vfo']):>8} {st['mod']:<5}", "", ""]
            else:
                rows = [f"{'SCAN' if st['md'] == 0 else ''}{b:>9} {st['ch']:>3}",
                        f" {format_mhz(c['f']):>8} {c['mod'] if c['mod'] != 'AUTO' else 'NFM':<5}",
                        c["tag"], self.bank_tags[b]]
            return [f"LCD{i + 1} [{r[:16]:<16}][{'':16}]" for i, r in enumerate(rows)]
        if cmd == "RM":
            return f"RM {self._cur()['mod'] if st['md'] != 8 else st['mod']}".replace("AUTO", "NFM")
        m = re.fullmatch(r"RM (AUTO|AM|FM|NFM|WFM)", cmd)
        if m:
            if st["md"] == 8:
                st["mod"] = m.group(1)
            else:
                self._cur()["mod"] = m.group(1)
            return "OK"
        m = re.fullmatch(r"PM(\d{3})(?: (\d{8}))?", cmd)
        if m:
            n = int(m.group(1))
            if not 1 <= n <= CHANNELS:
                return "NG"
            if m.group(2) is not None:
                f = from_wire(m.group(2))
                if f and not 25_000_000 <= f <= 1_300_000_000:
                    return "NG"
                self.mem[n]["f"] = f
                self.mem[n]["l"] = f == 0
                st.update(md=1, ch=n)
            return self._pm(n)
        m = re.fullmatch(r"MA(\d{3})", cmd)
        if m:
            st.update(md=1, ch=int(m.group(1)))
            return self._pm(st["ch"])
        m = re.fullmatch(r"TA ([CBS]) (\d{3}|[A-J])(?: (.*))?", cmd)
        if m:
            kind, key, text = m.groups()
            store = {"C": None, "B": self.bank_tags, "S": self.search_tags}[kind]
            if text is not None:
                if kind == "C":
                    self.mem[int(key)]["tag"] = text.rstrip()
                else:
                    store[key] = text.rstrip()
                return "OK"
            value = self.mem[int(key)]["tag"] if kind == "C" else store[key]
            return f"TA {kind} {key} {value}"
        m = re.fullmatch(r"L([LU]) ([A-J])", cmd)
        if m:
            return f"L{m.group(1)}00000000 {m.group(2)}"
        m = re.fullmatch(r"SB(?: ([A-J]+))?", cmd)
        if m:
            if m.group(1):
                self.banks = "".join(sorted(set(m.group(1))))
            return f"SB {self.banks}"
        m = re.fullmatch(r"RF(\d{8})\?", cmd)
        if m:
            st.update(md=8, vfo=from_wire(m.group(1)))
            return f"RF{m.group(1)}"
        if cmd == "RF":
            return f"RF{to_wire(st['vfo'])}" if st["md"] == 8 else "NG"
        if cmd == "ST":
            return "ST 25K"
        m = re.fullmatch(r"CS(\d{3})?", cmd)
        if m:
            if m.group(1):
                self._cur()["n"] = int(m.group(1))
                return "OK"
            return f"CS{self._cur()['n']:03d}"
        m = re.fullmatch(r"KEY(\d\d)(H?)(?: \d)?", cmd)
        if m:
            k = m.group(1)
            if k == "00":
                st["md"] = 0
            elif k == "01":
                st["md"] = 1
            elif k == "07" and st["md"] == 1:
                self._step_channel(1)
            elif k == "08" and st["md"] == 1:
                self._step_channel(-1)
            return "OK"
        per_channel = {"DL": "d", "LO": "l", "AT": "a", "AR": "r"}
        m = re.fullmatch(r"(DL|AT|PR|MU|LT|BP|QU|ID|RI|CT|AR|LO|EL)([NFAD])?", cmd)
        if m:
            code, val = m.groups()
            if val is None:
                if code in per_channel and st["md"] == 1:
                    return f"{code}{'N' if self._cur()[per_channel[code]] else 'F'}"
                return f"{code}{st[code]}"
            if code in per_channel and st["md"] == 1:
                self._cur()[per_channel[code]] = val == "N"
            st[code] = val
            return "OK"
        if cmd == "DS":
            return "NG"
        return "ERR"
