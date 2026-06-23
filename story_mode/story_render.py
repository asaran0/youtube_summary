"""
story_mode/story_render.py — YouTube-style story video renderer.

Layout (inspired by viral Hindi motivational channels):

    ┌─────────────────────────────────────────────────┐
    │  [CHANNEL LOGO — top-right]                     │
    │                                                 │
    │                                                 │
    │       बदलने निकल पड़ता                          │  ← large bold subtitle
    │       है, लेकिन  रात  को                        │    word-by-word, highlight
    │                                                 │
    │  ▄▂▄▅▃▆▄▂▃▅▄▂  [waveform animation]  ▄▂▄▅▃▆▄  │  ← bottom bar
    └─────────────────────────────────────────────────┘

Background: looping colour gradient (configurable palette) — no video
file dependency so it works out of the box. If STORY_BG_VIDEO is set
and the file exists, that video is used as background instead.

Channel logo: text badge rendered from STORY_CHANNEL_NAME (configurable).
Waveform: animated bars driven by actual audio amplitude per frame.
"""

import os
import math
import random
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from utils import get_logger

log = get_logger("story_render")

# ── Font candidates (language-aware, same logic as qa_slideshow) ─────────────
_DEVANAGARI_CANDIDATES = [
    "assets/NotoSansDevanagari-Regular.ttf",
    "assets/NotoSansDevanagari-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/System/Library/Fonts/Kohinoor.ttc",
    "/Library/Fonts/Kohinoor.ttf",
    "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc",
]
_LATIN_CANDIDATES = [
    "assets/fonts/NotoSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


def _load_font(size: int, lang: str, hint: str = None) -> ImageFont.FreeTypeFont:
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


# ── Colour palette ────────────────────────────────────────────────────────────
# Each palette is (bg_top, bg_bottom, accent) — used for gradient backgrounds
PALETTES = [
    ((15, 10, 40),   (40, 20, 80),   (255, 200, 50)),    # deep purple / gold
    ((5,  30, 60),   (10, 80, 120),  (100, 220, 255)),   # ocean blue / cyan
    ((40, 10, 10),   (100, 20, 20),  (255, 120, 60)),    # crimson / orange
    ((10, 40, 10),   (20, 90, 50),   (100, 255, 150)),   # forest / mint
    ((40, 20, 60),   (80, 10, 80),   (255, 100, 255)),   # violet / pink
    ((60, 30, 0),    (120, 60, 0),   (255, 200, 80)),    # sunset / amber
]


def _gradient_bg(w: int, h: int, top: tuple, bot: tuple) -> Image.Image:
    img = Image.new("RGB", (w, h))
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for c in range(3):
        col = np.linspace(top[c], bot[c], h, dtype=np.float32)
        arr[:, :, c] = col[:, np.newaxis]
    return Image.fromarray(arr)


# ── Waveform helpers ──────────────────────────────────────────────────────────

def _load_audio_samples(audio_path: str, target_sr: int = 22050) -> np.ndarray:
    """Load audio as mono float32 array via ffmpeg."""
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-ac", "1", "-ar", str(target_sr),
        "-f", "f32le", "-",
    ]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        log.warning("Could not load audio for waveform: %s", r.stderr[-200:])
        return np.zeros(target_sr, dtype=np.float32)
    return np.frombuffer(r.stdout, dtype=np.float32)


def _rms_envelope(samples: np.ndarray, sr: int, fps: int, n_bars: int = 40) -> np.ndarray:
    """
    Compute per-frame RMS amplitude envelope.
    Returns array shape (n_frames, n_bars) — values 0..1.
    """
    total_frames = math.ceil(len(samples) / sr * fps)
    frame_size   = sr // fps
    result = np.zeros((total_frames, n_bars), dtype=np.float32)

    for fi in range(total_frames):
        start = fi * frame_size
        chunk = samples[start : start + frame_size]
        if len(chunk) == 0:
            continue
        rms = float(np.sqrt(np.mean(chunk ** 2)))
        # Distribute rms into bars with slight random variation for visual interest
        for b in range(n_bars):
            phase   = math.sin(fi * 0.3 + b * 0.5) * 0.3 + 0.7
            bar_rms = min(1.0, rms * 6 * phase + 0.05)
            result[fi, b] = bar_rms

    # Smooth over time
    from scipy.ndimage import uniform_filter1d
    result = uniform_filter1d(result, size=3, axis=0)
    return result


