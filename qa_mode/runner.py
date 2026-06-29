"""
qa_mode/runner.py — Q&A / interview-prep mode pipeline.
"""

import os
import re
import time

from utils import (
    get_logger, ensure_dirs, clean_temp, get_video_duration,
    find_hindi_font, human_duration,
)
from qa_mode.tts import generate_tts_audio
from core.render import subtitles as subtitle_render
from core.render import slideshow as slideshow_render
from core.render import metadata as metadata_writer

from qa_mode import config as default_cfg
from qa_mode.loader import load_qa_file
from qa_mode.styles import resolve_style

log = get_logger("qa.runner")


# ── Paragraph-aware text helpers ──────────────────────────────────────────────

def _build_display_tokens(text: str) -> list[tuple[str, bool]]:
    """
    Convert display_text (which contains \\n\\n paragraph breaks) into a
    structured list of  (word, is_para_break_before)  tuples.

    Example:
        "Hello world.\\n\\nNew paragraph here."
        → [("Hello", False), ("world.", False),
           ("New", True),  ("paragraph", False), ("here.", False)]

    This lets us slice the first N words for the word-reveal animation
    while still knowing where paragraph boundaries fall.
    """
    tokens: list[tuple[str, bool]] = []
    paragraphs = re.split(r'\n\n+', text)
    for pi, para in enumerate(paragraphs):
        para = para.strip()
        if not para:
            continue
        if para.startswith("\u0001CODE\u0001"):
            # Code block: keep as ONE opaque token so it reveals as a whole
            # unit (it isn't spoken word-by-word, just shown once reached).
            tokens.append((para, pi > 0))
            continue
        words = para.split()
        for wi, word in enumerate(words):
            is_break = (pi > 0 and wi == 0)   # first word of a non-first paragraph
            tokens.append((word, is_break))
    return tokens


def _tokens_to_text(tokens: list[tuple[str, bool]], n: int) -> str:
    """
    Reconstruct text from the first n tokens, re-inserting \\n\\n where
    is_para_break_before is True.  Used to build visible_text for wrapping.
    """
    parts: list[str] = []
    for word, is_break in tokens[:n]:
        if is_break and parts:
            parts.append("\n\n")
        elif parts:
            parts.append(" ")
        parts.append(word)
    return "".join(parts)


def _build_qa_pairs(selected: list[dict], cfg=None) -> list[dict]:
    """
    Collapse flat segments into one dict per Q/A pair.
    spoken_words  — words from TTS text (parens stripped) — drives timing/highlight
    display_text  — full text including parens, with paragraph line breaks
    """
    cfg_ref = [cfg]  # mutable ref so inner scope can read it
    pairs = []
    i = 0
    while i < len(selected):
        seg = selected[i]
        if seg.get("style") == "question":
            question_text = seg.get("display_text", seg.get("text", ""))
            q_start = seg.get("new_start", seg.get("start", 0.0))
            j = i + 1
            while j < len(selected) and selected[j].get("style") != "answer":
                j += 1
            if j < len(selected):
                ans     = selected[j]
                a_start = ans.get("new_start", ans.get("start", 0.0))
                a_end   = ans.get("new_end",   ans.get("end",   a_start + 1.0))

                # spoken_text: what TTS speaks (parens stripped) — for timing
                spoken_text  = ans.get("spoken_text", ans.get("text", ""))
                # display_text: what screen shows (parens kept, paragraphs)
                display_text = ans.get("display_text", spoken_text)

                # display_tokens: list of (word, is_para_break_before)
                # Preserves \n\n paragraph boundaries so the renderer can
                # re-insert them even when slicing a partial visible window.
                display_tokens = _build_display_tokens(display_text)

                # POST_ANSWER_HOLD: extra seconds to hold final answer on screen
                # (configured via QA_POST_ANSWER_HOLD in config.py)
                hold = float(getattr(cfg_ref[0], "QA_POST_ANSWER_HOLD", 1.0))

                pairs.append({
                    "question":         question_text,
                    # q_spoken_words uses the RAW spoken text (no "Question N:" prefix)
                    # so char-weighted timing matches the actual TTS output.
                    "q_spoken_words":   seg.get("text", question_text).split(),
                    "q_num":            seg.get("q_num", ans.get("q_num", len(pairs) + 1)),
                    "display_text":     display_text,
                    "spoken_words":     spoken_text.split(),
                    "display_words":    display_text.split(),
                    "display_tokens":   display_tokens,
                    "video_start":      q_start,
                    "video_end":        a_end + hold,
                    "ans_start":        a_start,
                    "ans_end":          a_end,
                })
                i = j + 1
            else:
                i += 1
        else:
            i += 1
    return pairs


import numpy as np

