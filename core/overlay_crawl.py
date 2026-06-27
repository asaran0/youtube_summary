"""
overlay_crawl.py
================
Self-contained module for compositing animated crawl/ticker overlays onto a
PIL Image frame.  Zero dependencies outside Pillow + stdlib.

Designed so you can add as many crawl "ads" as you want — subscribe banners,
hooks, promos — each defined as a simple dict.  The renderer composites them
in order, so stacking is free.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

QUICK START
-----------
    from core.overlay_crawl import CrawlSpec, render_crawl_overlays

    specs = [
        CrawlSpec(
            text        = ">> Subscribe for Upcoming Q&A Sessions!",
            icon_left   = "(*)",            # ASCII icon drawn in accent colour
            icon_right  = "->",
            start_time  = total_dur - 5.0,  # show in last 5 s
            end_time    = total_dur,
            y_frac      = 0.42,             # 42% from top of frame
            style       = "pill",           # "pill" | "banner" | "neon" | "ghost"
            direction   = "ltr",            # left-to-right  ("rtl" also works)
            font        = my_font,
            text_color  = (255, 255, 255),
            accent_color= (245, 200, 66),
            bg_color    = (15, 15, 30),
            bg_opacity  = 0.82,
            padding_x   = 32,
            padding_y   = 14,
        ),
    ]

    # Inside make_frame(t):
    img = render_crawl_overlays(img, t, specs)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ANIMATION PHASES
----------------
Each CrawlSpec has a total duration = end_time - start_time.

    |← slide_in →|←─────── hold ────────→|← slide_out →|
    off-screen     fully visible            off-screen

slide_in  = min(0.6 s, 25% of duration)   crawl enters from left/right edge
hold      = remaining time                 text is fully visible, centred
slide_out = same as slide_in               crawl exits to left/right edge

You can set  hold_only=True  to skip the slide animation (just fade in/out).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

STYLES
------
  "pill"    Rounded pill with solid bg + thin accent border
  "banner"  Full-width solid bar (like a news ticker)
  "neon"    Dark bg + glowing accent border (multi-layer)
  "ghost"   No background, text + soft drop-shadow only

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

Color = Tuple[int, int, int]   # RGB


@dataclass
class CrawlSpec:
    """
    Defines ONE crawl/ticker animation.

    Required
    --------
    text        : str           — main message
    start_time  : float         — seconds from video start when crawl begins
    end_time    : float         — seconds from video start when crawl ends
    font        : ImageFont     — PIL font (already loaded by caller)

    Position
    --------
    y_frac      : float = 0.42  — vertical position as fraction of frame height
                                  0.0 = top, 1.0 = bottom
    x_frac      : float = 0.5   — horizontal centre when fully visible (0–1)

    Content
    -------
    icon_left   : str  = ""     — ASCII icon drawn left of text in accent colour
    icon_right  : str  = ""     — ASCII icon drawn right of text in accent colour
    sub_text    : str  = ""     — smaller line below main text (same font, 70% size)

    Style
    -----
    style       : str  = "pill" — "pill" | "banner" | "neon" | "ghost"
    direction   : str  = "ltr"  — "ltr" (left→right) | "rtl" (right→left)
    hold_only   : bool = False  — skip slide animation, just appear/disappear

    Colours
    -------
    text_color   : Color = (255, 255, 255)
    accent_color : Color = (245, 200, 66)
    bg_color     : Color = (15,  15,  30)
    bg_opacity   : float = 0.82           — 0.0 fully transparent, 1.0 opaque

    Sizing
    ------
    padding_x : int = 32    — horizontal padding inside pill/banner
    padding_y : int = 14    — vertical padding inside pill/banner
    border_w  : int = 3     — border thickness for pill/neon
    """

    text         : str
    start_time   : float
    end_time     : float
    font         : ImageFont.FreeTypeFont

    y_frac       : float = 0.42
    x_frac       : float = 0.5

    icon_left    : str   = "(*)"
    icon_right   : str   = ""
    sub_text     : str   = ""

    style        : str   = "pill"
    direction    : str   = "ltr"
    hold_only    : bool  = False

    text_color   : Color = (255, 255, 255)
    accent_color : Color = (245, 200,  66)
    bg_color     : Color = (15,  15,  30)
    bg_opacity   : float = 0.82

    padding_x    : int   = 32
    padding_y    : int   = 14
    border_w     : int   = 3


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_crawl_overlays(
    img: Image.Image,
    t: float,
    specs: list[CrawlSpec],
) -> Image.Image:
    """
    Composite all active CrawlSpec overlays onto `img` at time `t`.

    Parameters
    ----------
    img   : PIL RGB image (the current video frame)
    t     : current time in seconds
    specs : list of CrawlSpec (order = z-order, first = bottom)

    Returns
    -------
    Modified PIL RGB image (new object, original unchanged)
    """
    result = img.copy()
    for spec in specs:
        if t < spec.start_time or t >= spec.end_time:
            continue
        result = _draw_one_crawl(result, t, spec)
    return result


# ---------------------------------------------------------------------------
# Internal rendering
# ---------------------------------------------------------------------------

def _ease_out_cubic(x: float) -> float:
    return 1.0 - (1.0 - x) ** 3


def _ease_in_cubic(x: float) -> float:
    return x ** 3


def _draw_one_crawl(img: Image.Image, t: float, spec: CrawlSpec) -> Image.Image:
    W, H = img.size
    draw_probe = ImageDraw.Draw(img)

    # ── Measure text pieces ──────────────────────────────────────────────────
    def tw(text, fnt=None):
        fnt = fnt or spec.font
        bb = draw_probe.textbbox((0, 0), text, font=fnt)
        return bb[2] - bb[0]

    def th(fnt=None):
        fnt = fnt or spec.font
        # Use ascent+descent from getmetrics() so descenders (g,y,p,q)
        # are fully included — textbbox height often clips them.
        try:
            asc, desc = fnt.getmetrics()
            return asc + abs(desc)
        except Exception:
            bb = draw_probe.textbbox((0, 0), "Agpqy|", font=fnt)
            return bb[3] - bb[1]

    icon_l_str = (spec.icon_left  + "  ") if spec.icon_left  else ""
    icon_r_str = ("  " + spec.icon_right) if spec.icon_right else ""

    main_tw  = tw(spec.text)
    iconl_tw = tw(icon_l_str) if icon_l_str else 0
    iconr_tw = tw(icon_r_str) if icon_r_str else 0
    content_w = iconl_tw + main_tw + iconr_tw
    line_h    = th()

    # Sub-text uses a 70%-size version — PIL doesn't resize fonts dynamically,
    # so we just use the same font at reduced apparent size via a scaled surface.
    # For simplicity: sub-text is drawn at 75% scale using a Transform trick.
    has_sub  = bool(spec.sub_text)
    sub_tw   = tw(spec.sub_text) if has_sub else 0

    # Box sizing
    px, py    = spec.padding_x, spec.padding_y
    box_w     = max(content_w, sub_tw) + px * 2
    box_h     = line_h + py * 2 + (int(line_h * 0.75) + 6 if has_sub else 0)

    # ── Animation timing ─────────────────────────────────────────────────────
    total_dur  = max(spec.end_time - spec.start_time, 0.001)
    elapsed    = t - spec.start_time
    slide_dur  = 0.0 if spec.hold_only else min(0.55, total_dur * 0.25)

    # X positions: off-screen left and right
    if spec.style == "banner":
        target_x = 0                        # banner always full width
        off_left  = -W
        off_right =  W
    else:
        target_x  = int(W * spec.x_frac - box_w / 2)   # centred at x_frac
        off_left  = -box_w - 10
        off_right =  W + 10

    enter_from = off_left  if spec.direction == "ltr" else off_right
    exit_to    = off_right if spec.direction == "ltr" else off_left

    if elapsed < slide_dur:                     # slide in
        p   = _ease_out_cubic(elapsed / slide_dur)
        x   = int(enter_from + (target_x - enter_from) * p)
    elif elapsed > total_dur - slide_dur:       # slide out
        p   = _ease_in_cubic((elapsed - (total_dur - slide_dur)) / slide_dur)
        x   = int(target_x + (exit_to - target_x) * p)
    else:                                       # hold
        x   = target_x

    y = int(H * spec.y_frac - box_h / 2)

    # ── Build the crawl patch as an RGBA surface ─────────────────────────────
    style = spec.style

    if style == "banner":
        patch_w, patch_h = W, box_h
        patch_x          = 0
    else:
        patch_w = box_w
        patch_h = box_h
        patch_x = x

    patch = Image.new("RGBA", (patch_w, patch_h), (0, 0, 0, 0))
    pd    = ImageDraw.Draw(patch)
    alpha = int(255 * max(0.0, min(1.0, spec.bg_opacity)))
    bg    = (*spec.bg_color[:3], alpha)
    acc   = (*spec.accent_color[:3], 255)
    txt   = (*spec.text_color[:3],   255)

    # ── Style backgrounds ────────────────────────────────────────────────────
    if style == "pill":
        radius = patch_h // 2
        pd.rounded_rectangle([0, 0, patch_w - 1, patch_h - 1],
                              radius=radius, fill=bg)
        pd.rounded_rectangle([0, 0, patch_w - 1, patch_h - 1],
                              radius=radius,
                              outline=acc, width=spec.border_w)

    elif style == "banner":
        # No background fill — accent lines only (top and bottom)
        pd.rectangle([0, 0, patch_w, spec.border_w + 1], fill=acc)
        pd.rectangle([0, patch_h - spec.border_w - 1, patch_w, patch_h], fill=acc)

    elif style == "neon":
        radius = patch_h // 2
        # Multi-layer glow effect using progressively larger rectangles
        for glow_r in range(spec.border_w + 6, spec.border_w - 1, -1):
            glow_a = int(60 * (1 - glow_r / (spec.border_w + 7)))
            glow_c = (*spec.accent_color[:3], glow_a)
            pd.rounded_rectangle(
                [-glow_r, -glow_r, patch_w - 1 + glow_r, patch_h - 1 + glow_r],
                radius=radius + glow_r, outline=glow_c, width=1,
            )
        pd.rounded_rectangle([0, 0, patch_w - 1, patch_h - 1],
                              radius=radius, fill=bg)
        pd.rounded_rectangle([0, 0, patch_w - 1, patch_h - 1],
                              radius=radius, outline=acc, width=spec.border_w)

    elif style == "ghost":
        # No background — just a soft shadow behind text
        pass

    # ── Text content ─────────────────────────────────────────────────────────
    if style == "banner":
        # Centre text within the full-width banner
        text_x = (patch_w - content_w) // 2 - (W - box_w) // 2
        # But honour the slide animation: shift text proportionally
        text_x = (patch_w - content_w) // 2
    else:
        text_x = px

    text_y = py

    # Shadow for ghost style or general legibility
    shadow_off = 2
    for sx, sy in [(shadow_off, shadow_off)]:
        if icon_l_str:
            pd.text((text_x + sx, text_y + sy), icon_l_str,
                    font=spec.font, fill=(0, 0, 0, 80))
        pd.text((text_x + iconl_tw + sx, text_y + sy), spec.text,
                font=spec.font, fill=(0, 0, 0, 80))
        if icon_r_str:
            pd.text((text_x + iconl_tw + main_tw + sx, text_y + sy), icon_r_str,
                    font=spec.font, fill=(0, 0, 0, 80))

    # Actual text
    if icon_l_str:
        pd.text((text_x, text_y), icon_l_str,
                font=spec.font, fill=acc)
    pd.text((text_x + iconl_tw, text_y), spec.text,
            font=spec.font, fill=txt)
    if icon_r_str:
        pd.text((text_x + iconl_tw + main_tw, text_y), icon_r_str,
                font=spec.font, fill=acc)

    # Sub-text (below, slightly indented, 75% opacity)
    if has_sub:
        sub_y    = text_y + line_h + 6
        sub_x    = text_x + iconl_tw  # align under main text
        sub_col  = (*spec.text_color[:3], int(255 * 0.72))
        pd.text((sub_x + shadow_off, sub_y + shadow_off), spec.sub_text,
                font=spec.font, fill=(0, 0, 0, 60))
        pd.text((sub_x, sub_y), spec.sub_text,
                font=spec.font, fill=sub_col)

    # ── Composite patch onto frame ───────────────────────────────────────────
    base = img.convert("RGBA")
    if style == "banner":
        # Banner: always at x=0, slide only affects x of text (not the bar)
        base.paste(patch, (0, y), patch)
    else:
        # Clamp to frame edges
        cx = max(-patch_w + 10, min(W - 10, x))
        base.paste(patch, (cx, y), patch)

    return base.convert("RGB")


# ---------------------------------------------------------------------------
# Convenience builder — default subscribe spec
# ---------------------------------------------------------------------------

def make_subscribe_crawl(
    total_dur   : float,
    font        : ImageFont.FreeTypeFont,
    text        : str   = "Subscribe for Upcoming Q&A Sessions!",
    sub_text    : str   = "Hit the bell to never miss a video",
    show_last   : float = 5.0,
    y_frac      : float = 0.42,
    style       : str   = "pill",
    direction   : str   = "ltr",
    accent_color: Color = (245, 200, 66),
    bg_color    : Color = (15,  15,  30),
    bg_opacity  : float = 0.55,
) -> CrawlSpec:
    """
    Return a ready-to-use CrawlSpec for a subscribe ticker that slides in
    during the last `show_last` seconds of the video.

    Usage::

        from core.overlay_crawl import make_subscribe_crawl, render_crawl_overlays

        crawl_specs = [make_subscribe_crawl(total_dur, my_font)]

        # In make_frame(t):
        img = render_crawl_overlays(img, t, crawl_specs)
    """
    return CrawlSpec(
        text         = text,
        sub_text     = sub_text,
        icon_left    = "(+)",
        icon_right   = ">>",
        start_time   = max(0.0, total_dur - show_last),
        end_time     = total_dur,
        font         = font,
        y_frac       = y_frac,
        style        = style,
        direction    = direction,
        text_color   = (255, 255, 255),
        accent_color = accent_color,
        bg_color     = bg_color,
        bg_opacity   = bg_opacity,
        padding_x    = 36,
        padding_y    = 26,
        border_w     = 3,
    )


def make_hook_crawl(
    start_time  : float,
    duration    : float,
    font        : ImageFont.FreeTypeFont,
    text        : str,
    sub_text    : str   = "",
    y_frac      : float = 0.10,
    style       : str   = "neon",
    direction   : str   = "ltr",
    accent_color: Color = (80, 200, 255),
    bg_color    : Color = (5,   5,  20),
    bg_opacity  : float = 0.88,
) -> CrawlSpec:
    """
    Return a CrawlSpec for a hook/promo that can appear at any point.
    Perfect for the intro hook (start_time=0, duration=4) or mid-video
    promos.

    Usage::

        hook = make_hook_crawl(
            start_time = 0,
            duration   = 4.0,
            font       = my_font,
            text       = "3 things you MUST know about Kafka",
        )
        crawl_specs = [hook, subscribe_crawl]
    """
    return CrawlSpec(
        text         = text,
        sub_text     = sub_text,
        icon_left    = ">>",
        icon_right   = "<<",
        start_time   = start_time,
        end_time     = start_time + duration,
        font         = font,
        y_frac       = y_frac,
        style        = style,
        direction    = direction,
        text_color   = (255, 255, 255),
        accent_color = accent_color,
        bg_color     = bg_color,
        bg_opacity   = bg_opacity,
        padding_x    = 36,
        padding_y    = 14,
        border_w     = 4,
    )


# ---------------------------------------------------------------------------
# Empty-space smooth transition overlay
# ---------------------------------------------------------------------------

# ── Emoji → ASCII symbol map (PIL fonts don't render emoji glyphs) ────────────
_EMOJI_MAP = {
    "💬": "[>]", "👍": "[+]", "❤️": "<3", "📤": "^",
    "🔔": "(i)", "🎯": "*",  "✅": "[v]", "🔥": "!",
    "⭐": "*",   "🙏": "/\\", "👇": "v",  "💡": "!",
    "🎉": ">>",  "🏆": "[*]", "📌": ">",  "🚀": ">>",
}

def _clean_text(text: str) -> str:
    """Replace emoji with ASCII symbols and strip leftover variation selectors."""
    import re
    for emoji, sym in _EMOJI_MAP.items():
        text = text.replace(emoji, sym)
    # Remove any remaining emoji / variation selectors not in map
    text = re.sub(r"[𐀀-􏿿]", "", text)  # supplemental planes
    text = re.sub(r"️", "", text)                    # variation selector-16
    return text.strip()


def _wrap_text_lines(text: str, font, max_w: int) -> list[str]:
    """Word-wrap text to fit max_w pixels. Returns list of line strings."""
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        bb = probe.textbbox((0, 0), trial, font=font)
        if cur and (bb[2] - bb[0]) > max_w:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines or [""]


def render_empty_space_overlay(
    img: Image.Image,
    t: float,
    total_dur: float,
    font: ImageFont.FreeTypeFont,
    text_start: str  = "Try to Answer",
    text_end: str    = "In the Comments!",
    fade_in_at: float  = 10.0,
    fade_out_at: float =  3.0,
    bg_color: Color    = (0, 0, 0),
    text_color: Color  = (255, 255, 255),
    accent_color: Color= (245, 200, 66),
    y_frac: float      = 0.8,
    max_opacity: float = 0.55,
) -> Image.Image:
    """
    Smooth semi-transparent text overlay near the end of the video.
    Supports multi-line word-wrap and emoji → ASCII symbol conversion
    (PIL fonts don't render emoji glyphs natively).
    No underline — clean pill with text only.
    """
    time_left = total_dur - t
    if time_left > fade_in_at:
        return img

    if time_left > fade_out_at:
        progress = 1.0 - (time_left - fade_out_at) / (fade_in_at - fade_out_at)
        opacity  = max_opacity * _ease_out_cubic(max(0.0, min(1.0, progress)))
        label    = text_start
    else:
        progress = time_left / fade_out_at
        opacity  = max_opacity * _ease_out_cubic(max(0.0, min(1.0, progress)))
        label    = text_end

    if opacity < 0.01:
        return img

    # Clean emoji → ASCII, then word-wrap to 80% of frame width
    W, H    = img.size
    label   = _clean_text(label)
    max_w   = int(W * 0.82) - 80   # subtract padding
    lines   = _wrap_text_lines(label, font, max_w)

    alpha   = int(255 * opacity)
    pad_x   = 44
    pad_y   = 22

    # Measure all lines
    probe   = ImageDraw.Draw(img)
    try:
        asc, desc = font.getmetrics()
        lh = asc + abs(desc) + 8
    except Exception:
        bb = probe.textbbox((0, 0), "Ag", font=font)
        lh = (bb[3] - bb[1]) + 8

    max_line_w = max(
        probe.textbbox((0, 0), ln, font=font)[2] for ln in lines
    )
    box_w   = max_line_w + pad_x * 2
    box_h   = lh * len(lines) + pad_y * 2

    cx  = W // 2
    cy  = int(H * y_frac)
    bx  = max(0, min(W - box_w, cx - box_w // 2))
    by  = max(0, min(H - box_h, cy - box_h // 2))

    patch = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    pd    = ImageDraw.Draw(patch)

    # Rounded pill background — no underline, no accent line
    radius = min(box_h // 2, 36)
    pd.rounded_rectangle(
        [0, 0, box_w - 1, box_h - 1],
        radius=radius,
        fill=(*bg_color[:3], alpha),
    )
    # Thin accent border instead of underline
    pd.rounded_rectangle(
        [0, 0, box_w - 1, box_h - 1],
        radius=radius,
        outline=(*accent_color[:3], min(255, alpha + 40)),
        width=2,
    )

    # Draw each line centred in the pill
    for i, line in enumerate(lines):
        lw  = probe.textbbox((0, 0), line, font=font)[2]
        lx  = (box_w - lw) // 2
        ly  = pad_y + i * lh
        # Subtle shadow
        pd.text((lx + 1, ly + 1), line, font=font,
                fill=(*bg_color[:3], min(255, alpha + 50)))
        pd.text((lx, ly), line, font=font,
                fill=(*text_color[:3], min(255, alpha + 80)))

    base = img.convert("RGBA")
    bx   = max(0, min(W - box_w, bx))
    by      = max(0, min(H - box_h, by))
    base.paste(patch, (bx, by), patch)
    return base.convert("RGB")


# ---------------------------------------------------------------------------
# "Try to answer" toast — one per question, slides in at question start
# ---------------------------------------------------------------------------

def make_toast_crawls(
    entries       : list,
    font          : "ImageFont.FreeTypeFont",
    video_w       : int,
    video_h       : int,
    q_band_h      : int,
    prog_bar_h    : int,
    text          : str   = "Pause the video and try to answer by yourself first!",
    duration      : float = 4.0,
    style         : str   = "pill",
    accent_color  : Color = (245, 200, 66),
    bg_color      : Color = (15,  15,  30),
    bg_opacity    : float = 0.88,
    max_w_frac    : float = 0.80,
    top_offset_px : int   = 8,     # extra px gap below the progress bar / status bar
    padding_x     : int   = 40,    # horizontal padding inside pill
    padding_y     : int   = 20,    # vertical padding — increase to avoid text clipping
) -> list:
    """
    Return a list of CrawlSpec objects — one per question entry — each
    showing a "try to answer" toast at the start of the question phase.

    The toast:
      - slides in from the left at entry["v_start"]
      - holds for min(duration, question_phase_duration - 0.6s)
      - slides out before the answer starts
      - appears at the same vertical position as the subscribe banner
        (just below the top progress bar)

    Text is automatically word-wrapped to fit max_w_frac * video_w.
    Multi-line text is joined with  " · "  so it reads as one flowing line
    inside the pill (PIL single-text rendering keeps it clean).

    Parameters
    ----------
    entries      : list of entry dicts (from runner._run_split_layout)
    font         : PIL font for the toast text
    video_w/h    : frame dimensions
    q_band_h     : pixel height of the question band
    prog_bar_h   : pixel height of the top progress bar
    text         : toast message (auto-wrapped)
    duration     : max seconds the toast is visible
    style        : CrawlSpec style ("pill" recommended)
    accent_color : RGB accent colour
    bg_color     : RGB background colour
    bg_opacity   : 0-1 opacity
    max_w_frac   : max pill width fraction of video_w (for wrapping)
    """
    # ── Word-wrap the text to fit inside max_w_frac * video_w ────────────────
    max_text_px = int(video_w * max_w_frac) - 80   # subtract padding
    probe_img   = Image.new("RGB", (video_w, video_h))
    probe_draw  = ImageDraw.Draw(probe_img)

    def measure(s):
        bb = probe_draw.textbbox((0, 0), s, font=font)
        return bb[2] - bb[0]

    words      = text.split()
    lines      = []
    cur_line   = []
    for word in words:
        test = " ".join(cur_line + [word])
        if measure(test) <= max_text_px or not cur_line:
            cur_line.append(word)
        else:
            lines.append(" ".join(cur_line))
            cur_line = [word]
    if cur_line:
        lines.append(" ".join(cur_line))

    # Join lines with  " ·  " separator — keeps it as a single CrawlSpec.text
    # so the existing single-line pill renderer handles it cleanly.
    # For genuine multi-line we use sub_text for the second line.
    main_text = lines[0] if lines else text
    sub_text  = "  ".join(lines[1:]) if len(lines) > 1 else ""

    # ── Y position: prog_bar_h + top_offset_px + half pill height ───────────
    # top_offset_px gives a configurable gap below the status/progress bar.
    # Pill height includes padding_y * 2 so text never clips.
    line_h_est = max(30, int(font.size * 1.35)) if hasattr(font, 'size') else 44
    pill_h     = line_h_est + padding_y * 2 + (line_h_est + 6 if sub_text else 0)
    pill_h     = max(44, pill_h)
    y_top      = prog_bar_h + top_offset_px          # top edge of pill
    y_frac     = (y_top + pill_h // 2) / video_h     # centre of pill

    # ── Build one CrawlSpec per entry ─────────────────────────────────────────
    specs = []
    for entry in entries:
        q_start   = entry["v_start"]
        a_start   = entry["a_start"]
        q_dur     = max(a_start - q_start, 0.1)

        # Toast appears AFTER the question is spoken — in the tail of the
        # question phase, not at the very start.
        # We start it when ~80% of question phase has elapsed (question nearly done),
        # leaving 0.55s for slide-in and `duration` seconds of hold before answer.
        slide_dur   = 0.55
        toast_end   = a_start - 0.1          # always gone before answer starts

        # How much time is available for the toast?
        # Use at most `duration` but shrink gracefully if question phase is short.
        available   = toast_end - (q_start + q_dur * 0.75) - slide_dur
        actual_dur  = max(0.8, min(duration, available))   # min 0.8s, max `duration`

        toast_start = toast_end - actual_dur - slide_dur
        toast_start = max(q_start + 0.2, toast_start)      # never before question starts

        hold_time   = toast_end - toast_start - slide_dur
        if hold_time <= 0.15 or toast_start >= toast_end:
            continue   # genuinely no room — skip

        specs.append(CrawlSpec(
            text         = main_text,
            sub_text     = sub_text,
            icon_left    = ">>",
            icon_right   = "",
            start_time   = toast_start,
            end_time     = toast_end,
            font         = font,
            y_frac       = y_frac,
            style        = style,
            direction    = "ltr",
            text_color   = (255, 255, 255),
            accent_color = accent_color,
            bg_color     = bg_color,
            bg_opacity   = bg_opacity,
            padding_x    = padding_x,
            padding_y    = padding_y,
            border_w     = 3,
        ))
    return specs
