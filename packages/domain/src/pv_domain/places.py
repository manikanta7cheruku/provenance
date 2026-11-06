"""Other names for the same city (C-63), so "Bangalore" and "Bengaluru" are one place.

Both duplicate detection and eligibility compare place words, so both go through `canonical_word`.
Only well known renamings are listed; a word that is not here is left as it is.
"""

CITY_ALIASES: dict[str, str] = {
    "bangalore": "bengaluru",
    "bombay": "mumbai",
    "madras": "chennai",
    "calcutta": "kolkata",
    "gurgaon": "gurugram",
    "poona": "pune",
    "trivandrum": "thiruvananthapuram",
    "cochin": "kochi",
    "baroda": "vadodara",
    "mysore": "mysuru",
    "vizag": "visakhapatnam",
    "benares": "varanasi",
    "new delhi": "delhi",
    "ho chi minh": "saigon",
    "peking": "beijing",
    "nyc": "new york",
}

_SINGLE_WORD = {k: v for k, v in CITY_ALIASES.items() if " " not in k}
_PHRASES = {k: v for k, v in CITY_ALIASES.items() if " " in k}


def canonical_word(word: str) -> str:
    """One word of a place, lower case, with a known alternative name replaced."""
    return _SINGLE_WORD.get(word, word)


def canonical_phrase(text: str) -> str:
    """Lower case text with known multi word aliases replaced ("new delhi" becomes "delhi")."""
    for phrase, name in _PHRASES.items():
        if phrase in text:
            text = text.replace(phrase, name)
    return text