# ── Channel logo badge ────────────────────────────────────────────────────────

def _draw_channel_logo(draw: ImageDraw.ImageDraw, w: int, h: int,
                       text: str, font_hint: str, cfg,
                       accent: tuple) -> None:
    if not text:
        return
    logo_font = _load_font(
        getattr(cfg, "STORY_LOGO_FONT_SIZE", 28),
        getattr(cfg, "LANGUAGE", "hi"),
        font_hint,
    )
    padding = 14
    tw = draw.textbbox((0, 0), text, font=logo_font)[2]
    th = draw.textbbox((0, 0), text, font=logo_font)[3]
    bw = tw + padding * 2
    bh = th + padding * 2
    margin = 24
    x1 = w - bw - margin
    y1 = margin
    x2 = x1 + bw
    y2 = y1 + bh
    # Rounded pill background
    bg_color = getattr(cfg, "STORY_LOGO_BG_COLOR", (0, 0, 0, 180))
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rounded_rectangle([x1, y1, x2, y2], radius=bh // 2,
                          fill=(*bg_color[:3], bg_color[3] if len(bg_color) == 4 else 200))
    # Accent border
    od.rounded_rectangle([x1, y1, x2, y2], radius=bh // 2,
                          outline=(*accent, 200), width=2)
    draw._image.paste(Image.alpha_composite(
        draw._image.convert("RGBA"), overlay).convert("RGB"))
    # Redraw draw on updated image
    draw = ImageDraw.Draw(draw._image)
    draw.text((x1 + padding, y1 + padding), text,
               font=logo_font, fill=getattr(cfg, "STORY_LOGO_TEXT_COLOR", (255, 255, 255)))


# ── Waveform bar renderer ─────────────────────────────────────────────────────

