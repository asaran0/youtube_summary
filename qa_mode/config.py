"""
qa_mode/config.py — Settings specific to Q&A / interview-prep mode.

QA mode never shortens content (every question and answer is always
kept) and has its own TTS backend choice, pacing, and subtitle styling
— independently tunable from story_mode.
"""

MODE_NAME = "qa"

# ─────────────────────────────────────────────────────────────
#  LANGUAGE
# ─────────────────────────────────────────────────────────────
LANGUAGE = "en"

# ─────────────────────────────────────────────────────────────
#  OUTPUT MODE — reel (short, vertical) or full (long, landscape)
# ─────────────────────────────────────────────────────────────
OUTPUT_MODE = "full"

YOUTUBE_WIDTH = 1920
YOUTUBE_HEIGHT = 1080
REEL_WIDTH = 1080
REEL_HEIGHT = 1920
OUTPUT_FPS = 30

# ─────────────────────────────────────────────────────────────
#  NARRATION / TTS  — qa mode's own backend choice
# ─────────────────────────────────────────────────────────────
TTS_BACKEND = "macos"

XTTS_VOICE_SAMPLE = "assets/my_voice_sample.wav"

MACOS_TTS_VOICE = "Samantha"
MACOS_TTS_VOICES = {
    "hi": "Lekha",
    "hig": "Lekha",
    "en": "Samantha",
}
MACOS_TTS_RATE = 125
TTS_PAUSE_BETWEEN_SEGMENTS = 0.75
TTS_PAUSE_BETWEEN_PHRASES = 0.30
TTS_ANSWER_PAUSE_EXTRA = 0.6   # extra pause before an answer starts

AUDIO_POST_PROCESSING = True
AUDIO_FILTER = (
    "highpass=f=100,"
    "lowpass=f=10000,"
    "equalizer=f=7000:width_type=o:width=2:g=-3,"
    "acompressor=threshold=-16dB:ratio=2.5:attack=10:release=150:makeup=2,"
    "loudnorm=I=-16:TP=-1.5:LRA=9"
)

MMS_TTS_MODEL_IDS = {
    "hi": "facebook/mms-tts-hin",
    "hig": "facebook/mms-tts-hin",
    "en": "facebook/mms-tts-eng",
}

# Mode-specific extra phonetic dictionary — interview/technical terms
# checked before the shared core/lang/dictionary.py. Add domain terms
# here (e.g. for a different subject's interview prep) without
# touching the shared dictionary.
EXTRA_PHONETIC_DICT: dict[str, str] = {}

# ─────────────────────────────────────────────────────────────
#  BACKGROUND / SLIDESHOW
# ─────────────────────────────────────────────────────────────
BACKGROUND_IMAGE_PATHS: list[str] = []
BACKGROUND_DIR = "assets/backgrounds_qa"

# ─────────────────────────────────────────────────────────────
#  CONTENT LENGTH — QA mode always keeps every question and answer
# ─────────────────────────────────────────────────────────────
TARGET_RATIO = 1.00
KEEP_INTRO_SECONDS = 0
KEEP_OUTRO_SECONDS = 0

# ─────────────────────────────────────────────────────────────
#  Q&A SLIDE STRUCTURE
# ─────────────────────────────────────────────────────────────
QA_SHOW_QUESTION_LABEL = True
QA_QUESTION_LABEL_TEMPLATE = "प्रश्न {n}: "

QA_QUESTION_FONT_SIZE = round(58 * 1.25)
QA_QUESTION_FONT_COLOR = (255, 200, 40)     # gold
QA_ANSWER_FONT_SIZE = 58
QA_ANSWER_FONT_COLOR = (255, 255, 255)      # white

QA_TRY_YOURSELF_SECONDS = 0
QA_TRY_YOURSELF_TEXT = "रुकिए और पहले खुद उत्तर देने की कोशिश करें"
QA_TRY_YOURSELF_FONT_SIZE = 58
QA_TRY_YOURSELF_FONT_COLOR = (255, 255, 255)

QA_COUNTDOWN_SECONDS = 0
QA_COUNTDOWN_FONT_SIZE = round(58 * 1.6)
QA_COUNTDOWN_FONT_COLOR = (255, 200, 40)    # gold

# ─────────────────────────────────────────────────────────────
#  SPLIT-LAYOUT SLIDE SETTINGS
#  (used by qa_mode/qa_slideshow.py — the new split-panel renderer)
# ─────────────────────────────────────────────────────────────

