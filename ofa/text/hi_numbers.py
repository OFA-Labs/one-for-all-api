"""Spoken Hindi/Hinglish numbers, times and relative dates (§4.2; Deepgram numerals don't cover Hindi).
Works on Devanagari and Roman script. Pure functions; used to normalize commands for the engine."""
from __future__ import annotations

import datetime as dt
import re

ROMAN_UNITS = {
    "shunya": 0, "zero": 0, "ek": 1, "do": 2, "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "panch": 5, "chhe": 6,
    "che": 6, "chah": 6, "saat": 7, "sat": 7, "aath": 8, "aat": 8, "nau": 9, "das": 10, "dus": 10, "gyarah": 11,
    "barah": 12, "baarah": 12, "terah": 13, "chaudah": 14, "pandrah": 15, "pandrah": 15, "solah": 16, "satrah": 17,
    "atharah": 18, "unnis": 19, "bees": 20, "bis": 20, "ikkis": 21, "bais": 22, "teis": 23, "chaubis": 24,
    "pachchis": 25, "pachis": 25, "chhabbis": 26, "sattais": 27, "atthais": 28, "untis": 29, "tees": 30, "tis": 30,
    "ikattis": 31, "battis": 32, "taintis": 33, "chautis": 34, "paintis": 35, "chhattis": 36, "saintis": 37,
    "adtis": 38, "untalis": 39, "chalis": 40, "chaalis": 40, "iktalis": 41, "bayalis": 42, "taintalis": 43,
    "chavalis": 44, "paintalis": 45, "chhiyalis": 46, "saintalis": 47, "adtalis": 48, "unchas": 49, "pachas": 50,
    "pachaas": 50, "saath": 60, "sattar": 70, "assi": 80, "nabbe": 90, "nabbey": 90,
}
DEV_UNITS = {"शून्य": 0, "एक": 1, "दो": 2, "तीन": 3, "चार": 4, "पांच": 5, "पाँच": 5, "छह": 6, "छः": 6, "सात": 7,
             "आठ": 8, "नौ": 9, "दस": 10, "ग्यारह": 11, "बारह": 12, "तेरह": 13, "चौदह": 14, "पंद्रह": 15, "सोलह": 16,
             "सत्रह": 17, "अठारह": 18, "उन्नीस": 19, "बीस": 20, "पच्चीस": 25, "तीस": 30, "चालीस": 40, "पचास": 50,
             "साठ": 60, "सत्तर": 70, "अस्सी": 80, "नब्बे": 90}
SCALES = {"sau": 100, "so": 100, "सौ": 100, "hazaar": 1000, "hazar": 1000, "हज़ार": 1000, "हजार": 1000,
          "lakh": 100000, "laakh": 100000, "लाख": 100000, "crore": 10**7, "karod": 10**7, "करोड़": 10**7}
FRACTIONS = {"dedh": 1.5, "डेढ़": 1.5, "dhai": 2.5, "dhaai": 2.5, "ढाई": 2.5}
PREFIX = {"saadhe": 0.5, "sadhe": 0.5, "साढ़े": 0.5, "sava": 0.25, "sawa": 0.25, "सवा": 0.25,
          "paune": -0.25, "pone": -0.25, "पौने": -0.25}
UNITS = {**ROMAN_UNITS, **DEV_UNITS}
DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")


def _num_token(tok: str) -> float | None:
    tok = tok.translate(DIGITS)
    if re.fullmatch(r"\d+(\.\d+)?", tok):
        return float(tok)
    if tok in UNITS:
        return float(UNITS[tok])
    if tok in FRACTIONS:
        return FRACTIONS[tok]
    return None


def parse_number(text: str) -> float | None:
    """'do sau pachas' -> 250, 'dedh lakh' -> 150000, 'saadhe teen hazaar' -> 3500, 'paune do' -> 1.75."""
    toks = re.findall(r"[\wऀ-ॿ.]+", text.casefold())
    total, current, seen, mod = 0.0, 0.0, False, 0.0
    for t in toks:
        if t in PREFIX:
            mod = PREFIX[t]
            continue
        v = _num_token(t)
        if v is not None:
            current += v
            seen = True
            continue
        if t in SCALES and seen:
            scale = SCALES[t]
            base = (current or 1)
            if mod:
                base = base + mod if mod > 0 else base - 0.25
                mod = 0
            if scale == 100:
                current = base * 100
            else:
                total += base * scale
                current = 0
            continue
    if not seen:
        return None
    if mod:
        current = current + mod if mod > 0 else current - 0.25
    return total + current


