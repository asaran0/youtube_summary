"""
qa_mode/loader.py — Read a Q&A text file into TTS-ready segments.

Input file format:
    Q: What is an Abstract Class?
    A: An abstract class can have both abstract methods (without a body)
       and concrete methods (with a body).

Key behaviours:
  • Parenthetical content like (without a body) is SHOWN on screen but
    NOT spoken by TTS. This keeps the display rich while the word-by-word
    highlight stays perfectly in sync with the voice.
  • Answer display text is formatted into visual paragraphs by inserting
    a newline after every sentence boundary (. ? ! ।).
  • Pause after question is 1 second (TTS_ANSWER_PAUSE_EXTRA in config).
"""

import re


# ── Text helpers ──────────────────────────────────────────────────────────────

# def _strip_parens(text: str) -> str:
#     """
#     Remove all parenthetical content for TTS narration.
#     '(without a body)' → '' so the spoken word count matches display.
#     Handles nested and multiple parentheses cleanly.
#     """
#     # Remove (...) content — repeat to handle nested
#     result = text
#     for _ in range(5):
#         new = re.sub(r'\([^()]*\)', '', result)
#         if new == result:
#             break
#         result = new
#     # Collapse extra spaces left behind
#     return re.sub(r'  +', ' ', result).strip()

def _strip_parens(text: str) -> str:
    text = re.sub(r"[()]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def _spoken_words(text: str) -> list[str]:
    """Return the word list as TTS will speak them (parens stripped)."""
    return _strip_parens(text).split()


def _format_answer_display(text: str) -> str:
    """
    Format answer text for visual display:
    - Preserve parenthetical content (shown on screen)
    - Insert a blank line (\\n\\n) after every sentence ending (. ? ! ।)
      so the answer reads as clean paragraphs, not one dense block.
    - Bullet points (lines starting with - or •) each get their own line.
    """
    # Normalise whitespace first
    text = re.sub(r'\s+', ' ', text).strip()

    # Handle bullet points: insert \n\n before each bullet marker (- or •)
    # so they each appear on their own line
    text = re.sub(r'\s*[-•]\s+', r'\n\n• ', text)

    # Insert \n\n after sentence-ending punctuation followed by ANY next word
    # (capital OR lowercase OR Hindi) — not just capitals
    text = re.sub(
        r'([.?!।])\s+(?=[A-Za-z\u0900-\u097F])',
        r'\1\n\n',
        text,
    )

    # Clean up: remove leading/trailing blank lines
    text = text.strip()
    return text


# ── Main loader ───────────────────────────────────────────────────────────────

def load_qa_file(path: str, cfg) -> list[dict]:
    """Read a Q&A file and return segments ready for TTS + rendering."""
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    pattern = re.compile(r"Q(\d*):\s*(.+?)\s*A:\s*(.+?)(?=\n\s*Q:|\Z)", re.DOTALL)
    pairs = pattern.findall(raw)

    if not pairs:
        raise ValueError(f"No 'Q: ... A: ...' pairs found in {path}")

    segments = []
    seg_id = 0

    for q_num, (num, question, answer) in enumerate(pairs, start=1):
        question = " ".join(question.split())
        answer_raw = " ".join(answer.split())

        
        # ── Question ─────────────────────────────────────────────────────
        if cfg.QA_SHOW_QUESTION_LABEL:
            display_question = cfg.QA_QUESTION_LABEL_TEMPLATE.format(n=q_num) + question
        else:
            display_question = question
        if num:
            display_question = f"Q{num}.\n{display_question}"
        # Question: spoken text = display text (questions rarely have parens)
        segments.append({
            "id": seg_id,
            "start": float(seg_id),
            "end": float(seg_id + 1),
            "text": _strip_parens(question),
            "display_text": display_question,
            "avg_logprob": -0.1,
            "no_speech_prob": 0.01,
            "style": "question",
        })
        seg_id += 1

        # ── Try yourself (silent) ────────────────────────────────────────
        # segments.append({
        #     "id": seg_id,
        #     "start": float(seg_id),
        #     "end": float(seg_id + 1),
        #     "text": "",
        #     "display_text": cfg.QA_TRY_YOURSELF_TEXT,
        #     "avg_logprob": -0.1,
        #     "no_speech_prob": 0.01,
        #     "style": "try_yourself",
        #     "is_silent": True,
        #     "silent_duration": float(cfg.QA_TRY_YOURSELF_SECONDS),
        # })
        # seg_id += 1

        # ── Countdown (silent) ───────────────────────────────────────────
        # countdown_text = " ".join(str(n) for n in range(cfg.QA_COUNTDOWN_SECONDS, 0, -1))
        # segments.append({
        #     "id": seg_id,
        #     "start": float(seg_id),
        #     "end": float(seg_id + 1),
        #     "text": "",
        #     "display_text": countdown_text,
        #     "avg_logprob": -0.1,
        #     "no_speech_prob": 0.01,
        #     "style": "countdown",
        #     "is_silent": True,
        #     "silent_duration": float(cfg.QA_COUNTDOWN_SECONDS),
        # })
        # seg_id += 1

        # ── Answer ───────────────────────────────────────────────────────
        # text       → TTS speaks this (parens stripped)
        # display_text → shown on screen (parens kept, formatted into paragraphs)
        spoken_text  = _strip_parens(answer_raw)
        display_text = _format_answer_display(answer_raw)

        segments.append({
            "id": seg_id,
            "start": float(seg_id),
            "end": float(seg_id + 1),
            "text": spoken_text,
            "display_text": display_text,
            "spoken_text": spoken_text,       # explicit field for runner highlight sync
            "avg_logprob": -0.1,
            "no_speech_prob": 0.01,
            "style": "answer",
            "is_answer": True,
        })
        seg_id += 1

    return segments
