"""
story_mode/config.py — Settings specific to story mode.

Story mode reads a plain-text story file, optionally shortens it
(TARGET_RATIO), narrates it with its own TTS backend choice, and
renders it as a slideshow — independently tunable from qa_mode.
"""

import os

MODE_NAME = "story"

# ─────────────────────────────────────────────────────────────
#  LANGUAGE
# ─────────────────────────────────────────────────────────────
# "hi"  pure Hindi (English loanwords/acronyms transliterated)
# "en"  pure English (no transliteration)
# "hig" Hinglish — mixed Hindi/English, same transliteration as "hi"
LANGUAGE = "hi"

# ─────────────────────────────────────────────────────────────
#  OUTPUT MODE — reel (short, vertical) or full (long, landscape)
# ─────────────────────────────────────────────────────────────
# "reel" -> vertical 1080x1920, for Shorts/Reels
# "full" -> landscape 1920x1080, for regular YouTube videos
OUTPUT_MODE = "reel"

YOUTUBE_WIDTH = 1920
YOUTUBE_HEIGHT = 1080
REEL_WIDTH = 1080
REEL_HEIGHT = 1920
OUTPUT_FPS = 30

# ─────────────────────────────────────────────────────────────
#  NARRATION / TTS  — story mode's own backend choice
# ─────────────────────────────────────────────────────────────
# "xtts"  clones your own voice from a sample WAV — best realism, offline.
# "mms"   neural/offline after model download, one fixed voice.
# "macos" configurable installed system voices, zero setup.
TTS_BACKEND = "kokoro"

# ── Kokoro TTS settings for story mode ───────────────────────────────────────
# Slower speed makes narration feel more emotional and human.
# 0.82 = ~18% slower than natural — warm storytelling pace.
KOKORO_SPEED = 0.82

# Voice selection — change to switch gender or style.
# English male options : am_adam (deep) | am_michael (warm) | am_onyx (rich)
# English female opts  : af_heart (emotive★) | af_bella | af_nicole
# British male         : bm_george | bm_lewis
# Hindi male           : hm_omega★ | hm_psi
# Hindi female         : hf_alpha★ | hf_beta
KOKORO_VOICES = {
    "en":  "am_adam",    # ← deep male English narrator (change to "af_heart" for female)
    "hi":  "hm_omega",   # ← Hindi male narrator       (change to "hf_alpha" for female)
    "hig": "hm_omega",
}

# Sentence fade-in/out duration in seconds
STORY_SENTENCE_FADE = 0.22

XTTS_VOICE_SAMPLE = "assets/clean_voice_story.wav"

MACOS_TTS_VOICE = "Lekha"
MACOS_TTS_VOICES = {
    "hi": "Lekha",
    "hig": "Lekha",
    "en": "Samantha",
}
MACOS_TTS_RATE = 125
TTS_PAUSE_BETWEEN_SEGMENTS = 0.75
TTS_PAUSE_BETWEEN_PHRASES = 0.30
TTS_ANSWER_PAUSE_EXTRA = 0.0   # story mode has no Q&A pacing concept

AUDIO_POST_PROCESSING = True
AUDIO_FILTER = (
    # Remove subsonic rumble; 100Hz keeps XTTS Hindi voice warmth
    "highpass=f=100,"
    # Cap at 12kHz — XTTS Hindi doesn't add useful content above this
    "lowpass=f=12000,"
    # +2dB at 2kHz: sharpens Hindi consonant clarity (त, द, न, क etc.)
    "equalizer=f=2000:width_type=o:width=2:g=2.0,"
    # -2.5dB at 6kHz: tames sibilance harshness common in XTTS Hindi
    "equalizer=f=6000:width_type=o:width=2:g=-2.5,"
    # Light compressor — XTTS already has decent dynamics; just even it out
    "acompressor=threshold=-18dB:ratio=2.0:attack=15:release=250:makeup=1.5,"
    # -14 LUFS target: standard for YouTube narration
    "loudnorm=I=-14:TP=-1:LRA=11"
)

MMS_TTS_MODEL_IDS = {
    "hi": "facebook/mms-tts-hin",
    "hig": "facebook/mms-tts-hin",
    "en": "facebook/mms-tts-eng",
}

# Mode-specific extra phonetic dictionary entries — checked before the
# shared core/lang/dictionary.py, so story mode can override or add
# words without touching shared data. Empty by default.
EXTRA_PHONETIC_DICT: dict[str, str] = {}

# ─────────────────────────────────────────────────────────────
#  BACKGROUND / SLIDESHOW
# ─────────────────────────────────────────────────────────────
BACKGROUND_IMAGE_PATHS: list[str] = []
BACKGROUND_DIR = "background"

