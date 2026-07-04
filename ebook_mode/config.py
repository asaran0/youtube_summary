"""
ebook_mode/config.py — Settings for book summary videos (30-40 min).

Designed for books like Rich Dad Poor Dad, Atomic Habits, Think and
Grow Rich, etc. Input is a structured .txt file with chapter markers;
output is a YouTube-style narrated summary video.

Input file format:
─────────────────────────────────────────────────────────────
# Book Title
## Author: Robert Kiyosaki
## Tagline: What the Rich Teach Their Kids About Money

## Chapter 1: Rich Dad, Poor Dad
### Key Lesson
The rich don't work for money — they make money work for them.

Robert Kiyosaki grew up with two father figures...

> "The poor and middle class work for money. The rich have money work for them."

More narration continues here...

## Chapter 2: The Rich Don't Work for Money
...
─────────────────────────────────────────────────────────────
"""

import os

MODE_NAME = "ebook"

# ─────────────────────────────────────────────────────────────
#  LANGUAGE
# ─────────────────────────────────────────────────────────────
LANGUAGE = "hi"

# ─────────────────────────────────────────────────────────────
#  OUTPUT MODE
# ─────────────────────────────────────────────────────────────
# "full" → landscape 1920×1080 for regular YouTube (recommended for long-form)
# "reel" → vertical 1080×1920 for Shorts/Reels
OUTPUT_MODE    = "full"

YOUTUBE_WIDTH  = 1920
YOUTUBE_HEIGHT = 1080
REEL_WIDTH     = 1080
REEL_HEIGHT    = 1920
OUTPUT_FPS     = 30

# ─────────────────────────────────────────────────────────────
#  TTS / NARRATION
# ─────────────────────────────────────────────────────────────
TTS_BACKEND = "kokoro"

EBOOK_VOICE_GENDER = "male"   # "male" | "female"

# Slower than story mode — book narration benefits from a considered pace.
# 0.80 ≈ measured, authoritative; raise toward 0.90 for faster delivery.
KOKORO_SPEED = 0.80

_KOKORO_VOICES_BY_GENDER = {
    "male":   {"en": "am_adam",  "hi": "hm_omega", "hig": "hm_omega"},
    "female": {"en": "af_heart", "hi": "hf_alpha",  "hig": "hf_alpha"},
}
KOKORO_VOICES = _KOKORO_VOICES_BY_GENDER.get(EBOOK_VOICE_GENDER,
                _KOKORO_VOICES_BY_GENDER["male"])

MACOS_TTS_VOICE  = "Daniel"
MACOS_TTS_VOICES = {"en": "Daniel", "hi": "Lekha", "hig": "Lekha"}
MACOS_TTS_RATE   = 120

XTTS_VOICE_SAMPLE = "assets/clean_voice_story.wav"

MMS_TTS_MODEL_IDS = {
    "hi":  "facebook/mms-tts-hin",
    "hig": "facebook/mms-tts-hin",
    "en":  "facebook/mms-tts-eng",
}

# Pacing — generous gaps give the listener time to absorb each idea.
# Chapter transitions get even more space (see EBOOK_CHAPTER_PAUSE below).
TTS_PAUSE_BETWEEN_SEGMENTS    = 0.55   # gap between sentences
TTS_PAUSE_VARY_BY_PUNCTUATION = True   # longer pause after '...' '?' '!'
TTS_PAUSE_BETWEEN_PHRASES     = 0.30
TTS_ANSWER_PAUSE_EXTRA        = 0.0

# Extra silence injected before every chapter title card.
# Long enough to feel like a chapter break without being uncomfortable.
EBOOK_CHAPTER_PAUSE     = 2.5   # seconds before a new chapter card
EBOOK_LESSON_PAUSE      = 1.2   # seconds before a "Key Lesson" slide
EBOOK_QUOTE_PAUSE_AFTER = 1.0   # seconds of silence after a quote

# ─────────────────────────────────────────────────────────────
#  AUDIO POST-PROCESSING
# ─────────────────────────────────────────────────────────────
AUDIO_POST_PROCESSING = True
AUDIO_FILTER = (
    "highpass=f=80,"
    "lowpass=f=14000,"
    # Gentle warmth boost — makes narration feel like a podcast
    "equalizer=f=180:width_type=o:width=2:g=1.5,"
    # Presence clarity
    "equalizer=f=3000:width_type=o:width=2:g=1.2,"
    # Tame harshness
    "equalizer=f=7500:width_type=o:width=2:g=-2.0,"
    # Podcast-style light compression — even, never pumpy
    "acompressor=threshold=-18dB:ratio=2.0:attack=20:release=400:makeup=1.5,"
    # -14 LUFS: standard YouTube loudness
    "loudnorm=I=-14:TP=-1:LRA=12"
)

# ─────────────────────────────────────────────────────────────
#  BACKGROUND MUSIC
# ─────────────────────────────────────────────────────────────
BACKGROUND_MUSIC_ENABLED    = False
BACKGROUND_MUSIC_PATH       = "assets/cinematic.mp3"
BACKGROUND_MUSIC_VOLUME_DB  = 4.0   # subtle — below the narration bed
BACKGROUND_MUSIC_DUCK_RATIO = 20.0

# ─────────────────────────────────────────────────────────────
#  BACKGROUND VISUALS
# ─────────────────────────────────────────────────────────────
# "image"    — photo slideshow per chapter (recommended for book videos)
# "gradient" — animated colour gradient (zero setup, always works)
# "video"    — looping video clips
STORY_BG_MODE = "image"

# Single image used for all narration slides (put book-themed background here)
STORY_BG_IMAGE  = "background/reel_bg.png"

