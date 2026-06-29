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


def _detect_script(text: str) -> str:
    """Return 'hi' if text contains any Devanagari characters, else 'en'."""
    for ch in text:
        if "\u0900" <= ch <= "\u097F":
            return "hi"
    return "en"


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


# ── Background image / video helpers ─────────────────────────────────────────

def _prepare_image_bg(path: str, video_w: int, video_h: int,
                       blur_radius: int = 18, dim: float = 0.45) -> Image.Image:
    """
    Load an image, resize+crop to fill the frame (cover mode), apply
    Gaussian blur and dimming so subtitle text is always legible.

    blur_radius : pixels of Gaussian blur  (0 = no blur)
    dim         : multiply brightness by this (0.0 = black, 1.0 = original)
    """
    from PIL import ImageFilter
    img = Image.open(path).convert("RGB")
    # Cover: scale so the image fills the frame, crop centre
    iw, ih = img.size
    scale  = max(video_w / iw, video_h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img    = img.resize((nw, nh), Image.LANCZOS)
    left   = (nw - video_w) // 2
    top    = (nh - video_h) // 2
    img    = img.crop((left, top, left + video_w, top + video_h))
    # Blur
    if blur_radius > 0:
        img = img.filter(ImageFilter.GaussianBlur(radius=blur_radius))
    # Dim
    if dim < 1.0:
        arr = np.array(img, dtype=np.float32) * dim
        img = Image.fromarray(arr.clip(0, 255).astype(np.uint8))
    return img


def _get_bg_video_duration(path: str) -> float:
    """Return duration of a video file in seconds using ffprobe."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
    )
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


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

    try:
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
    except (BrokenPipeError, OSError) as e:
        proc.stdin.close()
        proc.wait()
        if os.path.exists(path):
            os.remove(path)
        raise RuntimeError(f"ffmpeg exited while writing waveform frames: {e}") from e

    proc.stdin.close()
    proc.wait()
    if proc.returncode != 0 or not os.path.exists(path):
        if os.path.exists(path):
            os.remove(path)
        raise RuntimeError(
            f"ffmpeg failed to produce waveform loop (exit code {proc.returncode})."
        )
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
    lang    = _detect_script(text)
    font    = _load_font(size, lang, font_path if lang == "hi" else None)
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
    pop_progress: float = 1.0,  # 0.0 = word just appeared, 1.0 = settled
) -> Image.Image:
    """
    Render one sentence frame. Words are revealed progressively as they're
    spoken; the currently-active word pops in with a small upward bounce
    and a brightness flash that settles to the normal highlight colour.
    """
    img  = bg.copy()
    draw = ImageDraw.Draw(img)
    lh   = _line_h(font) + 14
    total_h = len(lines) * lh
    y = center_y - total_h // 2

    pop_progress = max(0.0, min(1.0, pop_progress))
    pop_ease = _ease_out(pop_progress)

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

            word_y = y
            if is_active:
                # Brightness flash: start near-white, settle to highlight colour
                flash_col = tuple(min(255, int(highlight_color[i] * 0.5 + 255 * 0.5)) for i in range(3))
                col = tuple(int(flash_col[i] * (1.0 - pop_ease) + highlight_color[i] * pop_ease)
                            for i in range(3))
                # Upward bounce that settles into place
                word_y = y - int(6 * (1.0 - pop_ease))

            # Apply fade by blending toward the background colour
            if fade_alpha < 1.0:
                bg_sample = bg.getpixel((min(x, bg.width - 1),
                                          min(y + lh // 2, bg.height - 1)))
                col = tuple(int(col[i] * fade_alpha + bg_sample[i] * (1.0 - fade_alpha))
                            for i in range(3))
                sc  = tuple(int(stroke_color[i] * fade_alpha + bg_sample[i] * (1.0 - fade_alpha))
                            for i in range(3))
            else:
                sc = stroke_color

            ww = _text_w(draw, word, font)
            draw.text((x, word_y), word, font=font, fill=col,
                       stroke_width=stroke_w, stroke_fill=sc)
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

    # ── Detect background mode ───────────────────────────────────────────────
    bg_mode      = getattr(cfg, "STORY_BG_MODE",   "gradient").lower()
    bg_image_path = getattr(cfg, "STORY_BG_IMAGE",  "")
    bg_video_path = getattr(cfg, "STORY_BG_VIDEO",  "")
    bg_blur       = int(getattr(cfg,   "STORY_BG_BLUR",    18))
    bg_dim        = float(getattr(cfg, "STORY_BG_DIM",     0.45))

    # Validate and resolve bg_mode
    if bg_mode == "image" and not (bg_image_path and os.path.exists(bg_image_path)):
        log.warning("STORY_BG_MODE=image but STORY_BG_IMAGE not found (%s); "
                    "falling back to gradient.", bg_image_path)
        bg_mode = "gradient"
    if bg_mode == "video" and not (bg_video_path and os.path.exists(bg_video_path)):
        log.warning("STORY_BG_MODE=video but STORY_BG_VIDEO not found (%s); "
                    "falling back to gradient.", bg_video_path)
        bg_mode = "gradient"

    log.info("Background mode: %s", bg_mode)

    # Pre-load image background (shared across all chunks)
    static_image_bg = None
    if bg_mode == "image":
        log.info("Loading background image: %s …", bg_image_path)
        static_image_bg = _prepare_image_bg(
            bg_image_path, video_width, video_height, bg_blur, bg_dim
        )

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
        # Background per chunk:
        #   gradient → animated gradient (unique per sentence)
        #   image    → shared static photo (blur+dim applied once)
        #   video    → gradient used as PIL bg; video composited by ffmpeg later
        if bg_mode == "image" and static_image_bg is not None:
            bg = static_image_bg.copy()
        else:
            bg = _gradient_bg(video_width, video_height, palette[0], palette[1])
        words   = text.split()

        # Incremental wrap cache: wrap_cache[n] = wrapped lines using only
        # the first n words. O(n) total (one _wrap call per word count),
        # safe because each chunk is now exactly one sentence.
        wrap_cache = {0: [""]}
        cur_lines, cur_line = [], ""
        for n, w in enumerate(words, start=1):
            trial = (cur_line + " " + w).strip()
            if cur_line and _text_w(dummy_draw, trial, font) > max_text_w:
                cur_lines.append(cur_line)
                cur_line = w
            else:
                cur_line = trial
            wrap_cache[n] = cur_lines + [cur_line]

        chunks.append({
            "t_start":    t_start,
            "t_end":      t_end,
            "bg":         bg,
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
        pop_progress = 1.0  # how far the active word's pop-in animation has progressed
        if n_words > 0:
            words   = chunk["words"]
            lengths = [max(1, len(w)) for w in words]
            total   = sum(lengths)
            target  = progress * total
            cumul_before = 0
            active_w = n_words - 1
            for i, ln in enumerate(lengths):
                if cumul_before + ln >= target:
                    active_w = i
                    break
                cumul_before += ln

            word_frac_dur = lengths[active_w] / total
            word_dur_sec  = word_frac_dur * dur
            into_word     = max(0.0, (target - cumul_before) / max(lengths[active_w], 1)) * word_dur_sec
            pop_dur       = min(0.16, max(word_dur_sec * 0.6, 0.04))
            pop_progress  = max(0.0, min(1.0, into_word / pop_dur))
        else:
            active_w = -1

        # Reveal only words spoken so far (progressive word-by-word reveal)
        visible_n = max(active_w + 1, 0)
        lines = chunk["wrap_cache"].get(visible_n, chunk["wrap_cache"][chunk["n_words"]])

        # Render frame
        img = _render_sentence_frame(
            chunk["bg"], lines, font, active_w,
            text_color, chunk["accent"], stroke_col, stroke_w,
            center_y, fade_alpha=alpha, pop_progress=pop_progress,
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
        logger="bar",
    )
    video_clip.close()
    log.info("Subtitle render done → %s", tmp_nowave)

    # ── Step B1: video background (only when bg_mode == "video") ─────────────
    # The subtitle render (tmp_nowave) was produced on a gradient bg.
    # For video mode we composite the real background video BEHIND the
    # subtitle layer using ffmpeg's overlay filter with a luma-key so the
    # gradient background becomes transparent, leaving only the text visible.
    #
    # Strategy:
    #   [bg_video]  looped to total_dur, scaled to fill frame
    #   [subtitle]  our rendered video (gradient bg + text)
    #   overlay with lumakey: removes the dark gradient, keeps bright text
    #   Result: real video background + bright subtitle text on top
    tmp_bg_applied = tmp_nowave   # will be replaced if video bg is used
    if bg_mode == "video":
        tmp_bg_applied = output_path.replace(".mp4", "_bgvideo.mp4")
        log.info("Compositing background video: %s …", bg_video_path)

        # lumakey threshold: gradient bg pixels are dark (<0.25 luma),
        # text pixels are bright (>0.8). This removes the bg cleanly.
        # For very dark text on light bg, invert with chromakey instead.
        luma_thresh = float(getattr(cfg, "STORY_BG_VIDEO_LUMA_KEY",  0.20))
        luma_tol    = float(getattr(cfg, "STORY_BG_VIDEO_LUMA_TOL",  0.12))
        bg_video_dim = float(getattr(cfg, "STORY_BG_DIM", 0.45))

        bg_filter = (
            # Scale bg video to fill frame (cover), loop it
            f"[1:v]scale={video_width}:{video_height}:force_original_aspect_ratio=increase,"
            f"crop={video_width}:{video_height},"
            f"eq=brightness={bg_video_dim - 1.0:.2f},"   # dim it (eq brightness: -1..1)
            f"format=rgb24[bg];"
            # Make subtitle layer RGBA, luma-key out the dark gradient bg
            f"[0:v]format=rgba,"
            f"lumakey=threshold={luma_thresh}:tolerance={luma_tol}:softness=0.05[fg];"
            # Overlay fg on top of bg video
            f"[bg][fg]overlay=format=auto,"
            f"format=yuv420p[out]"
        )
        bg_cmd = [
            "ffmpeg", "-y",
            "-i", tmp_nowave,           # [0] subtitle render
            "-stream_loop", "-1",
            "-i", bg_video_path,        # [1] background video (looped)
            "-filter_complex", bg_filter,
            "-map", "[out]",
            "-c:v", cfg.VIDEO_CODEC, "-preset", "fast", "-crf", "18",
            "-t", str(total_dur),
            tmp_bg_applied,
        ]
        r = subprocess.run(bg_cmd, capture_output=True, text=True)
        if r.returncode != 0:
            log.warning("Video background composite failed; using gradient: %s",
                        r.stderr[-400:])
            tmp_bg_applied = tmp_nowave

    # ── Step B2: overlay waveform loop via ffmpeg screen-blend ───────────────
    tmp_waved = output_path.replace(".mp4", "_waved.mp4")
    wf_cmd = [
        "ffmpeg", "-y",
        "-i", tmp_bg_applied,
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
        log.warning("Waveform overlay failed, using video without waveform: %s", r.stderr[-300:])
        tmp_waved = tmp_bg_applied

    # ── Step C: mux audio (optionally mixed with ducked background music) ────
    bg_music = getattr(cfg, "STORY_BG_MUSIC", None)
    music_vol_db = float(getattr(cfg, "STORY_BG_MUSIC_VOLUME_DB", -22))
    duck_enabled = bool(getattr(cfg, "STORY_BG_MUSIC_DUCK", True))

    if bg_music and os.path.exists(bg_music):
        log.info("Mixing background music (%s) under narration …", bg_music)
        if duck_enabled:
            # Sidechain-compress the music against the narration so it
            # automatically ducks under speech and comes back up in gaps.
            audio_filter = (
                f"[2:a]volume={music_vol_db}dB,aloop=loop=-1:size=2e9,atrim=0:{total_dur}[music];"
                f"[1:a]asplit=2[narr1][narr2];"
                f"[music][narr1]sidechaincompress=threshold=0.05:ratio=8:attack=5:release=300[ducked];"
                f"[narr2][ducked]amix=inputs=2:duration=first:dropout_transition=0[aout]"
            )
        else:
            audio_filter = (
                f"[2:a]volume={music_vol_db}dB,aloop=loop=-1:size=2e9,atrim=0:{total_dur}[music];"
                f"[1:a][music]amix=inputs=2:duration=first:dropout_transition=0[aout]"
            )
        mux_cmd = [
            "ffmpeg", "-y",
            "-i", tmp_waved,
            "-i", audio_path,
            "-i", bg_music,
            "-filter_complex", audio_filter,
            "-map", "0:v", "-map", "[aout]",
            "-c:v", "copy",
            "-c:a", cfg.AUDIO_CODEC,
            "-b:a", cfg.AUDIO_BITRATE,
            "-shortest",
            output_path,
        ]
        r = subprocess.run(mux_cmd, capture_output=True, text=True)
        if r.returncode != 0:
            log.warning("Background music mix failed, falling back to narration-only audio: %s",
                        r.stderr[-400:])
            bg_music = None  # fall through to plain mux below

    if not bg_music or not os.path.exists(bg_music or ""):
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
    for tmp in [tmp_nowave, tmp_waved,
                output_path.replace(".mp4", "_bgvideo.mp4")]:
        if tmp != output_path and os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass

    log.info("Story video → %s", output_path)
