"""
main.py — Entry point for the Hindi/English/Hinglish video generator.

Two independent modes:

    STORY MODE  (--mode story)
        Plain text story -> optional shortening -> narration -> slideshow.
        See story_mode/ for its pipeline and story_mode/config.py for
        its settings.

    QA MODE  (--mode qa)
        Interview-prep Q&A file -> question/think/countdown/answer
        slides -> narration -> slideshow. Never shortens content.
        See qa_mode/ for its pipeline and qa_mode/config.py for its
        settings.

Each mode has its own config file — TTS backend, language, output
format (reel/full), styling, and pacing are all independently
configurable per mode. Edit story_mode/config.py or qa_mode/config.py
directly for permanent defaults, or override per-run with CLI flags
below.

Usage:
    python main.py --mode story --file story.txt --title "नेपोलियन हिल"
    python main.py --mode qa --file interview_questions.txt --title "HR इंटरव्यू"
    python main.py --mode story --file story.txt --output-mode reel --tts-backend xtts --voice-sample my_voice.wav
"""

import sys
import argparse
import logging

from utils import get_logger

log = get_logger("main")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py",
        description="🎬  Hindi/English/Hinglish Video Generator — story & Q&A modes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --mode story --file story.txt
  python main.py --mode story --file story.txt --output-mode reel
  python main.py --mode qa --file interview_questions.txt --title "HR इंटरव्यू"
  python main.py --mode qa --file qa.txt --tts-backend xtts --voice-sample my_voice.wav
        """,
    )

    p.add_argument("--mode", required=True, choices=["story", "qa"],
                    help="Which pipeline to run")
    p.add_argument("--file", required=True, metavar="FILE",
                    help="Path to the input text file (story text, or Q&A pairs)")
    p.add_argument("--title", default=None,
                   help="Output filename / metadata title")

    # ── Per-mode config overrides (apply to whichever --mode is chosen) ──
    p.add_argument("--language", choices=["hi", "en", "hig"], default=None,
                   help="Override LANGUAGE (hi / en / hig) for this run")
    p.add_argument("--output-mode", choices=["reel", "full"], default=None,
                   help="Override OUTPUT_MODE (reel / full) for this run")
    p.add_argument("--ratio", type=float, default=None,
                   help="Override TARGET_RATIO for this run (story mode only)")
    p.add_argument("--tts-backend", choices=["xtts", "mms", "macos"], default=None,
                   help="Override TTS_BACKEND for this run")
    p.add_argument("--voice-sample", default=None, metavar="WAV",
                   help="Path to a voice sample WAV (xtts backend only)")
    p.add_argument("--voice", default=None,
                   help="Override macOS TTS voice name")
    p.add_argument("--keep-temp", action="store_true",
                   help="Keep temporary files after processing")
    p.add_argument("--verbose", action="store_true",
                   help="Show debug-level logs")

    return p


def _apply_overrides(cfg, args: argparse.Namespace) -> None:
    """Apply CLI override flags onto the active mode's config module."""
    if args.language is not None:
        cfg.LANGUAGE = args.language
    if args.output_mode is not None:
        cfg.OUTPUT_MODE = args.output_mode
    if args.ratio is not None and hasattr(cfg, "TARGET_RATIO"):
        cfg.TARGET_RATIO = args.ratio
    if args.tts_backend is not None:
        cfg.TTS_BACKEND = args.tts_backend
    if args.voice_sample is not None:
        cfg.XTTS_VOICE_SAMPLE = args.voice_sample
    if args.voice is not None:
        cfg.MACOS_TTS_VOICE = args.voice
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "story":
        from story_mode import config as cfg
        from story_mode.runner import run
        default_title = "summary"
    else:
        from qa_mode import config as cfg
        from qa_mode.runner import run
        default_title = "interview_prep"

    _apply_overrides(cfg, args)
    title = args.title or default_title

    try:
        result = run(args.file, title=title, cfg=cfg, keep_temp=args.keep_temp)
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user.")
        sys.exit(0)
    except Exception as exc:
        log.exception("Pipeline failed: %s", exc)
        sys.exit(1)

    _print_completion_banner(result)


def _print_completion_banner(result: dict) -> None:
    from utils import human_duration
    print("\n" + "═" * 60)
    print("  ✅  DONE!  Video is ready.")
    print("═" * 60)
    print(f"  🎬  Video    : {result['video_path']}")
    print(f"  📄  Subtitles: {result['srt_path']}")
    print(f"  📋  Metadata : {result['meta_path']}")
    print(f"  ✂️  Duration : {human_duration(result['summary_duration'])}")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
