"""
qa_mode/styles.py — Subtitle style resolver for Q&A / interview-prep mode.

This is the only place that knows what "question", "answer",
"countdown", and "try_yourself" mean visually — core/render/subtitles.py
calls this as a callback without any built-in knowledge of QA mode's
vocabulary, so a future mode could define entirely different style
tags without touching core/render/ at all.
"""


def resolve_style(style: str, cfg) -> dict:
    """Look up font size / RGB color for a given Q&A style tag."""
    if style == "question":
        return {"size": cfg.QA_QUESTION_FONT_SIZE, "color": cfg.QA_QUESTION_FONT_COLOR}
    if style == "answer":
        return {"size": cfg.QA_ANSWER_FONT_SIZE, "color": cfg.QA_ANSWER_FONT_COLOR}
    if style == "countdown":
        return {"size": cfg.QA_COUNTDOWN_FONT_SIZE, "color": cfg.QA_COUNTDOWN_FONT_COLOR}
    if style == "try_yourself":
        return {"size": cfg.QA_TRY_YOURSELF_FONT_SIZE, "color": cfg.QA_TRY_YOURSELF_FONT_COLOR}
    return {"size": cfg.SUBTITLE_FONT_SIZE, "color": (255, 255, 255)}
