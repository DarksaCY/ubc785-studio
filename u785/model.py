"""Data model: memory channels, frequency parsing and formatting."""
import re

from .i18n import _
from dataclasses import dataclass, field, asdict

CHANNELS = 500
BANKS = "ABCDEFGHIJ"
PER_BANK = 50
MODULATIONS = ["AUTO", "AM", "FM", "NFM", "WFM"]

FREQ_MIN_HZ = 25_000_000
FREQ_MAX_HZ = 1_300_000_000


def bank_of(number: int) -> str:
    return BANKS[(number - 1) // PER_BANK]


def bank_range(letter: str) -> range:
    i = BANKS.index(letter.upper())
    return range(i * PER_BANK + 1, (i + 1) * PER_BANK + 1)


_UNITS = {"HZ": 1, "K": 1_000, "KHZ": 1_000, "КГЦ": 1_000, "M": 1_000_000, "MHZ": 1_000_000,
          "МГЦ": 1_000_000, "G": 1_000_000_000, "GHZ": 1_000_000_000, "ГГЦ": 1_000_000_000}


def parse_freq(text) -> int:
    """Parse a user-entered frequency into Hz.

    Accepts '145.5', '145,500', '145.500.000', '145500k', '145.5 MHz', '433075000',
    '1.2975G'. A bare number is read as MHz below 2000, kHz below 2 000 000, Hz above.
    Empty / '0' means an empty channel (returns 0).
    """
    if text is None:
        return 0
    s = str(text).strip().upper().replace(" ", "").replace("_", "")
    if s in ("", "0", "-", "---"):
        return 0
    m = re.fullmatch(r"([0-9.,]+)([A-ZА-Я]*)", s)
    if not m:
        raise ValueError(_("Not a frequency: {text}", text=repr(text)))
    num, unit = m.groups()
    if unit and unit not in _UNITS:
        raise ValueError(_("Unknown unit: {unit}", unit=repr(unit)))
    num = num.replace(",", ".")
    if num.count(".") > 1:
        # 145.500.000 style digit grouping -> plain Hz (or kHz with a unit)
        num = num.replace(".", "")
        value = float(num)
        mult = _UNITS[unit] if unit else 1
    else:
        value = float(num)
        if unit:
            mult = _UNITS[unit]
        elif value < 2_000:
            mult = 1_000_000
        elif value < 2_000_000:
            mult = 1_000
        else:
            mult = 1
    # Scanner resolution is 100 Hz; drop the rest like the radio display does
    # (446.00625 -> 446.0062). The epsilon absorbs float error in e.g. 145.55*1e6.
    hz = int(value * mult / 100.0 + 1e-6) * 100
    return hz


def validate_freq(hz: int) -> str | None:
    """Return an error message, or None if the frequency is acceptable."""
    if hz == 0:
        return None
    if hz < FREQ_MIN_HZ or hz > FREQ_MAX_HZ:
        return _("{f} MHz is outside 25–1300 MHz", f=format_mhz(hz))
    return None


def format_mhz(hz: int, empty: str = "") -> str:
    if not hz:
        return empty
    return f"{hz / 1_000_000:.4f}"


def to_wire(hz: int) -> str:
    """Frequency in the 8-digit, 100 Hz units the scanner uses."""
    return f"{hz // 100:08d}"


def from_wire(digits: str) -> int:
    return int(digits) * 100


@dataclass
class Channel:
    number: int
    freq_hz: int = 0
    mod: str = "AUTO"
    tag: str = ""
    tone: int = 0
    delay: bool = True
    lockout: bool = False
    atten: bool = False
    record: bool = False
    dirty: bool = field(default=False, compare=False)

    @property
    def bank(self) -> str:
        return bank_of(self.number)

    @property
    def empty(self) -> bool:
        return self.freq_hz == 0

    def content(self) -> dict:
        d = asdict(self)
        d.pop("dirty")
        return d

    def copy_from(self, other: "Channel") -> None:
        for k, v in other.content().items():
            if k != "number":
                setattr(self, k, v)

    def clear(self) -> None:
        self.copy_from(Channel(self.number))


def blank_memory() -> list[Channel]:
    return [Channel(n) for n in range(1, CHANNELS + 1)]


_TRANSLIT = dict(zip(
    "абвгдеёжзийклмнопрстуфхцчшщъыьэюя",
    ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r",
     "s", "t", "u", "f", "h", "ts", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"],
))


def radio_text(text: str, width: int = 16) -> str:
    """Make a tag the radio can display: transliterate Cyrillic, drop non-ASCII, pad to width."""
    out = []
    for c in text:
        low = c.lower()
        if low in _TRANSLIT:
            t = _TRANSLIT[low]
            out.append(t.capitalize() if c != low else t)
        elif 32 <= ord(c) < 127:
            out.append(c)
        else:
            out.append("?")
    return "".join(out)[:width].ljust(width)
