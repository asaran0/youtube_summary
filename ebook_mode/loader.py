"""
ebook_mode/loader.py — Parse a structured book-summary text file into
typed chunks ready for TTS and rendering.

Supported markup (plain text, no HTML):
─────────────────────────────────────────────────────────────────────
# Book Title                          ← book title (parsed once)
## Author: Robert Kiyosaki            ← metadata line
## Tagline: What the Rich Teach...    ← metadata line

## Chapter 1: Rich Dad, Poor Dad      ← chapter heading  (chunk_type="chapter_card")
### Key Lesson                         ← lesson heading   (chunk_type="lesson")
The rich don't work for money.         ← narration        (chunk_type="narration")

> "The poor and middle class work      ← block quote      (chunk_type="quote")
>  for money. The rich have money
>  work for them."

Regular narration continues here.
─────────────────────────────────────────────────────────────────────

Each returned chunk dict has:
    id            int   — sequential index
    chunk_type    str   — "chapter_card" | "lesson" | "quote" | "narration"
    text          str   — text spoken by TTS
    display_text  str   — text shown on screen (may differ — quotes get stripped >)
    chapter_num   int   — which chapter this belongs to (0 = intro)
    chapter_title str   — title of that chapter
    total_chapters int  — total chapter count (filled in after parsing)
    start / end   float — placeholder timing (replaced by TTS pipeline)
    avg_logprob   float — placeholder
    no_speech_prob float
"""

import re
from utils import get_logger

log = get_logger("ebook.loader")


def load_ebook_file(path: str, cfg=None) -> dict:
    """
    Parse the ebook text file.

    Returns:
        {
            "book_title":   str,
            "author":       str,
            "tagline":      str,
            "chunks":       list[dict],
            "chapter_list": list[{"num": int, "title": str}],
        }
    """
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    lines = raw.splitlines()

    book_title    = ""
    author        = ""
    tagline       = ""
    chapter_list  = []
    chunks        = []

    current_chapter_num   = 0
    current_chapter_title = "Introduction"

    chunk_id    = 0
    seg_dur     = 1.0     # placeholder — replaced by TTS pipeline
    pending_quote_lines: list[str] = []

    def _flush_quote():
        nonlocal chunk_id, pending_quote_lines
        if not pending_quote_lines:
            return
        raw_text = " ".join(pending_quote_lines).strip()
        display  = re.sub(r'^[">]\s*', "", raw_text).strip().strip('"').strip()
        spoken   = display  # TTS reads the clean text, no punctuation symbol
        chunks.append(_make_chunk(
            chunk_id, "quote", spoken, display,
            current_chapter_num, current_chapter_title, seg_dur,
        ))
        chunk_id += 1
        pending_quote_lines = []

    def _add_narration(text: str):
        nonlocal chunk_id
        sentences = _split_sentences(text)
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            chunks.append(_make_chunk(
                chunk_id, "narration", s, s,
                current_chapter_num, current_chapter_title, seg_dur,
            ))
            chunk_id += 1

    for raw_line in lines:
        line = raw_line.rstrip()

        # ── Book title ─────────────────────────────────────────────────────
        if line.startswith("# ") and not line.startswith("## "):
            book_title = line[2:].strip()
            continue

        # ── Metadata lines (Author / Tagline / etc.) ───────────────────────
        if line.startswith("## ") and ":" in line:
            rest = line[3:].strip()
            key, _, val = rest.partition(":")
            key = key.strip().lower()
            val = val.strip()
            if key == "author":
                author = val
                continue
            elif key == "tagline":
                tagline = val
                continue
            # If it looks like "Chapter N: Title" fall through below

        # ── Chapter heading ────────────────────────────────────────────────
        chapter_match = re.match(
            r"^##\s+(?:Chapter\s+)?(\d+)[:\.\s]\s*(.+)$", line, re.IGNORECASE
        )
        if chapter_match:
            _flush_quote()
            current_chapter_num   = int(chapter_match.group(1))
            current_chapter_title = chapter_match.group(2).strip()
            chapter_list.append({
                "num":   current_chapter_num,
                "title": current_chapter_title,
            })
            lang = getattr(cfg, "LANGUAGE", "en")
            if lang in ("hi", "hig"):
                spoken_card = f"अध्याय {current_chapter_num}। {current_chapter_title}।"
            else:
                spoken_card = f"Chapter {current_chapter_num}. {current_chapter_title}."
            chunks.append(_make_chunk(
                chunk_id, "chapter_card", spoken_card, current_chapter_title,
                current_chapter_num, current_chapter_title, seg_dur,
            ))
            chunk_id += 1
            continue

        # ── Section / Key Lesson heading (###) ────────────────────────────
        if line.startswith("### "):
            _flush_quote()
            lesson_text = line[4:].strip()
            lang        = getattr(cfg, "LANGUAGE", "en")
            _skip_labels = {
                "en":  {"key lesson", "lesson", "summary", "key point", "key idea"},
                "hi":  {"मुख्य सीख", "सीख", "सारांश", "मुख्य बिंदु"},
                "hig": {"key lesson", "lesson", "key sikh", "mukhya seekh"},
            }
            skip = _skip_labels.get(lang, _skip_labels["en"])
            if lesson_text.lower().strip("।.") in skip:
                # The heading IS the lesson label — speak it as-is, no prefix
                spoken = lesson_text
            elif lang in ("hi", "hig"):
                spoken = f"मुख्य सीख — {lesson_text}"
            else:
                spoken = f"Key lesson. {lesson_text}."
            chunks.append(_make_chunk(
                chunk_id, "lesson", spoken, lesson_text,
                current_chapter_num, current_chapter_title, seg_dur,
            ))
            chunk_id += 1
            continue

        # ── Block quote lines (start with > ) ─────────────────────────────
        if line.startswith(">"):
            q_text = line[1:].strip().strip('"').strip()
            if q_text:
                pending_quote_lines.append(q_text)
            continue

        # ── Non-quote line: flush any pending quote first ──────────────────
        if pending_quote_lines and line.strip():
            _flush_quote()

        # ── Empty line: just flush any pending quote ───────────────────────
        if not line.strip():
            _flush_quote()
            continue

        # ── Regular narration ──────────────────────────────────────────────
        _add_narration(line)

    # Flush any trailing quote
    _flush_quote()

    total = len(chapter_list)
    for c in chunks:
        c["total_chapters"] = total

    # Re-stamp placeholder timestamps sequentially
    for i, c in enumerate(chunks):
        c["start"] = round(i * seg_dur, 2)
        c["end"]   = round((i + 1) * seg_dur, 2)

    log.info(
        "Parsed '%s' by %s — %d chapters, %d chunks",
        book_title or path, author or "unknown", total, len(chunks),
    )

    return {
        "book_title":   book_title,
        "author":       author,
        "tagline":      tagline,
        "chunks":       chunks,
        "chapter_list": chapter_list,
    }


