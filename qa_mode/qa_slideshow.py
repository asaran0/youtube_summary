"""
qa_mode/qa_slideshow.py — Split-layout video renderer for Q&A mode.

Layout:
    ┌─────────────────────────────────┐
    │  Question (bold, centred)       │  ← top band
    ├─────────────────────────────────┤
    │  Answer revealed word-by-word,  │  ← bottom band
    │  currently-spoken word highlighted
    └─────────────────────────────────┘

Font selection is language-aware:
  LANGUAGE="en"  → Latin fonts (DejaVu/Arial/Liberation — no boxes)
  LANGUAGE="hi"  → Devanagari fonts (FreeSerif/Kohinoor)
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from utils import get_logger

log = get_logger("qa_slideshow")

# ── Language-aware font candidate lists ──────────────────────────────────────

_LATIN_FONT_CANDIDATES = [
    "assets/fonts/NotoSans-Regular.ttf",
    # Linux
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    # macOS
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Verdana.ttf",
    "/Library/Fonts/Verdana.ttf",
]

_DEVANAGARI_FONT_CANDIDATES = [
    "assets/NotoSansDevanagari-Regular.ttf",
    "assets/fonts/NotoSansDevanagari-Regular.ttf",
    # Linux
    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    # macOS — Kohinoor has both Devanagari AND Latin
    "/System/Library/Fonts/Kohinoor.ttc",
    "/Library/Fonts/Kohinoor.ttf",
    "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc",
]


def _load_fonts(font_path_hint: str, cfg) -> tuple:
    """Return (font_question, font_answer) — language-aware."""
    lang   = getattr(cfg, "LANGUAGE", "en").lower()
    q_size = getattr(cfg, "QA_SLIDE_QUESTION_FONT_SIZE", 68)
    a_size = getattr(cfg, "QA_SLIDE_ANSWER_FONT_SIZE",   50)

    if lang == "en":
        candidates = list(_LATIN_FONT_CANDIDATES)
    else:
        candidates = list(_DEVANAGARI_FONT_CANDIDATES)
        if font_path_hint and os.path.exists(font_path_hint):
            candidates.insert(0, font_path_hint)

    for p in getattr(cfg, "FALLBACK_FONT_SEARCH_PATHS", []):
        candidates.append(p)
    for p in getattr(cfg, "HINDI_FONT_SEARCH_PATHS", []):
        candidates.append(p)

    def _load(size):
        for path in candidates:
            if not path or not os.path.exists(path):
                continue
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
        log.warning("No suitable font for lang=%s; using PIL default", lang)
        return ImageFont.load_default()

    return _load(q_size), _load(a_size)


# ── Core slide renderer ───────────────────────────────────────────────────────

def _render_slide(
    video_width, video_height,
    q_band_h, a_band_h,
    q_bg, a_bg,
    q_lines, a_lines,
    font_q, font_a,
    q_color, a_color,
    margin_side, margin_top_q, margin_top_a,
    # Highlight params — word currently being spoken
    active_word: int = -1,          # global word index across all a_lines (-1 = no highlight)
    highlight_color: tuple = (255, 216, 76),
) -> Image.Image:
    img  = Image.new("RGB", (video_width, video_height))
    draw = ImageDraw.Draw(img)

    # Fill bands
    draw.rectangle([0, 0, video_width, q_band_h], fill=q_bg)
    draw.rectangle([0, q_band_h, video_width, video_height], fill=a_bg)

    # ── Question: vertically centred, horizontally centred ────────────────
    q_lh      = _line_height(font_q)
    total_q_h = len(q_lines) * q_lh + max(0, len(q_lines) - 1) * 8
    y = max((q_band_h - total_q_h) // 2, margin_top_q)
    for line in q_lines:
        tw = _text_width(draw, line, font_q)
        x  = (video_width - tw) // 2
        draw.text((x + 2, y + 2), line, font=font_q, fill=(0, 0, 0, 50))  # shadow
        draw.text((x, y), line, font=font_q, fill=q_color)
        y += q_lh + 8

    # ── Answer: top-aligned, with per-word highlight ───────────────────────
    a_lh       = _line_height(font_a)
    y          = q_band_h + margin_top_a
    word_index = 0  # cumulative word counter across lines

    for line in a_lines:
        x = margin_side
        tokens = _text_tokens(line)   # ["word", " ", "word", ...]
        for token in tokens:
            is_word = bool(token.strip())
            if is_word and word_index == active_word:
                color = highlight_color
            else:
                color = a_color
            draw.text((x, y), token, font=font_a, fill=color)
            tw = _text_width(draw, token, font_a)
            x += tw
            if is_word:
                word_index += 1
        y += a_lh + 4

    return img


# ── Text helpers ──────────────────────────────────────────────────────────────

def _text_tokens(text: str) -> list[str]:
    """Split into alternating word/whitespace tokens, preserving spaces."""
    import re
    return re.findall(r"\S+|\s+", text)


def _wrap_text_px(text: str, font, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    dummy = Image.new("RGB", (1, 1))
    draw  = ImageDraw.Draw(dummy)
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if current and _text_width(draw, trial, font) > max_width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def _paginate(lines: list[str], max_per_page: int) -> list[list[str]]:
    if not lines:
        return [[""]]
    return [lines[i : i + max_per_page] for i in range(0, len(lines), max_per_page)]


def _split_sentences(text: str) -> list[str]:
    """Split answer text into sentences on '.', '?', '!', '।' (Hindi
    full stop). Keeps the terminator attached to its sentence, mirroring
    story_mode/loader.py's sentence splitting."""
    import re
    parts = re.split(r"(?<=[।.!?])\s+", text.strip())
    return [p for p in parts if p.strip()]


def _paginate_by_sentence(text: str, font, max_width: int, max_lines_per_page: int) -> list[list[str]]:
    """
    Paginate answer text so each page holds one or more *complete*
    sentences, never cutting a sentence across two pages — unless a single
    sentence alone is longer than a full page, in which case only that
    sentence falls back to a hard line-count split. This is what makes a
    long answer read as "paragraph by paragraph" instead of an arbitrary
    wall-of-text chopped at a fixed line count.
    """
    sentences = _split_sentences(text)
    if not sentences:
        return [[""]]

    pages: list[list[str]] = []
    current: list[str] = []

    for sentence in sentences:
        lines = _wrap_text_px(sentence, font, max_width)

        if len(lines) > max_lines_per_page:
            # A single sentence is too long for one page on its own —
            # flush what we have, then hard-split just this sentence.
            if current:
                pages.append(current)
                current = []
            for i in range(0, len(lines), max_lines_per_page):
                pages.append(lines[i : i + max_lines_per_page])
            continue

        if current and len(current) + len(lines) > max_lines_per_page:
            pages.append(current)
            current = list(lines)
        else:
            current.extend(lines)

    if current:
        pages.append(current)

    return pages or [[""]]


def _count_words_in_lines(lines: list[str]) -> int:
    return sum(1 for line in lines for t in _text_tokens(line) if t.strip())


def _text_width(draw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _line_height(font) -> int:
    dummy = Image.new("RGB", (1, 1))
    draw  = ImageDraw.Draw(dummy)
    bbox  = draw.textbbox((0, 0), "Agj|ÄÅकि", font=font)
    return bbox[3] - bbox[1]


def _parse_color(val) -> tuple:
    if isinstance(val, (list, tuple)):
        return tuple(int(v) for v in val)
    if isinstance(val, str) and val.startswith("#"):
        h = val.lstrip("#")
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
    return (200, 200, 200)