def parse_time(text: str) -> dt.time | None:
    """'saadhe paanch baje' -> 05:30 (17:30 with shaam/raat), 'shaam ke saat' -> 19:00, '7:15' -> 07:15."""
    s = text.casefold().translate(DIGITS)
    if m := re.search(r"\b(\d{1,2})[:.](\d{2})\b", s):
        h, mnt = int(m[1]), int(m[2])
    else:
        n = parse_number(s)
        if n is None:
            return None
        h, mnt = int(n), int(round((n - int(n)) * 60))
    if re.search(r"shaam|sham|raat|evening|night|pm|शाम|रात|dopahar|दोपहर", s) and h < 12:
        h += 12 if not (re.search(r"dopahar|दोपहर", s) and h == 12) else 0
    if re.search(r"subah|morning|am|सुबह", s) and h == 12:
        h = 0
    if not (0 <= h < 24 and 0 <= mnt < 60):
        return None
    return dt.time(h, mnt)


WEEKDAYS = {"somvaar": 0, "somvar": 0, "सोमवार": 0, "monday": 0, "mangalvaar": 1, "mangalvar": 1, "मंगलवार": 1,
            "tuesday": 1, "budhvaar": 2, "budhvar": 2, "बुधवार": 2, "wednesday": 2, "guruvaar": 3, "guruvar": 3,
            "veervaar": 3, "गुरुवार": 3, "thursday": 3, "shukravaar": 4, "shukravar": 4, "शुक्रवार": 4, "friday": 4,
            "shanivaar": 5, "shanivar": 5, "शनिवार": 5, "saturday": 5, "ravivaar": 6, "ravivar": 6, "itvaar": 6,
            "रविवार": 6, "sunday": 6}


def parse_date(text: str, today: dt.date | None = None) -> dt.date | None:
    """'aaj' today, 'kal' (future context) tomorrow, 'parson' +2, 'agle somvaar' next Monday."""
    today = today or dt.date.today()
    s = text.casefold()
    if re.search(r"\b(aaj|today)\b|आज", s):
        return today
    if re.search(r"\b(parson|parso|day after tomorrow)\b|परसों", s):
        return today + dt.timedelta(days=2)
    if re.search(r"\b(kal|tomorrow)\b|कल", s):
        return today + dt.timedelta(days=1)
    for word, wd in WEEKDAYS.items():
        if word in s:
            delta = (wd - today.weekday()) % 7 or 7
            if re.search(r"agle|next|अगले", s) and delta < 7 and wd <= today.weekday():
                pass
            return today + dt.timedelta(days=delta)
    return None


AMBIGUOUS_SINGLE = {"do", "so", "sat", "che", "ek", "das", "nau", "tis", "bis", "char"}


def number_hints(text: str) -> list[tuple[str, float]]:
    """Whole-word runs of Hindi number words -> value. Never rewrites the user's text."""
    words = re.findall(r"[\wऀ-ॿ]+", text)
    hints, run = [], []

    def flush():
        if run and any(w.casefold() in UNITS or w.casefold() in FRACTIONS for w in run):
            phrase = " ".join(run)
            if not (len(run) == 1 and run[0].casefold() in AMBIGUOUS_SINGLE):
                n = parse_number(phrase)
                if n is not None:
                    hints.append((phrase, n))
        run.clear()
    for w in words:
        k = w.casefold()
        if k in UNITS or k in SCALES or k in FRACTIONS or k in PREFIX:
            run.append(w)
        else:
            flush()
    flush()
    return hints


def normalize_numbers(text: str) -> str:
    """The user's text unchanged, plus a bracketed digit hint for spoken Hindi numbers."""
    hints = number_hints(text)
    if not hints:
        return text
    shown = "; ".join(f"{p} = {int(n) if n == int(n) else n}" for p, n in hints)
    return f"{text} [number words: {shown}]"
