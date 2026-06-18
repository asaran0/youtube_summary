"""
config.py — All project settings in one place.
Edit this file to customize the summarizer behaviour.
"""

import os

# ─────────────────────────────────────────────────────────────
#  WHISPER  (transcription model)
# ─────────────────────────────────────────────────────────────
# Options (small → large = faster → better quality):
#   "tiny"     – fastest, lowest quality
#   "base"     – fast, decent quality
#   "small"    – good balance
#   "medium"   – recommended for M1 8 GB  ← default
#   "large-v3" – best quality, ~3 GB RAM, slower
WHISPER_MODEL = "medium"

# Output language. Supported values: "hi" and "en".
# "hi" transcribes Hindi. "en" uses Whisper translate mode for English output.
# LANGUAGE = "hi"
LANGUAGE = "en"

# ─────────────────────────────────────────────────────────────
#  NARRATION / TTS
# ─────────────────────────────────────────────────────────────
# "macos" supports configurable installed system voices.
# "mms" is neural/offline after model download, but has one voice per language.
TTS_BACKEND = "macos"
# MACOS_TTS_VOICE = "Lekha"       # Hindi: Lekha. English examples: Samantha, Daniel
MACOS_TTS_VOICE = "Daniel"       # Hindi: Lekha. English examples: Samantha, Daniel
MACOS_TTS_VOICES = {
    "hi": "Lekha",
    "en": "Samantha",
}
MACOS_TTS_RATE = 125            # slightly slower = clearer pronunciation
TTS_PAUSE_BETWEEN_SEGMENTS = 0.75   # slightly longer pause = more natural
TTS_ANSWER_PAUSE_EXTRA = 0.6        # extra pause before an answer in Q&A mode
TTS_PAUSE_BETWEEN_PHRASES = 0.30
AUDIO_POST_PROCESSING = True
AUDIO_FILTER = (
    # Remove very low rumble below 100 Hz (mic noise, hum)
    "highpass=f=100,"
    # Gentle high-frequency roll-off — Lekha sounds harsh above 10 kHz
    "lowpass=f=10000,"
    # De-ess: tame sibilance (स, श, च sounds that can sound sharp)
    "equalizer=f=7000:width_type=o:width=2:g=-3,"
    # Light compression: keeps loud and quiet parts balanced
    "acompressor=threshold=-16dB:ratio=2.5:attack=10:release=150:makeup=2,"
    # Loudness normalisation to broadcast standard (-16 LUFS)
    "loudnorm=I=-16:TP=-1.5:LRA=9"
)

MMS_TTS_MODEL_IDS = {
    "hi": "facebook/mms-tts-hin",
    "en": "facebook/mms-tts-eng",
}

# ─────────────────────────────────────────────────────────────
#  VIDEO SOURCE / BACKGROUND
# ─────────────────────────────────────────────────────────────
# Default creates a new slideshow video instead of reusing YouTube frames.
VIDEO_STYLE = "slideshow"       # "slideshow" (recommended) or "source"
DOWNLOAD_SOURCE_VIDEO = False   # audio-only is faster for slideshow mode
OUTPUT_FORMAT = "reel"          # "auto", "youtube", or "reel"

# Put one or more copyright-safe images here, or a folder in BACKGROUND_DIR.
# If empty, the app generates simple original image backgrounds.
BACKGROUND_IMAGE_PATHS = []
BACKGROUND_DIR = "assets/backgrounds"
SLIDE_SECONDS_MIN = 3.0
SLIDE_SECONDS_MAX = 9.0
SLIDE_TITLE_MAX_WORDS = 9

# ─────────────────────────────────────────────────────────────
#  SUMMARY LENGTH
# ─────────────────────────────────────────────────────────────
# What fraction of the original video to keep (0.70–0.80)
TARGET_RATIO = 1.00   # 75 %

# Keep first/last N seconds of the video always (intro/outro)
KEEP_INTRO_SECONDS = 10
KEEP_OUTRO_SECONDS = 10

# ─────────────────────────────────────────────────────────────
#  VIDEO DIMENSIONS
# ─────────────────────────────────────────────────────────────
YOUTUBE_WIDTH  = 1920
YOUTUBE_HEIGHT = 1080

REEL_WIDTH  = 1080
REEL_HEIGHT = 1920

# Frame rate of output video
OUTPUT_FPS = 30

# ─────────────────────────────────────────────────────────────
#  SUBTITLE STYLING
# ─────────────────────────────────────────────────────────────
SUBTITLE_FONT_SIZE   = 58          # px – large readable subtitles (was 42)
SUBTITLE_FONT_COLOR  = "white"
SUBTITLE_HIGHLIGHT_COLOR = (255, 216, 76)
SUBTITLE_POSITION    = "middle"    # "middle" or "bottom"
SUBTITLE_BG_ALPHA    = 0           # 0 removes the black subtitle box
SUBTITLE_MARGIN_Y    = 80          # px from bottom of frame

