"""
core/fonts.py — Centralised font loading for the entire video pipeline.

Key problems this solves
────────────────────────
1.  Devanagari boxes / tofu
    PIL's default layout engine renders each Unicode codepoint as an
    independent glyph, so Devanagari conjuncts like ध्य (ध + ् + य)
    come out as separate disconnected boxes.  The RAQM layout engine
    (libraqm + HarfBuzz) does proper OpenType shaping and correctly
    joins conjuncts.  This module always requests Layout.RAQM.

2.  English words inside Hindi text
    Any font used for Hindi must also cover the Latin Unicode block so
    that English words embedded in a Hindi sentence render normally
    rather than as boxes.  FreeSansBold covers both scripts.

3.  Font-path chaos
    Every renderer previously had its own list of candidate paths that
    diverged over time.  One canonical priority-ordered list lives here.

Usage
─────
    from core.fonts import get_font, get_font_path

    font = get_font(size=72, lang="hi")   # returns ImageFont
    path = get_font_path(lang="hi")       # returns str path
"""

import os
from functools import lru_cache

from PIL import ImageFont

# ── Candidate font paths — ordered by preference ────────────────────────────
# For Hindi / Devanagari we need a font that has:
#   (a) Devanagari Unicode block (U+0900–U+097F)
#   (b) Latin block so English words inside Hindi text still render
# FreeSansBold is installed on Ubuntu/Debian and covers both.
# The project's own assets/fonts/ folder is checked first so users can
# drop in NotoSansDevanagari-Bold.ttf without touching code.

_HINDI_CANDIDATES = [
    # Project-local (drop your preferred font here)
    "assets/fonts/NotoSansDevanagari-Bold.ttf",
    "assets/fonts/NotoSansDevanagari-Regular.ttf",
    "assets/NotoSansDevanagari-Bold.ttf",
    "assets/NotoSansDevanagari-Regular.ttf",
    # System Noto (Ubuntu noto package)
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    # GNU FreeFont — ships on most Linux distros, covers Devanagari + Latin
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    # macOS
    "/System/Library/Fonts/Kohinoor.ttc",
    "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc",
    "/Library/Fonts/NotoSansDevanagari-Regular.ttf",
    # Last resort — will render Latin fine but Devanagari may be boxes
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]

_LATIN_CANDIDATES = [
    # Project-local
    "assets/fonts/Poppins-Bold.ttf",
    "assets/fonts/NotoSans-Bold.ttf",
    # System Google Fonts (present on this server)
    "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
    "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf",
    "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
    # Fallbacks
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
]


@lru_cache(maxsize=None)
def get_font_path(lang: str = "en") -> str:
    """
    Return the path of the best available font for *lang*.
    Result is cached so disk scanning only happens once per language.
    """
    candidates = _HINDI_CANDIDATES if lang in ("hi", "hig") else _LATIN_CANDIDATES
    for path in candidates:
        if path and os.path.exists(path):
            return path
    # Absolute last resort — PIL built-in bitmap font (no Devanagari)
    return ""


@lru_cache(maxsize=256)
def get_font(size: int, lang: str = "en", path_hint: str = "") -> ImageFont.FreeTypeFont:
    """
    Load and return a PIL ImageFont for *lang* at *size* pixels.

    Always uses Layout.RAQM so that Devanagari conjuncts are shaped
    correctly.  Falls back gracefully if RAQM is unavailable or the
    font file is missing.

    path_hint — if set, tried first (lets callers override for a
                specific font without losing the fallback chain).
    """
    # Build candidate list: hint first, then language-appropriate list
    if path_hint:
        all_candidates = (
            [path_hint]
            + (_HINDI_CANDIDATES if lang in ("hi", "hig") else _LATIN_CANDIDATES)
        )
    else:
        all_candidates = (
            _HINDI_CANDIDATES if lang in ("hi", "hig") else _LATIN_CANDIDATES
        )

    # Try RAQM first (correct shaping), then basic engine as fallback
    for use_raqm in (True, False):
        engine = ImageFont.Layout.RAQM if use_raqm else ImageFont.Layout.BASIC
        for path in all_candidates:
            if not path or not os.path.exists(path):
                continue
            try:
                return ImageFont.truetype(path, size=size, layout_engine=engine)
            except Exception:
                continue

    # PIL built-in — last resort, no Unicode
    return ImageFont.load_default()


def font_supports_devanagari(path: str) -> bool:
    """Quick check: does this font file render 'अ' as a non-empty glyph?"""
    try:
        f   = ImageFont.truetype(path, 40, layout_engine=ImageFont.Layout.RAQM)
        bb  = f.getbbox("अ")
        return (bb[2] - bb[0]) > 2 and (bb[3] - bb[1]) > 2
    except Exception:
        return False


# ── Per-word mixed-script rendering ──────────────────────────────────────────

import re as _re

def is_devanagari_word(word: str) -> bool:
    """True if the word contains any Devanagari character (U+0900–U+097F)."""
    return any('\u0900' <= ch <= '\u097F' for ch in word)


