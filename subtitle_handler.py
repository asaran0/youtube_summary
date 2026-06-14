"""
subtitle_handler.py — Generate subtitle files and burn them into the video.

Two output files are created:
    output/<title>.srt   – standard SRT for any media player / YouTube upload
    temp/subtitles.ass   – styled ASS file used internally by ffmpeg to burn
                           clear, well-visible subtitles into the video.

The ASS file uses:
    •  Large font (config.SUBTITLE_FONT_SIZE)
    •  White text with a semi-transparent black box behind each line
    •  Positioned at the bottom of the screen with safe margins
    •  Noto Sans Devanagari (or whichever Hindi font was detected)
"""

import os
import re
import textwrap

import config
from utils import get_logger, seconds_to_srt, seconds_to_ass, _ass_time_to_seconds

log = get_logger("subtitles")


# ─────────────────────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────────────────────

def generate_subtitle_files(
    selected_chunks: list[dict],
    output_srt_path: str,
    font_path: str,
    video_width:  int,
    video_height: int,
) -> str:
    """
    Build .srt and .ass subtitle files from the remapped segments.

    Returns the path to the .ass file (used for burning into video).
    """
    # Flatten chunks → individual segments with new_start / new_end
    subtitle_items = _flatten_to_items(selected_chunks)
    log.info("Building subtitles from %d items", len(subtitle_items))

    # SRT file (standard, for external use / YouTube upload)
    _write_srt(subtitle_items, output_srt_path)
    log.info("SRT saved → %s", output_srt_path)

    # ASS file (internal, styled, for burning)
    ass_path = os.path.join(config.TEMP_DIR, "subtitles.ass")
    _write_ass(subtitle_items, ass_path, font_path, video_width, video_height)
    log.info("ASS saved → %s", ass_path)

    return ass_path