def _draw_waveform(draw: ImageDraw.ImageDraw, w: int, h: int,
                   bar_heights: np.ndarray, accent: tuple, cfg) -> None:
    """Draw animated waveform bars at the bottom of the frame."""
    n_bars   = len(bar_heights)
    bar_zone_h = int(h * getattr(cfg, "STORY_WAVEFORM_HEIGHT_RATIO", 0.10))
    bar_zone_y = h - bar_zone_h - int(h * 0.02)
    bar_w    = max(2, int(w * 0.60 / (n_bars * 1.5)))
    gap      = max(1, bar_w // 2)
    total_w  = n_bars * (bar_w + gap)
    start_x  = (w - total_w) // 2

    # Semi-transparent background strip
    strip_alpha = getattr(cfg, "STORY_WAVEFORM_BG_ALPHA", 80)
    bg_strip = Image.new("RGBA", (w, bar_zone_h + 16), (0, 0, 0, strip_alpha))
    draw._image.paste(Image.alpha_composite(
        draw._image.crop((0, bar_zone_y - 8, w, bar_zone_y + bar_zone_h + 8)).convert("RGBA"),
        bg_strip,
    ).convert("RGB"), (0, bar_zone_y - 8))
    draw = ImageDraw.Draw(draw._image)

    bar_color_base = getattr(cfg, "STORY_WAVEFORM_COLOR", None) or accent
    for i, amp in enumerate(bar_heights):
        bar_h  = max(4, int(amp * bar_zone_h))
        x      = start_x + i * (bar_w + gap)
        y_top  = bar_zone_y + (bar_zone_h - bar_h)
        y_bot  = bar_zone_y + bar_zone_h
        # Gradient: brighter at top
        brightness = 0.6 + 0.4 * (bar_h / bar_zone_h)
        color = tuple(min(255, int(c * brightness)) for c in bar_color_base)
        draw.rectangle([x, y_top, x + bar_w - 1, y_bot], fill=color)


# ── Text rendering with per-word highlight ────────────────────────────────────

def _wrap_text(text: str, font, max_w: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines, current = [], ""
    for w in words:
        trial = (current + " " + w).strip()
        bbox  = draw.textbbox((0, 0), trial, font=font)
        if current and (bbox[2] - bbox[0]) > max_w:
            lines.append(current)
            current = w
        else:
            current = trial
    if current:
        lines.append(current)
    return lines


def _text_w(draw, text, font):
    return draw.textbbox((0, 0), text, font=font)[2]


def _text_h(font):
    dummy = Image.new("RGB", (1, 1))
    d = ImageDraw.Draw(dummy)
    bbox = d.textbbox((0, 0), "Agj|कि", font=font)
    return bbox[3] - bbox[1]


def _draw_subtitle_frame(
    base_img: Image.Image,
    lines: list[str],
    font,
    active_word: int,
    text_color: tuple,
    highlight_color: tuple,
    stroke_color: tuple,
    stroke_w: int,
    center_y: int,
) -> Image.Image:
    """Draw subtitle lines centred vertically around center_y with per-word highlight."""
    img  = base_img.copy()
    draw = ImageDraw.Draw(img)
    lh   = _text_h(font) + 12
    total_h = len(lines) * lh
    y    = center_y - total_h // 2
    word_idx = 0

    for line in lines:
        tokens = []
        for tok in line.split(" "):
            tokens.append(("word", tok))
            tokens.append(("space", " "))
        if tokens and tokens[-1][0] == "space":
            tokens.pop()

        # Calculate line width for centering
        line_w = _text_w(draw, line, font)
        x = (img.width - line_w) // 2

        for tok_type, tok in tokens:
            if tok_type == "space":
                x += _text_w(draw, " ", font)
                continue
            is_active = (word_idx == active_word)
            color = highlight_color if is_active else text_color
            # Bold stroke/outline
            for dx in range(-stroke_w, stroke_w + 1):
                for dy in range(-stroke_w, stroke_w + 1):
                    if dx == 0 and dy == 0:
                        continue
                    draw.text((x + dx, y + dy), tok, font=font, fill=stroke_color)
            draw.text((x, y), tok, font=font, fill=color)
            x += _text_w(draw, tok, font)
            word_idx += 1
        y += lh

    return img


# ── Main renderer ─────────────────────────────────────────────────────────────

def compile_story_video(
    selected_chunks: list[dict],
    audio_path: str,
    output_path: str,
    video_width: int,
    video_height: int,
    font_path: str,
    cfg,
    title: str = "",
) -> None:
    """
    Build the YouTube-style story video using moviepy VideoClip.

    Each frame is rendered as:
      • Gradient background (cycling through PALETTES per sentence)
      • Large bold subtitle text, word-by-word reveal with highlight
      • Animated waveform bars at bottom
      • Channel logo badge top-right
    """
    from moviepy import AudioFileClip, VideoClip

    lang       = getattr(cfg, "LANGUAGE", "hi")
    sub_size   = getattr(cfg, "STORY_SUBTITLE_FONT_SIZE", 90)
    text_color = tuple(getattr(cfg, "STORY_TEXT_COLOR", (255, 255, 255)))
    hi_color   = tuple(getattr(cfg, "STORY_HIGHLIGHT_COLOR", (100, 255, 80)))
    stroke_col = tuple(getattr(cfg, "STORY_STROKE_COLOR", (0, 0, 0)))
    stroke_w   = getattr(cfg, "STORY_STROKE_WIDTH", 6)
    channel    = getattr(cfg, "STORY_CHANNEL_NAME", "")
    n_bars     = getattr(cfg, "STORY_WAVEFORM_BARS", 38)

    font = _load_font(sub_size, lang, font_path)

    # Pre-load audio amplitude envelope
    log.info("Loading audio for waveform animation …")
    samples  = _load_audio_samples(audio_path)
    envelope = _rms_envelope(samples, sr=22050, fps=cfg.OUTPUT_FPS, n_bars=n_bars)
    n_frames = envelope.shape[0]

    # Build per-chunk data
    chunks_data = []
    palette_idx = 0
    for chunk in selected_chunks:
        text    = chunk.get("text", chunk.get("display_text", ""))
        t_start = chunk.get("new_start", chunk.get("start", 0.0))
        t_end   = chunk.get("new_end",   chunk.get("end",   t_start + 1.0))
        if t_end - t_start < 0.05 or not text.strip():
            continue
        palette = PALETTES[palette_idx % len(PALETTES)]
        palette_idx += 1

        # Pre-render base gradient background
        bg = _gradient_bg(video_width, video_height, palette[0], palette[1])

        # Wrap subtitle
        dummy_draw = ImageDraw.Draw(bg.copy())
        max_text_w = int(video_width * 0.88)
        lines      = _wrap_text(text.strip(), font, max_text_w, dummy_draw)
        words      = text.strip().split()
        n_words    = len(words)

        chunks_data.append({
            "t_start":  t_start,
            "t_end":    t_end,
            "bg":       bg,
            "lines":    lines,
            "words":    words,
            "n_words":  n_words,
            "palette":  palette,
            "accent":   palette[2],
        })

    if not chunks_data:
        raise RuntimeError("No story chunks to render")

    total_dur = chunks_data[-1]["t_end"]
    center_y  = int(video_height * 0.46)   # slightly above center (logo takes top-right)

    # Pre-render channel badge position (static overlay)
    # We'll draw it every frame (cheap PIL op)

    def make_frame(t: float) -> np.ndarray:
        # Find active chunk
        chunk = None
        for c in chunks_data:
            if c["t_start"] <= t < c["t_end"]:
                chunk = c
                break
        if chunk is None:
            chunk = chunks_data[-1]

        # Word-by-word reveal + highlight
        dur       = max(chunk["t_end"] - chunk["t_start"], 0.001)
        progress  = (t - chunk["t_start"]) / dur
        n_words   = chunk["n_words"]
        active_w  = min(int(progress * n_words), n_words - 1)
        visible_n = active_w + 1
        vis_text  = " ".join(chunk["words"][:visible_n])

        # Re-wrap visible text
        bg_copy    = chunk["bg"].copy()
        dummy_draw = ImageDraw.Draw(bg_copy)
        vis_lines  = _wrap_text(vis_text, font, int(video_width * 0.88), dummy_draw)

        # Draw subtitle
        frame_img = _draw_subtitle_frame(
            bg_copy, vis_lines, font, active_w,
            text_color, chunk["accent"] if chunk["accent"] else hi_color,
            stroke_col, stroke_w, center_y,
        )

        # Draw waveform
        frame_idx = min(int(t * cfg.OUTPUT_FPS), n_frames - 1)
        bar_h     = envelope[frame_idx]
        frame_draw = ImageDraw.Draw(frame_img)
        _draw_waveform(frame_draw, video_width, video_height,
                       bar_h, chunk["accent"], cfg)

        # Draw channel logo
        if channel:
            _draw_channel_badge(frame_img, channel, font_path, cfg, chunk["accent"])

        return np.array(frame_img)

    audio_clip = AudioFileClip(audio_path)
    total_dur  = min(total_dur, audio_clip.duration)
    video_clip = VideoClip(make_frame, duration=total_dur)
    final      = video_clip.with_audio(audio_clip.subclipped(0, total_dur))
    final.write_videofile(
        output_path,
        fps=cfg.OUTPUT_FPS,
        codec=cfg.VIDEO_CODEC,
        audio_codec=cfg.AUDIO_CODEC,
        bitrate=cfg.VIDEO_BITRATE,
        audio_bitrate=cfg.AUDIO_BITRATE,
        logger=None,
    )
    log.info("Story video → %s", output_path)


# ── Channel badge (cached) ────────────────────────────────────────────────────
_badge_cache: dict = {}

def _draw_channel_badge(img: Image.Image, text: str, font_path: str, cfg, accent: tuple) -> None:
    """Draw channel name badge on top-right of img (in-place)."""
    size    = getattr(cfg, "STORY_LOGO_FONT_SIZE", 30)
    lang    = getattr(cfg, "LANGUAGE", "hi")
    font    = _load_font(size, lang, font_path)
    w, h    = img.size
    padding = 16
    margin  = 20

    draw    = ImageDraw.Draw(img)
    bbox    = draw.textbbox((0, 0), text, font=font)
    tw, th  = bbox[2] - bbox[0], bbox[3] - bbox[1]
    bw, bh  = tw + padding * 2, th + padding * 2

    x1 = w - bw - margin
    y1 = margin
    x2, y2 = x1 + bw, y1 + bh

    # Draw pill with alpha using RGBA overlay
    overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    bg_c = getattr(cfg, "STORY_LOGO_BG_COLOR", (0, 0, 0))
    od.rounded_rectangle([x1, y1, x2, y2], radius=bh // 2,
                          fill=(*bg_c[:3], 190))
    od.rounded_rectangle([x1, y1, x2, y2], radius=bh // 2,
                          outline=(*accent[:3], 220), width=2)
    merged = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    img.paste(merged)

    draw = ImageDraw.Draw(img)
    tc = getattr(cfg, "STORY_LOGO_TEXT_COLOR", (255, 255, 255))
    draw.text((x1 + padding, y1 + padding), text, font=font, fill=tc)
