"""
qa_mode/loader.py — Read a Q&A text file into TTS-ready segments.

Input file format:

    Q: आपकी ताकत क्या है?
    A: मेरी सबसे बड़ी ताकत यह है कि...

    Q: आप इस कंपनी में क्यों काम करना चाहते हैं?
    A: मैंने आपकी कंपनी के बारे में पढ़ा है...

Each question becomes 4 chunks:
  1. QUESTION     — spoken plainly, displayed with cfg.QA_QUESTION_LABEL_TEMPLATE
                     (if cfg.QA_SHOW_QUESTION_LABEL), styled "question".
  2. TRY_YOURSELF — silent, cfg.QA_TRY_YOURSELF_SECONDS long, displays
                     cfg.QA_TRY_YOURSELF_TEXT, styled "try_yourself".
  3. COUNTDOWN    — silent, cfg.QA_COUNTDOWN_SECONDS long, displays
                     "3 2 1" countdown, styled "countdown".
  4. ANSWER       — spoken normally, styled "answer".

Every chunk carries a "style" tag that core/render/subtitles.py uses
(via qa_mode/styles.py's resolve_style) to pick font size + color.
"""

import re


def parse_qa_text(raw: str) -> list[tuple[str, str]]:
    """Parse raw 'Q: ... A: ...' text into a list of (question, answer) tuples.
    Shared by load_qa_file() (reads from disk) and the API's text/file-upload
    input path (reads from an uploaded file or request body)."""
    pattern = re.compile(r"Q:\s*(.+?)\s*A:\s*(.+?)(?=\n\s*Q:|\Z)", re.DOTALL)
    pairs = pattern.findall(raw)
    if not pairs:
        raise ValueError("No 'Q: ... A: ...' pairs found in the given text")
    return pairs


def load_qa_file(path: str, cfg) -> list[dict]:
    """Read a Q&A file and return segments ready for TTS + rendering."""
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    try:
        pairs = parse_qa_text(raw)
    except ValueError:
        raise ValueError(f"No 'Q: ... A: ...' pairs found in {path}")

    return build_qa_segments(pairs, cfg)


def build_qa_segments(pairs: list[tuple[str, str]], cfg) -> list[dict]:
    """
    Build TTS/render-ready segments from an in-memory list of (question, answer)
    pairs. This is the shared core used by load_qa_file() (CLI/file input) and
    by the API (direct JSON input) — the file is just one way to produce `pairs`.
    """
    if not pairs:
        raise ValueError("No Q/A pairs provided")

    segments = []
    seg_id = 0
    for q_num, (question, answer) in enumerate(pairs, start=1):
        question = " ".join(question.split())
        answer = " ".join(answer.split())

        if cfg.QA_SHOW_QUESTION_LABEL:
            display_question = cfg.QA_QUESTION_LABEL_TEMPLATE.format(n=q_num) + question
        else:
            display_question = question

        # 1. QUESTION — spoken plainly, no added cue, larger gold text
        segments.append({
            "id": seg_id,
            "start": float(seg_id),
            "end": float(seg_id + 1),
            "text": question,
            "display_text": display_question,
            "avg_logprob": -0.1,
            "no_speech_prob": 0.01,
            "style": "question",
        })
        seg_id += 1

        # 2. TRY_YOURSELF — silent, prompts viewer to pause and think
        segments.append({
            "id": seg_id,
            "start": float(seg_id),
            "end": float(seg_id + 1),
            "text": "",
            "display_text": cfg.QA_TRY_YOURSELF_TEXT,
            "avg_logprob": -0.1,
            "no_speech_prob": 0.01,
            "style": "try_yourself",
            "is_silent": True,
            "silent_duration": float(cfg.QA_TRY_YOURSELF_SECONDS),
        })
        seg_id += 1

        # 3. COUNTDOWN — silent, shows "3 2 1"
        countdown_text = " ".join(str(n) for n in range(cfg.QA_COUNTDOWN_SECONDS, 0, -1))
        segments.append({
            "id": seg_id,
            "start": float(seg_id),
            "end": float(seg_id + 1),
            "text": "",
            "display_text": countdown_text,
            "avg_logprob": -0.1,
            "no_speech_prob": 0.01,
            "style": "countdown",
            "is_silent": True,
            "silent_duration": float(cfg.QA_COUNTDOWN_SECONDS),
        })
        seg_id += 1

        # 4. ANSWER — spoken normally, white text
        segments.append({
            "id": seg_id,
            "start": float(seg_id),
            "end": float(seg_id + 1),
            "text": answer,
            "display_text": answer,
            "avg_logprob": -0.1,
            "no_speech_prob": 0.01,
            "style": "answer",
            "is_answer": True,
        })
        seg_id += 1

    return segments
