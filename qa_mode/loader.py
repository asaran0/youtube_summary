"""
qa_mode/loader.py — Read a Q&A text file into TTS-ready segments.

Input file format (both styles accepted):

    Plain labels:
        Q: What is an Abstract Class?
        A: An abstract class can have both abstract methods (without a body)
           and concrete methods (with a body).

    Numbered labels:
        Q1: What is an Abstract Class?
        A1: An abstract class can have both abstract methods (without a body)
            and concrete methods (with a body).

        Q2: What is Kafka?
        A2: Kafka is a distributed event streaming platform.

Key behaviours:
  • Parenthetical content like (without a body) is SHOWN on screen but
    NOT spoken by TTS. This keeps the display rich while the word-by-word
    highlight stays perfectly in sync with the voice.
  • Answer display text is formatted into visual paragraphs by inserting
    a newline after every sentence boundary (. ? ! ।).
  • Pause after question is 1 second (TTS_ANSWER_PAUSE_EXTRA in config).
"""

import re
import textwrap

# Sentinel used to encode a code block as a single opaque "word" inside
# display_text, so the word-by-word reveal machinery (which operates on
# whitespace-split tokens) treats the whole block as one unit instead of
# shredding its line breaks. \u0001/\u0002 are control chars that will
# never appear in real question/answer text.
_CODE_FIELD_SEP = "\u0001"
_CODE_LINE_SEP  = "\u0002"
_CODE_TAG       = "\u0001CODE\u0001"

_FENCE_RE = re.compile(r"```([A-Za-z0-9_+-]*)[ \t]*\n?(.*?)```", re.DOTALL)

# Optional explanation right after a fence, written as a markdown blockquote:
#   ```bash
#   git revert <commit-id>
#   ```
#   > This undoes the buggy commit by creating a new one that reverses it.
# Captures one or more consecutive "> ..." lines immediately following the
# closing fence (allowing blank lines/whitespace right after the fence).
# Used as an optional FINAL summary after a code block (line-by-line or not).
_EXPLAIN_RE = re.compile(r"^[ \t]*\n*((?:^[ \t]*>[^\n]*\n?)+)", re.MULTILINE)

# Marker prepended to a final-summary explanation paragraph's display text —
# wrapped in parens so the EXISTING paren-stripping logic makes it invisible
# to TTS (the explanation sentence itself, after the marker, is fully spoken).
_EXPLAIN_MARKER = "(\U0001F4A1)"  # (💡)

# ── Line-by-line code walkthrough markers ──────────────────────────────────
# A fenced code block where one or more lines end in "## comment text"
# switches into "walkthrough mode": each code line is spoken + highlighted
# word-by-word (monospace card), immediately followed by its own comment
# spoken + highlighted in a distinct colour — like narrating a command in
# an interview ("first we do this, then this..."). These are real words in
# both spoken_text and display_text (not opaque), so they go through the
# normal word-reveal/highlight machinery; \u0010/\u0011/\u0013 are control
# characters glued to the front of a paragraph's first word — they never
# add an extra "word" to the count, just flag how that paragraph renders.
_CODE_LINE_MARK = "\u0010"   # paragraph = one spoken/highlighted code row
_COMMENT_MARK   = "\u0011"   # paragraph = one spoken/highlighted in-card comment row
_FIELD_SEP      = "\u0014"   # separates pos/lang/text fields glued onto a paragraph


def _encode_code_block(lang: str, code: str) -> str:
    """Pack a fenced code block into one sentinel-delimited token that
    survives whitespace collapsing and .split() intact."""
    # Dedent (removes common leading whitespace) but keep relative
    # indentation — important for Python/Java, harmless for bash/git.
    code = textwrap.dedent(code).strip("\n")
    lines = [ln.rstrip() for ln in code.split("\n")]
    return _CODE_TAG + (lang or "") + _CODE_FIELD_SEP + _CODE_LINE_SEP.join(lines)


