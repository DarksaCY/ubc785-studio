"""CSV import/export for channel memory.

Export always writes the canonical layout. Import is forgiving: it sniffs the
delimiter (, ; tab), accepts Russian/English header aliases, decimal commas and
any frequency notation parse_freq understands.
"""
import csv
import io

from . import tones
from .i18n import _
from .model import Channel, CHANNELS, MODULATIONS, format_mhz, parse_freq, validate_freq

HEADER = ["channel", "bank", "frequency_mhz", "modulation", "tag", "tone",
          "delay", "lockout", "attenuator", "record"]

ALIASES = {
    "channel": {"channel", "ch", "chan", "номер", "канал", "#", "no", "n", "mem", "memory"},
    "frequency_mhz": {"frequency_mhz", "frequency", "freq", "mhz", "частота", "rx", "rx freq",
                      "receive frequency", "output", "f"},
    "modulation": {"modulation", "mod", "mode", "модуляция", "режим"},
    "tag": {"tag", "alpha", "alpha tag", "name", "label", "description", "название", "имя",
            "метка", "описание", "comment"},
    "tone": {"tone", "ctcss", "dcs", "ctcss/dcs", "tone squelch", "тон", "субтон", "pl"},
    "delay": {"delay", "dly", "задержка"},
    "lockout": {"lockout", "l/o", "lo", "skip", "пропуск", "блок"},
    "attenuator": {"attenuator", "att", "аттенюатор"},
    "record": {"record", "rec", "line", "запись"},
}

_TRUE = {"1", "y", "yes", "true", "on", "n", "да", "+", "x", "вкл"}
_MOD_ALIASES = {"FMN": "NFM", "NBFM": "NFM", "FMW": "WFM", "WBFM": "WFM", "BFM": "WFM",
                "FM-N": "NFM", "FM-W": "WFM", "": "AUTO"}


def _flag(value: str, default: bool) -> bool:
    v = (value or "").strip().lower()
    if v == "":
        return default
    return v in _TRUE


def export_csv(channels: list[Channel], path: str, include_empty: bool = False) -> int:
    count = 0
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        for ch in channels:
            if ch.empty and not include_empty:
                continue
            w.writerow([ch.number, ch.bank, format_mhz(ch.freq_hz), ch.mod, ch.tag,
                        tones.label(ch.tone), int(ch.delay), int(ch.lockout),
                        int(ch.atten), int(ch.record)])
            count += 1
    return count


def _map_header(row: list[str]) -> dict[str, int] | None:
    mapping = {}
    for i, name in enumerate(row):
        key = name.strip().lower().replace("_", " ")
        for field, names in ALIASES.items():
            if field not in mapping and (key in names or key.replace(" ", "_") == field):
                mapping[field] = i
                break
    return mapping if "frequency_mhz" in mapping else None


def read_csv(path: str) -> tuple[list[Channel], list[str]]:
    """Return (channels, warnings). channel.number is 0 when the file has no channel column."""
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8-sig", "cp1251", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    return parse_csv_text(text)


def parse_csv_text(text: str) -> tuple[list[Channel], list[str]]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [r for r in csv.reader(io.StringIO(text), dialect) if any(c.strip() for c in r)]
    if not rows:
        return [], [_("File is empty")]
    mapping = _map_header(rows[0])
    if mapping:
        rows = rows[1:]
    else:
        # No recognizable header: assume "frequency[, tag]".
        mapping = {"frequency_mhz": 0, "tag": 1}

    out, warnings = [], []
    for line_no, row in enumerate(rows, start=2):
        get = lambda field: row[mapping[field]].strip() if field in mapping and mapping[field] < len(row) else ""
        try:
            hz = parse_freq(get("frequency_mhz"))
        except ValueError as e:
            warnings.append(_("Line {n}: {msg}", n=line_no, msg=e))
            continue
        err = validate_freq(hz)
        if err:
            warnings.append(_("Line {n}: {msg}", n=line_no, msg=err))
            continue
        number = 0
        if "channel" in mapping and get("channel"):
            try:
                number = int(float(get("channel")))
            except ValueError:
                warnings.append(_("Line {n}: channel number {value} not recognized", n=line_no, value=repr(get("channel"))))
            if not 0 <= number <= CHANNELS:
                warnings.append(_("Line {n}: channel {ch} outside 1–{max}", n=line_no, ch=number, max=CHANNELS))
                number = 0
        mod = get("modulation").upper()
        mod = _MOD_ALIASES.get(mod, mod)
        if mod not in MODULATIONS:
            warnings.append(_("Line {n}: modulation {mod} replaced with AUTO", n=line_no, mod=repr(mod)))
            mod = "AUTO"
        try:
            tone = tones.parse(get("tone"))
        except ValueError as e:
            warnings.append(_("Line {n}: {msg}", n=line_no, msg=e))
            tone = 0
        out.append(Channel(
            number=number, freq_hz=hz, mod=mod, tag=get("tag"), tone=tone,
            delay=_flag(get("delay"), True), lockout=_flag(get("lockout"), False),
            atten=_flag(get("attenuator"), False), record=_flag(get("record"), False),
        ))
    return out, warnings
