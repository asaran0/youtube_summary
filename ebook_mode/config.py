"""
ebook_mode/config.py — Settings for book summary videos (30-40 min).

Supports English, Hindi, and Hinglish (mixed Hindi/English).
Switch language with a single line:  LANGUAGE = "en" | "hi" | "hig"

Input file format (same for all languages):
─────────────────────────────────────────────────────────────
# Book Title / किताब का नाम
## Author: Robert Kiyosaki
## Tagline: ...

## Chapter 1: Rich Dad, Poor Dad / अध्याय 1: रिच डैड, पुअर डैड
### Key Lesson / मुख्य सीख
Lesson headline here.

Narration text here.

> "A direct quote from the book."
─────────────────────────────────────────────────────────────
"""

import os

MODE_NAME = "ebook"

# ─────────────────────────────────────────────────────────────
#  LANGUAGE — change this one line to switch the whole pipeline
# ─────────────────────────────────────────────────────────────
# "en"  → pure English
# "hi"  → pure Hindi (Devanagari, transliteration applied)
# "hig" → Hinglish — mixed Hindi/English (most natural for Indian YouTube)
LANGUAGE = "hi"

# ─────────────────────────────────────────────────────────────
#  OUTPUT MODE
# ─────────────────────────────────────────────────────────────
# "full" → landscape 1920×1080 for regular YouTube (best for long-form)
# "reel" → vertical 1080×1920 for Shorts / Reels
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

# Slightly slower than natural — book narration needs a measured, considered pace.
# 0.80 = authoritative; raise toward 0.90 for a faster delivery.
KOKORO_SPEED = 0.90

# Voices per language + gender.
# English male  : am_adam (deep/authoritative) | am_michael (warm) | am_onyx (rich)
# English female: af_heart (emotive) | af_bella | af_nicole
# Hindi male    : hm_omega★ | hm_psi
# Hindi female  : hf_alpha★ | hf_beta
_KOKORO_VOICES_BY_GENDER = {
    "male":   {"en": "am_adam",  "hi": "hm_omega", "hig": "hm_omega"},
    "female": {"en": "af_heart", "hi": "hf_alpha",  "hig": "hf_alpha"},
}
KOKORO_VOICES = _KOKORO_VOICES_BY_GENDER.get(EBOOK_VOICE_GENDER,
                _KOKORO_VOICES_BY_GENDER["male"])

_MACOS_VOICES_BY_GENDER = {
    "male":   {"en": "Daniel",  "hi": "Lekha", "hig": "Lekha"},
    "female": {"en": "Samantha","hi": "Lekha", "hig": "Lekha"},
}
MACOS_TTS_VOICES = _MACOS_VOICES_BY_GENDER.get(EBOOK_VOICE_GENDER,
                   _MACOS_VOICES_BY_GENDER["male"])
MACOS_TTS_VOICE  = MACOS_TTS_VOICES.get(LANGUAGE, "Daniel")
MACOS_TTS_RATE   = 120

_XTTS_SAMPLES_BY_GENDER = {
    "male":   "assets/clean_voice_story.wav",
    "female": "assets/clean_voice_story_female.wav",
}
XTTS_VOICE_SAMPLE = _XTTS_SAMPLES_BY_GENDER.get(EBOOK_VOICE_GENDER,
                    _XTTS_SAMPLES_BY_GENDER["male"])
if not os.path.exists(XTTS_VOICE_SAMPLE):
    XTTS_VOICE_SAMPLE = _XTTS_SAMPLES_BY_GENDER["male"]

MMS_TTS_MODEL_IDS = {
    "hi":  "facebook/mms-tts-hin",
    "hig": "facebook/mms-tts-hin",
    "en":  "facebook/mms-tts-eng",
}

# Pacing — generous gaps so the listener can absorb each idea.
TTS_PAUSE_BETWEEN_SEGMENTS    = 0.55
TTS_PAUSE_VARY_BY_PUNCTUATION = True   # longer after ? ! …
TTS_PAUSE_BETWEEN_PHRASES     = 0.30
TTS_ANSWER_PAUSE_EXTRA        = 0.0

# Chapter / lesson / quote breathing room
EBOOK_CHAPTER_PAUSE     = 1.5   # seconds before a new chapter card
EBOOK_LESSON_PAUSE      = 1   # seconds before a key lesson slide
EBOOK_QUOTE_PAUSE_AFTER = 0.5   # seconds after a quote

