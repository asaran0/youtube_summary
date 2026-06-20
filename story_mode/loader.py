"""
story_mode/loader.py — Read a plain text story file into TTS-ready segments.

Strips timestamp headers like [00:00:00 - 00:02:11] if present (so a
document copy-pasted with chapter markers still works), splits on
sentence-ending punctuation, and returns segments shaped like the
output of a transcription step — start/end are placeholders since
real timing comes from TTS generation later.
"""

import re


def load_text_file(path: str) -> list[dict]:
    """
    Read a story text file and return segments ready for summarization.

    Timestamps are fake placeholders (1 second apart) — real timing is
    set later by core.tts.pipeline once narration audio is generated.
    """
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    raw = re.sub(r"\[\d{2}:\d{2}:\d{2}[^\]]*\]", "", raw)
    sentences = re.split(r"(?<=[।.?!])\s+", raw.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        raise ValueError(f"No text found in {path}")

    seg_dur = 1.0
    return [
        {
            "id": i,
            "start": round(i * seg_dur, 2),
            "end": round((i + 1) * seg_dur, 2),
            "text": text,
            "avg_logprob": -0.1,
            "no_speech_prob": 0.01,
        }
        for i, text in enumerate(sentences)
    ]