def _split_code_lines_for_walkthrough(lang: str, code: str) -> list[tuple[str, tuple]] | None:
    """
    If any line in `code` has a trailing '## comment', parse the whole
    block into a line-by-line walkthrough rendered as ONE continuous
    VS-Code-style card: code rows in normal text colour, comment rows in
    a muted comment colour with a '#'/'//' prefix — exactly like reading
    a commented file top to bottom. Returns a list of
    ("codeline", (pos, lang, code_text)) / ("comment", (pos, lang, text))
    parts in speaking order, where `pos` (first/mid/last/only) tells the
    renderer when to draw the card's rounded top/header and rounded
    bottom, so consecutive rows stay visually joined into one block.
    Returns None if no line uses '##' (caller falls back to the silent
    single-card encoding instead).
    """
    code = textwrap.dedent(code).strip("\n")
    raw_lines = code.split("\n")
    parsed = []
    has_comment = False
    for ln in raw_lines:
        if "##" in ln:
            code_text, _, comment_text = ln.partition("##")
            code_text, comment_text = code_text.rstrip(), comment_text.strip()
            has_comment = True
        else:
            code_text, comment_text = ln.rstrip(), ""
        parsed.append((code_text, comment_text))

    if not has_comment:
        return None

    # Flatten into the actual row sequence (code row, then its comment row
    # if any) so we can compute first/mid/last/only across the WHOLE card.
    rows: list[tuple[str, str]] = []  # (role, text)
    for code_text, comment_text in parsed:
        if not code_text.strip():
            continue
        rows.append(("code", code_text))
        if comment_text:
            rows.append(("comment", comment_text))

    n = len(rows)
    parts: list[tuple[str, tuple]] = []
    for i, (role, text) in enumerate(rows):
        if n == 1:
            pos = "only"
        elif i == 0:
            pos = "first"
        elif i == n - 1:
            pos = "last"
        else:
            pos = "mid"
        kind = "codeline" if role == "code" else "comment"
        # lang is only needed on the very first row (draws the header once);
        # comments also carry it so the renderer can pick '#' vs '//'.
        parts.append((kind, (pos, lang, text)))
    return parts


def _take_explanation(text_after_fence: str) -> tuple[str, int]:
    """
    If `text_after_fence` starts with one or more '> ...' blockquote lines
    (the spoken explanation for the code block just above), return
    (explanation_text, chars_consumed). Otherwise ("", 0).
    """
    m = _EXPLAIN_RE.match(text_after_fence)
    if not m:
        return "", 0
    block = m.group(1)
    lines = [ln.split(">", 1)[1].strip() for ln in block.splitlines() if ">" in ln]
    explanation = " ".join(ln for ln in lines if ln)
    return explanation, m.end()


def _split_text_and_code(raw_answer: str) -> list[tuple[str, object]]:
    """
    Split a raw answer (with its original line breaks still intact) into
    an ordered list of parts, each a (kind, content) tuple:
      ("text", str)            — plain prose, gets paren-stripping etc.
      ("code", encoded_blob)   — a SILENT code block (no '##' lines) shown
                                  as one opaque card, never spoken.
      ("codeline", (lang, txt))— ONE line of a line-by-line walkthrough,
                                  spoken + highlighted like normal text.
      ("comment", str)         — that line's spoken inline comment.
      ("explain", str)         — optional final '> ...' summary after the
                                  whole block, spoken + shown as a callout.
    Must run BEFORE any whitespace collapsing, or multi-line code is lost.
    """
    parts: list[tuple[str, object]] = []
    pos = 0
    for m in _FENCE_RE.finditer(raw_answer):
        if m.start() > pos:
            parts.append(("text", raw_answer[pos:m.start()]))
        lang, code = m.group(1), m.group(2)

        walkthrough_parts = _split_code_lines_for_walkthrough(lang, code)
        if walkthrough_parts is not None:
            parts.extend(walkthrough_parts)
        else:
            parts.append(("code", _encode_code_block(lang, code)))
        pos = m.end()

        explanation, consumed = _take_explanation(raw_answer[pos:])
        if explanation:
            parts.append(("explain", explanation))
            pos += consumed
    if pos < len(raw_answer):
        parts.append(("text", raw_answer[pos:]))
    return parts


# ── Text helpers ──────────────────────────────────────────────────────────────