# ─────────────────────────────────────────────────────────────
#  ON-SCREEN LABEL TRANSLATIONS
#  Labels shown in chapter cards and lesson slides.
#  "auto" picks the right language from LANGUAGE above.
# ─────────────────────────────────────────────────────────────
_LABELS = {
    "en": {
        "chapter_prefix": "CHAPTER",         # "CHAPTER 1"
        "of_chapters":    "of {n} chapters", # "3 of 10 chapters"
        "key_lesson":     "KEY LESSON",
    },
    "hi": {
        "chapter_prefix": "अध्याय",           # "अध्याय 1"
        "of_chapters":    "{n} में से अध्याय", # "10 में से 3 अध्याय"
        "key_lesson":     "मुख्य सीख",
    },
    "hig": {
        "chapter_prefix": "Chapter",
        "of_chapters":    "of {n} chapters",
        "key_lesson":     "Key Lesson",
    },
}

def get_label(key: str, n: int = 0) -> str:
    """Return a localised UI label for the active LANGUAGE."""
    lang   = LANGUAGE if LANGUAGE in _LABELS else "en"
    tmpl   = _LABELS[lang].get(key, _LABELS["en"][key])
    return tmpl.replace("{n}", str(n))

# ─────────────────────────────────────────────────────────────
#  AUDIO POST-PROCESSING
# ─────────────────────────────────────────────────────────────
AUDIO_POST_PROCESSING = True

# Hindi/Hinglish — warmer EQ tuned for Kokoro Hindi voices
_AUDIO_FILTER_HI = (
    "highpass=f=100,"
    "lowpass=f=12000,"
    # Warmth boost — fills out the Hindi vocal midrange
    "equalizer=f=180:width_type=o:width=2:g=2.0,"
    # Consonant clarity (त ध न क)
    "equalizer=f=2500:width_type=o:width=2:g=1.8,"
    # Tame sibilance harshness
    "equalizer=f=6500:width_type=o:width=2:g=-2.5,"
    "acompressor=threshold=-18dB:ratio=2.0:attack=15:release=300:makeup=1.5,"
    "loudnorm=I=-14:TP=-1:LRA=11"
)

# English — standard podcast warmth
_AUDIO_FILTER_EN = (
    "highpass=f=80,"
    "lowpass=f=14000,"
    "equalizer=f=180:width_type=o:width=2:g=1.5,"
    "equalizer=f=3000:width_type=o:width=2:g=1.2,"
    "equalizer=f=7500:width_type=o:width=2:g=-2.0,"
    "acompressor=threshold=-18dB:ratio=2.0:attack=20:release=400:makeup=1.5,"
    "loudnorm=I=-14:TP=-1:LRA=12"
)

AUDIO_FILTER = _AUDIO_FILTER_HI if LANGUAGE in ("hi", "hig") else _AUDIO_FILTER_EN

# ─────────────────────────────────────────────────────────────
#  BACKGROUND MUSIC
# ─────────────────────────────────────────────────────────────
BACKGROUND_MUSIC_ENABLED    = True
BACKGROUND_MUSIC_PATH       = "background/cinematic.mp3"
BACKGROUND_MUSIC_VOLUME_DB  = 2.0
BACKGROUND_MUSIC_DUCK_RATIO = 20.0

# ─────────────────────────────────────────────────────────────
#  BACKGROUND VISUALS
# ─────────────────────────────────────────────────────────────
STORY_BG_MODE   = "image"
# STORY_BG_IMAGE  = "background/reel_bg.png"
STORY_BG_IMAGES = []
STORY_BG_VIDEO  = ""
STORY_BG_VIDEOS = []
STORY_BG_DIR    = "assets/pixabay_cache"

STORY_BG_BLUR = 0
STORY_BG_DIM = 1.0
STORY_BG_SLIDESHOW_XFADE  = 0.8
STORY_BG_VIDEO_LUMA_KEY   = 0.20
STORY_BG_VIDEO_LUMA_TOL   = 0.12

# ─────────────────────────────────────────────────────────────
#  TYPOGRAPHY & COLOUR
# ─────────────────────────────────────────────────────────────
# Font sizes — Hindi Devanagari glyphs are visually larger than Latin at the
# same pixel size, so we use a slightly smaller size for hi/hig.
_IS_HINDI = LANGUAGE in ("hi", "hig")

STORY_SUBTITLE_FONT_SIZE = 66  if _IS_HINDI else 72
EBOOK_CHAPTER_FONT_SIZE  = 78  if _IS_HINDI else 88
EBOOK_QUOTE_FONT_SIZE    = 60  if _IS_HINDI else 66
EBOOK_LESSON_FONT_SIZE   = 62  if _IS_HINDI else 68

STORY_TEXT_COLOR      = (255, 255, 255)
STORY_HIGHLIGHT_COLOR = (255, 215, 0)    # gold — neutral on any photo
STORY_STROKE_COLOR    = (0, 0, 0)
STORY_STROKE_WIDTH    = 5

