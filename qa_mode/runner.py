"""
qa_mode/runner.py — Q&A / interview-prep mode pipeline.

Q&A file -> load (question/try-yourself/countdown/answer chunks) ->
TTS -> subtitles -> slideshow -> metadata.

Deliberately has no summarization step — every question and answer is
always kept in full. This is the key structural difference from
story_mode, which is why the two are separate runners rather than one
shared pipeline with an "if mode == qa: skip summarizer" branch.
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


def run(qa_path: str, title: str = "interview_prep", cfg=default_cfg, keep_temp: bool = False) -> dict:
    """
    Run the full Q&A-mode pipeline. Returns a dict with output paths.
    """
    total_start = time.time()

    log.info("Checking dependencies …")
    ensure_dirs(cfg.OUTPUT_DIR, cfg.TEMP_DIR, cfg.ASSETS_DIR)

    from core.tts.factory import get_strategy
    get_strategy(cfg.TTS_BACKEND).check_available(cfg)

    log.info("Looking for Hindi font …")
    font_path = find_hindi_font(cfg)

    _step("STEP 1 / 3 — Loading Q&A file")
    selected = load_qa_file(qa_path, cfg)
    log.info("Loaded %d question/answer pairs from %s", len(selected) // 4, qa_path)

    _step("STEP 2 / 3 — Generating narration")
    tts_audio_path = generate_tts_audio(selected, cfg)
    summary_dur = selected[-1]["new_end"] if selected else get_video_duration(tts_audio_path)
    log.info("Narration duration: %s", human_duration(summary_dur))

    _step("STEP 3 / 3 — Subtitles + slideshow + metadata")
    safe_title = _safe_title(title)
    srt_path = os.path.join(cfg.OUTPUT_DIR, f"{safe_title}.srt")
    target_w, target_h = cfg.video_dimensions()

    ass_path = subtitle_render.generate_subtitle_files(
        selected_chunks=selected,
        output_srt_path=srt_path,
        font_path=font_path,
        video_width=target_w,
        video_height=target_h,
        cfg=cfg,
        style_resolver=resolve_style,
    )

    no_sub_path = os.path.join(cfg.TEMP_DIR, "qa_no_sub.mp4")
    slideshow_render.compile_slideshow_video(
        selected_chunks=selected,
        audio_path=tts_audio_path,
        output_path=no_sub_path,
        video_width=target_w,
        video_height=target_h,
        font_path=font_path,
        cfg=cfg,
        title=title,
    )

    font_dir = os.path.dirname(os.path.abspath(font_path))
    final_video_path = os.path.join(cfg.OUTPUT_DIR, f"{safe_title}_qa.mp4")
    subtitle_render.burn_subtitles(
        input_video=no_sub_path,
        ass_path=ass_path,
        output_video=final_video_path,
        font_dir=font_dir,
        cfg=cfg,
        style_resolver=resolve_style,
        font_path=font_path,
    )

    # Q&A mode has no topic groups (no banners) — pass an empty list
    meta_path = metadata_writer.generate_and_save(
        title_seed=title,
        selected_chunks=selected,
        topic_groups=[],
        summary_duration=summary_dur,
        output_dir=cfg.OUTPUT_DIR,
        cfg=cfg,
    )

    if not keep_temp:
        clean_temp(cfg)

    log.info("Total time: %s", human_duration(time.time() - total_start))

    return {
        "video_path": final_video_path,
        "srt_path": srt_path,
        "meta_path": meta_path,
        "summary_duration": summary_dur,
    }


def _step(msg: str) -> None:
    print(f"\n{'─' * 60}\n  {msg}\n{'─' * 60}")


def _safe_title(title: str, max_len: int = 40) -> str:
    import re
    safe = re.sub(r"[^\w\s\-]", "", title)
    safe = re.sub(r"\s+", "_", safe.strip())
    return safe[:max_len] or "interview_prep"
