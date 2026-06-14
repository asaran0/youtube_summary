"""
main.py — Entry point for the Hindi YouTube Video Summarizer.

Usage:
    python main.py <youtube_url>
    python main.py <youtube_url> --ratio 0.80
    python main.py <youtube_url> --model large-v3 --keep-temp

Run  python main.py --help  for all options.
"""

import os
import sys
import time
import argparse
import logging

# ── Project modules ──────────────────────────────────────────────────────────
import config
import downloader
import transcriber
import summarizer
import narration_adapter
import tts_generator
import slideshow_renderer
import subtitle_handler
import metadata_writer
from utils import (
    get_logger, ensure_dirs, clean_temp,
    get_video_duration, find_hindi_font,
    check_system_deps, check_python_deps,
    human_duration,
)

log = get_logger("main")


# ─────────────────────────────────────────────────────────────
#  CLI  ARGUMENT PARSER
# ─────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py",
        description="🎬  Hindi YouTube Video Summarizer — creates a condensed summary video",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py https://youtu.be/xxxxxxxxxxx
  python main.py https://youtu.be/xxxxxxxxxxx --ratio 0.80
  python main.py https://youtu.be/xxxxxxxxxxx --model large-v3
  python main.py https://youtu.be/xxxxxxxxxxx --no-banners --keep-temp
        """,
    )

    p.add_argument("url",
                   help="YouTube video URL")

    p.add_argument("--ratio", type=float, default=config.TARGET_RATIO,
                   metavar="RATIO",
                   help=f"Fraction of video to keep, e.g. 0.75  (default: {config.TARGET_RATIO})")

    p.add_argument("--model", default=config.WHISPER_MODEL,
                   choices=["tiny", "base", "small", "medium", "large-v3"],
                   help=f"Whisper model size  (default: {config.WHISPER_MODEL})")

    p.add_argument("--no-banners", action="store_true",
                   help="Disable animated topic banners")

    p.add_argument("--language", choices=["hi", "en"], default=config.LANGUAGE,
                   help=f"Output/transcription language: hi or en  (default: {config.LANGUAGE})")

    p.add_argument("--voice", default=None,
                   help="macOS TTS voice name  (default: language-specific)")

    p.add_argument("--tts-backend", choices=["macos", "mms"], default=config.TTS_BACKEND,
                   help=f"TTS backend  (default: {config.TTS_BACKEND})")

    p.add_argument("--format", choices=["auto", "youtube", "reel"], default=config.OUTPUT_FORMAT,
                   help=f"Output layout  (default: {config.OUTPUT_FORMAT})")

    p.add_argument("--keep-temp", action="store_true",
                   help="Keep temporary files after processing")

    p.add_argument("--output-dir", default=config.OUTPUT_DIR,
                   help=f"Directory for final output files  (default: {config.OUTPUT_DIR})")

    p.add_argument("--verbose", action="store_true",
                   help="Show debug-level log messages")

    return p


# ─────────────────────────────────────────────────────────────
#  MAIN PIPELINE
# ─────────────────────────────────────────────────────────────

def run(args: argparse.Namespace) -> None:
    """Execute the complete summarization pipeline."""

    total_start = time.time()

    # ── Apply CLI overrides to config ────────────────────────────────────
    config.TARGET_RATIO    = args.ratio
    config.WHISPER_MODEL   = args.model
    config.BANNER_ENABLED  = not args.no_banners
    config.OUTPUT_DIR      = args.output_dir
    config.LANGUAGE        = args.language
    config.MACOS_TTS_VOICE = args.voice or config.MACOS_TTS_VOICES.get(args.language, config.MACOS_TTS_VOICE)
    config.TTS_BACKEND     = args.tts_backend
    config.OUTPUT_FORMAT   = args.format

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # ── Sanity checks ────────────────────────────────────────────────────
    log.info("Checking dependencies …")
    check_system_deps()
    check_python_deps()

    ensure_dirs(config.OUTPUT_DIR, config.TEMP_DIR, config.ASSETS_DIR)

    # ── Locate / download Hindi font ─────────────────────────────────────
    log.info("Looking for Hindi font …")
    font_path = find_hindi_font()
    font_dir  = os.path.dirname(os.path.abspath(font_path))

    # ═══════════════════════════════════════════════════════════════
    #  STEP 1 — DOWNLOAD
    # ═══════════════════════════════════════════════════════════════
    _step("STEP 1 / 7 — Downloading audio")
    dl = downloader.download(args.url)

    video_path = dl["video_path"]
    audio_path = dl["audio_path"]
    orig_meta  = dl["metadata"]
    is_reel    = dl["is_reel"]

    total_duration = float(orig_meta.get("duration") or 0) or get_video_duration(audio_path)
    log.info("Original duration: %s", human_duration(total_duration))

    # ═══════════════════════════════════════════════════════════════
    #  STEP 2 — TRANSCRIBE
    # ═══════════════════════════════════════════════════════════════
    _step("STEP 2 / 7 — Transcribing audio (Whisper)")
    segments = transcriber.transcribe(audio_path)
    log.info("Full transcript: %d segments", len(segments))

    # ═══════════════════════════════════════════════════════════════
    #  STEP 3 — SELECT IMPORTANT SEGMENTS
    # ═══════════════════════════════════════════════════════════════
    _step("STEP 3 / 7 — Selecting important segments")
    result = summarizer.select_segments(segments, total_duration)

    selected = result["selected_segments"]
    topic_groups  = result["topic_groups"]
    summary_dur   = result["summary_duration"]

    log.info(
        "Kept %.0f %% of content  (%s → %s)",
        result["kept_ratio"] * 100,
        human_duration(total_duration),
        human_duration(summary_dur),
    )
    selected = narration_adapter.apply_storytelling(selected)

    # ═══════════════════════════════════════════════════════════════
    #  STEP 4 — GENERATE SUBTITLE FILE
    # ═══════════════════════════════════════════════════════════════
    _step("STEP 4 / 7 — Generating new narration")

    tts_audio_path = tts_generator.generate_tts_audio(selected)
    summary_dur = selected[-1]["new_end"] if selected else get_video_duration(tts_audio_path)
    topic_groups = _retime_topic_groups(topic_groups, selected)
    log.info("Generated narration duration: %s", human_duration(summary_dur))

    # ═══════════════════════════════════════════════════════════════
    #  STEP 5 — GENERATE SUBTITLE FILE
    # ═══════════════════════════════════════════════════════════════
    _step("STEP 5 / 7 — Generating subtitles")

    safe_title  = _safe_title(orig_meta.get("title", "summary"))
    srt_path    = os.path.join(config.OUTPUT_DIR, f"{safe_title}.srt")

    target_w, target_h = (
        (config.REEL_WIDTH, config.REEL_HEIGHT)
        if _use_reel_layout(is_reel)
        else (config.YOUTUBE_WIDTH, config.YOUTUBE_HEIGHT)
    )

    ass_path = subtitle_handler.generate_subtitle_files(
        selected_chunks=selected,
        output_srt_path=srt_path,
        font_path=font_path,
        video_width=target_w,
        video_height=target_h,
    )
    log.info("SRT file → %s", srt_path)

    # ═══════════════════════════════════════════════════════════════
    #  STEP 6 — COMPILE VIDEO  (new slideshow + generated voice)
    # ═══════════════════════════════════════════════════════════════
    _step("STEP 6 / 7 — Compiling slideshow video")

    no_sub_path = os.path.join(config.TEMP_DIR, "summary_no_sub.mp4")
    slideshow_renderer.compile_slideshow_video(
        selected_chunks=selected,
        audio_path=tts_audio_path,
        output_path=no_sub_path,
        video_width=target_w,
        video_height=target_h,
        font_path=font_path,
        title=orig_meta.get("title", ""),
    )

    # Burn subtitles in
    final_video_path = os.path.join(config.OUTPUT_DIR, f"{safe_title}_summary.mp4")
    subtitle_handler.burn_subtitles(
        input_video=no_sub_path,
        ass_path=ass_path,
        output_video=final_video_path,
        font_dir=font_dir,
        font_path=font_path,
    )

    # ═══════════════════════════════════════════════════════════════
    #  STEP 7 — METADATA FILE
    # ═══════════════════════════════════════════════════════════════
    _step("STEP 7 / 7 — Writing metadata")
    meta_path = metadata_writer.generate_and_save(
        original_metadata=orig_meta,
        selected_chunks=selected,
        topic_groups=topic_groups,
        summary_duration=summary_dur,
        output_dir=config.OUTPUT_DIR,
    )

    # ── Clean temp files (unless --keep-temp) ───────────────────────────
    if not args.keep_temp:
        log.info("Cleaning temporary files …")
        clean_temp()

    # ── Final summary ───────────────────────────────────────────────────
    elapsed = time.time() - total_start
    _print_completion_banner(
        video_path=final_video_path,
        srt_path=srt_path,
        meta_path=meta_path,
        original_dur=total_duration,
        summary_dur=summary_dur,
        elapsed=elapsed,
    )


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────

def _step(msg: str) -> None:
    """Print a prominent step header."""
    print(f"\n{'─' * 60}")
    print(f"  {msg}")
    print(f"{'─' * 60}")


def _safe_title(title: str, max_len: int = 40) -> str:
    """Convert title to a safe filename prefix."""
    import re
    safe = re.sub(r'[^\w\s\-]', '', title)
    safe = re.sub(r'\s+', '_', safe.strip())
    return safe[:max_len] or "summary"


def _use_reel_layout(source_is_reel: bool) -> bool:
    if config.OUTPUT_FORMAT == "reel":
        return True
    if config.OUTPUT_FORMAT == "youtube":
        return False
    return source_is_reel


def _retime_topic_groups(topic_groups: list[tuple], selected: list[dict]) -> list[tuple]:
    """Map topic chapter starts from original summary time to TTS time."""
    if not topic_groups or not selected:
        return topic_groups

    retimed = []
    for old_start, label in topic_groups:
        chunk = min(
            selected,
            key=lambda c: abs(c.get("source_new_start", c.get("new_start", 0.0)) - old_start),
        )
        retimed.append((chunk.get("new_start", 0.0), label))

    retimed[0] = (0.0, retimed[0][1])
    return retimed


def _print_completion_banner(
    video_path, srt_path, meta_path,
    original_dur, summary_dur, elapsed
) -> None:
    print("\n" + "═" * 60)
    print("  ✅  DONE!  Summary video is ready.")
    print("═" * 60)
    print(f"  🎬  Video   : {video_path}")
    print(f"  📄  Subtitles: {srt_path}")
    print(f"  📋  Metadata : {meta_path}")
    print(f"  ⏱  Original : {human_duration(original_dur)}")
    print(f"  ✂️  Summary  : {human_duration(summary_dur)}"
          f"  ({summary_dur / original_dur * 100:.0f} %)")
    print(f"  🕐  Processing time: {human_duration(elapsed)}")
    print("═" * 60 + "\n")


# ─────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = build_parser()
    args   = parser.parse_args()

    try:
        run(args)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.")
        sys.exit(0)
    except Exception as exc:
        log.exception("Pipeline failed: %s", exc)
        sys.exit(1)
