"""
utils.py — Shared helper functions used across all modules.
"""

import os
import sys
import logging
import subprocess
from pathlib import Path

import config


# ─────────────────────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────────────────────

def get_logger(name: str) -> logging.Logger:
    """Return a named logger with a human-friendly format."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s  [%(levelname)s]  %(name)s — %(message)s",
                              datefmt="%H:%M:%S")
        )
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


# ─────────────────────────────────────────────────────────────
#  DIRECTORIES
# ─────────────────────────────────────────────────────────────

def ensure_dirs(*paths: str) -> None:
    """Create directories if they don't exist."""
    for p in paths:
        Path(p).mkdir(parents=True, exist_ok=True)


def clean_temp() -> None:
    """Remove all files inside the temp directory."""
    import shutil
    if os.path.exists(config.TEMP_DIR):
        shutil.rmtree(config.TEMP_DIR)
    Path(config.TEMP_DIR).mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────
#  TIME FORMATTING
# ─────────────────────────────────────────────────────────────

def seconds_to_srt(seconds: float) -> str:
    """Convert float seconds → SRT timestamp string HH:MM:SS,mmm."""
    h   = int(seconds // 3600)
    m   = int((seconds % 3600) // 60)
    s   = int(seconds % 60)
    ms  = int(round((seconds - int(seconds)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def seconds_to_ass(seconds: float) -> str:
    """Convert float seconds → ASS timestamp string H:MM:SS.cc"""
    h  = int(seconds // 3600)
    m  = int((seconds % 3600) // 60)
    s  = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))   # centiseconds
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def human_duration(seconds: float) -> str:
    """Return a readable duration like '4m 32s'."""
    m = int(seconds // 60)
    s = int(seconds % 60)
    if m == 0:
        return f"{s}s"
    return f"{m}m {s}s"


# ─────────────────────────────────────────────────────────────
#  FFPROBE HELPERS
# ─────────────────────────────────────────────────────────────

def get_video_duration(filepath: str) -> float:
    """Return duration of a video/audio file in seconds."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        filepath,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(result.stdout.strip())


def get_video_dimensions(filepath: str) -> tuple[int, int]:
    """Return (width, height) of a video file."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=s=x:p=0",
        filepath,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    w, h = result.stdout.strip().split("x")
    return int(w), int(h)


def is_reel_format(filepath: str) -> bool:
    """Return True if the video is portrait / reel format (taller than wide)."""
    w, h = get_video_dimensions(filepath)
    return h > w


# ─────────────────────────────────────────────────────────────
#  FONT DETECTION
# ─────────────────────────────────────────────────────────────

def find_hindi_font() -> str:
    """
    Find a font file that supports Devanagari / Hindi script.
    Searches the paths listed in config.HINDI_FONT_SEARCH_PATHS.
    Downloads Noto Sans Devanagari as a fallback.
    """
    log = get_logger("font")

    for path in config.HINDI_FONT_SEARCH_PATHS:
        if os.path.exists(path):
            log.info("Using font: %s", path)
            return path

    log.warning("No Hindi font found locally. Downloading Noto Sans Devanagari …")
    return _download_noto_devanagari()


def _download_noto_devanagari() -> str:
    """Download Noto Sans Devanagari Regular from Google Fonts CDN."""
    import urllib.request

    ensure_dirs(config.ASSETS_DIR)
    dest = os.path.join(config.ASSETS_DIR, "NotoSansDevanagari-Regular.ttf")

    if os.path.exists(dest):
        return dest

    url = (
        "https://github.com/google/fonts/raw/main/ofl/"
        "notosansdevanagari/NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf"
    )
    # Try the simpler direct URL first
    urls = [
        "https://fonts.gstatic.com/s/notosansdevanagari/v26/TuGoUUFzXI5FBtUq5a8bjKYTZjtgoo_U62T5BDE.ttf",
        url,
    ]
    for u in urls:
        try:
            urllib.request.urlretrieve(u, dest)
            if os.path.getsize(dest) > 10_000:   # sanity-check it's a real file
                get_logger("font").info("Font downloaded → %s", dest)
                return dest
        except Exception:
            pass

    raise RuntimeError(
        "Could not download Hindi font automatically.\n"
        "Please run:  bash setup.sh\n"
        "Or manually copy a Devanagari .ttf into assets/NotoSansDevanagari-Regular.ttf"
    )


# ─────────────────────────────────────────────────────────────
#  DEPENDENCY CHECKS
# ─────────────────────────────────────────────────────────────

def check_system_deps() -> None:
    """Abort early with a helpful message if ffmpeg is not installed."""
    log = get_logger("deps")
    missing = []
    for tool in ("ffmpeg", "ffprobe"):
        r = subprocess.run(["which", tool], capture_output=True)
        if r.returncode != 0:
            missing.append(tool)

    if missing:
        log.error("Missing system tools: %s", ", ".join(missing))
        log.error("Install with:  brew install ffmpeg")
        sys.exit(1)

    log.info("ffmpeg ✓   ffprobe ✓")


def check_python_deps() -> None:
    """Check key Python packages are importable."""
    log = get_logger("deps")
    packages = {
        "yt_dlp":    "yt-dlp",
        "whisper":   "openai-whisper",
        "moviepy":   "moviepy",
        "PIL":       "Pillow",
        "numpy":     "numpy",
    }
    missing = []
    for mod, pkg in packages.items():
        try:
            __import__(mod)
        except ImportError:
            missing.append(pkg)

    if missing:
        log.error("Missing Python packages: %s", ", ".join(missing))
        log.error("Install with:  pip install %s", " ".join(missing))
        sys.exit(1)

    log.info("Python dependencies ✓")

def _ass_time_to_seconds(t: str) -> float:
    """Convert ASS timestamp H:MM:SS.cc to seconds."""
    try:
        h, m, rest = t.split(":")
        s, cs = rest.split(".")
        return int(h) * 3600 + int(m) * 60 + int(s) + int(cs) / 100
    except Exception:
        return 0.0