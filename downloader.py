"""
downloader.py — Download a YouTube video and its audio track.

Uses yt-dlp (free, open-source). No API key required.
Output:  temp/video.mp4   – optional full video (best quality ≤ 1080p)
         temp/audio.wav   – audio track (for Whisper)
         dict             – video metadata (title, description, duration …)
"""

import os
import json
import yt_dlp

import config
from utils import ensure_dirs, get_logger

log = get_logger("downloader")


# ─────────────────────────────────────────────────────────────
#  PUBLIC API
# ─────────────────────────────────────────────────────────────

def download(url: str, download_video: bool | None = None) -> dict:
    """
    Download video + extract audio.

    Returns
    -------
    dict with keys:
        video_path  – path to downloaded .mp4, or None in slideshow mode
        audio_path  – path to extracted .wav (16 kHz mono, ready for Whisper)
        metadata    – dict of video info (title, description, duration, …)
        is_reel     – True if portrait/reel format
    """
    ensure_dirs(config.TEMP_DIR, config.OUTPUT_DIR)

    log.info("Fetching video info …")
    metadata = _fetch_metadata(url)

    log.info("Title : %s", metadata.get("title", "—"))
    log.info("Duration: %d s", metadata.get("duration", 0))

    if download_video is None:
        download_video = config.DOWNLOAD_SOURCE_VIDEO or config.VIDEO_STYLE == "source"

    video_path = os.path.join(config.TEMP_DIR, "video.mp4")
    audio_path = os.path.join(config.TEMP_DIR, "audio.wav")

    if download_video:
        _download_video(url, video_path)
        _extract_audio(video_path, audio_path)
    else:
        video_path = None
        _download_audio(url, audio_path)

    # Detect reel vs normal from video dimensions
    w = metadata.get("width") or 0
    h = metadata.get("height") or 0
    if download_video and video_path:
        from utils import get_video_dimensions
        w, h = get_video_dimensions(video_path)
    is_reel = h > w
    if w and h:
        log.info("Format: %s  (%d × %d)", "REEL" if is_reel else "YOUTUBE", w, h)
    else:
        log.info("Format: dimensions unknown; using YouTube layout unless configured otherwise")

    return {
        "video_path": video_path,
        "audio_path": audio_path,
        "metadata":   metadata,
        "is_reel":    is_reel,
    }


# ─────────────────────────────────────────────────────────────
#  INTERNAL HELPERS
# ─────────────────────────────────────────────────────────────

def _fetch_metadata(url: str) -> dict:
    """Pull video metadata without downloading the video."""
    ydl_opts = {
        "quiet":        True,
        "no_warnings":  True,
        "skip_download": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "title":       info.get("title", ""),
        "description": info.get("description", ""),
        "duration":    info.get("duration", 0),
        "uploader":    info.get("uploader", ""),
        "upload_date": info.get("upload_date", ""),
        "view_count":  info.get("view_count", 0),
        "tags":        info.get("tags", []),
        "width":       info.get("width", 0) or 0,
        "height":      info.get("height", 0) or 0,
        "url":         url,
    }


def _download_video(url: str, output_path: str) -> None:
    """Download best quality video ≤ 1080p."""
    if os.path.exists(output_path):
        log.info("Video already downloaded, skipping.")
        return

    ydl_opts = {
        # Prefer mp4 container, max 1080p, merge video + audio
        "format": (
            "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[height<=1080]+bestaudio"
            "/best[height<=1080]"
        ),
        "outtmpl":      output_path,
        "quiet":        False,
        "no_warnings":  False,
        # Merge into a single mp4 using ffmpeg
        "postprocessors": [{
            "key":            "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }],
    }

    log.info("Downloading video …")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    # yt-dlp may append .mp4 suffix automatically
    if not os.path.exists(output_path):
        mp4_candidate = output_path + ".mp4"
        if os.path.exists(mp4_candidate):
            os.rename(mp4_candidate, output_path)

    log.info("Video saved → %s", output_path)


def _extract_audio(video_path: str, audio_path: str) -> None:
    """
    Extract 16 kHz mono WAV from the video.
    Whisper works best with 16 kHz mono audio.
    """
    if os.path.exists(audio_path):
        log.info("Audio already extracted, skipping.")
        return

    import subprocess
    cmd = [
        "ffmpeg", "-y",
        "-i",    video_path,
        "-vn",                   # no video
        "-ar",   "16000",        # 16 kHz sample rate
        "-ac",   "1",            # mono
        "-f",    "wav",
        audio_path,
    ]
    log.info("Extracting audio …")
    subprocess.run(cmd, check=True, capture_output=True)
    log.info("Audio saved → %s", audio_path)


def _download_audio(url: str, output_path: str) -> None:
    """Download and convert only the audio track for faster slideshow mode."""
    if os.path.exists(output_path):
        log.info("Audio already downloaded, skipping.")
        return

    temp_template = os.path.join(config.TEMP_DIR, "source_audio.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": temp_template,
        "quiet": False,
        "no_warnings": False,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }],
        "postprocessor_args": [
            "-ar", "16000",
            "-ac", "1",
        ],
    }

    log.info("Downloading audio only …")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    candidate = os.path.join(config.TEMP_DIR, "source_audio.wav")
    if os.path.exists(candidate):
        os.replace(candidate, output_path)
    if not os.path.exists(output_path):
        raise RuntimeError("Audio download finished but output WAV was not created")

    log.info("Audio saved → %s", output_path)
