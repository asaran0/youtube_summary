"""
story_mode/styles.py — Subtitle style resolver for story mode.

Story mode has no special per-line styling (no questions, answers,
countdowns) — every line uses the same default font size and color.
This module exists so core/render/subtitles.py has a consistent
interface across modes; if story mode ever needs its own special
styles (e.g. a highlighted "moral of the story" line), they'd be
added here without touching core/render/ at all.
"""


def resolve_style(style: str, cfg) -> dict:
    """Story mode: every line uses the same default size/color."""
    return {"size": cfg.SUBTITLE_FONT_SIZE, "color": (255, 255, 255)}
