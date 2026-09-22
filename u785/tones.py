"""CTCSS/DCS tone table used by the BC780/BC785 family.

Codes on the wire: 000 = off, 001-038 = CTCSS, 039-142 = DCS.
"""

from .i18n import _

CTCSS = [
    67.0, 71.9, 74.4, 77.0, 79.7, 82.5, 85.4, 88.5, 91.5, 94.8,
    97.4, 100.0, 103.5, 107.2, 110.9, 114.8, 118.8, 123.0, 127.3, 131.8,
    136.5, 141.3, 146.2, 151.4, 156.7, 162.2, 167.9, 173.8, 179.9, 186.2,
    192.8, 203.5, 210.7, 218.1, 225.7, 233.6, 241.8, 250.3,
]

DCS = [
    23, 25, 26, 31, 32, 36, 43, 47, 51, 53, 54, 65, 71, 72, 73, 74,
    114, 115, 116, 122, 125, 131, 132, 134, 143, 145, 152, 155, 156, 162, 165, 172,
    174, 205, 212, 223, 225, 226, 243, 244, 245, 246, 251, 252, 255, 261, 263, 265,
    266, 271, 274, 306, 311, 315, 325, 331, 332, 343, 346, 351, 356, 364, 365, 371,
    411, 412, 413, 423, 431, 432, 445, 446, 452, 454, 455, 462, 464, 465, 466, 503,
    506, 516, 523, 526, 532, 546, 565, 606, 612, 624, 627, 631, 632, 654, 662, 664,
    703, 712, 723, 731, 732, 734, 743, 754,
]

assert len(CTCSS) == 38 and len(DCS) == 104

MAX_CODE = len(CTCSS) + len(DCS)  # 142


def label(code: int) -> str:
    if code <= 0 or code > MAX_CODE:
        return "OFF"
    if code <= len(CTCSS):
        return f"CTCSS {CTCSS[code - 1]:.1f}"
    return f"DCS {DCS[code - len(CTCSS) - 1]:03d}"


ALL_LABELS = [label(c) for c in range(0, MAX_CODE + 1)]


def parse(text) -> int:
    """Accept a code number, 'OFF', '88.5', 'CTCSS 88.5', 'DCS 023', 'D023'."""
    if text is None:
        return 0
    s = str(text).strip().upper().replace(",", ".")
    if s in ("", "OFF", "NONE", "-", "0", "000", "НЕТ"):
        return 0
    is_dcs = s.startswith("DCS") or (s.startswith("D") and s[1:].strip().isdigit())
    num = s.replace("CTCSS", "").replace("DCS", "").replace("HZ", "").lstrip("D").strip()
    try:
        value = float(num)
    except ValueError:
        raise ValueError(_("Unknown tone: {text}", text=repr(text)))
    if is_dcs:
        if int(value) in DCS:
            return len(CTCSS) + DCS.index(int(value)) + 1
        raise ValueError(_("Unknown DCS code: {text}", text=repr(text)))
    if "." in num:
        for i, t in enumerate(CTCSS):
            if abs(t - value) < 0.05:
                return i + 1
        raise ValueError(_("Unknown CTCSS tone: {text}", text=repr(text)))
    code = int(value)
    if 0 <= code <= MAX_CODE:
        return code
    raise ValueError(_("Unknown tone: {text}", text=repr(text)))
