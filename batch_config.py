"""
batch_config.py — Configure batch video generation from a Q&A questions file.

HOW TO USE:
    1. Edit the settings below.
    2. Run:  python batch_runner.py
    3. Videos land in OUTPUT_DIR, one per part.

Each part gets its own video file  e.g. java_basics_part1_qa.mp4
                                        java_basics_part2_qa.mp4
                                        ...
and its own metadata file listing exactly which questions are in that part.
"""

# ── Input ────────────────────────────────────────────────────────────────────

# Path to the questions file (relative to this file, or absolute).
# Files live in the  questions/  folder by default.
QUESTIONS_FILE = "questions/artifical intelligence.txt"

# How many Q&A pairs to include in each part video.
QUESTIONS_PER_PART = 20

# Base name used for output filenames and video titles.
# e.g.  "java_basics"  →  java_basics_part1_qa.mp4, java_basics_part2_qa.mp4
BATCH_TITLE = "Artificial Intelligence Basic interview QA"

# ── Output ───────────────────────────────────────────────────────────────────

# Where finished videos and metadata are written.
# Overrides qa_mode/config.py OUTPUT_DIR for this batch run.
OUTPUT_DIR = "output/qa/ai"

# ── Optional overrides (set to None to use qa_mode/config.py defaults) ───────

# "en" | "hi" | "hig"  — None = use config default
LANGUAGE = "en"

# "reel" (1080×1920 vertical) | "full" (1920×1080 landscape) — None = default
OUTPUT_MODE = "full"

# "macos" | "xtts" | "mms" — None = use config default
TTS_BACKEND = "kokoro"

# Path to voice sample WAV (xtts only) — None = use config default
XTTS_VOICE_SAMPLE = "assets/clean_voice1.wav"

# macOS TTS voice name — None = use config default
MACOS_TTS_VOICE = None

# Keep temp files after each part?  False = clean up automatically
KEEP_TEMP = False
