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
from core.tts.pipeline import generate_tts_audio
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


def _build_qa_pairs(selected: list[dict]) -> list[dict]:
    """
    Collapse flat segments into one dict per Q/A pair.
    spoken_words  — words from TTS text (parens stripped) — drives timing/highlight
    display_text  — full text including parens, with paragraph line breaks
    """
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

                pairs.append({
                    "question":       question_text,
                    "display_text":   display_text,
                    "spoken_words":   spoken_text.split(),    # drives highlight timing
                    "display_words":  display_text.split(),   # flat list — used for word count only
                    "display_tokens": display_tokens,         # structured — used for rendering
                    "video_start":    q_start,
                    "video_end":      a_end,
                    "ans_start":      a_start,
                    "ans_end":        a_end,
                })
                i = j + 1
            else:
                i += 1
        else:
            i += 1
    return pairs


def _run_split_layout(selected, tts_audio_path, title, target_w, target_h, font_path, cfg) -> str:
    from qa_mode.qa_slideshow import (
        _load_fonts, _wrap_text_px, _paginate, _render_slide,
        _line_height, _parse_color, _count_words_in_lines,
    )
    from moviepy import AudioFileClip, VideoClip
    import numpy as np

    qa_pairs = _build_qa_pairs(selected)
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
    text_w      = target_w - 2 * margin_side
    a_line_h    = _line_height(font_a)
    para_gap    = int(a_line_h * 0.6)   # extra gap between paragraphs
    avail_a_h   = a_band_h - margin_top_a - margin_bot_a
    max_a_lines = max(1, avail_a_h // (a_line_h + 4))

    # Pre-compute per-pair entry data
    entries = []
    for pair in qa_pairs:
        # Wrap display text — respecting \n\n paragraph breaks
        all_display_lines = _wrap_paragraphs(pair["display_text"], font_a, text_w)
        entries.append({
            "q_lines":           _wrap_text_px(pair["question"], font_q, text_w),
            "spoken_words":      pair["spoken_words"],    # for timing
            "display_words":     pair["display_words"],   # flat word list for counting
            "display_tokens":    pair["display_tokens"],  # structured tokens for rendering
            "all_display_lines": all_display_lines,       # pre-wrapped with para marks
            "v_start":           pair["video_start"],
            "v_end":             pair["video_end"],
            "a_start":           pair["ans_start"],
            "a_end":             pair["ans_end"],
        })

    total_dur = min(entries[-1]["v_end"], audio_dur)

    def make_frame(t):
        entry = None
        for e in entries:
            if e["v_start"] <= t < e["v_end"]:
                entry = e
                break
        if entry is None:
            entry = entries[-1]

        if t < entry["a_start"]:
            # Question phase — blank answer band
            img = _render_slide_paragraphs(
                video_width=target_w, video_height=target_h,
                q_band_h=q_band_h, a_band_h=a_band_h,
                q_bg=q_bg, a_bg=a_bg,
                q_lines=entry["q_lines"], para_lines=[],
                font_q=font_q, font_a=font_a,
                q_color=q_color, a_color=a_color,
                margin_side=margin_side,
                margin_top_q=margin_top_q, margin_top_a=margin_top_a,
                para_gap=para_gap, max_lines=max_a_lines,
                active_word=-1, highlight_color=hi_color,
            )
            return np.array(img)

        # Answer phase ─────────────────────────────────────────────────
        ans_dur = max(entry["a_end"] - entry["a_start"], 0.001)
        progress = (t - entry["a_start"]) / ans_dur

        # active_word: index into SPOKEN words (drives timing/highlight)
        spoken_total  = len(entry["spoken_words"])
        active_spoken = min(int(progress * spoken_total), spoken_total - 1)

        # Map spoken word index → display word index
        # spoken words are a subset of display words (parens stripped).
        # We find the Nth spoken word's position in the display word list.
        active_display = _spoken_to_display_idx(
            active_spoken, entry["spoken_words"], entry["display_words"]
        )

        # Reveal display words up to and including active_display
        visible_n    = active_display + 1
        # Rebuild visible text from structured tokens — preserves \n\n breaks
        visible_text = _tokens_to_text(entry["display_tokens"], visible_n)

        # Re-wrap with paragraph awareness
        vis_para_lines = _wrap_paragraphs(visible_text, font_a, text_w)
        pages = _paginate_paras(vis_para_lines, max_a_lines)
        cur_page = pages[-1] if pages else []

        # Compute active word index within current page
        words_before_page = sum(
            _count_para_words(pages[pi]) for pi in range(len(pages) - 1)
        )
        page_active = active_display - words_before_page

        img = _render_slide_paragraphs(
            video_width=target_w, video_height=target_h,
            q_band_h=q_band_h, a_band_h=a_band_h,
            q_bg=q_bg, a_bg=a_bg,
            q_lines=entry["q_lines"], para_lines=cur_page,
            font_q=font_q, font_a=font_a,
            q_color=q_color, a_color=a_color,
            margin_side=margin_side,
            margin_top_q=margin_top_q, margin_top_a=margin_top_a,
            para_gap=para_gap, max_lines=max_a_lines,
            active_word=page_active, highlight_color=hi_color,
        )
        return np.array(img)

    audio_clip = AudioFileClip(tts_audio_path)
    video_clip = VideoClip(make_frame, duration=total_dur)
    final_clip = video_clip.with_audio(audio_clip.subclipped(0, total_dur))
    final_clip.write_videofile(
        final_path, fps=cfg.OUTPUT_FPS,
        codec=cfg.VIDEO_CODEC, audio_codec=cfg.AUDIO_CODEC,
        bitrate=cfg.VIDEO_BITRATE, audio_bitrate=cfg.AUDIO_BITRATE,
        logger=None,
    )
    return final_path




    """
    Wrap text into lines, treating \\n\\n as paragraph breaks.
    Returns a list where each item is either:
      - a string (a line of text)
      - None   (paragraph separator — renders as extra vertical gap)
    """
    from qa_mode.qa_slideshow import _wrap_text_px
    result = []
    paragraphs = re.split(r'\n\n+', text)
    for pi, para in enumerate(paragraphs):
        para = para.strip()
        if not para:
            continue
        lines = _wrap_text_px(para, font, max_width)
        result.extend(lines)
        if pi < len(paragraphs) - 1:
            result.append(None)   # paragraph break marker
    return result


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
        lines = _wrap_text_px(para, font, max_width)
        result.extend(lines)
    return result or [""]

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
    """Count words across a page of para_lines (skip None markers)."""
    from qa_mode.qa_slideshow import _text_tokens
    return sum(
        1 for item in para_lines if item is not None
        for t in _text_tokens(item) if t.strip()
    )


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
):
    from qa_mode.qa_slideshow import _line_height, _text_width, _text_tokens, _parse_color
    from PIL import Image, ImageDraw

    img  = Image.new("RGB", (video_width, video_height))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, video_width, q_band_h], fill=q_bg)
    draw.rectangle([0, q_band_h, video_width, video_height], fill=a_bg)

    # ── Question — vertically centred in top band ─────────────────────────
    q_lh      = _line_height(font_q)
    total_q_h = len(q_lines) * q_lh + max(0, len(q_lines) - 1) * 8
    y = max((q_band_h - total_q_h) // 2, margin_top_q)
    for line in q_lines:
        tw = _text_width(draw, line, font_q)
        x  = (video_width - tw) // 2
        draw.text((x + 2, y + 2), line, font=font_q, fill=(0, 0, 0, 50))
        draw.text((x, y), line, font=font_q, fill=q_color)
        y += q_lh + 8

    # ── Answer — paragraph-aware, with highlight on active word ───────────
    a_lh       = _line_height(font_a)
    y          = q_band_h + margin_top_a
    word_index = 0

    for item in para_lines:
        if item is None:
            # Paragraph break — extra vertical gap
            y += para_gap
            continue
        line = item
        x = margin_side
        tokens = _text_tokens(line)
        for token in tokens:
            is_word = bool(token.strip())
            color = highlight_color if (is_word and word_index == active_word) else a_color
            draw.text((x, y), token, font=font_a, fill=color)
            x += _text_width(draw, token, font_a)
            if is_word:
                word_index += 1
        y += a_lh + 4

    return img


# ── Pipeline entry point ──────────────────────────────────────────────────────




def run(qa_path: str, title: str = "interview_prep", cfg=default_cfg, keep_temp: bool = False) -> dict:
    total_start = time.time()
    ensure_dirs(cfg.OUTPUT_DIR, cfg.TEMP_DIR, cfg.ASSETS_DIR)

    from core.tts.factory import get_strategy
    get_strategy(cfg.TTS_BACKEND).check_available(cfg)

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