# ─────────────────────────────────────────────────────────────
#  SUMMARY LENGTH — story mode can shorten content; qa mode never does
# ─────────────────────────────────────────────────────────────
TARGET_RATIO = 1.00            # 1.00 = keep everything, no shortening
KEEP_INTRO_SECONDS = 10
KEEP_OUTRO_SECONDS = 10

WEIGHT_WORD_FREQ = 0.40
WEIGHT_CONFIDENCE = 0.25
WEIGHT_POSITION = 0.15
WEIGHT_COMPLETENESS = 0.20

# ─────────────────────────────────────────────────────────────
#  STORYTELLING SCRIPT STYLE
# ─────────────────────────────────────────────────────────────
STORYTELLING_MODE = False
STORYTELLING_ADD_INTRO = True
STORYTELLING_ADD_TRANSITIONS = True
STORYTELLING_MAX_TRANSITIONS = 8

# ─────────────────────────────────────────────────────────────
#  SUBTITLE STYLING
# ─────────────────────────────────────────────────────────────
SUBTITLE_FONT_SIZE = 58
SUBTITLE_FONT_COLOR = "white"
SUBTITLE_HIGHLIGHT_COLOR = (255, 216, 76)
SUBTITLE_POSITION = "middle"
SUBTITLE_BG_ALPHA = 0
SUBTITLE_MARGIN_Y = 80
SUBTITLE_MAX_WIDTH_RATIO = 0.86

# ─────────────────────────────────────────────────────────────
#  BANNER STYLING
# ─────────────────────────────────────────────────────────────
BANNER_FONT_SIZE = 48
BANNER_HEIGHT = 110
BANNER_BG_COLOR = (15, 20, 60)
BANNER_BG_ALPHA = 210
BANNER_TEXT_COLOR = (255, 220, 50)
BANNER_FADE_FRAMES = 12
BANNER_HOLD_SECONDS = 3.0
BANNER_ENABLED = True

# ─────────────────────────────────────────────────────────────
#  FONT PATHS (Devanagari / Hindi support)
# ─────────────────────────────────────────────────────────────
HINDI_FONT_SEARCH_PATHS = [
    "assets/NotoSansDevanagari-Regular.ttf",
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
OUTPUT_DIR = "output/story"
TEMP_DIR = "temp/story"
ASSETS_DIR = "assets"

# ─────────────────────────────────────────────────────────────
#  FFMPEG (video encoding)
# ─────────────────────────────────────────────────────────────
VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"
VIDEO_BITRATE = "4000k"
AUDIO_BITRATE = "192k"
CRF = 23


def video_dimensions() -> tuple[int, int]:
    """Resolve (width, height) from OUTPUT_MODE."""
    if OUTPUT_MODE == "reel":
        return REEL_WIDTH, REEL_HEIGHT
    return YOUTUBE_WIDTH, YOUTUBE_HEIGHT

# ─────────────────────────────────────────────────────────────
#  STORY VIDEO VISUAL SETTINGS  (story_mode/story_render.py)
# ─────────────────────────────────────────────────────────────

# ── Background ───────────────────────────────────────────────
# Set to a video file path to use as looping background.
# Leave empty ("") to use animated gradient backgrounds (default).
STORY_BG_VIDEO = ""

# ── Subtitle text ────────────────────────────────────────────
# Large bold text shown word-by-word in the centre of the screen.
STORY_SUBTITLE_FONT_SIZE = 95       # pixels — big and punchy
STORY_TEXT_COLOR         = (255, 255, 255)   # white body text
STORY_HIGHLIGHT_COLOR    = (100, 255, 80)    # green highlight (YouTube style)
STORY_STROKE_COLOR       = (0, 0, 0)         # black outline
STORY_STROKE_WIDTH       = 6                 # outline thickness in pixels

# ── Channel logo badge (top-right corner) ────────────────────
# Set STORY_CHANNEL_NAME to your channel name to show a pill badge.
# Leave empty ("") to hide the badge entirely.
STORY_CHANNEL_NAME       = "Ai Interview Guru"   # ← change to your channel name
STORY_LOGO_FONT_SIZE     = 30
STORY_LOGO_BG_COLOR      = (0, 0, 0)         # badge background (RGB)
STORY_LOGO_TEXT_COLOR    = (255, 255, 255)   # badge text colour

# ── Waveform animation (bottom centre) ───────────────────────
STORY_WAVEFORM_BARS         = 40    # number of animated bars
STORY_WAVEFORM_HEIGHT_RATIO = 0.09  # fraction of video height
STORY_WAVEFORM_COLOR        = None  # None = use palette accent colour
STORY_WAVEFORM_BG_ALPHA     = 70    # strip transparency (0=invisible, 255=solid)

# Use new story renderer instead of legacy subtitle-overlay approach
STORY_USE_NEW_RENDERER   = True