# Fraction of video height occupied by the QUESTION band (top section).
# 0.35 = 35% question / 65% answer. Range: 0.2 – 0.6.
QA_SLIDE_SPLIT_RATIO = 0.35

# Background fill colours for each band. RGB tuple or "#RRGGBB" hex.
QA_SLIDE_QUESTION_BG  = (205, 139,  97)   # warm peach / terracotta
QA_SLIDE_ANSWER_BG    = (183, 204, 174)   # sage green

# Text colours
QA_SLIDE_QUESTION_COLOR = (30,  30,  30)   # near-black (readable on peach)
QA_SLIDE_ANSWER_COLOR   = (30,  30,  30)   # near-black (readable on sage)

# Font sizes (pixels) for question and answer text inside the slide image.
# These are independent of the subtitle overlay sizes above.
QA_SLIDE_QUESTION_FONT_SIZE = 72    # bold-looking at 1080p
QA_SLIDE_ANSWER_FONT_SIZE   = 52

# Margins expressed as fractions of the video dimension they refer to.
# e.g. QA_SLIDE_MARGIN_TOP_Q = 0.04 → 4% of video height above question text.
QA_SLIDE_MARGIN_TOP_Q  = 0.04   # top gap inside question band
QA_SLIDE_MARGIN_BOT_Q  = 0.02   # bottom gap inside question band
QA_SLIDE_MARGIN_TOP_A  = 0.04   # top gap inside answer band
QA_SLIDE_MARGIN_BOT_A  = 0.10   # bottom gap inside answer band (~10% breathing room)
QA_SLIDE_MARGIN_SIDE   = 0.05   # left/right margin (fraction of video width)

# Whether to use the new split-layout renderer (True) or the legacy
# subtitle-overlay approach (False).
QA_USE_SPLIT_LAYOUT = True

# ─────────────────────────────────────────────────────────────
#  SUBTITLE STYLING (defaults — question/answer/countdown styles
#  above take precedence per-line via qa_mode/styles.py)
# ─────────────────────────────────────────────────────────────
SUBTITLE_FONT_SIZE = 58
SUBTITLE_FONT_COLOR = "white"
SUBTITLE_HIGHLIGHT_COLOR = (255, 216, 76)
SUBTITLE_POSITION = "middle"
SUBTITLE_BG_ALPHA = 0
SUBTITLE_MARGIN_Y = 80
SUBTITLE_MAX_WIDTH_RATIO = 0.86

# ─────────────────────────────────────────────────────────────
#  BANNER STYLING — disabled by default for QA mode (no topic groups)
# ─────────────────────────────────────────────────────────────
BANNER_FONT_SIZE = 48
BANNER_HEIGHT = 110
BANNER_BG_COLOR = (15, 20, 60)
BANNER_BG_ALPHA = 210
BANNER_TEXT_COLOR = (255, 220, 50)
BANNER_FADE_FRAMES = 12
BANNER_HOLD_SECONDS = 3.0
BANNER_ENABLED = False

# ─────────────────────────────────────────────────────────────
#  FONT PATHS (Devanagari / Hindi support)
# ─────────────────────────────────────────────────────────────
HINDI_FONT_SEARCH_PATHS = [
    "assets/NotoSansDevanagari-Regular.ttf",
    # Linux — FreeSerif has solid Devanagari coverage
    "/usr/share/fonts/truetype/freefont/FreeSerif.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
    "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
    # macOS
    "/Library/Fonts/NotoSansDevanagari-Regular.ttf",
    "/System/Library/Fonts/Supplemental/ITFDevanagari.ttc",
    "/System/Library/Fonts/Kohinoor.ttc",
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
OUTPUT_DIR = "output/qa"
TEMP_DIR = "temp/qa"
ASSETS_DIR = "assets"

# ─────────────────────────────────────────────────────────────
#  FFMPEG (video encoding)
# ─────────────────────────────────────────────────────────────
VIDEO_CODEC = "libx264"
AUDIO_CODEC = "aac"
VIDEO_BITRATE = "4000k"
AUDIO_BITRATE = "192k"
CRF = 23
TTS_PAUSE_BETWEEN_SEGMENTS = 1.0   # answer starts ~1s after question
TTS_PAUSE_BETWEEN_PHRASES = 0.20


def video_dimensions() -> tuple[int, int]:
    """Resolve (width, height) from OUTPUT_MODE."""
    if OUTPUT_MODE == "reel":
        return REEL_WIDTH, REEL_HEIGHT
    return YOUTUBE_WIDTH, YOUTUBE_HEIGHT
