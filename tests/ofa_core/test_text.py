"""B5 Hindi numbers/dates/times, B6 transliteration, D1–D3 verbatim + punctuation."""
import datetime as dt

import pytest

from ofa.text.dictation import find_span, spoken_punctuation, verbatim
from ofa.text.hi_numbers import normalize_numbers, parse_date, parse_number, parse_time
from ofa.text.translit import apply_script, has_devanagari, to_roman

NUMBERS = [("ek", 1), ("do", 2), ("paanch", 5), ("das", 10), ("pachchis", 25), ("pachas", 50), ("sau", None),
           ("ek sau", 100), ("do sau", 200), ("do sau pachas", 250), ("teen hazaar", 3000), ("dedh", 1.5),
           ("dhai", 2.5), ("dedh sau", 150), ("dhai hazaar", 2500), ("dedh lakh", 150000), ("do lakh", 200000),
           ("ek crore", 10**7), ("saadhe teen", 3.5), ("sava do", 2.25), ("paune do", 1.75), ("saadhe teen hazaar", 3500),
           ("paanch hazaar do sau", 5200), ("एक", 1), ("दो सौ", 200), ("तीन हज़ार", 3000), ("डेढ़ लाख", 150000),
           ("साढ़े पांच", 5.5), ("पौने दो", 1.75), ("२५", 25), ("150", 150), ("bees", 20), ("chalis", 40),
           ("nabbe", 90), ("assi", 80), ("saath", 60), ("sattar", 70), ("unnis", 19), ("gyarah", 11)]


@pytest.mark.parametrize("text,value", NUMBERS)
def test_numbers(text, value):
    assert parse_number(text) == value


TIMES = [("saadhe paanch baje", dt.time(5, 30)), ("shaam ke saat baje", dt.time(19, 0)), ("7:15", dt.time(7, 15)),
         ("raat nau baje", dt.time(21, 0)), ("subah das baje", dt.time(10, 0)), ("paune do baje", dt.time(1, 45)),
         ("sava aath", dt.time(8, 15)), ("शाम पांच बजे", dt.time(17, 0)), ("dopahar barah baje", dt.time(12, 0)),
         ("5 pm", dt.time(17, 0))]


@pytest.mark.parametrize("text,value", TIMES)
def test_times(text, value):
    assert parse_time(text) == value


MON = dt.date(2026, 11, 23)   # a Monday


@pytest.mark.parametrize("text,delta", [("aaj", 0), ("kal", 1), ("parson", 2), ("tomorrow", 1), ("आज", 0),
                                        ("कल", 1), ("परसों", 2), ("agle shukravaar", 4), ("friday", 4),
                                        ("somvaar", 7), ("next monday", 7)])
def test_dates(text, delta):
    assert parse_date(text, MON) == MON + dt.timedelta(days=delta)


def test_normalize_numbers_keeps_words_and_adds_digits():
    out = normalize_numbers("do sau pachas rupaye bhejo")
    assert out.startswith("do sau pachas (250)") and "rupaye bhejo" in out
    assert normalize_numbers("do it now") == "do it now"


def test_translit_changes_script_only():
    src = "कल मिलते हैं, ठीक है"
    out = to_roman(src)
    assert not has_devanagari(out)
    assert len(out.split()) == len(src.split())
    assert apply_script("hello दोस्त", "as_spoken") == "hello दोस्त"
    mixed = to_roman("meeting कल 5 बजे है")
    assert mixed.split()[0] == "meeting" and "5" in mixed.split()


def test_spoken_punctuation():
    assert spoken_punctuation("hello comma how are you question mark") == "hello, how are you?"
    assert spoken_punctuation("done full stop new line next item") == "done.\nnext item"


def test_find_span_exact_words_only():
    said = "Asha ko likho: Kal milte hain, theek hai? Aur bhej do"
    assert find_span(said, "kal milte hain theek hai") == "Kal milte hain, theek hai?"
    assert find_span(said, "we will meet tomorrow") is None
    assert find_span(said, "") is None


def test_verbatim_preserves_language_mix():
    assert verbatim("bro kal ka plan cancel karo comma sorry") == "bro kal ka plan cancel karo, sorry"
