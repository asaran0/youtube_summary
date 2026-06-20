"""
core/render/banners.py — Animated topic-announcement banners overlaid on video.

Each banner is a full-width semi-transparent strip near the top of the
frame. It fades in, holds for a few seconds, then fades out.

Mode-agnostic: both story_mode and qa_mode can use this for topic
banners; each passes its own cfg for styling/timing.
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from utils import get_logger

log = get_logger("banners")


def make_banner_clips(
    topic_groups: list[tuple],
    video_width: int,
    video_height: int,
    font_path: str,
    cfg,
) -> list:
    """
    Build a list of moviepy ImageClip banner objects for all topic groups.
    Returns a list of clips that can be passed to CompositeVideoClip.
    """
    if not cfg.BANNER_ENABLED or not topic_groups:
        return []

    from moviepy import ImageClip
    from moviepy.video.fx import CrossFadeIn, CrossFadeOut

    clips = []
    for (start_sec, text) in topic_groups:
        fade_dur = cfg.BANNER_FADE_FRAMES / cfg.OUTPUT_FPS
        hold_dur = cfg.BANNER_HOLD_SECONDS
        total_dur = hold_dur + 2 * fade_dur

        banner_img = _render_banner(text, video_width, font_path, cfg)
        banner_np = np.array(banner_img)

        clip = (
            ImageClip(banner_np, duration=total_dur)
            .with_start(start_sec)
            .with_position(("center", 0))
            .with_effects([CrossFadeIn(fade_dur), CrossFadeOut(fade_dur)])
        )
        clips.append(clip)
        log.debug("Banner @ %.1f s: %s", start_sec, text[:40])

    log.info("Created %d banner clips", len(clips))
    return clips


def _render_banner(text: str, width: int, font_path: str, cfg) -> Image.Image:
    """Render one banner as a PIL RGBA image."""
    height = cfg.BANNER_HEIGHT
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    r, g, b = cfg.BANNER_BG_COLOR
    alpha = cfg.BANNER_BG_ALPHA
    for x in range(width):
        fade = 1.0 if x < width * 0.80 else 1.0 - (x - width * 0.80) / (width * 0.20)
        a = int(alpha * fade)
        draw.line([(x, 0), (x, height)], fill=(r, g, b, a))

    accent_width = 8
    draw.rectangle([(0, 0), (accent_width, height)], fill=(255, 180, 0, 240))

    font = _load_font(font_path, cfg.BANNER_FONT_SIZE)

    try:
        bbox = draw.textbbox((0, 0), text, font=font)
        text_h = bbox[3] - bbox[1]
    except AttributeError:
        text_h = cfg.BANNER_FONT_SIZE

    y = (height - text_h) // 2
    x = accent_width + 20

    draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 160))
    draw.text((x, y), text, font=font, fill=(*cfg.BANNER_TEXT_COLOR, 255))

    draw.line([(0, height - 3), (width, height - 3)], fill=(255, 180, 0, 180), width=3)

    return img


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


def preview_banner(text: str, font_path: str, cfg, save_path: str = "temp/banner_preview.png") -> None:
    """Save a single banner to disk for visual inspection."""
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    img = _render_banner(text, 1920, font_path, cfg)
    img.save(save_path)
    log.info("Banner preview saved → %s", save_path)