def _strip_parens(text: str) -> str:
    """
    Remove all parenthetical content for TTS narration.
    '(without a body)' → '' so the spoken word count matches display.
    Handles nested and multiple parentheses cleanly.
    """
    # Remove (...) content — repeat to handle nested
    result = text
    for _ in range(5):
        new = re.sub(r'\([^()]*\)', '', result)
        if new == result:
            break
        result = new
    # Collapse extra spaces left behind
    return re.sub(r'  +', ' ', result).strip()


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

    # Support both plain labels and numbered labels:
    #   Q: ...  A: ...          (original format)
    #   Q1: ... A1: ...         (numbered format — number is ignored; order is used)
    #   Q1: ... A: ...          (mixed — also accepted)
    pattern = re.compile(
        r"Q(\d*):\s*(.+?)\s*A\d*:\s*(.+?)(?=\n\s*Q\d*:|\Z)",
        re.DOTALL,
    )
    pairs = pattern.findall(raw)

    if not pairs:
        raise ValueError(
            f"No Q/A pairs found in {path}.\n"
            f"Accepted formats:\n"
            f"  Q: question text\n  A: answer text\n"
            f"  Q1: question text\n  A1: answer text"
        )

    segments = []
    seg_id = 0
    ques_no = 0

    for q_num, (num, question, answer) in enumerate(pairs, start=1):
        question = " ".join(question.split())

        # Resolve the question number FIRST — use the explicit number from
        # Q97:, Q98:, Q99: etc. (series number), fall back to loop index
        # only for plain Q: format with no number.
        if num:
            ques_no = int(num)
        else:
            ques_no = q_num

        # ── Question ─────────────────────────────────────────────────────
        if cfg.QA_SHOW_QUESTION_LABEL:
            display_question = cfg.QA_QUESTION_LABEL_TEMPLATE.format(n=ques_no) + question
        else:
            display_question = question
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
            "q_num": ques_no,
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
        # text       → TTS speaks this (parens AND code blocks stripped —
        #              code is never read aloud, it's shown as a visual card)
        # display_text → shown on screen (parens kept, code blocks kept
        #              intact with original line breaks, formatted into
        #              paragraphs)
        parts = _split_text_and_code(answer)  # use ORIGINAL (uncollapsed) answer
        spoken_chunks  = []
        display_chunks = []
        for kind, content in parts:
            if kind == "code":
                display_chunks.append(content)   # opaque sentinel token, kept as-is
            elif kind == "codeline":
                pos, lang, code_text = content
                code_text = code_text.strip()
                if not code_text:
                    continue
                spoken_chunks.append(code_text)  # speak the command like normal text
                prefix = _CODE_LINE_MARK + pos + _FIELD_SEP + (lang or "") + _FIELD_SEP
                display_chunks.append(prefix + code_text)
            elif kind == "comment":
                pos, lang, content_text = content
                collapsed = " ".join(content_text.split())
                if not collapsed:
                    continue
                spoken_chunks.append(collapsed)  # spoken right after its code line
                prefix = _COMMENT_MARK + pos + _FIELD_SEP + (lang or "") + _FIELD_SEP
                display_chunks.append(prefix + collapsed)
            elif kind == "explain":
                collapsed = " ".join(content.split())
                if not collapsed:
                    continue
                spoken_chunks.append(collapsed)  # spoken in full, naturally
                # Kept as ONE paragraph (not sentence-split) so the whole
                # explanation stays grouped under the code card. The
                # (💡) marker is invisible to TTS (existing paren-strip
                # logic), and flags this paragraph for callout styling.
                display_chunks.append(f"{_EXPLAIN_MARKER} {collapsed}")
            else:
                collapsed = " ".join(content.split())
                if not collapsed:
                    continue
                spoken_chunks.append(_strip_parens(collapsed))
                display_chunks.append(_format_answer_display(collapsed))

        spoken_text  = " ".join(c for c in spoken_chunks if c)
        display_text = "\n\n".join(c for c in display_chunks if c)

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
            "q_num": ques_no,          # 1-based question number for "Q 1" label
        })
        seg_id += 1

    return segments
