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
LANGUAGE = "hi"

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

MACOS_TTS_VOICE = "Lekha"
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

QA_TRY_YOURSELF_SECONDS = 2
QA_TRY_YOURSELF_TEXT = "रुकिए और पहले खुद उत्तर देने की कोशिश करें"
QA_TRY_YOURSELF_FONT_SIZE = 58
QA_TRY_YOURSELF_FONT_COLOR = (255, 255, 255)

QA_COUNTDOWN_SECONDS = 3
QA_COUNTDOWN_FONT_SIZE = round(58 * 1.6)
QA_COUNTDOWN_FONT_COLOR = (255, 200, 40)    # gold

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


def video_dimensions() -> tuple[int, int]:
    """Resolve (width, height) from OUTPUT_MODE."""
    if OUTPUT_MODE == "reel":
        return REEL_WIDTH, REEL_HEIGHT
    return YOUTUBE_WIDTH, YOUTUBE_HEIGHT
