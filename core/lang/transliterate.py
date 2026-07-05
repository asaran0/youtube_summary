"""
core/lang/transliterate.py — Mixed-language text cleanup for TTS.

Supports three language modes, set per-mode via cfg.LANGUAGE:

  "hi"   Pure Hindi content (Devanagari script). English loanwords/
         acronyms still appear occasionally — these are transliterated
         to Hindi phonetics so the Hindi-voice TTS pronounces them
         correctly instead of skipping or mangling them.

  "en"   Pure English content. No transliteration needed — text is
         left as-is for an English-speaking TTS voice/model.

  "hig"  Hinglish — Roman-script mixed Hindi-English (NOT Devanagari).
         Input looks like: "Microservices ek architectural style hai".
         Strategy: use Kokoro's English voice; apply phonetic nudges to
         common Hindi connector words so the English voice pronounces
         "hai", "me", "ke" etc. naturally instead of reading them as
         English words.  Technical English terms are left untouched.
         See core/lang/roman_hindi.py for the full phonetics map.

Any TTS strategy calls clean_text() before synthesizing — this keeps
language-handling logic in one place shared by every backend.
"""

import re

from core.lang.dictionary import EN_TO_HI_PHONETIC

# Acronym fallback: spells out unknown ALL-CAPS short tokens letter-by-
# letter in Hindi, e.g. "API" → "ए पी आई". Only used for "hi" mode.
_LETTER_MAP = {
    "a": "ए", "b": "बी", "c": "सी", "d": "डी", "e": "ई",
    "f": "एफ", "g": "जी", "h": "एच", "i": "आई", "j": "जे",
    "k": "के", "l": "एल", "m": "एम", "n": "एन", "o": "ओ",
    "p": "पी", "q": "क्यू", "r": "आर", "s": "एस", "t": "टी",
    "u": "यू", "v": "वी", "w": "डब्ल्यू", "x": "एक्स",
    "y": "वाई", "z": "ज़ेड",
}

_ENGLISH_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*")


def clean_text(text: str, cfg) -> str:
    """
    Clean text before sending to any TTS engine.

    Removes timestamps, URLs, bracketed noise, repeated punctuation, and
    excess whitespace — then applies language-specific handling based on
    cfg.LANGUAGE ("hi" / "en" / "hig").
    """
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    # Strip parenthetical content — shown on screen but NOT spoken.
    for _ in range(5):
        stripped = re.sub(r"\([^()]*\)", "", text)
        if stripped == text:
            break
        text = stripped
    text = re.sub(r"[।\.]{2,}", "।", text)
    text = re.sub(r"\s+", " ", text).strip()

    language = getattr(cfg, "LANGUAGE", "hi")

    if language == "hi":
        # Pure Hindi (Devanagari): transliterate English words → Hindi phonetics
        text = transliterate_english_in_hindi(text, cfg)

    elif language == "hig":
        # Roman-script Hinglish: nudge Hindi connector words toward
        # English-TTS-friendly phonetics; leave English technical terms alone.
        # Import lazily so other modes pay zero import cost.
        from core.lang.roman_hindi import preprocess_roman_hinglish
        text = preprocess_roman_hinglish(text)

    # "en" — nothing to transliterate, left as-is

    return text


def transliterate_english_in_hindi(text: str, cfg=None) -> str:
    """
    Replace English words inside Hindi/Hinglish text with their Hindi
    phonetic equivalents.  Used for "hi" mode (Devanagari) only.

    Strategy (in order):
    1. Mode-specific cfg.EXTRA_PHONETIC_DICT (checked first — can override).
    2. Shared EN_TO_HI_PHONETIC dictionary (core/lang/dictionary.py).
    3. Genuine acronyms (ALL CAPS, 2-6 letters) → spelled out letter by letter.
    4. Any other unknown word → left as-is.
    """
    extra_dict = getattr(cfg, "EXTRA_PHONETIC_DICT", {}) if cfg else {}

    def replace_word(match: re.Match) -> str:
        word = match.group(0)
        lower = word.lower()

        if lower in extra_dict:
            return extra_dict[lower]
        if lower in EN_TO_HI_PHONETIC:
            return EN_TO_HI_PHONETIC[lower]

        is_all_caps_acronym = word.isupper() and 2 <= len(word) <= 6
        if is_all_caps_acronym:
            return " ".join(_LETTER_MAP.get(c.lower(), c) for c in word)

        return word

    return _ENGLISH_WORD_RE.sub(replace_word, text)
_LETTER_MAP = {
    "a": "ए", "b": "बी", "c": "सी", "d": "डी", "e": "ई",
    "f": "एफ", "g": "जी", "h": "एच", "i": "आई", "j": "जे",
    "k": "के", "l": "एल", "m": "एम", "n": "एन", "o": "ओ",
    "p": "पी", "q": "क्यू", "r": "आर", "s": "एस", "t": "टी",
    "u": "यू", "v": "वी", "w": "डब्ल्यू", "x": "एक्स",
    "y": "वाई", "z": "ज़ेड",
}