def _word_font(word: str, size: int) -> "ImageFont.FreeTypeFont":
    """Return the correct font for a single word based on its script."""
    lang = "hi" if is_devanagari_word(word) else "en"
    return get_font(size, lang=lang)


def measure_mixed_line(text: str, size: int) -> int:
    """
    Return the pixel width of *text* rendered with per-word font switching.
    Used for line-wrapping calculations so wrapping accounts for the fact
    that English words in a Hindi sentence use the wider Poppins font.
    """
    from PIL import Image, ImageDraw
    _dummy_img  = Image.new("RGB", (1, 1))
    _dummy_draw = ImageDraw.Draw(_dummy_img)

    words = text.split()
    if not words:
        return 0
    total = 0
    for i, word in enumerate(words):
        font = _word_font(word, size)
        bb   = _dummy_draw.textbbox((0, 0), word, font=font)
        total += bb[2] - bb[0]
        if i < len(words) - 1:
            sp_font = _word_font(word, size)   # space same font as preceding word
            sp_bb   = _dummy_draw.textbbox((0, 0), " ", font=sp_font)
            total  += sp_bb[2] - sp_bb[0]
    return total


def wrap_mixed_text(text: str, size: int, max_width: int) -> list:
    """
    Word-wrap *text* using per-word font widths so wrapping is accurate
    for mixed Hindi/English content.  Returns list of line strings.
    """
    words = text.split()
    if not words:
        return [""]

    from PIL import Image, ImageDraw
    _dummy_img  = Image.new("RGB", (1, 1))
    _dummy_draw = ImageDraw.Draw(_dummy_img)

    def _word_w(w):
        font = _word_font(w, size)
        bb   = _dummy_draw.textbbox((0, 0), w, font=font)
        return bb[2] - bb[0]

    def _space_w(w):
        font = _word_font(w, size)
        bb   = _dummy_draw.textbbox((0, 0), " ", font=font)
        return bb[2] - bb[0]

    lines, cur_words, cur_w = [], [], 0
    for word in words:
        ww = _word_w(word)
        sw = _space_w(word)
        if cur_words and cur_w + sw + ww > max_width:
            lines.append(" ".join(cur_words))
            cur_words, cur_w = [word], ww
        else:
            cur_w += (sw if cur_words else 0) + ww
            cur_words.append(word)
    if cur_words:
        lines.append(" ".join(cur_words))
    return lines


def render_mixed_line(
    draw,
    x: int,
    y: int,
    line: str,
    size: int,
    text_color: tuple,
    highlight_color: tuple = None,
    active_word_idx: int = -1,    # index within THIS line's words; -1 = no highlight
    stroke_width: int = 0,
    stroke_fill: tuple = (0, 0, 0),
    pop_scale: float = 1.0,       # >1.0 makes the active word slightly larger (pop anim)
) -> int:
    """
    Render one line of mixed Hindi/English text with per-word font switching.

    Words containing Devanagari characters → FreeSansBold (RAQM shaped).
    Words with only Latin/numbers/punctuation → Poppins-Bold (sharp, modern).

    active_word_idx  : which word in *this line* is the currently spoken
                       word (for the karaoke-style highlight). -1 = none.
    pop_scale        : scale factor for the active word (pop-in animation).
                       1.0 = normal size; pass values from _ease_out() for
                       a smooth grow effect.

    Returns the total pixel width rendered (useful for centering).
    """
    words = line.split()
    if not words:
        return 0

    total_w = 0
    cx      = x

    for i, word in enumerate(words):
        is_active = (i == active_word_idx)
        col       = highlight_color if (is_active and highlight_color) else text_color

        # Choose font — slightly larger for active word (pop animation)
        word_size = int(size * pop_scale) if is_active and pop_scale > 1.0 else size
        font      = _word_font(word, word_size)

        bb   = draw.textbbox((cx, y), word, font=font)
        word_w = bb[2] - bb[0]

        draw.text(
            (cx, y), word, font=font, fill=col,
            stroke_width=stroke_width,
            stroke_fill=stroke_fill,
        )

        # Space after word (use current word's font for space width)
        sp_font = font if not is_active else _word_font(word, size)  # normal size space
        sp_bb   = draw.textbbox((0, 0), " ", font=sp_font)
        sp_w    = sp_bb[2] - sp_bb[0]

        cx      += word_w + (sp_w if i < len(words) - 1 else 0)
        total_w  = cx - x

    return total_w


def line_height_for_size(size: int) -> int:
    """
    Return a consistent line height for mixed-script text at *size*.
    Uses the taller of both fonts plus a small leading gap.
    """
    hi_font = get_font(size, "hi")
    en_font = get_font(size, "en")
    def _lh(f):
        try:
            a, d = f.getmetrics()
            return a + abs(d)
        except Exception:
            return size + 8
    return max(_lh(hi_font), _lh(en_font)) + 6
