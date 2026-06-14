"""
banner_maker.py — Create animated topic-announcement banners overlaid on the video.

Each banner is a full-width semi-transparent strip near the top of the frame.
It fades in, holds for a few seconds, then fades out.

Banners are returned as moviepy ImageClips so they can be composited directly
on the video without extra files.
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import config
from utils import get_logger, find_hindi_font

log = get_logger("banners")


# ─────────────────────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────────────────────

def make_banner_clips(
    topic_groups:  list[tuple],   # [(new_start_sec, banner_text), …]
    video_width:   int,
    video_height:  int,
    font_path:     str,
) -> list:
    """
    Build a list of moviepy ImageClip banner objects for all topic groups.

    Returns a list of clips that can be passed to CompositeVideoClip.
    """
    if not config.BANNER_ENABLED or not topic_groups:
        return []

    from moviepy.editor import ImageClip

    clips = []
    for (start_sec, text) in topic_groups:
        # Duration = hold time + 2 × fade
        fade_dur  = config.BANNER_FADE_FRAMES / config.OUTPUT_FPS
        hold_dur  = config.BANNER_HOLD_SECONDS
        total_dur = hold_dur + 2 * fade_dur

        # Build the PIL banner image (RGBA)
        banner_img = _render_banner(text, video_width, font_path)

        # Convert PIL → numpy array
        banner_np = np.array(banner_img)

        # Create moviepy clip
        clip = (
            ImageClip(banner_np, duration=total_dur)
            .set_start(start_sec)
            .set_position(("center", 0))          # top of frame
            .crossfadein(fade_dur)
            .crossfadeout(fade_dur)
        )
        clips.append(clip)
        log.debug("Banner @ %.1f s: %s", start_sec, text[:40])

    log.info("Created %d banner clips", len(clips))
    return clips


# ─────────────────────────────────────────────────────────────
#  BANNER RENDERING  (PIL)
# ─────────────────────────────────────────────────────────────

def _render_banner(text: str, width: int, font_path: str) -> Image.Image:
    """
    Render one banner as a PIL RGBA image.

    Layout (top to bottom):
        ┌──── coloured gradient strip ────────────────────────┐
        │  ●  <text>                                          │
        └─────────────────────────────────────────────────────┘
    """
    height = config.BANNER_HEIGHT
    img    = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw   = ImageDraw.Draw(img)

    # --- Background gradient (left: solid, right: fades to transparent) -----
    r, g, b = config.BANNER_BG_COLOR
    alpha   = config.BANNER_BG_ALPHA
    for x in range(width):
        # Slight fade on the rightmost 20 % to look polished
        fade = 1.0 if x < width * 0.80 else 1.0 - (x - width * 0.80) / (width * 0.20)
        a    = int(alpha * fade)
        draw.line([(x, 0), (x, height)], fill=(r, g, b, a))

    # --- Accent left bar -----------------------------------------------------
    accent_width = 8
    draw.rectangle(
        [(0, 0), (accent_width, height)],
        fill=(255, 180, 0, 240),   # golden accent stripe
    )

    # --- Text ----------------------------------------------------------------
    font = _load_font(font_path, config.BANNER_FONT_SIZE)

    # Measure text to centre vertically
    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_h = bbox[3] - bbox[1]
    except AttributeError:
        # Older Pillow
        text_h = config.BANNER_FONT_SIZE

    y = (height - text_h) // 2
    x = accent_width + 20

    # Soft shadow for readability
    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 160))
    # Main text
    draw.text((x, y), text, font=font, fill=(*config.BANNER_TEXT_COLOR, 255))

    # --- Thin bottom border --------------------------------------------------
    draw.line([(0, height - 3), (width, height - 3)], fill=(255, 180, 0, 180), width=3)

    return img


# ─────────────────────────────────────────────────────────────
#  FONT LOADING
# ─────────────────────────────────────────────────────────────

_font_cache: dict = {}


def _load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    """Load and cache a PIL font at the requested size."""
    key = (font_path, size)
    if key not in _font_cache:
        try:
            _font_cache[key] = ImageFont.truetype(font_path, size=size)
        except Exception as e:
            log.warning("Could not load font %s at size %d: %s. Using default.", font_path, size, e)
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


# ─────────────────────────────────────────────────────────────
#  QUICK PREVIEW UTILITY  (for debugging / testing)
# ─────────────────────────────────────────────────────────────

def preview_banner(text: str, font_path: str, save_path: str = "temp/banner_preview.png") -> None:
    """Save a single banner to disk for visual inspection."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    img = _render_banner(text, 1920, font_path)
    img.save(save_path)
    log.info("Banner preview saved → %s", save_path)
