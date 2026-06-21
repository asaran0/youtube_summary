"""
qa_mode/qa_slideshow.py — Split-layout video renderer for Q&A mode.

Each slide is divided into two horizontal bands:

    ┌──────────────────────────────────────────┐
    │                                          │  ← QUESTION BAND (top %)
    │   How would you handle inter-service…?  │
    │                                          │
    ├──────────────────────────────────────────┤
    │                                          │  ← ANSWER BAND (bottom %)
    │   For simple, direct communication,      │
    │   I would use RestTemplate …             │
    │                                          │
    └──────────────────────────────────────────┘

The question text is always visible (static) on the top band.
The answer text is revealed word-by-word in the bottom band.

When the answer is long and won't fit in one slide, the renderer
automatically paginates: same question on top, continuation on next slide.

All visual settings (colors, font sizes, margins) come from cfg.
"""

import os
import subprocess
import numpy as np

from PIL import Image, ImageDraw, ImageFont
from utils import ensure_dirs, get_logger

log = get_logger("qa_slideshow")

# ─────────────────────────────────────────────────────────────
#  PUBLIC ENTRY POINT  (word-by-word via moviepy)
# ─────────────────────────────────────────────────────────────

def compile_qa_slideshow(
    qa_pairs: list[dict],
    audio_path: str,
    output_path: str,
    video_width: int,
    video_height: int,
    font_path: str,
    cfg,
) -> None:
    """
    Build a split-layout Q&A video with word-by-word answer reveal.

    qa_pairs — list of dicts:
        {question, answer, duration, start (cumulative in video), end}
    audio_path — TTS audio file (.wav or .mp3)
    output_path — final .mp4 destination
    """
    from moviepy import AudioFileClip, VideoClip

    ensure_dirs(cfg.TEMP_DIR, cfg.OUTPUT_DIR)

    font_q, font_a = _load_fonts(font_path, cfg)

    # ── Geometry ─────────────────────────────────────────────
    split_ratio  = getattr(cfg, "QA_SLIDE_SPLIT_RATIO", 0.35)
    margin_top_q = int(video_height * getattr(cfg, "QA_SLIDE_MARGIN_TOP_Q",  0.04))
    margin_top_a = int(video_height * getattr(cfg, "QA_SLIDE_MARGIN_TOP_A",  0.04))
    margin_bot_a = int(video_height * getattr(cfg, "QA_SLIDE_MARGIN_BOT_A",  0.10))
    margin_side  = int(video_width  * getattr(cfg, "QA_SLIDE_MARGIN_SIDE",   0.05))

    q_band_h = int(video_height * split_ratio)
    a_band_h = video_height - q_band_h

    q_bg    = _parse_color(getattr(cfg, "QA_SLIDE_QUESTION_BG",    (205, 139,  97)))
    a_bg    = _parse_color(getattr(cfg, "QA_SLIDE_ANSWER_BG",      (183, 204, 174)))
    q_color = _parse_color(getattr(cfg, "QA_SLIDE_QUESTION_COLOR", (30,  30,  30)))
    a_color = _parse_color(getattr(cfg, "QA_SLIDE_ANSWER_COLOR",   (30,  30,  30)))

    text_w   = video_width - 2 * margin_side
    a_line_h = _line_height(font_a)
    avail_a_h = a_band_h - margin_top_a - margin_bot_a
    max_a_lines = max(1, avail_a_h // (a_line_h + 4))

    # ── Pre-compute per-pair data ─────────────────────────────
    entries = []
    for pair in qa_pairs:
        q_lines   = _wrap_text_px(pair["question"], font_q, text_w)
        all_words = pair["answer"].split()
        entries.append({
            "q_lines":   q_lines,
            "all_words": all_words,
            "start":     pair["video_start"],   # seconds within output video
            "end":       pair["video_end"],
        })

    total_dur = entries[-1]["end"] if entries else 1.0

    # ── Frame function ────────────────────────────────────────
    blank = np.zeros((video_height, video_width, 3), dtype=np.uint8)

    def make_frame(t):
        entry = None
        for e in entries:
            if e["start"] <= t < e["end"]:
                entry = e
                break
        if entry is None:
            entry = entries[-1] if entries else None
        if entry is None:
            return blank

        progress     = (t - entry["start"]) / max(entry["end"] - entry["start"], 0.001)
        total_words  = len(entry["all_words"])
        visible_n    = min(int(progress * total_words) + 1, total_words)
        visible_text = " ".join(entry["all_words"][:visible_n])

        visible_lines = _wrap_text_px(visible_text, font_a, text_w)
        pages   = _paginate(visible_lines, max_a_lines)
        cur_page = pages[-1] if pages else []

        img = _render_slide(
            video_width=video_width, video_height=video_height,
            q_band_h=q_band_h, a_band_h=a_band_h,
            q_bg=q_bg, a_bg=a_bg,
            q_lines=entry["q_lines"], a_lines=cur_page,
            font_q=font_q, font_a=font_a,
            q_color=q_color, a_color=a_color,
            margin_side=margin_side,
            margin_top_q=margin_top_q, margin_top_a=margin_top_a,
        )
        return np.array(img)

    # ── Build video clip ──────────────────────────────────────
    video_clip = VideoClip(make_frame, duration=total_dur)
    audio_clip = AudioFileClip(audio_path)
    if audio_clip.duration > total_dur:
        audio_clip = audio_clip.subclipped(0, total_dur)
    final = video_clip.with_audio(audio_clip)

    final.write_videofile(
        output_path,
        fps=cfg.OUTPUT_FPS,
        codec=cfg.VIDEO_CODEC,
        audio_codec=cfg.AUDIO_CODEC,
        bitrate=cfg.VIDEO_BITRATE,
        audio_bitrate=cfg.AUDIO_BITRATE,
        logger=None,
    )
    log.info("QA split-layout video → %s", output_path)


# ─────────────────────────────────────────────────────────────
#  SLIDE RENDERER
# ─────────────────────────────────────────────────────────────

def _render_slide(
    video_width, video_height,
    q_band_h, a_band_h,
    q_bg, a_bg,
    q_lines, a_lines,
    font_q, font_a,
    q_color, a_color,
    margin_side, margin_top_q, margin_top_a,
) -> Image.Image:
    img  = Image.new("RGB", (video_width, video_height))
    draw = ImageDraw.Draw(img)

    # Fill bands
    draw.rectangle([0, 0, video_width, q_band_h], fill=q_bg)
    draw.rectangle([0, q_band_h, video_width, video_height], fill=a_bg)

    # Question — vertically centred in its band, horizontally centred
    q_lh = _line_height(font_q)
    total_q_h = len(q_lines) * q_lh + max(0, len(q_lines) - 1) * 8
    y = max((q_band_h - total_q_h) // 2, margin_top_q)
    for line in q_lines:
        tw = _text_width(draw, line, font_q)
        x  = (video_width - tw) // 2
        # Subtle drop-shadow
        draw.text((x + 2, y + 2), line, font=font_q, fill=(0, 0, 0, 50))
        draw.text((x, y), line, font=font_q, fill=q_color)
        y += q_lh + 8

    # Answer — top-aligned in answer band, left-aligned with margin
    a_lh = _line_height(font_a)
    y = q_band_h + margin_top_a
    for line in a_lines:
        draw.text((margin_side, y), line, font=font_a, fill=a_color)
        y += a_lh + 4

    return img


# ─────────────────────────────────────────────────────────────
#  FONT LOADING
# ─────────────────────────────────────────────────────────────

# Ordered list of system fonts known to support Devanagari (Hindi)
_HINDI_FONT_CANDIDATES = [
    # From config (set at runtime)
    # System paths — Linux
    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    # macOS
    "/Library/Fonts/NotoSansDevanagari-Regular.ttf",
    "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc",
    "/System/Library/Fonts/Kohinoor.ttc",
]


def _load_fonts(font_path: str, cfg) -> tuple:
    """Return (font_question, font_answer) PIL ImageFont objects."""
    q_size = getattr(cfg, "QA_SLIDE_QUESTION_FONT_SIZE",
                     getattr(cfg, "QA_QUESTION_FONT_SIZE", 64))
    a_size = getattr(cfg, "QA_SLIDE_ANSWER_FONT_SIZE",
                     getattr(cfg, "QA_ANSWER_FONT_SIZE",   48))

    # Build candidate list: config font first, then known Hindi fonts
    candidates = []
    if font_path and os.path.exists(font_path):
        candidates.append(font_path)
    for path in getattr(cfg, "HINDI_FONT_SEARCH_PATHS", []):
        if os.path.exists(path):
            candidates.append(path)
    candidates.extend(_HINDI_FONT_CANDIDATES)
    for path in getattr(cfg, "FALLBACK_FONT_SEARCH_PATHS", []):
        if os.path.exists(path):
            candidates.append(path)

    def _load(size):
        for path in candidates:
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
        log.warning("No Hindi font found; using PIL default (may show boxes for Hindi)")
        return ImageFont.load_default()

    return _load(q_size), _load(a_size)


# ─────────────────────────────────────────────────────────────
#  TEXT UTILITIES
# ─────────────────────────────────────────────────────────────

def _wrap_text_px(text: str, font, max_width: int) -> list[str]:
    """Word-wrap text so each line fits within max_width pixels."""
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
