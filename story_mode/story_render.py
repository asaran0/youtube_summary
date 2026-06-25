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

_WAVEFORM_LOOP_SECS = 4
_WAVEFORM_LOOP_FPS  = 30


def _waveform_loop_path(accent: tuple, video_w: int, video_h: int,
                        n_bars: int, bar_zone_ratio: float, cfg) -> str:
    """
    Return path to a cached looping waveform MP4 for this accent colour.
    Creates it (once) if it does not already exist.
    The clip is black-background with coloured bars — overlaid via ffmpeg
    screen-blend so the black disappears and only the bright bars show.
    """
    os.makedirs("assets/waveform_loops", exist_ok=True)
    hex_accent = "%02x%02x%02x" % (accent[0], accent[1], accent[2])
    cache_path = f"assets/waveform_loops/wf_{hex_accent}_{video_w}x{video_h}.mp4"

    if os.path.exists(cache_path):
        log.info("Waveform loop cache hit  → %s", cache_path)
        return cache_path

    log.info("Rendering waveform loop  → %s  (4 s, done once)", cache_path)
    fps        = _WAVEFORM_LOOP_FPS
    dur        = _WAVEFORM_LOOP_SECS
    n_frames   = fps * dur
    bar_zone_h = int(video_h * bar_zone_ratio)
    bar_w      = max(2, int(video_w * 0.60 / (n_bars * 1.5)))
    gap        = max(1, bar_w // 2)
    total_bw   = n_bars * (bar_w + gap)
    start_x    = (video_w - total_bw) // 2
    bar_zone_y = video_h - bar_zone_h - int(video_h * 0.02)
    bg_alpha   = getattr(cfg, "STORY_WAVEFORM_BG_ALPHA", 80)
    bar_color  = getattr(cfg, "STORY_WAVEFORM_COLOR", None) or accent

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pixel_format", "rgb24",
        "-video_size", f"{video_w}x{video_h}",
        "-framerate", str(fps),
        "-i", "pipe:0",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", "-crf", "23",
        "-t", str(dur),
        cache_path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    rng         = random.Random(42)
    bar_phases  = [rng.uniform(0, 2 * math.pi) for _ in range(n_bars)]
    bar_freqs   = [rng.uniform(0.8, 2.5)        for _ in range(n_bars)]

    for fi in range(n_frames):
        t     = fi / fps
        frame = Image.new("RGB", (video_w, video_h), (0, 0, 0))
        draw  = ImageDraw.Draw(frame)

        # Semi-transparent strip (only the bottom strip region)
        strip_h  = bar_zone_h + 16
        strip_y0 = bar_zone_y - 8
        strip    = Image.new("RGBA", (video_w, strip_h), (0, 0, 0, bg_alpha))
        region   = frame.crop((0, strip_y0, video_w, strip_y0 + strip_h)).convert("RGBA")
        frame.paste(Image.alpha_composite(region, strip).convert("RGB"), (0, strip_y0))
        draw = ImageDraw.Draw(frame)

        for i in range(n_bars):
            amp = (
                0.45
                + 0.40 * math.sin(2 * math.pi * bar_freqs[i] * t + bar_phases[i])
                + 0.15 * math.sin(2 * math.pi * bar_freqs[i] * 2.3 * t + bar_phases[i] * 1.7)
            )
            amp      = max(0.05, min(1.0, amp))
            bh_px    = max(4, int(amp * bar_zone_h))
            x        = start_x + i * (bar_w + gap)
            y_top    = bar_zone_y + (bar_zone_h - bh_px)
            y_bot    = bar_zone_y + bar_zone_h
            bright   = 0.6 + 0.4 * amp
            color    = tuple(min(255, int(c * bright)) for c in bar_color)
            draw.rectangle([x, y_top, x + bar_w - 1, y_bot], fill=color)

        proc.stdin.write(frame.tobytes())

    proc.stdin.close()
    proc.wait()
    log.info("Waveform loop ready      → %s", cache_path)
    return cache_path



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
    """Draw animated waveform bars at the bottom of the frame.

    The semi-transparent strip is drawn as a direct RGBA patch (cropped to
    just the strip region) rather than a full-frame composite, which was the
    main cause of the video render hang.
    """
    n_bars     = len(bar_heights)
    bar_zone_h = int(h * getattr(cfg, "STORY_WAVEFORM_HEIGHT_RATIO", 0.10))
    bar_zone_y = h - bar_zone_h - int(h * 0.02)
    bar_w      = max(2, int(w * 0.60 / (n_bars * 1.5)))
    gap        = max(1, bar_w // 2)
    total_w    = n_bars * (bar_w + gap)
    start_x    = (w - total_w) // 2

    # Semi-transparent background strip — composite only the strip region,
    # NOT the full frame. This is 10-20x faster than the old full-frame crop.
    strip_alpha = getattr(cfg, "STORY_WAVEFORM_BG_ALPHA", 80)
    strip_y0    = bar_zone_y - 8
    strip_h     = bar_zone_h + 16
    strip_y1    = strip_y0 + strip_h
    region      = draw._image.crop((0, strip_y0, w, strip_y1)).convert("RGBA")
    overlay     = Image.new("RGBA", (w, strip_h), (0, 0, 0, strip_alpha))
    merged      = Image.alpha_composite(region, overlay).convert("RGB")
    draw._image.paste(merged, (0, strip_y0))
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

    # Get (or create) the looping waveform asset for this palette's accent colour.
    # Use the first chunk's accent as the loop colour — most videos share one palette.
    first_accent = PALETTES[0][2]   # will be overridden per-chunk via ffmpeg overlay
    bar_zone_ratio = getattr(cfg, "STORY_WAVEFORM_HEIGHT_RATIO", 0.10)
    # We pre-generate one loop per distinct accent colour used in this video.
    # Collect unique accents first, generate loops, then overlay them all via ffmpeg.
    unique_accents = list({PALETTES[i % len(PALETTES)][2]
                           for i in range(len(selected_chunks))})
    waveform_loops = {}
    for acc in unique_accents:
        waveform_loops[acc] = _waveform_loop_path(
            acc, video_width, video_height, n_bars, bar_zone_ratio, cfg
        )

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

    # Pre-cache wrapped lines for every possible (chunk_idx, visible_n) combination.
    # This avoids re-running _wrap_text on every single frame — which was adding
    # ~1-3ms per frame and causing stutter on long videos.
    max_w_px = int(video_width * 0.88)
    for c in chunks_data:
        wrap_cache = {}
        dummy_img  = c["bg"].copy()
        dd         = ImageDraw.Draw(dummy_img)
        for n in range(1, c["n_words"] + 1):
            vis  = " ".join(c["words"][:n])
            wrap_cache[n] = _wrap_text(vis, font, max_w_px, dd)
        c["wrap_cache"] = wrap_cache

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

        # Use pre-cached wrapped lines — no recomputation per frame
        vis_lines = chunk["wrap_cache"][visible_n]

        # Draw subtitle on a fresh copy of the pre-rendered gradient bg
        bg_copy   = chunk["bg"].copy()
        frame_img = _draw_subtitle_frame(
            bg_copy, vis_lines, font, active_w,
            text_color, chunk["accent"] if chunk["accent"] else hi_color,
            stroke_col, stroke_w, center_y,
        )

        # Waveform is overlaid via ffmpeg after rendering — not drawn per frame.

        # Draw channel logo (fast — cached patch composite)
        if channel:
            _draw_channel_badge(frame_img, channel, font_path, cfg, chunk["accent"])

        return np.array(frame_img)

    audio_clip = AudioFileClip(audio_path)
    total_dur  = min(total_dur, audio_clip.duration)
    audio_clip.close()

    # ── Step A: render the subtitle / badge video without audio ──────────────
    # This is now very fast — no per-frame waveform drawing at all.
    tmp_nowave = output_path.replace(".mp4", "_nowave.mp4")
    video_clip = VideoClip(make_frame, duration=total_dur)
    video_clip.write_videofile(
        tmp_nowave,
        fps=cfg.OUTPUT_FPS,
        codec=cfg.VIDEO_CODEC,
        bitrate=cfg.VIDEO_BITRATE,
        audio=False,
        logger=None,
    )
    video_clip.close()
    log.info("Subtitle video (no waveform) → %s", tmp_nowave)

    # ── Step B: overlay the looping waveform clip via ffmpeg ────────────────
    # Use the most common accent in this video for the waveform loop.
    # (All loops have black backgrounds, so screen/add blend works well.)
    primary_accent = PALETTES[0][2]
    wf_loop = waveform_loops.get(primary_accent, list(waveform_loops.values())[0])

    tmp_waved = output_path.replace(".mp4", "_waved.mp4")
    # ffmpeg filter:
    #   [1:v] loop the short waveform clip to match total_dur
    #   blend=addition: adds bright bars onto the dark story background
    #   This is zero-copy fast — ffmpeg does it in a single pass.
    wf_cmd = [
        "ffmpeg", "-y",
        "-i", tmp_nowave,                    # [0:v] story video (no audio)
        "-stream_loop", "-1",                # loop input [1] indefinitely
        "-i", wf_loop,                       # [1:v] waveform loop
        "-filter_complex",
        # blend=screen: black pixels in the waveform loop become transparent,
        # bright bar pixels composite onto the story background perfectly.
        "[0:v]format=rgb24[base];"
        "[1:v]format=rgb24[wf];"
        "[base][wf]blend=all_mode=screen[v];"
        "[v]format=yuv420p[out]",
        "-map", "[out]",
        "-c:v", cfg.VIDEO_CODEC,
        "-preset", "fast",
        "-crf", "18",
        "-t", str(total_dur),
        tmp_waved,
    ]
    r = subprocess.run(wf_cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log.warning("ffmpeg overlay failed, using no-waveform version: %s", r.stderr[-300:])
        tmp_waved = tmp_nowave   # graceful fallback

    # ── Step C: mux in audio ─────────────────────────────────────────────────
    mux_cmd = [
        "ffmpeg", "-y",
        "-i", tmp_waved,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", cfg.AUDIO_CODEC,
        "-b:a", cfg.AUDIO_BITRATE,
        "-shortest",
        output_path,
    ]
    subprocess.run(mux_cmd, check=True, capture_output=True)

    # Cleanup temp files
    for tmp in [tmp_nowave, tmp_waved]:
        if tmp != output_path and os.path.exists(tmp):
            os.remove(tmp)

    log.info("Story video → %s", output_path)


# ── Channel badge (cached) ────────────────────────────────────────────────────
# Pre-render badge overlays keyed by accent colour so we never do a
# full-image alpha_composite inside the per-frame render loop.
_badge_cache: dict = {}


def _make_badge_overlay(text: str, font_path: str, cfg, accent: tuple,
                        img_w: int, img_h: int) -> tuple:
    """
    Return (overlay_rgba, paste_x, paste_y, text_x, text_y, font, tc)
    for the channel badge. The RGBA overlay is a minimal crop — just the
    pill area — so compositing is fast (small patch, not full frame).
    Cached per (text, accent) key so we only build it once per palette.
    """
    cache_key = (text, accent, img_w, img_h)
    if cache_key in _badge_cache:
        return _badge_cache[cache_key]

    size    = getattr(cfg, "STORY_LOGO_FONT_SIZE", 30)
    lang    = getattr(cfg, "LANGUAGE", "hi")
    font    = _load_font(size, lang, font_path)
    padding = 16
    margin  = 20

    dummy = Image.new("RGB", (1, 1))
    dd    = ImageDraw.Draw(dummy)
    bbox  = dd.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    bw, bh = tw + padding * 2, th + padding * 2

    x1 = img_w - bw - margin
    y1 = margin
    x2, y2 = x1 + bw, y1 + bh

    # Build a small RGBA patch covering only the badge region (+ 2px margin)
    pad   = 4
    patch = Image.new("RGBA", (bw + pad * 2, bh + pad * 2), (0, 0, 0, 0))
    pd    = ImageDraw.Draw(patch)
    bg_c  = getattr(cfg, "STORY_LOGO_BG_COLOR", (0, 0, 0))
    pd.rounded_rectangle([pad, pad, bw + pad, bh + pad], radius=bh // 2,
                          fill=(*bg_c[:3], 190))
    pd.rounded_rectangle([pad, pad, bw + pad, bh + pad], radius=bh // 2,
                          outline=(*accent[:3], 220), width=2)
    tc = getattr(cfg, "STORY_LOGO_TEXT_COLOR", (255, 255, 255))
    pd.text((pad + padding, pad + padding), text, font=font, fill=tc)

    result = (patch, x1 - pad, y1 - pad, font, tc)
    _badge_cache[cache_key] = result
    return result


def _draw_channel_badge(img: Image.Image, text: str, font_path: str, cfg, accent: tuple) -> None:
    """Draw channel name badge on top-right of img (in-place). Fast: patches only the badge area."""
    if not text:
        return
    w, h = img.size
    patch, px, py, font, tc = _make_badge_overlay(text, font_path, cfg, accent, w, h)
    # Composite only the small badge patch — not the whole frame
    region = img.crop((px, py, px + patch.width, py + patch.height)).convert("RGBA")
    merged = Image.alpha_composite(region, patch).convert("RGB")
    img.paste(merged, (px, py))
