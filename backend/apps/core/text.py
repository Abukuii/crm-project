"""Qidiruv uchun matnni normallashtirish: kirill ↔ lotin, apostroflar, registr.

"Цемент М-400", "sement m400" va "SEMENT" bir xil kalitga keladi.
"""

import re

_CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo", "ж": "j",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "x", "ц": "s",
    "ч": "ch", "ш": "sh", "щ": "sh", "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu",
    "я": "ya", "ў": "o", "қ": "q", "ғ": "g", "ҳ": "h",
}  # fmt: skip

_APOSTROPHES = re.compile(r"[ʻʼ'`’‘]")
_NON_WORD = re.compile(r"[^a-z0-9]+")


def normalize(text: str) -> str:
    if not text:
        return ""
    text = text.lower()
    text = "".join(_CYR_TO_LAT.get(ch, ch) for ch in text)
    text = _APOSTROPHES.sub("", text)  # o'zbek → ozbek, g'isht → gisht
    text = text.replace("ts", "s")  # tsement → sement
    text = _NON_WORD.sub(" ", text)
    return " ".join(text.split())


def search_key(text: str) -> str:
    """Bo'shliqsiz variant: "m 400" va "m400" ham mos kelishi uchun."""
    return normalize(text).replace(" ", "")