# Multiple images: one per chapter, cycling if fewer than chapters
STORY_BG_IMAGES = []

STORY_BG_VIDEO  = ""
STORY_BG_VIDEOS = []
STORY_BG_DIR    = "background"

# For ebooks: clean, sharp backgrounds — minimal blur, moderate dim for readability.
STORY_BG_BLUR              = 0      # 0 = no blur; raise to 8-12 for heavy bokeh
STORY_BG_DIM               = 0.55   # 0.55 = 45% darker — keeps text readable

STORY_BG_SLIDESHOW_XFADE   = 0.8
STORY_BG_VIDEO_LUMA_KEY    = 0.20
STORY_BG_VIDEO_LUMA_TOL    = 0.12

# ─────────────────────────────────────────────────────────────
#  TYPOGRAPHY & COLOUR
# ─────────────────────────────────────────────────────────────
STORY_SUBTITLE_FONT_SIZE = 72    # body narration text
EBOOK_CHAPTER_FONT_SIZE  = 88    # chapter card title
EBOOK_QUOTE_FONT_SIZE    = 66    # quote callout text
EBOOK_LESSON_FONT_SIZE   = 68    # key lesson text

STORY_TEXT_COLOR      = (255, 255, 255)   # white narration text
STORY_HIGHLIGHT_COLOR = (255, 215, 0)     # gold word highlight — neutral on photos
STORY_STROKE_COLOR    = (0, 0, 0)
STORY_STROKE_WIDTH    = 5

# Chapter card colours
EBOOK_CHAPTER_BG_COLOR      = (10, 10, 30)      # near-black deep-blue card bg
EBOOK_CHAPTER_TEXT_COLOR    = (255, 255, 255)
EBOOK_CHAPTER_ACCENT_COLOR  = (255, 215, 0)     # gold — chapter number / divider
EBOOK_CHAPTER_NUMBER_SIZE   = 48

# Quote callout colours
EBOOK_QUOTE_TEXT_COLOR      = (220, 220, 220)
EBOOK_QUOTE_BAR_COLOR       = (255, 215, 0)     # gold left-bar on quotes
EBOOK_QUOTE_BG_COLOR        = (0, 0, 0)         # semi-transparent black behind quotes
EBOOK_QUOTE_BG_ALPHA        = 160               # 0–255; how opaque the quote box is

# Key Lesson colours
EBOOK_LESSON_TEXT_COLOR     = (255, 240, 100)   # warm yellow — stands out as a lesson
EBOOK_LESSON_BG_COLOR       = (20, 10, 60)
EBOOK_LESSON_BG_ALPHA       = 180

# Progress bar (shows chapter X of N across the top)
EBOOK_PROGRESS_BAR_HEIGHT    = 8     # pixels; 0 to disable
EBOOK_PROGRESS_BAR_COLOR     = (255, 215, 0)
EBOOK_PROGRESS_BAR_BG_COLOR  = (40, 40, 40)

# ─────────────────────────────────────────────────────────────
#  WAVEFORM ANIMATION
# ─────────────────────────────────────────────────────────────
STORY_WAVEFORM_BARS          = 35
STORY_WAVEFORM_HEIGHT_RATIO  = 0.07
STORY_WAVEFORM_COLOR         = (255, 215, 0)   # gold bars — matches highlight
STORY_WAVEFORM_BG_ALPHA      = 60

# ─────────────────────────────────────────────────────────────
#  CHANNEL BADGE
# ─────────────────────────────────────────────────────────────
STORY_CHANNEL_NAME      = "Book Insights"
STORY_LOGO_FONT_SIZE    = 28
STORY_LOGO_BG_COLOR     = (0, 0, 0)
STORY_LOGO_TEXT_COLOR   = (255, 255, 255)

# ─────────────────────────────────────────────────────────────
#  CHAPTER CARD DISPLAY DURATION
# ─────────────────────────────────────────────────────────────
# How long the chapter title card stays on screen (seconds).
# The TTS for the chapter title narration sets a floor; this adds extra hold.
EBOOK_CHAPTER_CARD_MIN_DUR   = 4.0   # minimum seconds on screen
EBOOK_CHAPTER_CARD_EXTRA_DUR = 0.5   # padding after narration finishes

# ─────────────────────────────────────────────────────────────
#  FONT PATHS
# ─────────────────────────────────────────────────────────────
HINDI_FONT_SEARCH_PATHS = [
    "assets/NotoSansDevanagari-Regular.ttf",
    "/Library/Fonts/NotoSansDevanagari-Regular.ttf",
    "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
]

FALLBACK_FONT_SEARCH_PATHS = [
    "assets/fonts/NotoSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]

# ─────────────────────────────────────────────────────────────
#  DIRECTORIES & ENCODING
# ─────────────────────────────────────────────────────────────
OUTPUT_DIR = "output/ebook"
TEMP_DIR   = "temp/ebook"
ASSETS_DIR = "assets"

VIDEO_CODEC   = "libx264"
AUDIO_CODEC   = "aac"
VIDEO_BITRATE = "6000k"     # higher for long-form landscape
AUDIO_BITRATE = "192k"
CRF           = 20

STORY_USE_NEW_RENDERER = True

# ─────────────────────────────────────────────────────────────
#  SENTENCE FADE
# ─────────────────────────────────────────────────────────────
STORY_SENTENCE_FADE = 0.20

EXTRA_PHONETIC_DICT: dict[str, str] = {}


def video_dimensions() -> tuple[int, int]:
    if OUTPUT_MODE == "reel":
        return REEL_WIDTH, REEL_HEIGHT
    return YOUTUBE_WIDTH, YOUTUBE_HEIGHT
