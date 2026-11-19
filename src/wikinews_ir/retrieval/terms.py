"""Compare literal query words with the complete archived article."""

import re
import unicodedata

_WORD = re.compile(r"[^\W_]+")


def query_words(query):
    words = {}
    for token in _WORD.findall(unicodedata.normalize("NFC", query)):
        words.setdefault(token.casefold(), token)
    return words


def missing_terms(words, source):
    if not words or not isinstance(source.get("body"), str):
        return []
    remaining = set(words)
    for field in ("title", "body"):
        for token in _WORD.finditer(unicodedata.normalize("NFC", source.get(field) or "")):
            remaining.discard(token.group().casefold())
            if not remaining:
                return []
    return [original for key, original in words.items() if key in remaining]
