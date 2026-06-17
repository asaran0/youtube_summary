"""
main.py — Entry point for the Hindi Video Summarizer.

Two independent flows, one entry point:

    TEXT MODE  (--text story.txt)
        story.txt → Lekha TTS → slideshow video
        No YouTube URL, no download, no Whisper.

    URL MODE   (python main.py <youtube_url>)
        YouTube → download → Whisper → summarize → Lekha TTS → slideshow video

Usage:
    python main.py https://youtu.be/xxxxxxxxxxx
    python main.py --text story.txt
    python main.py --text story.txt --title "नेपोलियन हिल"
    python main.py https://youtu.be/xxxxxxxxxxx --ratio 0.80
"""

import os
import sys
import time
import argparse
import logging

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
#  CLI
# ─────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py",
        description="🎬  Hindi Video Summarizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py https://youtu.be/xxxxxxxxxxx
  python main.py https://youtu.be/xxxxxxxxxxx --ratio 0.80
  python main.py --text story.txt
  python main.py --text story.txt --title "नेपोलियन हिल"
        """,
    )

    # ── Input: exactly one of url or --text required ─────────────
    input_group = p.add_mutually_exclusive_group(required=True)
    input_group.add_argument("url", nargs="?", default=None,
                             help="YouTube video URL")
    input_group.add_argument("--text", metavar="FILE",
                             help="Path to a Hindi .txt file (skips download & Whisper)")

    # ── Shared options ────────────────────────────────────────────
    p.add_argument("--title", default="summary",
                   help="Output filename title (used in text mode)")
    p.add_argument("--ratio", type=float, default=config.TARGET_RATIO,
                   metavar="RATIO",
                   help=f"Fraction of content to keep (default: {config.TARGET_RATIO})")
    p.add_argument("--model", default=config.WHISPER_MODEL,
                   choices=["tiny", "base", "small", "medium", "large-v3"],
                   help=f"Whisper model size (default: {config.WHISPER_MODEL})")
    p.add_argument("--no-banners", action="store_true",
                   help="Disable animated topic banners")
    p.add_argument("--language", choices=["hi", "en"], default=config.LANGUAGE,
                   help=f"Language (default: {config.LANGUAGE})")
    p.add_argument("--voice", default=None,
                   help="macOS TTS voice name")
    p.add_argument("--tts-backend", choices=["macos", "mms"], default=config.TTS_BACKEND,
                   help=f"TTS backend (default: {config.TTS_BACKEND})")
    p.add_argument("--format", choices=["auto", "youtube", "reel"], default=config.OUTPUT_FORMAT,
                   help=f"Output layout (default: {config.OUTPUT_FORMAT})")
    p.add_argument("--keep-temp", action="store_true",
                   help="Keep temporary files after processing")
    p.add_argument("--output-dir", default=config.OUTPUT_DIR,
                   help=f"Output directory (default: {config.OUTPUT_DIR})")
    p.add_argument("--verbose", action="store_true",
                   help="Show debug-level logs")

    return p


# ─────────────────────────────────────────────────────────────
#  SHARED SETUP  (runs before both flows)
# ─────────────────────────────────────────────────────────────

def _apply_config(args: argparse.Namespace) -> None:
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


def _shared_setup() -> str:
    """Dependency checks, dirs, font. Returns font_path."""
    log.info("Checking dependencies …")
    check_system_deps()
    check_python_deps()
    ensure_dirs(config.OUTPUT_DIR, config.TEMP_DIR, config.ASSETS_DIR)
    log.info("Looking for Hindi font …")
    return find_hindi_font()


# ─────────────────────────────────────────────────────────────
#  SHARED STEPS  (used by both flows)
# ─────────────────────────────────────────────────────────────

def _step3_to_7(
    segments: list[dict],
    total_duration: float,
    safe_title: str,
    font_path: str,
    is_reel: bool,
    orig_meta: dict,
    args: argparse.Namespace,
) -> None:
    """
    Steps 3–7 are identical for both flows:
    summarize → TTS → subtitles → slideshow → metadata
    """

    # ── Step 3: Summarize ────────────────────────────────────────
    _step("STEP 3 / 5 — Selecting segments")
    result   = summarizer.select_segments(segments, total_duration)
    selected = result["selected_segments"]
    topic_groups = result["topic_groups"]
    log.info("Kept %.0f%% of content", result["kept_ratio"] * 100)

    selected = narration_adapter.apply_storytelling(selected)

    # ── Step 4: TTS ──────────────────────────────────────────────
    _step("STEP 4 / 5 — Generating Lekha narration")
    tts_audio_path = tts_generator.generate_tts_audio(selected)
    summary_dur    = selected[-1]["new_end"] if selected else get_video_duration(tts_audio_path)
    topic_groups   = _retime_topic_groups(topic_groups, selected)
    log.info("Narration duration: %s", human_duration(summary_dur))

    # total_duration fallback for text-only mode (was 0.0 before TTS)
    if total_duration == 0.0:
        total_duration = summary_dur

    # ── Step 5: Subtitles ────────────────────────────────────────
    _step("STEP 5 / 5 — Subtitles + slideshow + metadata")
    srt_path = os.path.join(config.OUTPUT_DIR, f"{safe_title}.srt")
    target_w, target_h = _video_dimensions(is_reel)

    ass_path = subtitle_handler.generate_subtitle_files(
        selected_chunks=selected,
        output_srt_path=srt_path,
        font_path=font_path,
        video_width=target_w,
        video_height=target_h,
    )

    # ── Slideshow + burn subs ────────────────────────────────────
    font_dir    = os.path.dirname(os.path.abspath(font_path))
    no_sub_path = os.path.join(config.TEMP_DIR, "summary_no_sub.mp4")
    slideshow_renderer.compile_slideshow_video(
        selected_chunks=selected,
        audio_path=tts_audio_path,
        output_path=no_sub_path,
        video_width=target_w,
        video_height=target_h,
        font_path=font_path,
        title=orig_meta.get("title", safe_title),
    )

    final_video_path = os.path.join(config.OUTPUT_DIR, f"{safe_title}_summary.mp4")
    subtitle_handler.burn_subtitles(
        input_video=no_sub_path,
        ass_path=ass_path,
        output_video=final_video_path,
        font_dir=font_dir,
        font_path=font_path,
    )

    # ── Metadata ─────────────────────────────────────────────────
    meta_path = metadata_writer.generate_and_save(
        original_metadata=orig_meta,
        selected_chunks=selected,
        topic_groups=topic_groups,
        summary_duration=summary_dur,
        output_dir=config.OUTPUT_DIR,
    )

    if not args.keep_temp:
        clean_temp()

    _print_completion_banner(
        video_path=final_video_path,
        srt_path=srt_path,
        meta_path=meta_path,
        original_dur=total_duration,
        summary_dur=summary_dur,
    )


# ─────────────────────────────────────────────────────────────
#  FLOW A — TEXT FILE  (no URL, no Whisper)
# ─────────────────────────────────────────────────────────────

def run_text_flow(args: argparse.Namespace) -> None:
    """
    Text file → segments → Lekha TTS → slideshow.
    No download. No Whisper. No YouTube URL needed.
    """
    total_start = time.time()
    _apply_config(args)
    font_path = _shared_setup()

    _step("STEP 1 / 5 — Loading text file")
    segments = _load_text_file(args.text)
    log.info("Loaded %d sentences from %s", len(segments), args.text)

    _step("STEP 2 / 5 — Ready (no download needed)")
    safe_title   = _safe_title(args.title)
    orig_meta    = {"title": args.title}
    total_duration = 0.0   # unknown until after TTS; set inside _step3_to_7

    _step3_to_7(
        segments=segments,
        total_duration=total_duration,
        safe_title=safe_title,
        font_path=font_path,
        is_reel=False,
        orig_meta=orig_meta,
        args=args,
    )

    log.info("Total time: %s", human_duration(time.time() - total_start))


# ─────────────────────────────────────────────────────────────
#  FLOW B — YOUTUBE URL  (original flow, unchanged)
# ─────────────────────────────────────────────────────────────

def run_url_flow(args: argparse.Namespace) -> None:
    """
    YouTube URL → download → Whisper → summarize → Lekha TTS → slideshow.
    Original flow. Nothing changed here.
    """
    total_start = time.time()
    _apply_config(args)
    font_path = _shared_setup()

    _step("STEP 1 / 5 — Downloading audio")
    dl             = downloader.download(args.url)
    audio_path     = dl["audio_path"]
    orig_meta      = dl["metadata"]
    is_reel        = dl["is_reel"]
    total_duration = float(orig_meta.get("duration") or 0) or get_video_duration(audio_path)
    log.info("Original duration: %s", human_duration(total_duration))

    _step("STEP 2 / 5 — Transcribing (Whisper)")
    segments = transcriber.transcribe(audio_path)
    log.info("Transcribed %d segments", len(segments))

    safe_title = _safe_title(orig_meta.get("title", "summary"))

    _step3_to_7(
        segments=segments,
        total_duration=total_duration,
        safe_title=safe_title,
        font_path=font_path,
        is_reel=is_reel,
        orig_meta=orig_meta,
        args=args,
    )

    log.info("Total time: %s", human_duration(time.time() - total_start))


# ─────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────

def _load_text_file(path: str) -> list[dict]:
    """
    Read a plain Hindi .txt file and return Whisper-compatible segments.
    Strips timestamp headers like [00:00:00 - 00:02:11] automatically.
    Splits on sentence-ending punctuation: ।  .  ?  !
    Fake timestamps spread evenly (corrected after TTS).
    """
    import re

    with open(path, encoding="utf-8") as f:
        raw = f.read()

    raw = re.sub(r"\[\d{2}:\d{2}:\d{2}[^\]]*\]", "", raw)   # strip timestamps
    sentences = re.split(r"(?<=[।.?!])\s+", raw.strip())
    sentences = [s.strip() for s in sentences if s.strip()]

    if not sentences:
        raise ValueError(f"No text found in {path}")

    seg_dur = 1.0   # placeholder; real timing set after TTS
    return [
        {
            "id":               i,
            "start":            round(i * seg_dur, 2),
            "end":              round((i + 1) * seg_dur, 2),
            "text":             text,
            "avg_logprob":      -0.1,
            "no_speech_prob":   0.01,
        }
        for i, text in enumerate(sentences)
    ]


def _step(msg: str) -> None:
    print(f"\n{'─' * 60}\n  {msg}\n{'─' * 60}")


def _safe_title(title: str, max_len: int = 40) -> str:
    import re
    safe = re.sub(r"[^\w\s\-]", "", title)
    safe = re.sub(r"\s+", "_", safe.strip())
    return safe[:max_len] or "summary"


def _video_dimensions(is_reel: bool) -> tuple[int, int]:
    if config.OUTPUT_FORMAT == "reel" or (config.OUTPUT_FORMAT == "auto" and is_reel):
        return config.REEL_WIDTH, config.REEL_HEIGHT
    return config.YOUTUBE_WIDTH, config.YOUTUBE_HEIGHT


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


def _print_completion_banner(video_path, srt_path, meta_path, original_dur, summary_dur):
    print("\n" + "═" * 60)
    print("  ✅  DONE!  Summary video is ready.")
    print("═" * 60)
    print(f"  🎬  Video    : {video_path}")
    print(f"  📄  Subtitles: {srt_path}")
    print(f"  📋  Metadata : {meta_path}")
    if original_dur:
        print(f"  ⏱  Original : {human_duration(original_dur)}")
    print(f"  ✂️  Output   : {human_duration(summary_dur)}")
    print("═" * 60 + "\n")


# ─────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = build_parser()
    args   = parser.parse_args()

    # One decision here, then delegate to the right flow — no if/else inside flows
    flow = run_text_flow if args.text else run_url_flow

    try:
        flow(args)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.")
        sys.exit(0)
    except Exception as exc:
        log.exception("Pipeline failed: %s", exc)
        sys.exit(1)