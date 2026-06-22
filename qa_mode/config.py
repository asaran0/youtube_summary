"""
qa_mode/config.py — Settings specific to Q&A / interview-prep mode.
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

YOUTUBE_WIDTH  = 1920
YOUTUBE_HEIGHT = 1080
REEL_WIDTH     = 1080
REEL_HEIGHT    = 1920
OUTPUT_FPS     = 30

# ─────────────────────────────────────────────────────────────
#  NARRATION / TTS
# ─────────────────────────────────────────────────────────────
TTS_BACKEND = "xtts"

XTTS_VOICE_SAMPLE = "assets/clean_voice.wav"

MACOS_TTS_VOICE = "Samantha"
MACOS_TTS_VOICES = {
    "hi":  "Lekha",
    "hig": "Lekha",
    "en":  "Samantha",
}
MACOS_TTS_RATE = 125

# Gap between question being spoken and answer starting: 1 second
TTS_PAUSE_BETWEEN_SEGMENTS = 0.3
TTS_PAUSE_BETWEEN_PHRASES  = 0.20
TTS_ANSWER_PAUSE_EXTRA     = 1.0   # 1 second pause before answer begins

AUDIO_POST_PROCESSING = True
AUDIO_FILTER = (
    # Remove low rumble while keeping voice warmth (80Hz not 100Hz)
    "highpass=f=80,"
    # Allow full voice presence up to 14kHz
    "lowpass=f=14000,"
    # Slight presence boost at 3kHz for clarity, gentle cut at 7kHz for harshness
    "equalizer=f=3000:width_type=o:width=2:g=1.5,"
    "equalizer=f=7000:width_type=o:width=2:g=-2,"
    # Gentle compressor — lower ratio and makeup to avoid pumping
    "acompressor=threshold=-20dB:ratio=1.8:attack=20:release=300:makeup=1,"
    # Louder target (-14 LUFS) with more dynamic range (LRA=12)
    "loudnorm=I=-14:TP=-1:LRA=12"
)

MMS_TTS_MODEL_IDS = {
    "hi":  "facebook/mms-tts-hin",
    "hig": "facebook/mms-tts-hin",
    "en":  "facebook/mms-tts-eng",
}

EXTRA_PHONETIC_DICT: dict[str, str] = {}

# ─────────────────────────────────────────────────────────────
#  BACKGROUND / SLIDESHOW
# ─────────────────────────────────────────────────────────────
BACKGROUND_IMAGE_PATHS: list[str] = []
BACKGROUND_DIR = "assets/backgrounds_qa"

# ─────────────────────────────────────────────────────────────
#  CONTENT LENGTH
# ─────────────────────────────────────────────────────────────
TARGET_RATIO       = 1.00
KEEP_INTRO_SECONDS = 0
KEEP_OUTRO_SECONDS = 0

# ─────────────────────────────────────────────────────────────
#  Q&A SLIDE STRUCTURE
# ─────────────────────────────────────────────────────────────
QA_SHOW_QUESTION_LABEL       = False          # No "Q 1:" prefix — question is shown as-is
QA_QUESTION_LABEL_TEMPLATE   = "Q{n}: "       # Only used if QA_SHOW_QUESTION_LABEL = True

QA_QUESTION_FONT_SIZE  = round(58 * 1.25)
QA_QUESTION_FONT_COLOR = (255, 200, 40)
QA_ANSWER_FONT_SIZE    = 58
QA_ANSWER_FONT_COLOR   = (255, 255, 255)

# Set to 0 — no "try yourself" pause, no countdown
QA_TRY_YOURSELF_SECONDS   = 0
QA_TRY_YOURSELF_TEXT      = ""
QA_TRY_YOURSELF_FONT_SIZE = 58
QA_TRY_YOURSELF_FONT_COLOR = (255, 255, 255)

QA_COUNTDOWN_SECONDS   = 0
QA_COUNTDOWN_FONT_SIZE = round(58 * 1.6)
QA_COUNTDOWN_FONT_COLOR = (255, 200, 40)

# ─────────────────────────────────────────────────────────────
#  SPLIT-LAYOUT SLIDE SETTINGS  (qa_mode/qa_slideshow.py)
# ─────────────────────────────────────────────────────────────

# Fraction of video height for the QUESTION band (top).
# 0.35 = 35% question / 65% answer
QA_SLIDE_SPLIT_RATIO = 0.35

# Background colours — RGB tuple or "#RRGGBB"
QA_SLIDE_QUESTION_BG    = (205, 139,  97)   # warm peach
QA_SLIDE_ANSWER_BG      = (183, 204, 174)   # sage green

# Text colours
QA_SLIDE_QUESTION_COLOR  = (30,  30,  30)
QA_SLIDE_ANSWER_COLOR    = (30,  30,  30)
# Highlight colour for the word currently being spoken in the answer
QA_SLIDE_HIGHLIGHT_COLOR = (220, 120,  0)   # deep amber — readable on sage green

# Font sizes in pixels
QA_SLIDE_QUESTION_FONT_SIZE = 68
QA_SLIDE_ANSWER_FONT_SIZE   = 50

# Margins as fractions of video dimension
QA_SLIDE_MARGIN_TOP_Q  = 0.04   # gap above question text
QA_SLIDE_MARGIN_BOT_Q  = 0.02
QA_SLIDE_MARGIN_TOP_A  = 0.04   # gap above answer text
QA_SLIDE_MARGIN_BOT_A  = 0.10   # breathing room at bottom (~10%)
QA_SLIDE_MARGIN_SIDE   = 0.05   # left/right margin

# True = new split-layout renderer; False = legacy subtitle overlay
QA_USE_SPLIT_LAYOUT = True

# ─────────────────────────────────────────────────────────────
#  SUBTITLE STYLING
# ─────────────────────────────────────────────────────────────
SUBTITLE_FONT_SIZE        = 58
SUBTITLE_FONT_COLOR       = "white"
SUBTITLE_HIGHLIGHT_COLOR  = (255, 216, 76)
SUBTITLE_POSITION         = "middle"
SUBTITLE_BG_ALPHA         = 0
SUBTITLE_MARGIN_Y         = 80
SUBTITLE_MAX_WIDTH_RATIO  = 0.86

# ─────────────────────────────────────────────────────────────
#  BANNER STYLING (disabled for QA mode)
# ─────────────────────────────────────────────────────────────
BANNER_FONT_SIZE    = 48
BANNER_HEIGHT       = 110
BANNER_BG_COLOR     = (15, 20, 60)
BANNER_BG_ALPHA     = 210
BANNER_TEXT_COLOR   = (255, 220, 50)
BANNER_FADE_FRAMES  = 12
BANNER_HOLD_SECONDS = 3.0
BANNER_ENABLED      = False

# ─────────────────────────────────────────────────────────────
#  FONT PATHS
# ─────────────────────────────────────────────────────────────
HINDI_FONT_SEARCH_PATHS = [
    "assets/NotoSansDevanagari-Regular.ttf",
    # Linux
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
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
]

# ─────────────────────────────────────────────────────────────
#  DIRECTORIES
# ─────────────────────────────────────────────────────────────
OUTPUT_DIR = "output/qa"
TEMP_DIR   = "temp/qa"
ASSETS_DIR = "assets"

# ─────────────────────────────────────────────────────────────
#  FFMPEG
# ─────────────────────────────────────────────────────────────
VIDEO_CODEC    = "libx264"
AUDIO_CODEC    = "aac"
VIDEO_BITRATE  = "4000k"
AUDIO_BITRATE  = "192k"
CRF            = 23


def video_dimensions() -> tuple[int, int]:
    if OUTPUT_MODE == "reel":
        return REEL_WIDTH, REEL_HEIGHT
    return YOUTUBE_WIDTH, YOUTUBE_HEIGHT
