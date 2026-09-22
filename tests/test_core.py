import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from u785 import tones
from u785.csvio import export_csv, parse_csv_text, read_csv
from u785.model import Channel, parse_freq, radio_text, bank_of, format_mhz
from u785.protocol import Scanner, SIM_PORT, parse_lcd, parse_pm, parse_tag, signal_bars


@pytest.mark.parametrize("text,hz", [
    ("145.5", 145_500_000), ("145,500", 145_500_000), ("145.500.000", 145_500_000),
    ("145500k", 145_500_000), ("145.5 MHz", 145_500_000), ("433075000", 433_075_000),
    ("1.2975G", 1_297_500_000), ("446006.25", 446_006_200), ("145.55", 145_550_000), ("156.8 МГц", 156_800_000),
    ("", 0), ("0", 0), ("121.5", 121_500_000),
])
def test_parse_freq(text, hz):
    assert parse_freq(text) == hz


def test_parse_freq_rejects_garbage():
    with pytest.raises(ValueError):
        parse_freq("abc")


def test_tones_roundtrip():
    assert tones.label(0) == "OFF"
    assert tones.parse("88.5") == 8
    assert tones.label(8) == "CTCSS 88.5"
    assert tones.parse("DCS 023") == 39
    assert tones.label(142) == "DCS 754"
    for code in range(0, 143):
        assert tones.parse(tones.label(code)) == code


# Replies captured from a real UBC785XLT (UB343ZH, fw 107).
def test_parse_real_pm():
    ch = parse_pm("C001 F01306250 TF DN LF AF RF N000", 1)
    assert (ch.number, ch.freq_hz, ch.delay, ch.lockout, ch.tone) == (1, 130_625_000, True, False, 0)
    empty = parse_pm("C010 F00000000 TF DF LN AF RF N000", 10)
    assert empty.empty and empty.lockout and not empty.delay


def test_parse_real_tag_and_lcd():
    assert parse_tag("TA C 001 PFO Tower Main", "TA C 001") == "PFO Tower Main"
    assert parse_tag("TA B A AVIATION", "TA B A") == "AVIATION"
    assert parse_tag("TA S A ", "TA S A") == ""
    rows = parse_lcd(["LCD1 [         C 102  ][                ]",
                      "LCD2 [ 156.1000 NFM   ][                ]",
                      "LCD3 [VHF Channel 2   ][                ]",
                      "LCD4 [MARINE          ][                ]"])
    assert rows[1].strip() == "156.1000 NFM" and rows[3].strip() == "MARINE"


def test_signal_bars():
    assert [signal_bars(x) for x in (0, 58, 66, 90, 100, 130, 200)] == [0, 1, 2, 3, 4, 5, 6]


def test_radio_text():
    assert radio_text("Аэропорт Пулково") == "Aeroport Pulkovo"
    assert len(radio_text("x")) == 16


def test_csv_roundtrip():
    chans = [Channel(1, 130_625_000, "AM", "Tower", 0), Channel(2), Channel(51, 145_500_000, "NFM", "Calling", 8, lockout=True)]
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "x.csv")
        assert export_csv(chans, path) == 2
        back, warnings = read_csv(path)
    assert not warnings
    assert [c.content() for c in back] == [chans[0].content(), chans[2].content()]


def test_csv_forgiving_import():
    text = "Частота;Название;Модуляция\n145,500;Позывной;FMN\n9999;bad;AM\n433.075;LPD1;\n"
    items, warnings = parse_csv_text(text)
    assert [c.freq_hz for c in items] == [145_500_000, 433_075_000]
    assert items[0].mod == "NFM" and items[0].tag == "Позывной" and items[1].mod == "AUTO"
    assert len(warnings) == 1


def test_simulator_write_read_cycle():
    s = Scanner(SIM_PORT)
    assert "UBC785XLT" in s.identify()["model"]
    ch = Channel(200, 145_550_000, "NFM", "Тест", tones.parse("88.5"), delay=False, atten=True)
    back = s.write_channel(ch)
    assert back.freq_hz == 145_550_000 and back.tone == 8 and not back.delay and back.atten
    assert s.read_tag(200) == "Test"
    s.write_channel(Channel(200))
    assert s.read_channel(200).empty
    assert bank_of(200) == "D" and format_mhz(0, "—") == "—"