EBOOK_CHAPTER_BG_COLOR     = (10, 10, 30)
EBOOK_CHAPTER_TEXT_COLOR   = (255, 255, 255)
EBOOK_CHAPTER_ACCENT_COLOR = (255, 215, 0)
EBOOK_CHAPTER_NUMBER_SIZE  = 44 if _IS_HINDI else 48

EBOOK_QUOTE_TEXT_COLOR  = (220, 220, 220)
EBOOK_QUOTE_BAR_COLOR   = (255, 215, 0)
EBOOK_QUOTE_BG_COLOR    = (0, 0, 0)
EBOOK_QUOTE_BG_ALPHA    = 160

EBOOK_LESSON_TEXT_COLOR = (255, 240, 100)
EBOOK_LESSON_BG_COLOR   = (20, 10, 60)
EBOOK_LESSON_BG_ALPHA   = 180

EBOOK_PROGRESS_BAR_HEIGHT   = 8
EBOOK_PROGRESS_BAR_COLOR    = (255, 215, 0)
EBOOK_PROGRESS_BAR_BG_COLOR = (40, 40, 40)

# ─────────────────────────────────────────────────────────────
#  WAVEFORM ANIMATION
# ─────────────────────────────────────────────────────────────
STORY_WAVEFORM_BARS         = 35
STORY_WAVEFORM_HEIGHT_RATIO = 0.07
STORY_WAVEFORM_COLOR        = (255, 215, 0)
STORY_WAVEFORM_BG_ALPHA     = 60

# ─────────────────────────────────────────────────────────────
#  CHANNEL BADGE
# ─────────────────────────────────────────────────────────────
STORY_CHANNEL_NAME   = "Book Insights"
STORY_LOGO_FONT_SIZE = 28
STORY_LOGO_BG_COLOR  = (0, 0, 0)
STORY_LOGO_TEXT_COLOR = (255, 255, 255)

# ─────────────────────────────────────────────────────────────
#  CHAPTER CARD TIMING
# ─────────────────────────────────────────────────────────────
EBOOK_CHAPTER_CARD_MIN_DUR   = 4.0
EBOOK_CHAPTER_CARD_EXTRA_DUR = 0.5

# ─────────────────────────────────────────────────────────────
#  FONT PATHS — Devanagari first for hi/hig, Latin first for en
# ─────────────────────────────────────────────────────────────
HINDI_FONT_SEARCH_PATHS = [
    "assets/NotoSansDevanagari-Regular.ttf",
    "assets/NotoSansDevanagari-Bold.ttf",
    "/Library/Fonts/NotoSansDevanagari-Regular.ttf",
    "/System/Library/Fonts/Kohinoor.ttc",
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
#  PIXABAY IMAGE BACKGROUNDS
#  Set STORY_BG_MODE = "pixabay" to auto-download images that
#  match the story/chapter content from Pixabay.
#
#  Free API key: https://pixabay.com/api/docs/  (500 req/hour)
#
#  How it works:
#    1. Keywords extracted per chapter (ebook) or per story segment.
#    2. Hindi text → English keywords via built-in translation map.
#    3. Images downloaded, resized, cached in PIXABAY_CACHE_DIR.
#    4. Re-runs reuse cached images (no re-download).
#    5. Falls back to gradient if key is missing or network fails.
# ─────────────────────────────────────────────────────────────
PIXABAY_API_KEY          = "8DRN6mB3iaPHTQO6mlPM5d9P2lt9l8l3SKGNVqpcn1wfJ3XvmX1UR23c"        # ← paste your free key here
PIXABAY_IMAGES_PER_QUERY = 3        # images downloaded per chapter/segment
PIXABAY_CACHE_DIR        = "assets/pixabay_cache"
PIXABAY_ORIENTATION      = "horizontal"   # "vertical" for reels
PIXABAY_SAFE_SEARCH      = True
# ─────────────────────────────────────────────────────────────
#  DIRECTORIES & ENCODING
# ─────────────────────────────────────────────────────────────
OUTPUT_DIR    = "output/ebook"
TEMP_DIR      = "temp/ebook"
ASSETS_DIR    = "assets"

VIDEO_CODEC   = "libx264"
AUDIO_CODEC   = "aac"
VIDEO_BITRATE = "6000k"
AUDIO_BITRATE = "192k"
CRF           = 20

STORY_USE_NEW_RENDERER = True
STORY_SENTENCE_FADE    = 0.20

EXTRA_PHONETIC_DICT: dict[str, str] = {}


def video_dimensions() -> tuple[int, int]:
    if OUTPUT_MODE == "reel":
        return REEL_WIDTH, REEL_HEIGHT
    return YOUTUBE_WIDTH, YOUTUBE_HEIGHT
