"""
ebook_mode/render.py — Renders special visual frames for ebook videos.

Provides three frame types on top of the base story_render pipeline:

  chapter_card  — Full-screen title card with chapter number, title,
                  and a gold divider. Appears at every chapter break.

  lesson        — Semi-transparent overlay with a distinct warm-yellow
                  tinted background — visually distinct from narration
                  so the viewer knows "this is the key idea".

  quote         — Gold left-bar + slightly transparent dark box behind
                  the quote text. Classic blockquote treatment.

All three respect the background (image/gradient) set in cfg and do NOT
add any colour tint on top of photos — they draw self-contained overlays
that sit on the image rather than replacing it.

The progress bar (chapter X of N across the top/bottom) is drawn onto
every frame via draw_progress_bar().
"""

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from utils import get_logger

log = get_logger("ebook.render")


# ── Font loading (shared with story_render) ──────────────────────────────────

_LATIN_CANDIDATES = [
    "assets/fonts/NotoSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]
_DEVANAGARI_CANDIDATES = [
    "assets/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
]


def _load_font(size: int, lang: str = "en", hint: str = None) -> ImageFont.FreeTypeFont:
    candidates = []
    if hint and os.path.exists(hint):
        candidates.append(hint)
    if lang == "en":
        candidates.extend(_LATIN_CANDIDATES)
        candidates.extend(_DEVANAGARI_CANDIDATES)
    else:
        candidates.extend(_DEVANAGARI_CANDIDATES)
        candidates.extend(_LATIN_CANDIDATES)
    for path in candidates:
        if not path or not os.path.exists(path):
            continue
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font) -> tuple[int, int]:
    bb = draw.textbbox((0, 0), text, font=font)
    return bb[2] - bb[0], bb[3] - bb[1]


