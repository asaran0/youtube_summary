"""
core/lang/transliterate.py — Mixed-language text cleanup for TTS.

Supports three language modes, set per-mode via cfg.LANGUAGE:

  "hi"   Pure Hindi content. English loanwords/acronyms still appear
         occasionally (brand names, technical terms) — these get
         transliterated to Hindi phonetics so the TTS voice (which is
         speaking in Hindi) pronounces them correctly instead of
         skipping them or mangling them.

  "en"   Pure English content. No transliteration needed — text is
         left as-is for an English-speaking TTS voice/model.

  "hig"  Hinglish — genuinely mixed Hindi and English in the same
         sentences (not just occasional loanwords, but real
         code-switching). Same transliteration as "hi" mode, since the
         Devanagari portions are still spoken by a Hindi-capable voice
         and the English portions need the same phonetic treatment.

Any TTS strategy (xtts / mms / macos) calls clean_text() before
synthesizing — this keeps the language-handling logic in one place
shared by every backend, rather than duplicated per strategy.
"""

import re

from core.lang.dictionary import EN_TO_HI_PHONETIC

# Acronym fallback: spells out unknown ALL-CAPS short tokens letter by
# letter in Hindi, e.g. "API" -> "ए पी आई". Only used when a word isn't
# in EN_TO_HI_PHONETIC and looks like a genuine acronym (not a real
# word like "try" or "final", which would sound broken if spelled out).
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

    Removes timestamps, URLs, bracketed noise, repeated punctuation,
    and excess whitespace — then applies language-specific handling
    based on cfg.LANGUAGE ("hi" / "en" / "hig").
    """
    print("*****")
    print(text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\[.*?\]", "", text)
    # Strip parenthetical content — shown on screen but NOT spoken.
    # Repeat up to 5x for nested parens e.g. ((like this)).
    # for _ in range(5):
    #     stripped = re.sub(r"\([^()]*\)", "", text)
    #     if stripped == text:
    #         break
    #     text = stripped
    # text = re.sub(r"[।\.]{2,}", "।", text)
    # text = re.sub(r"\s+", " ", text).strip()
    print("*************** ", text)

    language = getattr(cfg, "LANGUAGE", "hi")
    if language in ("hi", "hig"):
        text = transliterate_english_in_hindi(text, cfg)
    # "en" — nothing to transliterate, left as-is

    return text


def transliterate_english_in_hindi(text: str, cfg=None) -> str:
    """
    Replace English words inside Hindi/Hinglish text with their Hindi
    phonetic equivalents.

    Strategy (in order):
    1. Dictionary lookup (core/lang/dictionary.py) — covers common
       words plus programming/CS terms. Mode-specific extra entries
       (cfg.EXTRA_PHONETIC_DICT, if a mode config defines one) are
       checked first so a mode can override or extend the shared list
       without editing the shared dictionary.
    2. Genuine acronyms (ALL CAPS, 2-6 letters, e.g. "API", "SQL") not
       in any dictionary -> spelled out letter-by-letter.
    3. Any other unknown word -> left as-is; letter-spelling a real
       word like "try" or "final" sounds far worse than an imperfect
       attempt by the TTS engine itself.
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