def _run_split_layout(selected, tts_audio_path, title, target_w, target_h, font_path, cfg) -> str:
    from qa_mode.qa_slideshow import (
        _load_fonts, _wrap_text_px, _paginate, _render_slide,
        _line_height, _parse_color, _count_words_in_lines,
    )
    from moviepy import AudioFileClip, VideoClip
    from PIL import Image
    import numpy as np

    qa_pairs = _build_qa_pairs(selected, cfg)
    if not qa_pairs:
        raise RuntimeError("No Q/A pairs found in selected segments")

    audio_dur = get_video_duration(tts_audio_path)

    # Rescale placeholder timestamps if TTS didn't write new_start/new_end
    last_end = qa_pairs[-1]["video_end"]
    if last_end < audio_dur * 0.5:
        log.warning("Rescaling placeholder timestamps (last=%.1fs audio=%.1fs)",
                    last_end, audio_dur)
        scale = audio_dur / max(last_end, 0.001)
        for p in qa_pairs:
            p["video_start"] *= scale
            p["video_end"]   *= scale
            p["ans_start"]   *= scale
            p["ans_end"]     *= scale

    safe_title = _safe_title(title)
    final_path = os.path.join(cfg.OUTPUT_DIR, f"{safe_title}_qa.mp4")

    # ── Geometry ──────────────────────────────────────────────────────────
    split_ratio  = getattr(cfg, "QA_SLIDE_SPLIT_RATIO", 0.35)
    margin_top_q = int(target_h * getattr(cfg, "QA_SLIDE_MARGIN_TOP_Q",  0.04))
    margin_top_a = int(target_h * getattr(cfg, "QA_SLIDE_MARGIN_TOP_A",  0.04))
    margin_bot_a = int(target_h * getattr(cfg, "QA_SLIDE_MARGIN_BOT_A",  0.10))
    margin_side  = int(target_w * getattr(cfg, "QA_SLIDE_MARGIN_SIDE",   0.05))

    q_band_h = int(target_h * split_ratio)
    a_band_h = target_h - q_band_h

    q_bg     = _parse_color(getattr(cfg, "QA_SLIDE_QUESTION_BG",    (205, 139,  97)))
    a_bg     = _parse_color(getattr(cfg, "QA_SLIDE_ANSWER_BG",      (183, 204, 174)))
    q_color  = _parse_color(getattr(cfg, "QA_SLIDE_QUESTION_COLOR", (30,  30,  30)))
    a_color  = _parse_color(getattr(cfg, "QA_SLIDE_ANSWER_COLOR",   (30,  30,  30)))
    hi_color = _parse_color(getattr(cfg, "QA_SLIDE_HIGHLIGHT_COLOR",
                             getattr(cfg, "SUBTITLE_HIGHLIGHT_COLOR", (220, 120, 0))))

    font_q, font_a = _load_fonts(font_path, cfg)
    # Reserve ~32px on the left for the bullet glyph (● ) so wrapped lines
    # don't extend past the right margin when bullets are drawn.
    _BULLET_RESERVE = 32
    text_w      = target_w - 2 * margin_side - _BULLET_RESERVE
    a_line_h    = _line_height(font_a)
    para_gap    = int(a_line_h * 0.6)
    avail_a_h   = a_band_h - margin_top_a - margin_bot_a
    # Each paragraph gap (None separator) costs para_gap px of vertical space.
    # Assume avg ~2 paragraphs per page so reserve 2 * para_gap.
    # This keeps text well inside the margin_bot_a boundary.
    avail_a_h_for_lines = max(1, avail_a_h - 2 * para_gap)
    max_a_lines = max(1, avail_a_h_for_lines // (a_line_h + 4))

    # ── Feature: load new config values ──────────────────────────────────
    from PIL import ImageFont as _PILFont

    use_progress    = getattr(cfg, "QA_PROGRESS_BAR",       True)
    prog_bar_h      = getattr(cfg, "QA_PROGRESS_BAR_HEIGHT", 8)
    prog_bar_color  = _parse_color(getattr(cfg, "QA_PROGRESS_BAR_COLOR", (245, 200, 66)))
    prog_bar_bg     = _parse_color(getattr(cfg, "QA_PROGRESS_BAR_BG",    (80, 80, 80)))

    use_badge       = getattr(cfg, "QA_QUESTION_BADGE",      True)
    badge_text_col  = _parse_color(getattr(cfg, "QA_BADGE_TEXT_COLOR",   (255, 255, 255)))
    badge_padding   = getattr(cfg, "QA_BADGE_PADDING",       18)
    badge_margin    = getattr(cfg, "QA_BADGE_MARGIN",        20)
    _badge_fs       = getattr(cfg, "QA_BADGE_FONT_SIZE",     36)

    use_divider     = getattr(cfg, "QA_DIVIDER",             True)
    divider_color   = _parse_color(getattr(cfg, "QA_DIVIDER_COLOR",  (255, 255, 255)))
    divider_h       = getattr(cfg, "QA_DIVIDER_HEIGHT",      4)
    divider_alpha   = getattr(cfg, "QA_DIVIDER_ALPHA",       80)

    sentence_reveal = getattr(cfg, "QA_SENTENCE_REVEAL",     True)
    fade_dur        = getattr(cfg, "QA_FADE_DURATION",       0.35)

    use_watermark   = getattr(cfg, "QA_WATERMARK",           True)
    watermark_text  = getattr(cfg, "QA_WATERMARK_TEXT",      "@ai.interview.guru1") if use_watermark else None
    watermark_col   = _parse_color(getattr(cfg, "QA_WATERMARK_COLOR", (255, 255, 255)))
    watermark_alpha = getattr(cfg, "QA_WATERMARK_ALPHA",     90)
    _wm_fs          = getattr(cfg, "QA_WATERMARK_FONT_SIZE", 32)

    # Load badge + watermark fonts (reuse same font file as answer font)
    from qa_mode.qa_slideshow import _load_fonts as _lf2
    _badge_font = _load_fonts(font_path, type("_C", (), {"LANGUAGE": getattr(cfg,"LANGUAGE","en"),
        "QA_SLIDE_QUESTION_FONT_SIZE": _badge_fs,
        "QA_SLIDE_ANSWER_FONT_SIZE":   _badge_fs,
        "FALLBACK_FONT_SEARCH_PATHS":  getattr(cfg,"FALLBACK_FONT_SEARCH_PATHS",[]),
        "HINDI_FONT_SEARCH_PATHS":     getattr(cfg,"HINDI_FONT_SEARCH_PATHS",[]),
    })())[1]
    _wm_font = _load_fonts(font_path, type("_C", (), {"LANGUAGE": getattr(cfg,"LANGUAGE","en"),
        "QA_SLIDE_QUESTION_FONT_SIZE": _wm_fs,
        "QA_SLIDE_ANSWER_FONT_SIZE":   _wm_fs,
        "FALLBACK_FONT_SEARCH_PATHS":  getattr(cfg,"FALLBACK_FONT_SEARCH_PATHS",[]),
        "HINDI_FONT_SEARCH_PATHS":     getattr(cfg,"HINDI_FONT_SEARCH_PATHS",[]),
    })())[1]

    # Subscribe strip font — large and bold-feeling, bigger than badge
    _sub_fs = max(32, getattr(cfg, "QA_SUBSCRIBE_FONT_SIZE", int(
        getattr(cfg, "QA_SLIDE_QUESTION_FONT_SIZE", 52) * 0.72
    )))
    _sub_font = _load_fonts(font_path, type("_C", (), {
        "LANGUAGE":                  getattr(cfg, "LANGUAGE", "en"),
        "QA_SLIDE_QUESTION_FONT_SIZE": _sub_fs,
        "QA_SLIDE_ANSWER_FONT_SIZE":   _sub_fs,
        "FALLBACK_FONT_SEARCH_PATHS":  getattr(cfg, "FALLBACK_FONT_SEARCH_PATHS", []),
        "HINDI_FONT_SEARCH_PATHS":     getattr(cfg, "HINDI_FONT_SEARCH_PATHS", []),
    })())[0]

    # Question number label font — smaller than question font
    _qnum_fs = max(20, getattr(cfg, "QA_QNUM_FONT_SIZE", int(
        getattr(cfg, "QA_SLIDE_QUESTION_FONT_SIZE", 52) * 0.55
    )))
    _qnum_font = _load_fonts(font_path, type("_C", (), {
        "LANGUAGE":                  getattr(cfg, "LANGUAGE", "en"),
        "QA_SLIDE_QUESTION_FONT_SIZE": _qnum_fs,
        "QA_SLIDE_ANSWER_FONT_SIZE":   _qnum_fs,
        "FALLBACK_FONT_SEARCH_PATHS":  getattr(cfg, "FALLBACK_FONT_SEARCH_PATHS", []),
        "HINDI_FONT_SEARCH_PATHS":     getattr(cfg, "HINDI_FONT_SEARCH_PATHS", []),
    })())[0]

    # ── Crawl / ticker overlays (subscribe, hooks, promos) ─────────────────
    from core.overlay_crawl import (make_subscribe_crawl, render_crawl_overlays,
                                    render_empty_space_overlay, make_toast_crawls)
    subscribe_secs   = float(getattr(cfg, "QA_SUBSCRIBE_SECS",  5.0))
    subscribe_text   = getattr(cfg, "QA_SUBSCRIBE_TEXT",
                               "Subscribe for Upcoming Q&A Sessions!")
    subscribe_accent = _parse_color(getattr(cfg, "QA_SUBSCRIBE_ACCENT",
                                            (245, 200, 66)))
    subscribe_bg     = _parse_color(getattr(cfg, "QA_SUBSCRIBE_BG",
                                            (15, 15, 30)))
    subscribe_style  = getattr(cfg, "QA_SUBSCRIBE_STYLE", "pill")
    # crawl_specs is a list — add more CrawlSpec objects here for hooks/promos
    # They are evaluated lazily (need total_dur), so we build after safe_dur is set.
    _crawl_specs_pending = True   # flag: build after safe_dur known

    # Bottom-of-question-band progress animation config
    use_bot_progress     = getattr(cfg, "QA_BOT_PROGRESS",        True)
    bot_progress_h       = getattr(cfg, "QA_BOT_PROGRESS_HEIGHT", 6)
    bot_progress_color   = _parse_color(getattr(cfg, "QA_BOT_PROGRESS_COLOR",
                                                 (245, 200, 66)))
    bot_progress_bg      = _parse_color(getattr(cfg, "QA_BOT_PROGRESS_BG",
                                                 (60, 60, 60)))

    total_pairs = len(qa_pairs)

    # Pre-compute per-pair entry data
    entries = []
    for entry_idx, pair in enumerate(qa_pairs):
        # Wrap display text — respecting \n\n paragraph breaks
        all_display_lines = _wrap_paragraphs(pair["display_text"], font_a, text_w)
        entries.append({
            "q_lines":           _wrap_text_px(pair["question"], font_q, text_w),
            "q_spoken_words":    pair.get("q_spoken_words", pair["question"].split()),
            "q_num":             pair.get("q_num", entry_idx + 1),
            "spoken_words":      pair["spoken_words"],
            "display_words":     pair["display_words"],
            "display_tokens":    pair["display_tokens"],
            "all_display_lines": all_display_lines,
            "v_start":           pair["video_start"],
            "v_end":             pair["video_end"],
            "a_start":           pair["ans_start"],
            "a_end":             pair["ans_end"],
        })

    # total_dur: the video runs for exactly as long as the audio.
    # v_end values already include the post-answer hold; we clamp to audio
    # duration so subclipped() never receives an end_time > clip duration.
    post_hold = float(getattr(cfg, "QA_POST_ANSWER_HOLD", 1.0))
    total_dur = min(max(audio_dur, entries[-1]["v_end"]), audio_dur)

    # Crossfade state: store last rendered numpy frame so we can blend
    # smoothly between questions without any black flash.
    _xfade = {"prev_frame": None, "prev_entry_idx": -1}

    def _crossfade_blend(new_frame_np, t, entry, entry_idx):
        """
        Return a numpy RGB frame that smoothly crossfades from the
        previously cached frame to new_frame_np during transitions.
        No black frame is ever inserted — the two slides blend directly.
        """
        import numpy as np
        hold     = float(getattr(cfg, "QA_POST_ANSWER_HOLD", 1.0))
        xdur     = min(fade_dur, hold * 0.85)   # crossfade window in seconds
        if xdur <= 0 or fade_dur <= 0:
            _xfade["prev_frame"]     = new_frame_np
            _xfade["prev_entry_idx"] = entry_idx
            return new_frame_np

        # ── Detect transition: entry changed since last frame ─────────────────
        if entry_idx != _xfade["prev_entry_idx"]:
            # Just crossed into a new question — reset crossfade
            _xfade["xfade_start"]    = t
            _xfade["prev_entry_idx"] = entry_idx
            # prev_frame keeps the OLD entry's last frame for blending

        xfade_start = _xfade.get("xfade_start", t)
        elapsed     = t - xfade_start

        if elapsed < xdur and _xfade["prev_frame"] is not None and entry_idx > 0:
            # Ease-in-out blend: 0 → fully prev, 1 → fully new
            p      = elapsed / xdur
            p      = 3 * p * p - 2 * p * p * p   # smoothstep
            frame  = (
                (1.0 - p) * _xfade["prev_frame"].astype(np.float32)
                +       p  * new_frame_np.astype(np.float32)
            ).clip(0, 255).astype(np.uint8)
        else:
            frame = new_frame_np

        _xfade["prev_frame"] = new_frame_np
        return frame

    def _get_sentence_visible_n(progress, tokens):
        """
        Sentence-by-sentence reveal: reveal all words up to end of the
        sentence that corresponds to current progress fraction.
        A sentence ends when a token ends with . ? ! or contains \n\n boundary.
        """
        total = len(tokens)
        if total == 0:
            return 0
        target_word = int(progress * total)
        # Walk forward to end of current sentence
        sentence_enders = {'.', '?', '!', '।'}
        for i in range(target_word, total):
            word, _ = tokens[i]
            clean_word = word.rstrip().rstrip('.!?,')  
            if any(clean_word.endswith(e) for e in sentence_enders):
                return i + 1
            # also break at paragraph boundaries
            if i + 1 < total and tokens[i + 1][1]:   # next token is para start
                return i + 1
        return total

    def make_frame(t):
        # Find which entry owns time t.
        # v_end now includes the post-answer hold so there are no gaps
        # between pairs — but guard with fallback to last entry anyway.
        entry     = None
        entry_idx = 0
        for idx, e in enumerate(entries):
            if e["v_start"] <= t < e["v_end"]:
                entry     = e
                entry_idx = idx
                break
        if entry is None:
            # t is past all v_end (tail of last hold) — keep showing last answer
            entry     = entries[-1]
            entry_idx = len(entries) - 1

        # ── Progress bar fraction: (completed questions + current answer progress)
        if use_progress:
            if t < entry["a_start"]:
                prog_frac = entry_idx / total_pairs
            else:
                ans_dur   = max(entry["a_end"] - entry["a_start"], 0.001)
                ans_prog  = (t - entry["a_start"]) / ans_dur
                prog_frac = (entry_idx + ans_prog) / total_pairs
        else:
            prog_frac = None

        # ── Badge text
        badge_str = f"Q {entry_idx + 1} / {total_pairs}" if use_badge else None

        # Crossfade handled after rendering — fade_alpha always 255 (no black overlay)
        fa = 255

        # ── Common render kwargs
        # (subscribe handled by render_crawl_overlays below)

        # Bottom-of-Q-band progress: fraction of current answer spoken
        if use_bot_progress and t >= entry["a_start"] and t < entry["a_end"]:
            ans_dur_bot    = max(entry["a_end"] - entry["a_start"], 0.001)
            bot_prog_frac  = min((t - entry["a_start"]) / ans_dur_bot, 1.0)
        elif use_bot_progress and t >= entry["a_end"]:
            bot_prog_frac  = 1.0
        else:
            bot_prog_frac  = 0.0

        common = dict(
            video_width=target_w, video_height=target_h,
            q_band_h=q_band_h, a_band_h=a_band_h,
            q_bg=q_bg, a_bg=a_bg,
            font_q=font_q, font_a=font_a,
            q_color=q_color, a_color=a_color,
            margin_side=margin_side,
            margin_top_q=margin_top_q, margin_top_a=margin_top_a,
            margin_bot_a=margin_bot_a,
            para_gap=para_gap, max_lines=max_a_lines,
            highlight_color=hi_color,
            progress_frac=prog_frac,
            progress_bar_h=prog_bar_h,
            progress_bar_color=prog_bar_color,
            progress_bar_bg=prog_bar_bg,
            badge_text=badge_str,
            badge_font=_badge_font,
            badge_text_color=badge_text_col,
            badge_padding=badge_padding,
            badge_margin=badge_margin,
            divider=use_divider,
            divider_color=divider_color,
            divider_height=divider_h,
            divider_alpha=divider_alpha,
            watermark_text=watermark_text,
            watermark_font=_wm_font,
            watermark_color=watermark_col,
            watermark_alpha=watermark_alpha,
            fade_alpha=fa,
            # New params
            q_num=entry["q_num"],
            q_num_font=_qnum_font,
            bot_progress_frac=bot_prog_frac if use_bot_progress else None,
            bot_progress_h=bot_progress_h,
            bot_progress_color=bot_progress_color,
            bot_progress_bg=bot_progress_bg,
            total_dur=safe_dur,
        )

        if t < entry["a_start"]:
            # ── Question phase — blank answer band, question words highlighted
            q_dur        = max(entry["a_start"] - entry["v_start"], 0.001)
            q_progress   = min((t - entry["v_start"]) / q_dur, 1.0)
            active_q_word = _char_weighted_word_idx(
                q_progress, entry["q_spoken_words"]
            )
            img = _render_slide_paragraphs(
                q_lines=entry["q_lines"], para_lines=[],
                active_word=-1,
                active_q_word=active_q_word,
                **common,
            )
        else:
            # ── Answer phase ───────────────────────────────────────────────
            is_hold = t >= entry["a_end"]
            ans_dur       = max(entry["a_end"] - entry["a_start"], 0.001)
            progress      = min((t - entry["a_start"]) / ans_dur, 1.0)
            active_spoken = _char_weighted_word_idx(progress, entry["spoken_words"])
            active_display = _spoken_to_display_idx(
                active_spoken, entry["spoken_words"], entry["display_words"]
            )
            if is_hold:
                visible_n = len(entry["display_tokens"])
            elif sentence_reveal:
                visible_n = _get_sentence_visible_n(progress, entry["display_tokens"])
            else:
                visible_n = active_display + 1
            visible_text   = _tokens_to_text(entry["display_tokens"], visible_n)
            vis_para_lines = _wrap_paragraphs(visible_text, font_a, text_w)
            pages          = _paginate_paras(vis_para_lines, max_a_lines)
            cur_page       = pages[-1] if pages else []
            words_before_page = sum(
                _count_para_words(pages[pi]) for pi in range(len(pages) - 1)
            )
            page_active = -1 if is_hold else (active_display - words_before_page)
            img = _render_slide_paragraphs(
                q_lines=entry["q_lines"], para_lines=cur_page,
                active_word=page_active, **common,
            )

        # ── Crossfade between questions (direct frame blend, no black) ──────
        frame_np = _crossfade_blend(
            np.array(img, dtype=np.uint8), t, entry, entry_idx
        )
        img = Image.fromarray(frame_np)

        # Apply crawl/ticker overlays — runs for both question and answer phases
        img = render_crawl_overlays(img, t, crawl_specs)
        # Smooth empty-space overlay near end of video
        img = render_empty_space_overlay(
            img, t, safe_dur, font=_sub_font,
            text_start  = getattr(cfg, "QA_TRANSITION_TEXT_START",
                                  "Try to answer in the comments!"),
            text_end    = getattr(cfg, "QA_TRANSITION_TEXT_END",
                                  "Like, Share and Subscribe [i]"),
            fade_in_at  = float(getattr(cfg, "QA_TRANSITION_FADE_IN_AT",  10.0)),
            fade_out_at = float(getattr(cfg, "QA_TRANSITION_FADE_OUT_AT",  3.0)),
            accent_color= subscribe_accent,
            max_opacity = float(getattr(cfg, "QA_TRANSITION_OPACITY", 0.55)),
        )
        return np.array(img)

    audio_clip = AudioFileClip(tts_audio_path)
    # Hard clamp: never ask subclipped() for more than the clip has.
    # Floating-point timing accumulation can push total_dur 1-2 frames over.
    safe_dur   = min(total_dur, audio_clip.duration)

    # Build crawl specs now that safe_dur is known
    # y_frac: position subscribe banner near the top of the question band.
    # It sits just below the top progress bar, above the "Question N" label.
    # progress_bar_h + half the subscribe pill height ≈ a small fraction of target_h.
    _sub_pill_h    = max(40, int(getattr(cfg, "QA_SUBSCRIBE_FONT_SIZE", 32) * 1.9))
    _sub_y_frac    = (prog_bar_h + _sub_pill_h // 2) / target_h

    crawl_specs = [
        make_subscribe_crawl(
            total_dur    = safe_dur,
            font         = _sub_font,
            text         = subscribe_text,
            show_last    = subscribe_secs,
            style        = subscribe_style,
            accent_color = subscribe_accent,
            bg_color     = subscribe_bg,
            y_frac       = _sub_y_frac,
        )
    ]
    # Add "try to answer" toast at the start of each question
    if getattr(cfg, "QA_TRY_TOAST_ENABLED", True):
        toast_specs = make_toast_crawls(
            entries       = entries,
            font          = _sub_font,
            video_w       = target_w,
            video_h       = target_h,
            q_band_h      = q_band_h,
            prog_bar_h    = prog_bar_h,
            text          = getattr(cfg, "QA_TRY_TOAST_TEXT",
                                    "Pause the video and try to answer by yourself first!"),
            duration      = float(getattr(cfg, "QA_TRY_TOAST_DURATION",   4.0)),
            style         = getattr(cfg, "QA_TRY_TOAST_STYLE",            "pill"),
            accent_color  = _parse_color(getattr(cfg, "QA_TRY_TOAST_ACCENT", (245, 200, 66))),
            bg_color      = _parse_color(getattr(cfg, "QA_TRY_TOAST_BG",     (15, 15, 30))),
            bg_opacity    = float(getattr(cfg, "QA_TRY_TOAST_OPACITY",    0.88)),
            max_w_frac    = float(getattr(cfg, "QA_TRY_TOAST_MAX_W",      0.80)),
            top_offset_px = int(getattr(cfg,   "QA_TRY_TOAST_TOP_OFFSET", 8)),
            padding_x     = int(getattr(cfg,   "QA_TRY_TOAST_PADDING_X",  40)),
            padding_y     = int(getattr(cfg,   "QA_TRY_TOAST_PADDING_Y",  20)),
        )
        crawl_specs.extend(toast_specs)

    # Add hook crawl if configured
    if getattr(cfg, "QA_HOOK_TEXT", ""):
        from core.overlay_crawl import make_hook_crawl
        crawl_specs.insert(0, make_hook_crawl(
            start_time   = float(getattr(cfg, "QA_HOOK_START",    0.0)),
            duration     = float(getattr(cfg, "QA_HOOK_DURATION", 4.0)),
            font         = _sub_font,
            text         = cfg.QA_HOOK_TEXT,
            sub_text     = getattr(cfg, "QA_HOOK_SUBTEXT", ""),
            y_frac       = float(getattr(cfg, "QA_HOOK_Y_FRAC",   0.10)),
            style        = getattr(cfg, "QA_HOOK_STYLE",  "neon"),
            accent_color = _parse_color(getattr(cfg, "QA_HOOK_ACCENT", (80, 200, 255))),
        ))

    video_clip = VideoClip(make_frame, duration=safe_dur)
    final_clip = video_clip.with_audio(audio_clip.subclipped(0, safe_dur))
    final_clip.write_videofile(
        final_path, fps=cfg.OUTPUT_FPS,
        codec=cfg.VIDEO_CODEC, audio_codec=cfg.AUDIO_CODEC,
        bitrate=cfg.VIDEO_BITRATE, audio_bitrate=cfg.AUDIO_BITRATE,
        logger=None,
    )
    return final_path



def _wrap_paragraphs(text: str, font, max_width: int) -> list:
    """
    Wrap text into display lines, treating \n\n as hard paragraph breaks.
    Returns a flat list of str lines with None inserted between paragraphs
    as a separator marker. Consumers check `if item is None` to add
    extra vertical spacing (paragraph gap).
    """
    from qa_mode.qa_slideshow import _wrap_text_px
    result = []
    paragraphs = re.split(r'\n\n+', text)
    for pi, para in enumerate(paragraphs):
        para = para.strip()
        if not para:
            continue
        if pi > 0:
            result.append(None)
        if para.startswith("\u0001CODE\u0001"):
            result.extend(_decode_code_block_lines(para))
            continue
        lines = _wrap_text_px(para, font, max_width)
        result.extend(lines)
    return result or [""]


def _decode_code_block_lines(encoded: str) -> list[str]:
    """
    Turn a sentinel-encoded code block ("\\u0001CODE\\u0001{lang}\\u0001{lines...}")
    into a list of "\\u0001CL\\u0001{position}\\u0001{lang}\\u0001{line_text}"
    marker strings — one per code line — that _render_slide_paragraphs and
    _count_para_words know how to recognise and render/count specially.
    """
    body = encoded[len("\u0001CODE\u0001"):]
    lang, _, rest = body.partition("\u0001")
    lines = rest.split("\u0002") if rest else [""]
    out = []
    n = len(lines)
    for i, line_text in enumerate(lines):
        if n == 1:
            pos = "only"
        elif i == 0:
            pos = "first"
        elif i == n - 1:
            pos = "last"
        else:
            pos = "mid"
        out.append(f"\u0001CL\u0001{pos}\u0001{lang}\u0001{line_text}")
    return out

def _paginate_paras(para_lines: list, max_lines: int) -> list[list]:
    """Paginate para_lines (strings + None markers) respecting max_lines."""
    if not para_lines:
        return [[]]
    pages, current, line_count = [], [], 0
    for item in para_lines:
        if item is None:
            current.append(None)
        else:
            if line_count >= max_lines:
                pages.append(current)
                current, line_count = [], 0
            current.append(item)
            line_count += 1
    if current:
        pages.append(current)
    return pages if pages else [[]]


def _count_para_words(para_lines: list) -> int:
    """Count words across a page of para_lines (skip None markers and code lines)."""
    from qa_mode.qa_slideshow import _text_tokens
    return sum(
        1 for item in para_lines
        if item is not None and not item.startswith("\u0001CL\u0001")
        for t in _text_tokens(item) if t.strip()
    )


def _char_weighted_word_idx(progress: float, spoken_words: list) -> int:
    """
    Return the index of the word currently being spoken, using
    character-count weighting instead of uniform time per word.

    TTS takes roughly proportional time per character (syllables ≈ chars),
    so a 10-letter word occupies ~2x the time of a 5-letter word.
    This makes the highlight track the voice far more accurately than
    the old `int(progress * n_words)` uniform approach.
    """
    if not spoken_words:
        return 0
    # Build cumulative char weights (min 1 per word to avoid zero-width words)
    lengths = [max(1, len(w)) for w in spoken_words]
    total   = sum(lengths)
    target  = progress * total
    cumul   = 0
    for i, ln in enumerate(lengths):
        cumul += ln
        if cumul >= target:
            return i
    return len(spoken_words) - 1


def _spoken_to_display_idx(spoken_idx: int, spoken_words: list, display_words: list) -> int:
    """
    Map an index in spoken_words to the corresponding index in display_words.

    spoken_words = display_words with parenthetical words removed.
    We walk display_words, skipping words that are inside parentheses,
    and count until we've matched spoken_idx+1 spoken words.
    """
    import re
    spoken_count = 0
    inside_paren = 0
    for disp_idx, word in enumerate(display_words):
        # Track paren depth
        inside_paren += word.count('(') - word.count(')')
        in_paren = inside_paren > 0 or (
            word.startswith('(') and not word.endswith(')')
        )
        # A word is "spoken" if it's not inside parens and not pure punctuation
        clean = re.sub(r'[().,;:!?]', '', word)
        if clean and not in_paren and not (word.startswith('(') or word.endswith(')')):
            if spoken_count == spoken_idx:
                return disp_idx
            spoken_count += 1

    return len(display_words) - 1


# ── Code-block rendering (monospace card with terminal-style header) ────────

_MONO_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Supplemental/Courier New.ttf",
    "/Library/Fonts/Courier New.ttf",
]

_MONO_FONT_CACHE: dict = {}


def _get_mono_font(size: int):
    if size in _MONO_FONT_CACHE:
        return _MONO_FONT_CACHE[size]
    from PIL import ImageFont
    font = None
    for p in _MONO_FONT_CANDIDATES:
        if os.path.exists(p):
            try:
                font = ImageFont.truetype(p, size=size)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()
    _MONO_FONT_CACHE[size] = font
    return font


def _rounded_rect(draw, box, radius, fill, corners=(True, True, True, True)):
    """rounded_rectangle with selective corners; falls back to a plain
    rectangle on Pillow versions too old to support the `corners` kwarg."""
    try:
        draw.rounded_rectangle(box, radius=radius, fill=fill, corners=corners)
    except TypeError:
        draw.rectangle(box, fill=fill)


def _draw_code_line(draw, marker: str, x0: int, y: int, video_width: int,
                     y_max: int, line_h: int) -> int:
    """
    Draw one line of a code block (terminal-style card). `marker` is
    "\\u0001CL\\u0001{pos}\\u0001{lang}\\u0001{line_text}" where pos is
    one of first/mid/last/only. Returns the new y cursor.
    """
    from qa_mode.qa_slideshow import _text_width, _line_height

    body = marker[len("\u0001CL\u0001"):]
    pos, lang, line_text = body.split("\u0001", 2)

    card_bg    = (32, 34, 40)
    header_bg  = (24, 25, 30)
    text_color = (210, 230, 210)
    lang_color = (150, 160, 175)
    pad_x      = 18
    radius     = 14

    card_w = video_width - 2 * x0
    top_rounded    = pos in ("first", "only")
    bottom_rounded = pos in ("last", "only")

    mono_size = max(16, int(line_h * 0.62))
    font = _get_mono_font(mono_size)
    fh   = _line_height(font)

    if top_rounded:
        header_h = fh + 14
        _rounded_rect(draw, [x0, y, x0 + card_w, y + header_h], radius,
                      fill=header_bg, corners=(True, True, False, False))
        dot_r = max(4, header_h // 7)
        dot_y = y + header_h // 2
        for i, col in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
            cx = x0 + pad_x + i * (dot_r * 2 + 6) + dot_r
            draw.ellipse([cx - dot_r, dot_y - dot_r, cx + dot_r, dot_y + dot_r], fill=col)
        if lang:
            lw = _text_width(draw, lang, font)
            draw.text((x0 + card_w - pad_x - lw, dot_y - fh // 2),
                      lang, font=font, fill=lang_color)
        y += header_h

    row_h = fh + 14
    if y + row_h > y_max:
        return y  # out of room — caller already guards this, just be safe
    _rounded_rect(draw, [x0, y, x0 + card_w, y + row_h], radius,
                  fill=card_bg, corners=(False, False, bottom_rounded, bottom_rounded))
    draw.text((x0 + pad_x, y + 7), line_text, font=font, fill=text_color)
    return y + row_h


# ── Paragraph-aware slide renderer ───────────────────────────────────────────

def _render_slide_paragraphs(
    video_width, video_height,
    q_band_h, a_band_h,
    q_bg, a_bg,
    q_lines, para_lines,
    font_q, font_a,
    q_color, a_color,
    margin_side, margin_top_q, margin_top_a,
    para_gap, max_lines,
    active_word=-1,
    highlight_color=(220, 120, 0),
    progress_frac=None,
    progress_bar_h=8,
    progress_bar_color=(245, 200, 66),
    progress_bar_bg=(80, 80, 80),
    badge_text=None,
    badge_font=None,
    badge_text_color=(255, 255, 255),
    badge_padding=18,
    badge_margin=20,
    divider=False,
    divider_color=(255, 255, 255),
    divider_height=4,
    divider_alpha=80,
    watermark_text=None,
    watermark_font=None,
    watermark_color=(255, 255, 255),
    watermark_alpha=90,
    fade_alpha=255,
    margin_bot_a=0,
    # ── New params ────────────────────────────────────────────────────────
    q_num=None,               # int: question number shown small above question
    q_num_font=None,          # font for q_num label
    bot_progress_frac=None,   # 0-1 progress bar at bottom of question band
    bot_progress_h=6,
    bot_progress_color=(245, 200, 66),
    bot_progress_bg=(60, 60, 60),
    total_dur=None,
    active_q_word=-1,  # index of currently-spoken word in question text (-1 = none)
):
    from qa_mode.qa_slideshow import _line_height, _text_width, _text_tokens, _parse_color
    from PIL import Image, ImageDraw

    img  = Image.new("RGB", (video_width, video_height))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, video_width, q_band_h], fill=q_bg)
    draw.rectangle([0, q_band_h, video_width, video_height], fill=a_bg)

    # ── 3. Divider line between bands ────────────────────────────────────
    if divider and divider_height > 0:
        dc = tuple(list(divider_color[:3]))
        # Blend divider colour over the band colours for opacity effect
        alpha = divider_alpha / 255.0
        blended = tuple(int(dc[i] * alpha + q_bg[i] * (1 - alpha)) for i in range(3))
        dy = q_band_h - divider_height // 2
        draw.rectangle([0, dy, video_width, dy + divider_height], fill=blended)

    # ── Question — vertically centred in top band ─────────────────────────
    q_lh      = _line_height(font_q)
    top_reserve = progress_bar_h if progress_frac is not None else 0

    # Question number label (e.g. "Question 1") — small, centred, above question text
    q_num_h = 0
    if q_num is not None and q_num_font is not None:
        q_num_lh  = _line_height(q_num_font)
        q_num_text = f"Question {q_num}"
        q_num_h   = q_num_lh + 6   # 6px gap below label

    total_q_h = q_num_h + len(q_lines) * q_lh + max(0, len(q_lines) - 1) * 8
    bot_reserve = bot_progress_h if bot_progress_frac is not None else 0
    usable_q    = q_band_h - top_reserve - bot_reserve
    y = top_reserve + max((usable_q - total_q_h) // 2, margin_top_q)

    # Draw question number label — no background, soft white text centred
    if q_num is not None and q_num_font is not None:
        q_num_text  = f"Question {q_num}"
        ntw         = _text_width(draw, q_num_text, q_num_font)
        nx          = (video_width - ntw) // 2
        nlh         = _line_height(q_num_font)
        # Letter-spacing effect: thin shadow only, bright readable colour
        shadow_col  = (0, 0, 0, 45)
        label_col   = (50, 50, 50, 210)   # near-black, clear on any q_bg
        # Draw with RGBA so alpha works
        tmp = img.convert("RGBA")
        td  = ImageDraw.Draw(tmp)
        td.text((nx + 1, y + 1), q_num_text, font=q_num_font, fill=shadow_col)
        td.text((nx, y),         q_num_text, font=q_num_font, fill=label_col)
        img  = tmp.convert("RGB")
        draw = ImageDraw.Draw(img)
        y   += q_num_h

    # Draw question text word by word, highlighting the currently spoken word.
    # We tokenise each line then measure the full line width to centre it,
    # then draw word-by-word so we can change colour per word.
    q_word_cursor = 0   # tracks which absolute word index we are at
    for line in q_lines:
        words_in_line = line.split()
        if not words_in_line:
            y += q_lh + 8
            continue

        # Measure full line for centring
        tw  = _text_width(draw, line, font_q)
        x   = (video_width - tw) // 2

        # Shadow pass (whole line at once — cheaper)
        draw.text((x + 2, y + 2), line, font=font_q, fill=(0, 0, 0, 50))

        # Word-by-word colour pass
        cx = x
        for word in words_in_line:
            is_active = (active_q_word >= 0 and q_word_cursor == active_q_word)
            col = highlight_color if is_active else q_color
            draw.text((cx, y), word, font=font_q, fill=col)
            cx += _text_width(draw, word + " ", font_q)
            q_word_cursor += 1
        y += q_lh + 8

    # ── Answer — paragraph-aware, with bullet + highlight on active word ───
    a_lh          = _line_height(font_a)
    y             = q_band_h + margin_top_a
    word_index    = 0
    BULLET        = "● "          # filled circle bullet
    BULLET_INDENT = 28            # px indent for continuation lines of same paragraph
    bullet_color  = highlight_color   # bullet shares accent colour
    # We draw a bullet at the start of each paragraph (first line after a
    # None separator, or the very first line). Continuation lines of the
    # same paragraph are indented to align with the text after the bullet.
    start_of_para = True          # True = next rendered line is a para start
    # Hard bottom boundary — never draw below this y coordinate.
    # This enforces QA_SLIDE_MARGIN_BOT_A regardless of pagination drift.
    y_max = q_band_h + a_band_h - margin_bot_a

    for item in para_lines:
        if item is None:
            y += para_gap
            start_of_para = True  # next line starts a new paragraph
            continue
        line = item

        if line.startswith("\u0001CL\u0001"):
            if y + a_lh > y_max:
                continue  # 0 spoken words, safe to just skip — nothing to sync
            y = _draw_code_line(draw, line, x0=margin_side, y=y,
                                video_width=video_width, y_max=y_max,
                                line_h=a_lh)
            start_of_para = True  # prose after code starts fresh (gets a bullet)
            continue

        # Skip this line entirely if it would overflow the bottom margin
        if y + a_lh > y_max:
            if not line.startswith("\u0001CL\u0001"):
                for token in _text_tokens(line):
                    if token.strip():
                        word_index += 1
            continue

        if start_of_para:
            # Draw bullet glyph before the line content
            bw = _text_width(draw, BULLET, font_a)
            draw.text((margin_side, y), BULLET, font=font_a, fill=bullet_color)
            x = margin_side + bw
            start_of_para = False
        else:
            # Continuation line — indent to align under text (after bullet)
            x = margin_side + BULLET_INDENT

        tokens = _text_tokens(line)
        for token in tokens:
            is_word = bool(token.strip())
            color = highlight_color if (is_word and word_index == active_word) else a_color
            draw.text((x, y), token, font=font_a, fill=color)
            x += _text_width(draw, token, font_a)
            if is_word:
                word_index += 1
        y += a_lh + 4

    # ── 1. Progress bar — drawn after content so it sits on top ──────────
    if progress_frac is not None and progress_bar_h > 0:
        draw.rectangle([0, 0, video_width, progress_bar_h], fill=progress_bar_bg)
        filled_w = int(video_width * max(0.0, min(1.0, progress_frac)))
        if filled_w > 0:
            draw.rectangle([0, 0, filled_w, progress_bar_h], fill=progress_bar_color)

    # ── 2. Question number badge — pill in top-right of question band ─────
    if badge_text and badge_font:
        bw = _text_width(draw, badge_text, badge_font)
        bh = _line_height(badge_font)
        pad_x, pad_y = badge_padding, badge_padding // 2
        pill_w = bw + 2 * pad_x
        pill_h = bh + 2 * pad_y
        bx = video_width - pill_w - badge_margin
        by = (progress_bar_h if progress_frac is not None else 0) + badge_margin
        # Semi-transparent dark pill
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        odraw   = ImageDraw.Draw(overlay)
        odraw.rounded_rectangle(
            [bx, by, bx + pill_w, by + pill_h],
            radius=pill_h // 2,
            fill=(0, 0, 0, 120),
        )
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)
        draw.text((bx + pad_x, by + pad_y), badge_text,
                  font=badge_font, fill=badge_text_color)

    # ── 6. Watermark ──────────────────────────────────────────────────────
    if watermark_text and watermark_font:
        ww = _text_width(draw, watermark_text, watermark_font)
        wh = _line_height(watermark_font)
        wx = video_width - ww - margin_side
        wy = video_height - wh - (margin_side // 2)
        alpha = watermark_alpha / 255.0
        wc = tuple(int(watermark_color[i] * alpha + a_bg[i] * (1 - alpha))
                   for i in range(3))
        draw.text((wx, wy), watermark_text, font=watermark_font, fill=wc)

    # ── 7. Bottom-of-question-band progress bar (answer spoken progress) ───
    if bot_progress_frac is not None and bot_progress_h > 0:
        # Sits at the very bottom edge of the question band
        by0 = q_band_h - bot_progress_h
        by1 = q_band_h
        draw.rectangle([0, by0, video_width, by1], fill=bot_progress_bg)
        filled = int(video_width * max(0.0, min(1.0, bot_progress_frac)))
        if filled > 0:
            draw.rectangle([0, by0, filled, by1], fill=bot_progress_color)

    # ── 5. Fade overlay — removed; crossfade is now done via numpy blend ─
    if False:  # kept as placeholder so surrounding code is unchanged
        pass
        if False:
            img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    return img


# ── Pipeline entry point ──────────────────────────────────────────────────────




def run(qa_path: str, title: str = "interview_prep", cfg=default_cfg, keep_temp: bool = False) -> dict:
    total_start = time.time()
    ensure_dirs(cfg.OUTPUT_DIR, cfg.TEMP_DIR, cfg.ASSETS_DIR)

    from qa_mode.tts import check_backend_available
    check_backend_available(cfg)

    font_path = find_hindi_font(cfg)

    _step("STEP 1 / 3 — Loading Q&A file")
    selected = load_qa_file(qa_path, cfg)
    log.info("Loaded %d Q/A pairs", len(selected) // 4)

    _step("STEP 2 / 3 — Generating narration")
    tts_audio_path = generate_tts_audio(selected, cfg)
    summary_dur = selected[-1].get("new_end", get_video_duration(tts_audio_path))
    log.info("Narration: %s", human_duration(summary_dur))

    _step("STEP 3 / 3 — Building video")
    safe_title = _safe_title(title)
    target_w, target_h = cfg.video_dimensions()
    use_split = getattr(cfg, "QA_USE_SPLIT_LAYOUT", True)

    srt_path = os.path.join(cfg.OUTPUT_DIR, f"{safe_title}.srt")
    ass_path = subtitle_render.generate_subtitle_files(
        selected_chunks=selected, output_srt_path=srt_path,
        font_path=font_path, video_width=target_w, video_height=target_h,
        cfg=cfg, style_resolver=resolve_style,
    )

    if use_split:
        log.info("Split-layout renderer (lang=%s)", getattr(cfg, "LANGUAGE", "?"))
        final_video_path = _run_split_layout(
            selected, tts_audio_path, title, target_w, target_h, font_path, cfg,
        )
    else:
        no_sub_path = os.path.join(cfg.TEMP_DIR, "qa_no_sub.mp4")
        slideshow_render.compile_slideshow_video(
            selected_chunks=selected, audio_path=tts_audio_path,
            output_path=no_sub_path, video_width=target_w, video_height=target_h,
            font_path=font_path, cfg=cfg, title=title,
        )
        font_dir = os.path.dirname(os.path.abspath(font_path))
        final_video_path = os.path.join(cfg.OUTPUT_DIR, f"{safe_title}_qa.mp4")
        subtitle_render.burn_subtitles(
            input_video=no_sub_path, ass_path=ass_path, output_video=final_video_path,
            font_dir=font_dir, cfg=cfg, style_resolver=resolve_style, font_path=font_path,
        )

    meta_path = metadata_writer.generate_and_save(
        title_seed=title, selected_chunks=selected, topic_groups=[],
        summary_duration=summary_dur, output_dir=cfg.OUTPUT_DIR, cfg=cfg,
    )

    if not keep_temp:
        clean_temp(cfg)

    log.info("Total: %s", human_duration(time.time() - total_start))
    return {"video_path": final_video_path, "srt_path": srt_path,
            "meta_path": meta_path, "summary_duration": summary_dur}


def _step(msg):
    print(f"\n{'─'*60}\n  {msg}\n{'─'*60}")


def _safe_title(title, max_len=40):
    safe = re.sub(r"[^\w\s\-]", "", title)
    safe = re.sub(r"\s+", "_", safe.strip())

    # Preserve _partN suffix — extract before truncating so it is never cut off
    part_match = re.search(r'(_part\d+)$', safe, re.IGNORECASE)
    if part_match:
        suffix = part_match.group(1)           # e.g. "_part2"
        base   = safe[: part_match.start()]    # everything before the suffix
        safe   = base[: max(1, max_len - len(suffix))] + suffix
    else:
        safe = safe[:max_len]

    return safe or "interview_prep"
