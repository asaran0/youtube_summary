"""
core/lang/tokenize.py — Shared word tokenizer and stop-word list.

Used by both story_mode's summarizer (to score chunks by word
importance) and core/render's metadata writer (to extract keywords).
Kept in core/lang/ since this is language-processing logic, not
specific to either story or qa mode.
"""

import re

# Common Hindi + English stop-words (add more as needed)
STOPWORDS = {
    "और", "में", "है", "के", "को", "से", "का", "की", "पर", "यह",
    "इस", "वह", "तो", "भी", "एक", "लेकिन", "जो", "हो", "होता",
    "हैं", "था", "थी", "थे", "जब", "तब", "कि", "ने", "हम", "आप",
    "मैं", "वो", "इन", "उन", "ये", "वे", "उस", "इसे", "उसे",
    "कोई", "कुछ", "सब", "सभी", "अब", "या", "नहीं", "नही", "बहुत",
    "अपने", "अपना", "अपनी", "जैसे", "जैसा", "ही", "रहा", "रही",
    "सकते", "सकता", "सकती", "करते", "करता", "करती", "करना",
    "the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
    "of", "for", "to", "and", "or", "but", "not", "this", "that",
}


def tokenize(text: str) -> list[str]:
    """Split text into lowercase words, stripping punctuation, removing stop-words."""
    words = re.findall(r"[\w']+", text.lower())
    return [w for w in words if w not in STOPWORDS]
