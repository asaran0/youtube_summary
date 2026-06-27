"""
story_mode/story_render.py — YouTube-style story video renderer.

Layout:
    ┌─────────────────────────────────────────────────┐
    │  [CHANNEL BADGE — top-right]                    │
    │                                                 │
    │                                                 │
    │    One sentence at a time, centred,             │  ← bold subtitle
    │    currently-spoken word highlighted            │
    │                                                 │
    │  ▄▂▄▅▃▆▄▂▃▅▄  [waveform — added post-render]  │
    └─────────────────────────────────────────────────┘

Each sentence appears alone on screen:
  • Fades in at sentence start (0.25 s)
  • Currently-spoken word highlighted in accent colour
  • Fades out at sentence end (0.25 s)
  • Background gradient changes per sentence

Waveform is composited in a single ffmpeg pass after MoviePy render —
fast, no per-frame PIL overhead.
"""

import os
import math
import random
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from utils import get_logger

log = get_logger("story_render")

# ── Font loading ──────────────────────────────────────────────────────────────
_DEVANAGARI_CANDIDATES = [
    "assets/NotoSansDevanagari-Regular.ttf",
    "assets/NotoSansDevanagari-Bold.ttf",
    "/System/Library/Fonts/Kohinoor.ttc",
    "/Library/Fonts/Kohinoor.ttf",
    "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
]
_LATIN_CANDIDATES = [
    "assets/fonts/NotoSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
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
    log.warning("No font found for size=%d lang=%s, using default", size, lang)
    return ImageFont.load_default()


# ── Colour palettes ───────────────────────────────────────────────────────────
# (bg_top, bg_bottom, accent)
PALETTES = [
    ((15, 10, 40),   (40, 20, 80),   (255, 200, 50)),
    ((5,  30, 60),   (10, 80, 120),  (100, 220, 255)),
    ((40, 10, 10),   (100, 20, 20),  (255, 120, 60)),
    ((10, 40, 10),   (20, 90, 50),   (100, 255, 150)),
    ((40, 20, 60),   (80, 10, 80),   (255, 100, 255)),
    ((60, 30, 0),    (120, 60, 0),   (255, 200, 80)),
]


def _gradient_bg(w: int, h: int, top: tuple, bot: tuple) -> Image.Image:
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for c in range(3):
        col = np.linspace(top[c], bot[c], h, dtype=np.float32)
        arr[:, :, c] = col[:, np.newaxis]
    return Image.fromarray(arr)


# ── Easing ────────────────────────────────────────────────────────────────────
def _ease_out(p: float) -> float:
    return 1.0 - (1.0 - p) ** 2


def _ease_in(p: float) -> float:
    return p ** 2


# ── Font metrics ──────────────────────────────────────────────────────────────
def _line_h(font: ImageFont.FreeTypeFont) -> int:
    try:
        asc, desc = font.getmetrics()
        return asc + abs(desc)
    except Exception:
        dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        bb = dummy.textbbox((0, 0), "Agpqy|कि", font=font)
        return bb[3] - bb[1]


def _text_w(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    return draw.textbbox((0, 0), text, font=font)[2]


# ── Text wrapping ─────────────────────────────────────────────────────────────
def _wrap(text: str, font, max_w: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if cur and _text_w(draw, trial, font) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


# ── Waveform loop (pre-rendered once, reused via ffmpeg) ──────────────────────
_WAVEFORM_LOOP_SECS = 4
_WAVEFORM_LOOP_FPS  = 30


def _waveform_loop_path(accent: tuple, video_w: int, video_h: int,
                        n_bars: int, bar_zone_ratio: float, cfg) -> str:
    """
    Return path to a cached looping waveform MP4.
    Black background + coloured bars; overlaid with ffmpeg screen-blend
    so black disappears and only bars show on the story background.
    Generated once per accent colour, cached in assets/waveform_loops/.
    """
    os.makedirs("assets/waveform_loops", exist_ok=True)
    hex_a = "%02x%02x%02x" % tuple(accent[:3])
    path  = f"assets/waveform_loops/wf_{hex_a}_{video_w}x{video_h}.mp4"

    if os.path.exists(path):
        log.info("Waveform loop cache hit → %s", path)
        return path

    log.info("Rendering waveform loop → %s …", path)
    fps        = _WAVEFORM_LOOP_FPS
    n_frames   = fps * _WAVEFORM_LOOP_SECS
    bar_zone_h = int(video_h * bar_zone_ratio)
    bar_w      = max(2, int(video_w * 0.60 / (n_bars * 1.5)))
    gap        = max(1, bar_w // 2)
    total_bw   = n_bars * (bar_w + gap)
    start_x    = (video_w - total_bw) // 2
    bar_zone_y = video_h - bar_zone_h - int(video_h * 0.02)
    bg_alpha   = getattr(cfg, "STORY_WAVEFORM_BG_ALPHA", 70)
    bar_color  = tuple(getattr(cfg, "STORY_WAVEFORM_COLOR", None) or accent)

    cmd = [
        "ffmpeg", "-y",
        "-f", "rawvideo", "-pixel_format", "rgb24",
        "-video_size", f"{video_w}x{video_h}",
        "-framerate", str(fps),
        "-i", "pipe:0",
        "-c:v", "libx264", "-preset", "ultrafast",
        "-pix_fmt", "yuv420p", "-crf", "23",
        "-t", str(_WAVEFORM_LOOP_SECS),
        path,
    ]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    rng        = random.Random(42)
    phases     = [rng.uniform(0, 2 * math.pi) for _ in range(n_bars)]
    freqs      = [rng.uniform(0.8, 2.5)       for _ in range(n_bars)]
    strip_h    = bar_zone_h + 16
    strip_y0   = bar_zone_y - 8

    for fi in range(n_frames):
        t     = fi / fps
        frame = Image.new("RGB", (video_w, video_h), (0, 0, 0))

        # Semi-transparent strip background
        strip  = Image.new("RGBA", (video_w, strip_h), (0, 0, 0, bg_alpha))
        region = frame.crop((0, strip_y0, video_w, strip_y0 + strip_h)).convert("RGBA")
        frame.paste(Image.alpha_composite(region, strip).convert("RGB"), (0, strip_y0))
        draw = ImageDraw.Draw(frame)

        for i in range(n_bars):
            amp = (0.45
                   + 0.40 * math.sin(2 * math.pi * freqs[i] * t + phases[i])
                   + 0.15 * math.sin(2 * math.pi * freqs[i] * 2.3 * t + phases[i] * 1.7))
            amp    = max(0.05, min(1.0, amp))
            bh_px  = max(4, int(amp * bar_zone_h))
            x      = start_x + i * (bar_w + gap)
            bright = 0.6 + 0.4 * amp
            color  = tuple(min(255, int(c * bright)) for c in bar_color)
            draw.rectangle([x, bar_zone_y + bar_zone_h - bh_px,
                            x + bar_w - 1, bar_zone_y + bar_zone_h], fill=color)

        proc.stdin.write(frame.tobytes())

    proc.stdin.close()
    proc.wait()
    log.info("Waveform loop ready → %s", path)
    return path


# ── Channel badge (cached small-patch composite) ──────────────────────────────
_badge_cache: dict = {}


def _get_badge_patch(text: str, font_path: str, cfg, accent: tuple,
                     img_w: int, img_h: int):
    key = (text, tuple(accent[:3]), img_w, img_h)
    if key in _badge_cache:
        return _badge_cache[key]

    size    = getattr(cfg, "STORY_LOGO_FONT_SIZE", 30)
    lang    = getattr(cfg, "LANGUAGE", "hi")
    font    = _load_font(size, lang, font_path)
    padding = 16
    margin  = 20

    dd   = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    bbox = dd.textbbox((0, 0), text, font=font)
    tw   = bbox[2] - bbox[0]
    th   = bbox[3] - bbox[1]
    bw   = tw + padding * 2
    bh   = th + padding * 2

    x1 = img_w - bw - margin
    y1 = margin
    pad = 4
    patch = Image.new("RGBA", (bw + pad * 2, bh + pad * 2), (0, 0, 0, 0))
    pd    = ImageDraw.Draw(patch)
    bg_c  = getattr(cfg, "STORY_LOGO_BG_COLOR", (0, 0, 0))
    tc    = getattr(cfg, "STORY_LOGO_TEXT_COLOR", (255, 255, 255))
    pd.rounded_rectangle([pad, pad, bw + pad, bh + pad],
                          radius=bh // 2, fill=(*bg_c[:3], 190))
    pd.rounded_rectangle([pad, pad, bw + pad, bh + pad],
                          radius=bh // 2, outline=(*accent[:3], 220), width=2)
    pd.text((pad + padding, pad + padding), text, font=font, fill=tc)

    result = (patch, x1 - pad, y1 - pad)
    _badge_cache[key] = result
    return result


def _draw_badge(img: Image.Image, text: str, font_path: str, cfg, accent: tuple) -> None:
    if not text:
        return
    patch, px, py = _get_badge_patch(text, font_path, cfg, accent, *img.size)
    region = img.crop((px, py, px + patch.width, py + patch.height)).convert("RGBA")
    img.paste(Image.alpha_composite(region, patch).convert("RGB"), (px, py))


# ── Sentence frame renderer ───────────────────────────────────────────────────

def _render_sentence_frame(
    bg: Image.Image,
    lines: list[str],
    font,
    active_word: int,          # index of currently-spoken word (-1 = none)
    text_color: tuple,
    highlight_color: tuple,
    stroke_color: tuple,
    stroke_w: int,
    center_y: int,
    fade_alpha: float = 1.0,   # 0.0 = invisible, 1.0 = fully opaque
) -> Image.Image:
    """
    Render one sentence frame. Only the current sentence is shown —
    centred on screen, word-by-word highlight, with fade alpha applied.
    """
    img  = bg.copy()
    draw = ImageDraw.Draw(img)
    lh   = _line_h(font) + 14
    total_h = len(lines) * lh
    y = center_y - total_h // 2

    word_cursor = 0
    for line in lines:
        words = line.split()
        if not words:
            y += lh
            continue

        # Measure full line for centering
        line_w = _text_w(draw, line, font)
        x = (img.width - line_w) // 2

        for word in words:
            is_active = (active_word >= 0 and word_cursor == active_word)
            col = highlight_color if is_active else text_color

            # Apply fade by blending toward the background colour
            if fade_alpha < 1.0:
                # Sample background colour at word position (approximate)
                bg_sample = bg.getpixel((min(x, bg.width - 1),
                                          min(y + lh // 2, bg.height - 1)))
                col = tuple(int(col[i] * fade_alpha + bg_sample[i] * (1.0 - fade_alpha))
                            for i in range(3))
                sc  = tuple(int(stroke_color[i] * fade_alpha + bg_sample[i] * (1.0 - fade_alpha))
                            for i in range(3))
            else:
                sc = stroke_color

            ww = _text_w(draw, word, font)
            # Stroke
            for dx in range(-stroke_w, stroke_w + 1):
                for dy in range(-stroke_w, stroke_w + 1):
                    if dx == 0 and dy == 0:
                        continue
                    draw.text((x + dx, y + dy), word, font=font, fill=sc)
            draw.text((x, y), word, font=font, fill=col)
            x += ww + _text_w(draw, " ", font)
            word_cursor += 1
        y += lh

    return img


# ── Main compile function ─────────────────────────────────────────────────────

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
    Build the story video:
      Step A — Render sentence frames (one sentence at a time, fade in/out,
                word highlight) via MoviePy VideoClip
      Step B — Overlay looping waveform animation via ffmpeg screen-blend
      Step C — Mux audio
    """
    from moviepy import AudioFileClip, VideoClip

    lang       = getattr(cfg, "LANGUAGE", "hi")
    sub_size   = getattr(cfg, "STORY_SUBTITLE_FONT_SIZE", 95)
    text_color = tuple(getattr(cfg, "STORY_TEXT_COLOR",      (255, 255, 255)))
    hi_color   = tuple(getattr(cfg, "STORY_HIGHLIGHT_COLOR", (255, 220, 60)))
    stroke_col = tuple(getattr(cfg, "STORY_STROKE_COLOR",    (0, 0, 0)))
    stroke_w   = int(getattr(cfg, "STORY_STROKE_WIDTH", 6))
    channel    = getattr(cfg, "STORY_CHANNEL_NAME", "")
    n_bars     = int(getattr(cfg, "STORY_WAVEFORM_BARS", 40))
    fade_dur   = float(getattr(cfg, "STORY_SENTENCE_FADE", 0.22))  # seconds
    bar_ratio  = float(getattr(cfg, "STORY_WAVEFORM_HEIGHT_RATIO", 0.09))
    center_y   = int(video_height * 0.46)
    max_text_w = int(video_width * 0.84)

    font = _load_font(sub_size, lang, font_path)

    # ── Build chunk data ──────────────────────────────────────────────────────
    chunks = []
    dummy_draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    for idx, chunk in enumerate(selected_chunks):
        text    = chunk.get("text", chunk.get("display_text", "")).strip()
        t_start = float(chunk.get("new_start", chunk.get("start", 0.0)))
        t_end   = float(chunk.get("new_end",   chunk.get("end",   t_start + 1.0)))
        if t_end - t_start < 0.05 or not text:
            continue

        palette = PALETTES[idx % len(PALETTES)]
        bg      = _gradient_bg(video_width, video_height, palette[0], palette[1])
        lines   = _wrap(text, font, max_text_w, dummy_draw)
        words   = text.split()

        # Pre-cache wrapped lines for every possible visible word count
        # (avoids re-wrapping on every frame — huge speedup)
        wrap_cache = {}
        for n in range(1, len(words) + 1):
            wrap_cache[n] = _wrap(" ".join(words[:n]), font, max_text_w, dummy_draw)
        wrap_cache[0] = [""]

        chunks.append({
            "t_start":    t_start,
            "t_end":      t_end,
            "bg":         bg,
            "lines":      lines,
            "words":      words,
            "n_words":    len(words),
            "accent":     palette[2],
            "wrap_cache": wrap_cache,
        })

    if not chunks:
        raise RuntimeError("No story chunks to render")

    # ── Waveform loop assets (generated once per accent colour) ───────────────
    unique_accents = list({c["accent"] for c in chunks})
    waveform_loops = {
        acc: _waveform_loop_path(acc, video_width, video_height, n_bars, bar_ratio, cfg)
        for acc in unique_accents
    }
    primary_accent = chunks[0]["accent"]
    wf_loop = waveform_loops.get(primary_accent, list(waveform_loops.values())[0])

    # ── make_frame ────────────────────────────────────────────────────────────
    def make_frame(t: float) -> np.ndarray:
        # Find active chunk
        chunk = None
        for c in chunks:
            if c["t_start"] <= t < c["t_end"]:
                chunk = c
                break
        if chunk is None:
            chunk = chunks[-1]

        dur      = max(chunk["t_end"] - chunk["t_start"], 0.001)
        elapsed  = t - chunk["t_start"]
        progress = elapsed / dur

        # ── Fade alpha: ease in at start, ease out at end ─────────────────
        if elapsed < fade_dur:
            alpha = _ease_out(elapsed / fade_dur)
        elif elapsed > dur - fade_dur:
            alpha = _ease_in((chunk["t_end"] - t) / fade_dur)
        else:
            alpha = 1.0
        alpha = max(0.0, min(1.0, alpha))

        # ── Active word via char-weighted timing ──────────────────────────
        n_words = chunk["n_words"]
        if n_words > 0:
            words   = chunk["words"]
            lengths = [max(1, len(w)) for w in words]
            total   = sum(lengths)
            target  = progress * total
            cumul   = 0
            active_w = n_words - 1
            for i, ln in enumerate(lengths):
                cumul += ln
                if cumul >= target:
                    active_w = i
                    break
        else:
            active_w = -1

        # Show only the sentence for the current chunk (not cumulative)
        # Use full lines — all words shown, active word highlighted
        lines = chunk["lines"]

        # Render frame
        img = _render_sentence_frame(
            chunk["bg"], lines, font, active_w,
            text_color, chunk["accent"], stroke_col, stroke_w,
            center_y, fade_alpha=alpha,
        )

        # Channel badge
        if channel:
            _draw_badge(img, channel, font_path, cfg, chunk["accent"])

        return np.array(img)

    # ── Step A: render subtitle video (no audio, no waveform) ────────────────
    audio_clip = AudioFileClip(audio_path)
    total_dur  = min(chunks[-1]["t_end"], audio_clip.duration)
    audio_clip.close()

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
    log.info("Subtitle render done → %s", tmp_nowave)

    # ── Step B: overlay waveform loop via ffmpeg screen-blend ────────────────
    tmp_waved = output_path.replace(".mp4", "_waved.mp4")
    wf_cmd = [
        "ffmpeg", "-y",
        "-i", tmp_nowave,
        "-stream_loop", "-1",
        "-i", wf_loop,
        "-filter_complex",
        "[0:v]format=rgb24[base];"
        "[1:v]format=rgb24[wf];"
        "[base][wf]blend=all_mode=screen[v];"
        "[v]format=yuv420p[out]",
        "-map", "[out]",
        "-c:v", cfg.VIDEO_CODEC,
        "-preset", "fast", "-crf", "18",
        "-t", str(total_dur),
        tmp_waved,
    ]
    r = subprocess.run(wf_cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log.warning("Waveform overlay failed, using plain video: %s", r.stderr[-300:])
        tmp_waved = tmp_nowave

    # ── Step C: mux audio ────────────────────────────────────────────────────
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

    # Cleanup
    for tmp in [tmp_nowave, tmp_waved]:
        if tmp != output_path and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass

    log.info("Story video → %s", output_path)