def burn_subtitles(
    input_video: str,
    ass_path:    str,
    output_video: str,
    font_dir:    str,
    font_path:   str | None = None,
) -> None:
    """
    Burn subtitles into video using moviepy + PIL.
    Replaces the ffmpeg ass filter (requires libass, not always available).
    """
    from moviepy.editor import VideoFileClip
    from PIL import Image, ImageDraw, ImageFont
    import numpy as np

    log.info("Burning subtitles (moviepy+PIL) …")

    # ── Parse ASS dialogue lines ──────────────────────────────
    subtitles = []
    with open(ass_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.startswith("Dialogue:"):
                continue
            parts = line.split(",", 9)
            if len(parts) < 10:
                continue
            start = _ass_time_to_seconds(parts[1].strip())
            end   = _ass_time_to_seconds(parts[2].strip())
            text  = parts[9].strip()
            # Clean ASS tags and line breaks
            text  = re.sub(r"\{[^}]*\}", "", text)
            text  = text.replace(r"\N", "\n").replace(r"\n", "\n")
            if text:
                subtitles.append((start, end, text))

    # ── Load video ────────────────────────────────────────────
    clip = VideoFileClip(input_video)
    W, H = clip.size

    # ── Find font ─────────────────────────────────────────────
    font_size = config.SUBTITLE_FONT_SIZE
    font_pil = _load_subtitle_font(font_path, font_dir, font_size, ImageFont)
    fallback_font = _load_fallback_font(font_size, ImageFont)
    if font_pil is None:
        font_pil = fallback_font or ImageFont.load_default()
    if fallback_font is None:
        fallback_font = font_pil

    bg_alpha  = config.SUBTITLE_BG_ALPHA   # 0-255 opacity

    def make_frame(t):
        frame = clip.get_frame(t)
        img   = Image.fromarray(frame).convert("RGBA")

        for (start, end, text) in subtitles:
            if not (start <= t < end):
                continue

            draw   = ImageDraw.Draw(img)
            raw_lines = text.split("\n")
            lines = []
            for raw_line in raw_lines:
                lines.extend(
                    _wrap_line_to_pixels(
                        draw,
                        raw_line,
                        font_pil,
                        fallback_font,
                        int(W * config.SUBTITLE_MAX_WIDTH_RATIO),
                    )
                )

            # Measure total text block size
            line_sizes = [_mixed_text_size(draw, ln, font_pil, fallback_font) for ln in lines]
            line_heights = [size[1] for size in line_sizes]
            line_widths  = [size[0] for size in line_sizes]
            pad     = 10
            block_w = max(line_widths) + pad * 2
            block_h = sum(line_heights) + pad * 2 + 4 * (len(lines) - 1)

            x0 = (W - block_w) // 2
            y0 = _subtitle_y(H, block_h)

            if bg_alpha > 0:
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
                odraw   = ImageDraw.Draw(overlay)
                odraw.rounded_rectangle(
                    [x0, y0, x0 + block_w, y0 + block_h],
                    radius=6,
                    fill=(0, 0, 0, bg_alpha),
                )
                img = Image.alpha_composite(img, overlay)
                draw = ImageDraw.Draw(img)

            # Draw each line centred
            cy = y0 + pad
            total_words = _count_words(lines)
            progress = (t - start) / max(end - start, 0.01)
            active_word = min(max(int(progress * total_words), 0), max(total_words - 1, 0))
            word_offset = 0
            for i, ln in enumerate(lines):
                lw = line_widths[i]
                lx = (W - lw) // 2
                for dx, dy in [(-2,0),(2,0),(0,-2),(0,2),(-1,-1),(1,-1),(-1,1),(1,1)]:
                    _draw_highlighted_text(
                        draw, (lx + dx, cy + dy), ln, font_pil, fallback_font,
                        active_word, word_offset, outline=True
                    )
                _draw_highlighted_text(
                    draw, (lx, cy), ln, font_pil, fallback_font,
                    active_word, word_offset, outline=False
                )
                word_offset += _count_words([ln])
                cy += line_heights[i] + 4

        return np.array(img.convert("RGB"))

    # ── Write output ──────────────────────────────────────────
    final = clip.fl(lambda gf, t: make_frame(t), apply_to="video")
    final.write_videofile(
        output_video,
        codec=config.VIDEO_CODEC,
        audio_codec=config.AUDIO_CODEC,
        bitrate=config.VIDEO_BITRATE,
        audio_bitrate=config.AUDIO_BITRATE,
        logger=None,
    )
    log.info("Subtitles burned → %s", output_video)

# ─────────────────────────────────────────────────────────────
#  SRT WRITER
# ─────────────────────────────────────────────────────────────

def _write_srt(items: list[dict], path: str) -> None:
    lines = []
    for i, item in enumerate(items, start=1):
        text = _wrap_text(item["text"], config.SUBTITLE_MAX_CHARS)
        lines.append(str(i))
        lines.append(f"{seconds_to_srt(item['start'])} --> {seconds_to_srt(item['end'])}")
        lines.append(text)
        lines.append("")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ─────────────────────────────────────────────────────────────
#  ASS WRITER
# ─────────────────────────────────────────────────────────────

def _write_ass(
    items: list[dict],
    path:  str,
    font_path:    str,
    video_width:  int,
    video_height: int,
) -> None:
    """Write a styled ASS subtitle file."""
    font_name = _extract_font_name(font_path)

    # Convert config colour (R,G,B) to ASS colour &H00BBGGRR
    # ASS stores colours as BGR, hex
    ass_primary = "&H00FFFFFF"       # white text
    ass_outline = "&H00000000"       # black outline
    ass_back    = _rgba_to_ass_back(config.SUBTITLE_BG_ALPHA)

    # Vertical margin from bottom edge
    margin_v = config.SUBTITLE_MARGIN_Y

    header = f"""\
[Script Info]
ScriptType: v4.00+
PlayResX: {video_width}
PlayResY: {video_height}
ScaledBorderAndShadow: yes
YCbCr Matrix: None

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{config.SUBTITLE_FONT_SIZE},{ass_primary},&H000000FF,{ass_outline},{ass_back},1,0,0,0,100,100,0,0,3,2,1,2,20,20,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    dialogue_lines = []
    for item in items:
        text = _ass_escape(_wrap_text_ass(item["text"], config.SUBTITLE_MAX_CHARS))
        start = seconds_to_ass(item["start"])
        end   = seconds_to_ass(item["end"])
        dialogue_lines.append(
            f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}"
        )

    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(dialogue_lines))
        f.write("\n")


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────

def _flatten_to_items(chunks: list[dict]) -> list[dict]:
    """
    Flatten chunk → segment hierarchy into a flat list of
    {start, end, text} items using remapped timestamps.
    """
    items = []
    for chunk in chunks:
        for seg in chunk.get("segments", []):
            start = seg["new_start"] if "new_start" in seg else seg["start"]
            end   = seg["new_end"] if "new_end" in seg else seg["end"]
            text  = seg["text"].strip()
            if text and (end - start) > 0.1:
                items.append({"start": start, "end": end, "text": text})
    return items


def _load_subtitle_font(font_path: str | None, font_dir: str, size: int, image_font):
    """Prefer the exact detected font so Hindi text does not render as boxes."""
    candidates = []
    if font_path:
        candidates.append(font_path)
    if font_dir and os.path.isdir(font_dir):
        for fname in os.listdir(font_dir):
            if fname.lower().endswith((".ttf", ".ttc", ".otf")):
                candidates.append(os.path.join(font_dir, fname))

    for candidate in candidates:
        try:
            return image_font.truetype(
                candidate,
                size=size,
                layout_engine=image_font.Layout.RAQM,
            )
        except Exception:
            continue
    return None


def _load_fallback_font(size: int, image_font):
    for path in config.FALLBACK_FONT_SEARCH_PATHS:
        if not os.path.exists(path):
            continue
        try:
            return image_font.truetype(
                path,
                size=size,
                layout_engine=image_font.Layout.RAQM,
            )
        except Exception:
            continue
    return None


def _subtitle_y(video_height: int, block_height: int) -> int:
    if config.SUBTITLE_POSITION == "middle":
        return max((video_height - block_height) // 2, 0)
    return max(video_height - config.SUBTITLE_MARGIN_Y - block_height, 0)


def _font_for_char(ch: str, primary_font, fallback_font):
    code = ord(ch)
    if 0x0900 <= code <= 0x097F:
        return primary_font
    return fallback_font


def _mixed_text_size(draw, text: str, primary_font, fallback_font) -> tuple[int, int]:
    width = 0
    height = 0
    for run, font in _font_runs(text, primary_font, fallback_font):
        bbox = draw.textbbox((0, 0), run, font=font)
        width += bbox[2] - bbox[0]
        height = max(height, bbox[3] - bbox[1])
    return width, height or primary_font.size


def _wrap_line_to_pixels(draw, text: str, primary_font, fallback_font, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [text]

    lines = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if current and _mixed_text_size(draw, trial, primary_font, fallback_font)[0] > max_width:
            lines.append(current)
            current = word
        else:
            current = trial

    if current:
        lines.append(current)
    return lines


def _draw_mixed_text(draw, xy: tuple[int, int], text: str, primary_font, fallback_font, fill) -> None:
    x, y = xy
    for run, font in _font_runs(text, primary_font, fallback_font):
        draw.text((x, y), run, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), run, font=font)
        x += bbox[2] - bbox[0]


def _draw_highlighted_text(
    draw,
    xy: tuple[int, int],
    text: str,
    primary_font,
    fallback_font,
    active_word: int,
    word_offset: int,
    outline: bool,
) -> None:
    x, y = xy
    word_index = word_offset
    for token in _text_tokens(text):
        is_word = bool(token.strip())
        if outline:
            fill = (0, 0, 0, 230)
        elif is_word and word_index == active_word:
            fill = (*config.SUBTITLE_HIGHLIGHT_COLOR, 255)
        else:
            fill = (255, 255, 255, 255)

        _draw_mixed_text(draw, (x, y), token, primary_font, fallback_font, fill)
        token_w, _ = _mixed_text_size(draw, token, primary_font, fallback_font)
        x += token_w
        if is_word:
            word_index += 1


def _text_tokens(text: str) -> list[str]:
    return re.findall(r"\S+|\s+", text)


def _count_words(lines: list[str]) -> int:
    return max(sum(1 for line in lines for token in _text_tokens(line) if token.strip()), 1)


def _font_runs(text: str, primary_font, fallback_font) -> list[tuple[str, object]]:
    runs = []
    current = []
    current_font = None

    for ch in text:
        font = _font_for_char(ch, primary_font, fallback_font)
        if current and font is not current_font:
            runs.append(("".join(current), current_font))
            current = [ch]
        else:
            current.append(ch)
        current_font = font

    if current:
        runs.append(("".join(current), current_font))
    return runs


def _wrap_text(text: str, max_chars: int) -> str:
    """Wrap text to max_chars per line using standard textwrap."""
    return "\n".join(textwrap.wrap(text, width=max_chars))


def _wrap_text_ass(text: str, max_chars: int) -> str:
    """Wrap for ASS using \\N as line break."""
    wrapped = textwrap.wrap(text, width=max_chars)
    return r"\N".join(wrapped)


def _ass_escape(text: str) -> str:
    """Escape characters that have special meaning in ASS."""
    return text.replace("{", r"\{").replace("}", r"\}")


def _extract_font_name(font_path: str) -> str:
    """Try to get the PostScript font name from the file, else use filename."""
    try:
        from PIL import ImageFont
        font = ImageFont.truetype(font_path, size=12)
        return font.getname()[0]   # family name
    except Exception:
        base = os.path.basename(font_path)
        name = os.path.splitext(base)[0]
        # Normalise  NotoSansDevanagari-Regular → Noto Sans Devanagari
        return name.replace("-", " ").replace("_", " ")


def _rgba_to_ass_back(alpha: int) -> str:
    """Convert 0-255 opacity to ASS BackColour (background box colour)."""
    # ASS alpha: 0x00=opaque, 0xFF=transparent  →  invert
    ass_alpha = 255 - alpha
    return f"&H{ass_alpha:02X}000000"