# ── Helpers ────────────────────────────────────────────────────────────────

def _make_chunk(
    cid: int, chunk_type: str, text: str, display_text: str,
    chapter_num: int, chapter_title: str, seg_dur: float,
) -> dict:
    return {
        "id":              cid,
        "chunk_type":      chunk_type,
        "text":            text,
        "display_text":    display_text,
        "chapter_num":     chapter_num,
        "chapter_title":   chapter_title,
        "total_chapters":  0,   # filled in after full parse
        "start":           round(cid * seg_dur, 2),
        "end":             round((cid + 1) * seg_dur, 2),
        "avg_logprob":     -0.1,
        "no_speech_prob":  0.01,
    }


def _split_sentences(text: str) -> list[str]:
    """
    Split a paragraph into individual sentences for TTS chunking.

    Handles:
    - English: . ? !  (skips abbreviations like Mr. Dr. etc.)
    - Hindi / Devanagari: । (danda, U+0964) and ॥ (double danda, U+0965)
    - Hinglish: both of the above mixed together
    """
    # Normalise double danda to single for splitting purposes
    text = text.replace("॥", "।")

    # Split on Hindi danda first (simple — danda never appears mid-word)
    if "।" in text:
        raw_parts = re.split(r"।\s*", text.strip())
        parts = [p.strip() for p in raw_parts if p.strip()]
        # If each part still has English sentences inside, split those too
        result = []
        for part in parts:
            if re.search(r"[.?!]\s+[A-Za-z\u0900-\u097F]", part):
                result.extend(_split_english_sentences(part))
            else:
                result.append(part)
        return result or [text.strip()]

    return _split_english_sentences(text)


def _split_english_sentences(text: str) -> list[str]:
    """
    Split English text on sentence-ending punctuation (. ? !).
    Avoids splitting on common abbreviations (Mr. Dr. etc.) by checking
    whether the word before the dot is a known abbreviation.
    """
    ABBREVS = {"mr", "mrs", "ms", "dr", "prof", "sr", "jr", "vs",
               "etc", "approx", "dept", "viz", "fig", "vol", "no",
               "pp", "op", "inc", "ltd", "corp", "co"}

    # Split on any ./?/! followed by whitespace
    raw = re.split(r'([.?!])\s+', text.strip())
    # raw alternates:  sentence_fragment, punctuation, fragment, punctuation ...
    # Reconstruct sentences, skipping splits that look like abbreviations
    result  = []
    current = ""
    i = 0
    while i < len(raw):
        fragment = raw[i]
        if i + 1 < len(raw) and raw[i + 1] in ".?!":
            punct      = raw[i + 1]
            last_word  = fragment.rstrip().split()[-1].lower().rstrip(".,;:") if fragment.strip() else ""
            is_abbrev  = (last_word in ABBREVS or
                         (len(last_word) == 1 and last_word.isalpha()))
            if is_abbrev and punct == ".":
                current += fragment + punct + " "
                i += 2
            else:
                current += fragment + punct
                result.append(current.strip())
                current = ""
                i += 2
        else:
            current += fragment
            i += 1
    if current.strip():
        result.append(current.strip())

    return [s for s in result if s] or [text.strip()]
