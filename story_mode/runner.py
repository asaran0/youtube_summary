"""
story_mode/runner.py — Story mode pipeline.

text file -> load -> summarize -> storytelling -> TTS
-> story_render (new YouTube-style visual) or legacy subtitle overlay
"""

import os
import re
import time

from utils import (
    get_logger, ensure_dirs, clean_temp, get_video_duration,
    find_hindi_font, human_duration,
)
from story_mode.tts import generate_tts_audio
from core.render import subtitles as subtitle_render
from core.render import slideshow as slideshow_render
from core.render import metadata as metadata_writer

from story_mode import config as default_cfg
from story_mode.loader import load_text_file
from story_mode.summarizer import select_segments
from story_mode.narration import apply_storytelling
from story_mode.styles import resolve_style

log = get_logger("story.runner")


def run(text_path: str, title: str = "summary", cfg=default_cfg, keep_temp: bool = False) -> dict:
    total_start = time.time()

    ensure_dirs(cfg.OUTPUT_DIR, cfg.TEMP_DIR, cfg.ASSETS_DIR)

    from story_mode.tts import check_backend_available
    check_backend_available(cfg)

    font_path = find_hindi_font(cfg)

    _step("STEP 1 / 4 — Loading story text")
    segments = load_text_file(text_path)
    log.info("Loaded %d sentences from %s", len(segments), text_path)

    _step("STEP 2 / 4 — Selecting segments")
    result       = select_segments(segments, 0.0, cfg)
    selected     = result["selected_segments"]
    topic_groups = result["topic_groups"]
    log.info("Kept %.0f%% of content", result["kept_ratio"] * 100)

    selected = apply_storytelling(selected, cfg)

    _step("STEP 3 / 4 — Generating narration")
    tts_audio_path = generate_tts_audio(selected, cfg)
    summary_dur    = selected[-1]["new_end"] if selected else get_video_duration(tts_audio_path)
    topic_groups   = _retime_topic_groups(topic_groups, selected)
    log.info("Narration duration: %s", human_duration(summary_dur))

    _step("STEP 4 / 4 — Building video")
    safe_title  = _safe_title(title)
    target_w, target_h = cfg.video_dimensions()
    use_new     = getattr(cfg, "STORY_USE_NEW_RENDERER", True)

    if use_new:
        from story_mode.story_render import compile_story_video
        final_video_path = os.path.join(cfg.OUTPUT_DIR, f"{safe_title}_summary.mp4")
        log.info("Using YouTube-style story renderer")
        compile_story_video(
            selected_chunks=selected,
            audio_path=tts_audio_path,
            output_path=final_video_path,
            video_width=target_w,
            video_height=target_h,
            font_path=font_path,
            cfg=cfg,
            title=title,
        )
        # Still generate SRT for upload
        srt_path = os.path.join(cfg.OUTPUT_DIR, f"{safe_title}.srt")
        subtitle_render.generate_subtitle_files(
            selected_chunks=selected,
            output_srt_path=srt_path,
            font_path=font_path,
            video_width=target_w,
            video_height=target_h,
            cfg=cfg,
            style_resolver=resolve_style,
        )
    else:
        # Legacy subtitle-overlay path
        srt_path = os.path.join(cfg.OUTPUT_DIR, f"{safe_title}.srt")
        ass_path = subtitle_render.generate_subtitle_files(
            selected_chunks=selected,
            output_srt_path=srt_path,
            font_path=font_path,
            video_width=target_w,
            video_height=target_h,
            cfg=cfg,
            style_resolver=resolve_style,
        )
        no_sub_path = os.path.join(cfg.TEMP_DIR, "summary_no_sub.mp4")
        slideshow_render.compile_slideshow_video(
            selected_chunks=selected,
            audio_path=tts_audio_path,
            output_path=no_sub_path,
            video_width=target_w,
            video_height=target_h,
            font_path=font_path,
            cfg=cfg,
            title=title,
            topic_groups=topic_groups,
        )
        font_dir = os.path.dirname(os.path.abspath(font_path))
        final_video_path = os.path.join(cfg.OUTPUT_DIR, f"{safe_title}_summary.mp4")
        subtitle_render.burn_subtitles(
            input_video=no_sub_path,
            ass_path=ass_path,
            output_video=final_video_path,
            font_dir=font_dir,
            cfg=cfg,
            style_resolver=resolve_style,
            font_path=font_path,
        )

    meta_path = metadata_writer.generate_and_save(
        title_seed=title,
        selected_chunks=selected,
        topic_groups=topic_groups,
        summary_duration=summary_dur,
        output_dir=cfg.OUTPUT_DIR,
        cfg=cfg,
    )

    if not keep_temp:
        clean_temp(cfg)

    log.info("Total time: %s", human_duration(time.time() - total_start))
    return {
        "video_path": final_video_path,
        "srt_path":   srt_path,
        "meta_path":  meta_path,
        "summary_duration": summary_dur,
    }


def _step(msg: str) -> None:
    print(f"\n{'─' * 60}\n  {msg}\n{'─' * 60}")


def _safe_title(title: str, max_len: int = 40) -> str:
    safe = re.sub(r"[^\w\s\-]", "", title)
    safe = re.sub(r"\s+", "_", safe.strip())
    return safe[:max_len] or "summary"


def _retime_topic_groups(topic_groups, selected):
    if not topic_groups or not selected:
        return topic_groups
    retimed = []
    for old_start, label in topic_groups:
        chunk = min(selected,
                    key=lambda c: abs(c.get("source_new_start", c.get("new_start", 0.0)) - old_start))
        retimed.append((chunk.get("new_start", 0.0), label))
    retimed[0] = (0.0, retimed[0][1])
    return retimed
