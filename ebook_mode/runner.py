"""
ebook_mode/runner.py — Ebook summary video pipeline.

Flow:
    structured .txt file
        → ebook_mode.loader.load_ebook_file()          (parse chapters/quotes/lessons)
        → core.tts.pipeline (TTS for all chunks)       (narration audio)
        → ebook_mode.video.compile_ebook_video()       (visual rendering)
        → final .mp4 + .srt

Usage:
    from ebook_mode.runner import run
    result = run("rich_dad_poor_dad.txt", title="Rich Dad Poor Dad")
    print(result["video_path"])
"""

import os
import re
import time

from utils import get_logger, ensure_dirs, clean_temp, get_video_duration, \
    find_hindi_font, human_duration
from ebook_mode.loader import load_ebook_file
from ebook_mode import config as default_cfg

log = get_logger("ebook.runner")


def run(text_path: str, title: str = "", cfg=default_cfg,
        keep_temp: bool = False) -> dict:

    total_start = time.time()
    ensure_dirs(cfg.OUTPUT_DIR, cfg.TEMP_DIR, cfg.ASSETS_DIR)

    # Check TTS backend
    try:
        from story_mode.tts import check_backend_available
        check_backend_available(cfg)
    except Exception as e:
        log.warning("TTS backend check skipped: %s", e)

    font_path = find_hindi_font(cfg)

    # ── STEP 1: Parse ebook file ──────────────────────────────────────────
    _step("STEP 1 / 4 — Parsing ebook file")
    parsed      = load_ebook_file(text_path, cfg=cfg)
    book_title  = parsed["book_title"] or title or "Book Summary"
    author      = parsed["author"]
    chunks      = parsed["chunks"]
    chapter_list = parsed["chapter_list"]

    if not title:
        title = book_title

    log.info("Book: '%s' by %s — %d chapters, %d chunks",
             book_title, author or "unknown", len(chapter_list), len(chunks))

    if not chunks:
        raise ValueError(f"No content parsed from {text_path}")

    # ── STEP 2: Generate TTS audio ────────────────────────────────────────
    _step("STEP 2 / 4 — Generating narration audio")
    tts_audio_path = _generate_tts(chunks, cfg)
    total_dur      = get_video_duration(tts_audio_path)
    log.info("Narration duration: %s", human_duration(total_dur))

    # ── STEP 3: Retime chunks from TTS output ─────────────────────────────
    _step("STEP 3 / 4 — Retiming chunks")
    chunks = _retime_chunks(chunks, total_dur)

    # ── STEP 4: Build video ───────────────────────────────────────────────
    _step("STEP 4 / 4 — Building ebook video")
    safe_title = _safe_title(title)
    target_w, target_h = cfg.video_dimensions()

    # ── Pixabay image download (if configured) ────────────────────────────
    if getattr(cfg, "STORY_BG_MODE", "gradient").lower() == "pixabay":
        _step("Downloading Pixabay images for background")
        from core.pixabay import download_images_for_chunks
        px_paths = download_images_for_chunks(chunks, cfg, target_w, target_h)
        if px_paths:
            cfg.STORY_BG_IMAGES = px_paths
            cfg.STORY_BG_MODE   = "image"
            log.info("Pixabay: using %d downloaded images", len(px_paths))
        else:
            log.warning("Pixabay download failed — falling back to gradient")
            cfg.STORY_BG_MODE = "gradient"

    # ── Pre-render smooth slideshow if image mode with multiple images ────
    # Builds a beautiful Ken Burns + xfade slideshow video ONCE using ffmpeg,
    # then make_frame() just reads frames from it — much smoother and faster
    # than PIL per-frame rendering.
    slideshow_path = ""
    if getattr(cfg, "STORY_BG_MODE", "gradient").lower() == "image":
        from core.slideshow import resolve_image_dir, build_slideshow_video
        img_paths = resolve_image_dir(cfg)
        if len(img_paths) > 1:
            _step("Pre-rendering background slideshow (Ken Burns + smooth transitions)")
            sl_out = os.path.join(cfg.TEMP_DIR, f"{safe_title}_slideshow.mp4")
            os.makedirs(cfg.TEMP_DIR, exist_ok=True)
            slideshow_path = build_slideshow_video(
                image_paths=img_paths,
                output_path=sl_out,
                total_duration=total_dur,
                video_w=target_w,
                video_h=target_h,
                cfg=cfg,
                shuffle=True,
            )
            if slideshow_path:
                log.info("Slideshow ready (%d images) → %s", len(img_paths), slideshow_path)
            else:
                log.warning("Slideshow render failed — static image fallback")
        elif len(img_paths) == 1:
            log.info("Single image background: %s", img_paths[0])

    from ebook_mode.video import compile_ebook_video
    final_video_path = os.path.join(cfg.OUTPUT_DIR, f"{safe_title}_ebook_summary.mp4")

    print(f"DEBUG bg_mode={getattr(cfg,'STORY_BG_MODE','?')}")
    print(f"DEBUG BG_DIR={getattr(cfg,'STORY_BG_DIR','?')}")
    print(f"DEBUG BG_IMAGES={getattr(cfg,'STORY_BG_IMAGES',[])}")
    # import os
    bg_dir = getattr(cfg,'STORY_BG_DIR','background')
    # if os.path.isdir(bg_dir):
    #     print(f"DEBUG images in dir: {os.listdir(bg_dir)}")
    # else:
    print(f"DEBUG dir does not exist: {bg_dir}")

    compile_ebook_video(
        chunks=chunks,
        audio_path=tts_audio_path,
        output_path=final_video_path,
        video_width=target_w,
        video_height=target_h,
        font_path=font_path,
        cfg=cfg,
        book_title=book_title,
        slideshow_path=slideshow_path,
    )

    # ── SRT subtitle file ─────────────────────────────────────────────────
    srt_path = os.path.join(cfg.OUTPUT_DIR, f"{safe_title}.srt")
    _write_srt(chunks, srt_path)

    # ── Chapter index (useful for YouTube timestamps in description) ───────
    index_path = os.path.join(cfg.OUTPUT_DIR, f"{safe_title}_chapters.txt")
    _write_chapter_index(chunks, book_title, author, index_path)

    if not keep_temp:
        clean_temp(cfg)

    log.info("Total time: %s", human_duration(time.time() - total_start))
    log.info("Video:   %s", final_video_path)
    log.info("SRT:     %s", srt_path)
    log.info("Chapters: %s", index_path)

    return {
        "video_path":  final_video_path,
        "srt_path":    srt_path,
        "index_path":  index_path,
        "total_duration": total_dur,
        "book_title":  book_title,
        "author":      author,
    }