def _wrap_text(text: str, font, max_w: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        tw, _ = _text_size(draw, trial, font)
        if cur and tw > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _line_height(font: ImageFont.FreeTypeFont) -> int:
    try:
        asc, desc = font.getmetrics()
        return asc + abs(desc)
    except Exception:
        return 40


# ── Progress bar ─────────────────────────────────────────────────────────────

def draw_progress_bar(
    img: Image.Image,
    chapter_num: int,
    total_chapters: int,
    cfg,
) -> None:
    """
    Draw a thin progress bar at the top of `img` (in-place).
    Shows how far through the book we are (chapter N of total_chapters).
    Set EBOOK_PROGRESS_BAR_HEIGHT = 0 in config to disable.
    """
    bar_h = int(getattr(cfg, "EBOOK_PROGRESS_BAR_HEIGHT", 8))
    if bar_h <= 0 or total_chapters <= 0:
        return

    bar_color = tuple(getattr(cfg, "EBOOK_PROGRESS_BAR_COLOR", (255, 215, 0)))
    bg_color  = tuple(getattr(cfg, "EBOOK_PROGRESS_BAR_BG_COLOR", (40, 40, 40)))

    w = img.width
    draw = ImageDraw.Draw(img)

    # Background track
    draw.rectangle([0, 0, w - 1, bar_h - 1], fill=bg_color)

    # Filled portion
    progress  = max(0.0, min(1.0, chapter_num / max(total_chapters, 1)))
    filled_w  = int(w * progress)
    if filled_w > 0:
        draw.rectangle([0, 0, filled_w - 1, bar_h - 1], fill=bar_color)


# ── Chapter card ─────────────────────────────────────────────────────────────

def render_chapter_card(
    bg: Image.Image,
    chapter_num: int,
    chapter_title: str,
    total_chapters: int,
    fade_alpha: float,
    font_path: str,
    cfg,
) -> Image.Image:
    """
    Full-screen chapter title card. Draws a centred black panel with:
        • "CHAPTER N" in gold (small caps style)
        • ─────── gold divider ───────
        • Chapter title in large white text
        • "X of N chapters" sub-label in grey

    Uses a semi-transparent black overlay over the background image so the
    photo shows through subtly — no colour tint is added to the photo itself.
    """
    w, h = bg.size
    img  = bg.copy().convert("RGBA")
    draw = ImageDraw.Draw(img)

    accent  = tuple(getattr(cfg, "EBOOK_CHAPTER_ACCENT_COLOR", (255, 215, 0)))
    bg_col  = tuple(getattr(cfg, "EBOOK_CHAPTER_BG_COLOR",     (10, 10, 30)))
    txt_col = tuple(getattr(cfg, "EBOOK_CHAPTER_TEXT_COLOR",   (255, 255, 255)))

    title_size  = int(getattr(cfg, "EBOOK_CHAPTER_FONT_SIZE",   88))
    num_size    = int(getattr(cfg, "EBOOK_CHAPTER_NUMBER_SIZE", 48))
    lang        = getattr(cfg, "LANGUAGE", "en")

    font_title = _load_font(title_size, lang, font_path)
    font_num   = _load_font(num_size,   lang, font_path)
    font_sub   = _load_font(int(num_size * 0.65), lang, font_path)

    # ── Semi-transparent black panel covering the full frame ─────────────
    panel = Image.new("RGBA", (w, h), (*bg_col[:3], 210))
    img   = Image.alpha_composite(img, panel)
    draw  = ImageDraw.Draw(img)

    # ── Layout: stack vertically around vertical centre ──────────────────
    lh_title = _line_height(font_title) + 12
    lh_num   = _line_height(font_num)
    lh_sub   = _line_height(font_sub)
    divider_h = 4
    divider_gap = 24

    max_title_w = int(w * 0.78)
    title_lines = _wrap_text(chapter_title, font_title, max_title_w, draw)

    total_block_h = (
        lh_num + divider_gap + divider_h + divider_gap
        + len(title_lines) * lh_title
        + divider_gap + lh_sub
    )
    y = (h - total_block_h) // 2

    # ── "CHAPTER N" / "अध्याय N" label ──────────────────────────────────
    # Use localised prefix from config if available, otherwise fall back
    get_label = getattr(cfg, "get_label", None)
    if callable(get_label):
        chapter_prefix = get_label("chapter_prefix")
        of_chapters_tmpl = get_label("of_chapters", n=total_chapters)
    else:
        chapter_prefix   = "CHAPTER"
        of_chapters_tmpl = f"of {total_chapters} chapters"

    num_label = f"{chapter_prefix}  {chapter_num}"
    nw, _ = _text_size(draw, num_label, font_num)
    draw.text(((w - nw) // 2, y), num_label, font=font_num, fill=(*accent, 255))
    y += lh_num + divider_gap

    # Gold divider
    div_w = int(w * 0.35)
    draw.rectangle([(w - div_w) // 2, y, (w + div_w) // 2, y + divider_h],
                   fill=(*accent, 255))
    y += divider_h + divider_gap

    # Chapter title lines
    for line in title_lines:
        lw, _ = _text_size(draw, line, font_title)
        draw.text(
            ((w - lw) // 2, y), line, font=font_title,
            fill=(*txt_col, 255),
            stroke_width=3, stroke_fill=(0, 0, 0, 200),
        )
        y += lh_title

    y += divider_gap

    # "X of N chapters" / "N में से X अध्याय"
    sub_label = f"{chapter_num} {of_chapters_tmpl}"
    sw, _ = _text_size(draw, sub_label, font_sub)
    draw.text(((w - sw) // 2, y), sub_label, font=font_sub,
              fill=(180, 180, 180, 255))

    # ── Fade alpha (for in/out transitions) ─────────────────────────────
    result = img.convert("RGB")
    if fade_alpha < 1.0:
        black = Image.new("RGB", (w, h), (0, 0, 0))
        result = Image.blend(black, result, fade_alpha)

    draw_progress_bar(result, chapter_num, total_chapters, cfg)
    return result


# ── Quote callout ────────────────────────────────────────────────────────────

def render_quote_frame(
    bg: Image.Image,
    quote_text: str,
    chapter_num: int,
    total_chapters: int,
    active_word: int,
    fade_alpha: float,
    font_path: str,
    cfg,
) -> Image.Image:
    """
    Quote callout: a semi-transparent dark box centred on screen with a
    gold left-bar, large quote text, and word-by-word highlighting.
    The background photo shows through the rest of the frame unchanged.
    """
    w, h  = bg.size
    img   = bg.copy().convert("RGBA")

    quote_size  = int(getattr(cfg, "EBOOK_QUOTE_FONT_SIZE",  66))
    bar_col     = tuple(getattr(cfg, "EBOOK_QUOTE_BAR_COLOR",    (255, 215, 0)))
    txt_col     = tuple(getattr(cfg, "EBOOK_QUOTE_TEXT_COLOR",   (220, 220, 220)))
    hi_col      = tuple(getattr(cfg, "STORY_HIGHLIGHT_COLOR",    (255, 215, 0)))
    box_col     = tuple(getattr(cfg, "EBOOK_QUOTE_BG_COLOR",     (0, 0, 0)))
    box_alpha   = int(getattr(cfg,  "EBOOK_QUOTE_BG_ALPHA",      160))
    stroke_col  = (0, 0, 0)
    stroke_w    = 3
    lang        = getattr(cfg, "LANGUAGE", "en")

    font        = _load_font(quote_size, lang, font_path)
    dummy_draw  = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    max_text_w  = int(w * 0.74)
    lh          = _line_height(font) + 10

    words = quote_text.split()
    lines = _wrap_text(quote_text, font, max_text_w, dummy_draw)
    total_block_h = len(lines) * lh

    # Box geometry
    pad_x, pad_y = 60, 48
    bar_w        = 8
    box_x1 = int(w * 0.08)
    box_x2 = int(w * 0.92)
    box_y1 = h // 2 - total_block_h // 2 - pad_y
    box_y2 = h // 2 + total_block_h // 2 + pad_y

    # Semi-transparent background box
    box_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd        = ImageDraw.Draw(box_layer)
    bd.rectangle([box_x1, box_y1, box_x2, box_y2],
                 fill=(*box_col[:3], box_alpha))
    img = Image.alpha_composite(img, box_layer)
    draw = ImageDraw.Draw(img)

    # Gold left bar
    draw.rectangle([box_x1, box_y1, box_x1 + bar_w, box_y2],
                   fill=(*bar_col[:3], 255))

    # Text: word-by-word reveal with active word highlight
    text_x = box_x1 + bar_w + pad_x
    y = h // 2 - total_block_h // 2
    word_cursor = 0

    for line in lines:
        line_words = line.split()
        x = text_x
        for word in line_words:
            is_active = (active_word >= 0 and word_cursor == active_word)
            col = (*hi_col[:3], 255) if is_active else (*txt_col[:3], 255)
            ww, _ = _text_size(draw, word, font)
            draw.text((x, y), word, font=font, fill=col,
                      stroke_width=stroke_w, stroke_fill=(*stroke_col, 255))
            x += ww + _text_size(draw, " ", font)[0]
            word_cursor += 1
        y += lh

    # Fade
    result = img.convert("RGB")
    if fade_alpha < 1.0:
        black  = Image.new("RGB", (w, h), (0, 0, 0))
        result = Image.blend(black, result, fade_alpha)

    draw_progress_bar(result, chapter_num, total_chapters, cfg)
    return result


# ── Key Lesson slide ─────────────────────────────────────────────────────────

def render_lesson_frame(
    bg: Image.Image,
    lesson_text: str,
    chapter_num: int,
    total_chapters: int,
    fade_alpha: float,
    font_path: str,
    cfg,
) -> Image.Image:
    """
    Key lesson callout: warm-yellow text on a semi-transparent deep-blue
    panel. Used for '### Key Lesson' sections. No word-by-word animation —
    the whole lesson appears at once since it's usually a short headline.
    """
    w, h  = bg.size
    img   = bg.copy().convert("RGBA")

    lesson_size = int(getattr(cfg, "EBOOK_LESSON_FONT_SIZE",    68))
    txt_col     = tuple(getattr(cfg, "EBOOK_LESSON_TEXT_COLOR", (255, 240, 100)))
    box_col     = tuple(getattr(cfg, "EBOOK_LESSON_BG_COLOR",   (20, 10, 60)))
    box_alpha   = int(getattr(cfg,  "EBOOK_LESSON_BG_ALPHA",    180))
    lang        = getattr(cfg, "LANGUAGE", "en")

    font        = _load_font(lesson_size, lang, font_path)
    dummy_draw  = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    max_text_w  = int(w * 0.80)
    lh          = _line_height(font) + 12

    lines       = _wrap_text(lesson_text, font, max_text_w, dummy_draw)
    total_h     = len(lines) * lh
    pad_x, pad_y = 80, 44

    box_x1 = int(w * 0.06)
    box_x2 = int(w * 0.94)
    box_y1 = h // 2 - total_h // 2 - pad_y
    box_y2 = h // 2 + total_h // 2 + pad_y

    box_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd        = ImageDraw.Draw(box_layer)
    bd.rounded_rectangle([box_x1, box_y1, box_x2, box_y2],
                         radius=16, fill=(*box_col[:3], box_alpha))
    img  = Image.alpha_composite(img, box_layer)
    draw = ImageDraw.Draw(img)

    # Label: "KEY LESSON" / "मुख्य सीख" in small gold text above the main text
    accent     = tuple(getattr(cfg, "EBOOK_CHAPTER_ACCENT_COLOR", (255, 215, 0)))
    label_fnt  = _load_font(int(lesson_size * 0.42), lang, font_path)
    get_label  = getattr(cfg, "get_label", None)
    label      = get_label("key_lesson") if callable(get_label) else "KEY LESSON"
    lw, _     = _text_size(draw, label, label_fnt)
    draw.text(((w - lw) // 2, box_y1 + 14), label, font=label_fnt,
              fill=(*accent[:3], 220))

    y = h // 2 - total_h // 2
    for line in lines:
        lw2, _ = _text_size(draw, line, font)
        draw.text(
            ((w - lw2) // 2, y), line, font=font,
            fill=(*txt_col[:3], 255),
            stroke_width=3, stroke_fill=(0, 0, 0, 200),
        )
        y += lh

    result = img.convert("RGB")
    if fade_alpha < 1.0:
        black  = Image.new("RGB", (w, h), (0, 0, 0))
        result = Image.blend(black, result, fade_alpha)

    draw_progress_bar(result, chapter_num, total_chapters, cfg)
    return result
