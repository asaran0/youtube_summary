"""
narration_adapter.py - Make selected transcript chunks feel more narrative.

This is intentionally lightweight and offline. It does not invent new facts or
call an LLM; it adds short framing/transition phrases so the generated voice
sounds more like an explainer than raw transcript stitching.
"""

import config
from utils import get_logger

log = get_logger("narration")

HINDI_INTRO = ""
ENGLISH_INTRO = ""
# HINDI_INTRO = "चलिए, इसे कहानी की तरह आसान भाषा में समझते हैं।"
# ENGLISH_INTRO = "Let's understand this in a simple, story-like way."

HINDI_TRANSITIONS = [
    "अब ध्यान से समझिए,",
    "यहां सबसे जरूरी बात यह है कि",
    "आगे कहानी में बात आती है कि",
    "इसे आसान शब्दों में कहें तो",
    "अब अगला हिस्सा इसे और साफ करता है:",
]

ENGLISH_TRANSITIONS = [
    "Now, here is the important part:",
    "In simple words,",
    "The next idea makes this clearer:",
    "Here is what matters most:",
    "Think of it this way:",
]


def apply_storytelling(chunks: list[dict]) -> list[dict]:
    """Add light narrative pacing to chunk text before TTS/subtitles."""
    if not config.STORYTELLING_MODE or not chunks:
        return chunks

    intro = ENGLISH_INTRO if config.LANGUAGE == "en" else HINDI_INTRO
    transitions = ENGLISH_TRANSITIONS if config.LANGUAGE == "en" else HINDI_TRANSITIONS

    transition_count = 0
    for index, chunk in enumerate(chunks):
        text = _clean_text(chunk.get("text", ""))
        if not text:
            continue

        prefix = ""
        if index == 0 and config.STORYTELLING_ADD_INTRO:
            prefix = intro + " "
        elif (
            config.STORYTELLING_ADD_TRANSITIONS
            and transition_count < config.STORYTELLING_MAX_TRANSITIONS
            and index % 2 == 1
        ):
            prefix = transitions[transition_count % len(transitions)] + " "
            transition_count += 1

        chunk["original_text"] = chunk.get("original_text", text)
        chunk["text"] = prefix + text

    log.info("Applied storytelling narration style")
    return chunks


def _clean_text(text: str) -> str:
    return " ".join(text.split()).strip()
