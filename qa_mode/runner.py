"""
qa_mode/runner.py — Q&A / interview-prep mode pipeline.
"""

import os
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


def _build_qa_pairs(selected: list[dict]) -> list[dict]:
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
                pairs.append({
                    "question":    question_text,
                    "answer":      ans.get("display_text", ans.get("text", "")),
                    "video_start": q_start,
                    "video_end":   a_end,
                    "ans_start":   a_start,
                    "ans_end":     a_end,
                })
                i = j + 1
            else:
                i += 1
        else:
            i += 1
    return pairs


def _run_split_layout(selected, tts_audio_path, title, target_w, target_h, font_path, cfg) -> str:
    from qa_mode.qa_slideshow import (
        _load_fonts, _wrap_text_px, _paginate, _paginate_by_sentence, _render_slide,
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
        log.warning("Rescaling placeholder timestamps (last=%.1fs audio=%.1fs)", last_end, audio_dur)
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

    q_bg    = _parse_color(getattr(cfg, "QA_SLIDE_QUESTION_BG",    (205, 139,  97)))
    a_bg    = _parse_color(getattr(cfg, "QA_SLIDE_ANSWER_BG",      (183, 204, 174)))
    q_color = _parse_color(getattr(cfg, "QA_SLIDE_QUESTION_COLOR", (30,  30,  30)))
    a_color = _parse_color(getattr(cfg, "QA_SLIDE_ANSWER_COLOR",   (30,  30,  30)))
    hi_color = _parse_color(getattr(cfg, "QA_SLIDE_HIGHLIGHT_COLOR",
                             getattr(cfg, "SUBTITLE_HIGHLIGHT_COLOR", (255, 178, 0))))

    font_q, font_a = _load_fonts(font_path, cfg)
    text_w      = target_w - 2 * margin_side
    a_line_h    = _line_height(font_a)
    avail_a_h   = a_band_h - margin_top_a - margin_bot_a
    max_a_lines = max(1, avail_a_h // (a_line_h + 4))

    # Pre-compute per-pair data
    entries = []
    for pair in qa_pairs:
        all_words  = pair["answer"].split()
        all_lines  = _wrap_text_px(pair["answer"], font_a, text_w)
        all_pages  = _paginate_by_sentence(pair["answer"], font_a, text_w, max_a_lines)
        # Word count per page (for tracking which page a word falls on)
        page_word_counts = [_count_words_in_lines(p) for p in all_pages]
        entries.append({
            "q_lines":          _wrap_text_px(pair["question"], font_q, text_w),
            "all_words":        all_words,
            "all_lines":        all_lines,
            "all_pages":        all_pages,
            "page_word_counts": page_word_counts,
            "v_start":          pair["video_start"],
            "v_end":            pair["video_end"],
            "a_start":          pair["ans_start"],
            "a_end":            pair["ans_end"],
        })

    total_dur = min(entries[-1]["v_end"], audio_dur)

    def make_frame(t):
        # Find current entry
        entry = None
        for e in entries:
            if e["v_start"] <= t < e["v_end"]:
                entry = e
                break
        if entry is None:
            entry = entries[-1]

        if t < entry["a_start"]:
            # Question phase — show question, empty answer
            img = _render_slide(
                video_width=target_w, video_height=target_h,
                q_band_h=q_band_h, a_band_h=a_band_h,
                q_bg=q_bg, a_bg=a_bg,
                q_lines=entry["q_lines"], a_lines=[],
                font_q=font_q, font_a=font_a,
                q_color=q_color, a_color=a_color,
                margin_side=margin_side,
                margin_top_q=margin_top_q, margin_top_a=margin_top_a,
                active_word=-1, highlight_color=hi_color,
            )
            return np.array(img)

        # Answer phase — word-by-word reveal with highlight on current word
        ans_dur     = max(entry["a_end"] - entry["a_start"], 0.001)
        progress    = (t - entry["a_start"]) / ans_dur
        total_words = len(entry["all_words"])

        # active_word: the word currently being spoken (highlighted)
        # visible_words: all words shown so far (revealed = active + past)
        active_word  = min(int(progress * total_words), total_words - 1)
        visible_n    = active_word + 1   # show up to and including the active word

        visible_text = " ".join(entry["all_words"][:visible_n])
        pages        = _paginate_by_sentence(visible_text, font_a, text_w, max_a_lines)
        cur_page     = pages[-1] if pages else []

        # active_word offset within cur_page
        # Words before this page have already been shown; subtract them
        words_before_page = sum(
            _count_words_in_lines(pages[i]) for i in range(len(pages) - 1)
        )
        page_active = active_word - words_before_page

        img = _render_slide(
            video_width=target_w, video_height=target_h,
            q_band_h=q_band_h, a_band_h=a_band_h,
            q_bg=q_bg, a_bg=a_bg,
            q_lines=entry["q_lines"], a_lines=cur_page,
            font_q=font_q, font_a=font_a,
            q_color=q_color, a_color=a_color,
            margin_side=margin_side,
            margin_top_q=margin_top_q, margin_top_a=margin_top_a,
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


def run(qa_path: str, title: str = "interview_prep", cfg=default_cfg, keep_temp: bool = False) -> dict:
    """File-based entry point (CLI). Loads the Q&A file, then delegates to
    run_from_segments() for the rest of the pipeline."""
    _step("STEP 1 / 3 — Loading Q&A file")
    selected = load_qa_file(qa_path, cfg)
    log.info("Loaded %d question/answer pairs", len(selected) // 4)
    return run_from_segments(selected, title=title, cfg=cfg, keep_temp=keep_temp)


def run_from_segments(selected: list[dict], title: str = "interview_prep",
                       cfg=default_cfg, keep_temp: bool = False) -> dict:
    """
    Core pipeline, decoupled from file I/O. `selected` is the segment list
    produced either by qa_mode.loader.load_qa_file() (CLI) or
    qa_mode.loader.build_qa_segments() (API, given in-memory Q&A pairs).
    """
    total_start = time.time()
    ensure_dirs(cfg.OUTPUT_DIR, cfg.TEMP_DIR, cfg.ASSETS_DIR)

    from core.tts.factory import get_strategy
    get_strategy(cfg.TTS_BACKEND).check_available(cfg)

    font_path = find_hindi_font(cfg)

    _step("STEP 2 / 3 — Generating narration")
    tts_audio_path = generate_tts_audio(selected, cfg)
    summary_dur = selected[-1].get("new_end", get_video_duration(tts_audio_path))
    log.info("Narration duration: %s", human_duration(summary_dur))

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
        log.info("Split-layout renderer (lang=%s, highlight=ON)", getattr(cfg, "LANGUAGE", "?"))
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

    log.info("Total time: %s", human_duration(time.time() - total_start))
    return {
        "video_path": final_video_path, "srt_path": srt_path,
        "meta_path": meta_path, "summary_duration": summary_dur,
    }


def _step(msg):
    print(f"\n{'─'*60}\n  {msg}\n{'─'*60}")


def _safe_title(title, max_len=40):
    import re
    safe = re.sub(r"[^\w\s\-]", "", title)
    safe = re.sub(r"\s+", "_", safe.strip())
    return safe[:max_len] or "interview_prep"