# ── TTS generation ────────────────────────────────────────────────────────────

def _generate_tts(chunks: list[dict], cfg) -> str:
    """
    Run TTS on all chunks in sequence. Chapter cards get a leading silence
    pause so the visual card has breathing room before the narration starts.
    """
    from story_mode.tts import generate_tts_audio

    chapter_pause = float(getattr(cfg, "EBOOK_CHAPTER_PAUSE",     2.5))
    lesson_pause  = float(getattr(cfg, "EBOOK_LESSON_PAUSE",       1.2))
    quote_pause   = float(getattr(cfg, "EBOOK_QUOTE_PAUSE_AFTER",  1.0))

    # Inject pause markers as silent placeholder entries that TTS will honour
    # by generating silence segments of the requested duration.
    # We do this by adding a "pause_before" key that pipeline.py respects,
    # falling back to inserting short silent wav clips if not supported.
    for chunk in chunks:
        ctype = chunk.get("chunk_type", "narration")
        if ctype == "chapter_card":
            chunk["pause_before"] = chapter_pause
        elif ctype == "lesson":
            chunk["pause_before"] = lesson_pause
        elif ctype == "quote":
            chunk["pause_after"] = quote_pause

    return generate_tts_audio(chunks, cfg)


# ── Timestamp retiming ────────────────────────────────────────────────────────

def _retime_chunks(chunks: list[dict], total_dur: float) -> list[dict]:
    """
    After TTS, real timing comes from the pipeline via new_start/new_end.
    Fall back to proportional distribution if those keys aren't set.
    """
    if all("new_start" in c and "new_end" in c for c in chunks):
        return chunks

    log.warning("new_start/new_end not set — distributing proportionally")
    n      = len(chunks)
    dur_ea = total_dur / n if n else 1.0
    for i, c in enumerate(chunks):
        c["new_start"] = round(i * dur_ea, 3)
        c["new_end"]   = round((i + 1) * dur_ea, 3)
    return chunks


# ── SRT writer ────────────────────────────────────────────────────────────────

def _write_srt(chunks: list[dict], path: str) -> None:
    def _ts(s: float) -> str:
        s   = max(0.0, s)
        h   = int(s // 3600)
        m   = int((s % 3600) // 60)
        sec = int(s % 60)
        ms  = int((s % 1) * 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

    with open(path, "w", encoding="utf-8") as f:
        idx = 1
        for c in chunks:
            start = c.get("new_start", c.get("start", 0.0))
            end   = c.get("new_end",   c.get("end",   start + 1.0))
            text  = c.get("display_text", c.get("text", "")).strip()
            if not text:
                continue
            f.write(f"{idx}\n{_ts(start)} --> {_ts(end)}\n{text}\n\n")
            idx += 1
    log.info("SRT → %s", path)


# ── Chapter index ─────────────────────────────────────────────────────────────

def _write_chapter_index(chunks: list[dict], book_title: str,
                          author: str, path: str) -> None:
    """
    Write a YouTube-ready chapter index file:
        00:00  Introduction
        03:22  Chapter 1: Rich Dad, Poor Dad
        ...
    """
    def _ts_yt(s: float) -> str:
        s = max(0.0, s)
        m = int(s // 60)
        sec = int(s % 60)
        return f"{m:02d}:{sec:02d}"

    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{book_title}")
        if author:
            f.write(f" by {author}")
        f.write("\n\nTimestamps:\n")

        for c in chunks:
            if c.get("chunk_type") != "chapter_card":
                continue
            start  = c.get("new_start", c.get("start", 0.0))
            label  = c.get("display_text", c.get("text", "")).strip()
            chap_n = c.get("chapter_num", "")
            f.write(f"{_ts_yt(start)}  Chapter {chap_n}: {label}\n")

    log.info("Chapter index → %s", path)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _step(msg: str) -> None:
    print(f"\n{'─' * 64}\n  {msg}\n{'─' * 64}")


def _safe_title(title: str, max_len: int = 48) -> str:
    safe = re.sub(r"[^\w\s\-]", "", title)
    safe = re.sub(r"\s+", "_", safe.strip())
    return safe[:max_len] or "ebook_summary"
