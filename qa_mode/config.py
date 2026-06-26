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
OUTPUT_MODE = "reel"

YOUTUBE_WIDTH  = 1920
YOUTUBE_HEIGHT = 1080
REEL_WIDTH     = 1080
REEL_HEIGHT    = 1920
OUTPUT_FPS     = 30

# ─────────────────────────────────────────────────────────────
#  NARRATION / TTS
# ─────────────────────────────────────────────────────────────
TTS_BACKEND = "kokoro"

XTTS_VOICE_SAMPLE = "assets/clean_voice1.wav"

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
TTS_ANSWER_PAUSE_EXTRA     = 0.0   # no pause before answer begins

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
QA_TRY_YOURSELF_SECONDS   = 0   # keep 0 — no delay before answer
QA_TRY_YOURSELF_TEXT      = ""
QA_TRY_YOURSELF_FONT_SIZE = 58
QA_TRY_YOURSELF_FONT_COLOR = (255, 255, 255)

QA_COUNTDOWN_SECONDS   = 0   # keep 0 — no countdown delay
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

# ── Feature flags & settings ──────────────────────────────────

# 1. PROGRESS BAR — thin bar at very top showing Q index / total
QA_PROGRESS_BAR         = True
QA_PROGRESS_BAR_HEIGHT  = 8           # pixels tall
QA_PROGRESS_BAR_COLOR   = (245, 200, 66)    # filled portion
QA_PROGRESS_BAR_BG      = (80, 80, 80)      # unfilled portion

# 2. QUESTION NUMBER BADGE — "Q 3 / 10" pill in top-right of question band
QA_QUESTION_BADGE       = True
QA_BADGE_TEXT_COLOR     = (255, 255, 255)
QA_BADGE_FONT_SIZE      = 36     # pixels
QA_BADGE_PADDING        = 18     # horizontal padding inside pill
QA_BADGE_MARGIN         = 20     # margin from right/top edge

# 3. DIVIDER LINE between question and answer bands
QA_DIVIDER              = True
QA_DIVIDER_COLOR        = (255, 255, 255)
QA_DIVIDER_HEIGHT       = 4      # pixels thick
QA_DIVIDER_ALPHA        = 80     # 0-255 opacity

# 4. SENTENCE-BY-SENTENCE reveal instead of word-by-word
#    True  = reveal one full sentence at a time (smoother)
#    False = original word-by-word reveal
QA_SENTENCE_REVEAL      = False    # word-by-word (smoother than sentence)

# 4b. POST-ANSWER HOLD — seconds to display full answer before next question
QA_POST_ANSWER_HOLD     = 1.0

# 5. FADE TRANSITION between question->answer and between questions
#    Duration in seconds (0 = no fade)
QA_FADE_DURATION        = 0.35

# 6. WATERMARK — text shown in bottom-right corner of every frame
QA_WATERMARK            = True
QA_WATERMARK_TEXT       = "@ai.interview.guru1"
QA_WATERMARK_COLOR      = (255, 255, 255)
QA_WATERMARK_ALPHA      = 90     # 0-255 opacity
QA_WATERMARK_FONT_SIZE  = 32     # pixels

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


# ── Question number label ─────────────────────────────────────────────────────
QA_QNUM_FONT_SIZE      = 28          # font size for "Question 1" label above question text

# ── Bottom-of-question-band progress bar ─────────────────────────────────────
QA_BOT_PROGRESS        = True        # show answer-spoken progress bar at bottom of Q band
QA_BOT_PROGRESS_HEIGHT = 6           # height in pixels
QA_BOT_PROGRESS_COLOR  = (245, 200, 66)   # filled portion colour
QA_BOT_PROGRESS_BG     = (60, 60, 60)     # unfilled portion colour

# ── Subscribe crawl overlay (slides in during last N seconds) ─────────────────
QA_SUBSCRIBE_SECS      = 7.0         # show in last N seconds of video
QA_SUBSCRIBE_TEXT      = "Subscribe for Upcoming Q&A Sessions!"
QA_SUBSCRIBE_STYLE     = "pill"      # "pill" | "banner" | "neon" | "ghost"
QA_SUBSCRIBE_ACCENT    = (245, 200, 66)
QA_SUBSCRIBE_BG        = (15, 15, 30)

# ── End-of-video empty-space smooth transition ───────────────────────────────
QA_TRANSITION_FADE_IN_AT  = 10.0   # seconds before end: overlay starts fading in
QA_TRANSITION_FADE_OUT_AT =  3.0   # seconds before end: overlay starts fading out
QA_TRANSITION_OPACITY     =  0.55  # peak opacity (0.0–1.0)

# ── Hook crawl overlay (appears at the start, or any custom time) ─────────────
# Set QA_HOOK_TEXT to a non-empty string to enable. Leave empty to disable.
QA_HOOK_TEXT           = ""          # e.g. "3 things every Java dev must know"
QA_HOOK_SUBTEXT        = ""          # smaller line below hook text
QA_HOOK_START          = 0.0        # seconds from video start
QA_HOOK_DURATION       = 4.0        # how long the hook stays on screen
QA_HOOK_Y_FRAC         = 0.10       # vertical position: 0.0=top, 1.0=bottom
QA_HOOK_STYLE          = "neon"     # "pill" | "banner" | "neon" | "ghost"
QA_HOOK_ACCENT         = (80, 200, 255)


def video_dimensions() -> tuple[int, int]:
    if OUTPUT_MODE == "reel":
        return REEL_WIDTH, REEL_HEIGHT
    return YOUTUBE_WIDTH, YOUTUBE_HEIGHT