# SUBTITLE_MAX_CHARS scales with font size automatically, so .srt/.ass
# exports wrap at roughly the same visual width no matter the font size.
# (Baseline: 42 chars looked right at 42px font → ~1764 px-chars budget.)
_SUBTITLE_CHAR_PIXEL_BUDGET = 42 * 42
SUBTITLE_MAX_CHARS = max(12, round(_SUBTITLE_CHAR_PIXEL_BUDGET / SUBTITLE_FONT_SIZE))

SUBTITLE_MAX_WIDTH_RATIO = 0.86    # actual burned-in text wraps to this
                                    # fraction of screen width — already
                                    # font-size independent, no change needed

# ─────────────────────────────────────────────────────────────
#  Q&A / INTERVIEW MODE STYLING
# ─────────────────────────────────────────────────────────────
QA_SHOW_QUESTION_LABEL = True       # show "प्रश्न 1: ..." prefix on screen
QA_QUESTION_LABEL_TEMPLATE = "प्रश्न {n}: "   # {n} = question number, 1-based

QA_QUESTION_FONT_SIZE = round(SUBTITLE_FONT_SIZE * 1.25)   # bigger than answer
QA_QUESTION_FONT_COLOR = (255, 200, 40)    # yellow/gold (R, G, B)
QA_ANSWER_FONT_SIZE   = SUBTITLE_FONT_SIZE
QA_ANSWER_FONT_COLOR  = (255, 255, 255)    # white, same as normal subtitles

# Silent "try it yourself" prompt — shown right after the question,
# before the countdown. Nothing is spoken during this slide.
QA_TRY_YOURSELF_SECONDS = 2
QA_TRY_YOURSELF_TEXT = "रुकिए और पहले खुद उत्तर देने की कोशिश करें"
QA_TRY_YOURSELF_FONT_SIZE = SUBTITLE_FONT_SIZE
QA_TRY_YOURSELF_FONT_COLOR = (255, 255, 255)   # white

QA_COUNTDOWN_SECONDS  = 3           # pause length before answer starts
QA_COUNTDOWN_FONT_SIZE = round(SUBTITLE_FONT_SIZE * 1.6)
QA_COUNTDOWN_FONT_COLOR = (255, 200, 40)   # matches question color

# ─────────────────────────────────────────────────────────────
#  STORYTELLING SCRIPT STYLE
# ─────────────────────────────────────────────────────────────
STORYTELLING_MODE = True
STORYTELLING_ADD_INTRO = True
STORYTELLING_ADD_TRANSITIONS = True
STORYTELLING_MAX_TRANSITIONS = 8

# ─────────────────────────────────────────────────────────────
#  BANNER STYLING
# ─────────────────────────────────────────────────────────────
BANNER_FONT_SIZE    = 48
BANNER_HEIGHT       = 110          # px
BANNER_BG_COLOR     = (15, 20, 60) # dark-navy RGB
BANNER_BG_ALPHA     = 210
BANNER_TEXT_COLOR   = (255, 220, 50)  # golden yellow
BANNER_FADE_FRAMES  = 12           # frames for fade-in / fade-out
BANNER_HOLD_SECONDS = 3.0          # seconds to show banner at full opacity

# Show a banner at the start of every new topic group
BANNER_ENABLED = True

# ─────────────────────────────────────────────────────────────
#  FONT PATHS (Devanagari / Hindi support)
# ─────────────────────────────────────────────────────────────
# Priority order – first existing path is used
HINDI_FONT_SEARCH_PATHS = [
    "assets/NotoSansDevanagari-Regular.ttf",          # bundled (setup.sh downloads this)
    "/Library/Fonts/NotoSansDevanagari-Regular.ttf",
    "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc",
    "/System/Library/Fonts/Kohinoor.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
]

FALLBACK_FONT_SEARCH_PATHS = [
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]

# ─────────────────────────────────────────────────────────────
#  DIRECTORIES
# ─────────────────────────────────────────────────────────────
OUTPUT_DIR = "output"    # final files go here
TEMP_DIR   = "temp"      # intermediate files (auto-cleaned)
ASSETS_DIR = "assets"    # fonts, images, etc.

# ─────────────────────────────────────────────────────────────
#  FFMPEG  (video encoding)
# ─────────────────────────────────────────────────────────────
VIDEO_CODEC   = "libx264"
AUDIO_CODEC   = "aac"
VIDEO_BITRATE = "4000k"   # raise for higher quality (larger file)
AUDIO_BITRATE = "192k"
CRF           = 23        # 0=lossless, 23=default, 28=smaller file

# ─────────────────────────────────────────────────────────────
#  SCORING WEIGHTS  (used by summarizer.py)
# ─────────────────────────────────────────────────────────────
WEIGHT_WORD_FREQ   = 0.40  # TF-IDF information density
WEIGHT_CONFIDENCE  = 0.25  # Whisper model confidence
WEIGHT_POSITION    = 0.15  # bonus for intro / outro segments
WEIGHT_COMPLETENESS= 0.20  # bonus for sentences ending with punctuation