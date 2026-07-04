"""
main.py — Entry point for the Hindi/English/Hinglish video generator.

Three independent modes:

    STORY MODE  (--mode story)
        Plain text story -> optional shortening -> narration -> slideshow.
        See story_mode/ for its pipeline and story_mode/config.py for
        its settings.

    QA MODE  (--mode qa)
        Interview-prep Q&A file -> question/think/countdown/answer
        slides -> narration -> slideshow. Never shortens content.
        See qa_mode/ for its pipeline and qa_mode/config.py for its
        settings.

    EBOOK MODE  (--mode ebook)
        Structured book-summary text file with chapter headings, key
        lessons, and block quotes -> chapter title cards + narration
        + quote callouts -> 30-40 min YouTube-style summary video.
        See ebook_mode/ for its pipeline and ebook_mode/config.py.

        Input file format:
            # Book Title
            ## Author: Name
            ## Chapter 1: Title
            ### Key Lesson
            Narration text here.
            > "A direct quote from the book."

        Example:
            python main.py --mode ebook --file examples/rich_dad_poor_dad.txt

Each mode has its own config file — TTS backend, language, output
format (reel/full), styling, and pacing are all independently
configurable per mode.

Usage:
    python main.py --mode story --file story.txt --title "Napoleon Hill"
    python main.py --mode qa --file interview_questions.txt --title "HR Interview"
    python main.py --mode ebook --file rich_dad_poor_dad.txt --title "Rich Dad Poor Dad"
    python main.py --mode ebook --file book.txt --output-mode reel
"""

import sys
import argparse
import logging

from utils import get_logger

log = get_logger("main")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="main.py",
        description="🎬  Video Generator — story, Q&A, and ebook summary modes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --mode story --file story.txt
  python main.py --mode story --file story.txt --output-mode reel
  python main.py --mode qa --file interview_questions.txt --title "HR Interview"
  python main.py --mode ebook --file examples/rich_dad_poor_dad.txt
  python main.py --mode ebook --file book.txt --language en --output-mode full
        """,
    )

    p.add_argument("--mode", required=True, choices=["story", "qa", "ebook"],
                    help="Which pipeline to run")
    p.add_argument("--file", required=True, metavar="FILE",
                    help="Path to the input text file")
    p.add_argument("--title", default=None,
                   help="Output filename / metadata title (ebook: auto-detected from file)")

    # ── Per-mode config overrides ─────────────────────────────────────────
    p.add_argument("--language", choices=["hi", "en", "hig"], default=None,
                   help="Override LANGUAGE for this run")
    p.add_argument("--output-mode", choices=["reel", "full"], default=None,
                   help="Override OUTPUT_MODE (reel / full) for this run")
    p.add_argument("--ratio", type=float, default=None,
                   help="Override TARGET_RATIO (story mode only)")
    p.add_argument("--tts-backend", choices=["kokoro", "xtts", "mms", "macos"],
                   default=None, help="Override TTS_BACKEND for this run")
    p.add_argument("--voice-sample", default=None, metavar="WAV",
                   help="Path to a voice sample WAV (xtts backend only)")
    p.add_argument("--voice", default=None,
                   help="Override macOS TTS voice name")
    p.add_argument("--bg-music", default=None, metavar="FILE",
                   help="Path to background music file (mp3/wav) — enables music bed")
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
    if args.bg_music is not None:
        cfg.BACKGROUND_MUSIC_ENABLED = True
        cfg.BACKGROUND_MUSIC_PATH    = args.bg_music
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.mode == "story":
        from story_mode import config as cfg
        from story_mode.runner import run
        default_title = "summary"
    elif args.mode == "qa":
        from qa_mode import config as cfg
        from qa_mode.runner import run
        default_title = "interview_prep"
    else:  # ebook
        from ebook_mode import config as cfg
        from ebook_mode.runner import run
        default_title = "ebook_summary"

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

    _print_completion_banner(result, args.mode)


def _print_completion_banner(result: dict, mode: str) -> None:
    from utils import human_duration
    print("\n" + "═" * 64)
    print("  ✅  DONE!  Video is ready.")
    print("═" * 64)
    print(f"  🎬  Video     : {result['video_path']}")
    print(f"  📄  Subtitles : {result['srt_path']}")

    if mode == "ebook":
        if result.get("index_path"):
            print(f"  📚  Chapters  : {result['index_path']}")
        if result.get("book_title"):
            print(f"  📖  Book      : {result['book_title']}")
            if result.get("author"):
                print(f"  ✍️   Author    : {result['author']}")
        dur_key = "total_duration"
    else:
        if result.get("meta_path"):
            print(f"  📋  Metadata  : {result['meta_path']}")
        dur_key = "summary_duration"

    if result.get(dur_key):
        print(f"  ✂️   Duration  : {human_duration(result[dur_key])}")
    print("═" * 64 + "\n")


if __name__ == "__main__":
    main()
